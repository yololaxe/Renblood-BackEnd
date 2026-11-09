"""Publish due, explicitly scheduled rules. Dry-run unless --apply is supplied."""
import argparse
import time
from datetime import datetime,timezone
from dotenv import dotenv_values
from pymongo import MongoClient
from .store import Bank
from .desk import Desk

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True);parser.add_argument('--database',required=True);parser.add_argument('--apply',action='store_true')
    parser.add_argument('--watch',action='store_true',help='Keep running every 60 seconds; requires --apply')
    args=parser.parse_args();config=dotenv_values(args.env_file)
    if args.watch and not args.apply:parser.error('--watch requires --apply.')
    if config.get('MONGO_DB_NAME')!=args.database:parser.error('Database mismatch.')
    with MongoClient(config['MONGO_URI'],serverSelectionTimeoutMS=3000) as client:
        bank=Bank(client[args.database])
        if not args.apply:
            print('Due schedules:',bank.db.economy_policy_schedule.count_documents({'state':'SCHEDULED','effective_at':{'$lte':datetime.now(timezone.utc).isoformat()}}));return
        bank.initialize()
        while True:
            for result in Desk(bank).publish_due():print(result['schedule_id'],result['state'],flush=True)
            bank.db.economy_services.update_one({'_id':'policy-publisher'},{'$set':{'last_seen':datetime.now(timezone.utc).isoformat()}},upsert=True)
            if not args.watch:break
            time.sleep(60)
if __name__=='__main__':main()
