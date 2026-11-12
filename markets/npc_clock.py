"""Refresh an enabled dynamic economy off the request/tick thread.

The first NPC catalogue read after fifteen minutes schedules one shared job.
An atomic Mongo lease prevents one recalculation per player or web worker.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import logging
from pymongo.errors import DuplicateKeyError
from django.conf import settings
from django.db import connections

logger=logging.getLogger(__name__)
executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='market-clock')


def refresh_if_due(bank):
    if bank.db.name != settings.MONGO_DB_NAME: return
    config=bank.db.market_economy_config.find_one({}) or {}
    if not config.get('dynamic_economy_enabled'): return
    now=datetime.now(timezone.utc);clock=bank.db.economy_services
    lease={'_id':'npc-market-clock','next_check':now+timedelta(minutes=15),'started_at':now}
    acquired=clock.find_one_and_update({'_id':lease['_id'],'next_check':{'$lte':now}},{'$set':{k:v for k,v in lease.items() if k!='_id'}})
    if not acquired:
        try:clock.insert_one(lease)
        except DuplicateKeyError:return
    def run():
        try:
            from .services import recalculate_prices
            result=recalculate_prices(triggered_by='npc-market-clock',trigger_source='SYSTEM')
            clock.update_one({'_id':lease['_id']},{'$set':{'last_success':datetime.now(timezone.utc),'status':'SUCCESS'}})
        except Exception:
            logger.exception('Automatic market recalculation failed; previous prices remain active')
            clock.update_one({'_id':lease['_id']},{'$set':{'status':'FAILED','next_check':datetime.now(timezone.utc)+timedelta(minutes=1)}})
        finally:connections.close_all()
    executor.submit(run)
