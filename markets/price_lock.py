"""One publisher for all price recalculations, including manual admin actions."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from django.db import connection
from pymongo.errors import DuplicateKeyError
from rest_framework.exceptions import ValidationError

held=ContextVar('market_price_lease',default=None)


@contextmanager
def price_calculation_lease():
    connection.ensure_connection();collection=connection.connection.economy_services
    now=datetime.now(timezone.utc);token=str(uuid4())
    lease={'_id':'market-price-publisher','token':token,'expires_at':now+timedelta(minutes=10)}
    acquired=collection.find_one_and_update({'_id':lease['_id'],'expires_at':{'$lte':now}},
        {'$set':{'token':token,'expires_at':lease['expires_at']}})
    if not acquired:
        try:collection.insert_one(lease)
        except DuplicateKeyError:
            raise ValidationError('Un calcul des cours est déjà en cours. Les prix précédents restent disponibles.')
    context=held.set((collection,token))
    try:yield
    finally:
        held.reset(context)
        collection.delete_one({'_id':lease['_id'],'token':token})


def verify_price_calculation_lease():
    lease=held.get()
    if lease is None:return  # Unit calculation tests replace the external publisher lease.
    collection,token=lease
    if not collection.find_one({'_id':'market-price-publisher','token':token,'expires_at':{'$gt':datetime.now(timezone.utc)}}):
        raise ValidationError('Le verrou du calcul a expiré. Aucun nouveau cours n’a été publié par ce calcul.')
