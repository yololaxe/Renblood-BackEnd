"""Explicit, repeatable migration. Dry-run by default. No Django startup."""
import argparse, json, sys
from pathlib import Path
from dotenv import dotenv_values
from pymongo import MongoClient
from .store import Bank
from .domain import EconomyError

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True);parser.add_argument('--database',required=True)
    parser.add_argument('--report',required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--player-id',action='append')
    parser.add_argument('--expected-report', help='Require selected balances to match a prior dry run.')
    args=parser.parse_args(); path=Path(args.report)
    expected = None
    if args.expected_report:
        if not args.apply or not args.player_id:
            parser.error('--expected-report requires --apply and explicit --player-id values.')
        preview = json.loads(Path(args.expected_report).read_text(encoding='utf-8'))
        if preview.get('database') != args.database or preview.get('applied') is not False:
            parser.error('Expected report must be a dry run from the target database.')
        expected = {row['owner_id']: row['balance'] for row in preview['results'] if row['status'] == 'ready'}
        if any(owner not in expected for owner in args.player_id):
            parser.error('Some selected players were not ready in the dry run.')
    if path.exists(): parser.error('Report already exists.')
    config=dotenv_values(args.env_file)
    if config.get('MONGO_DB_NAME')!=args.database: parser.error('Database mismatch.')
    client=MongoClient(config['MONGO_URI'],serverSelectionTimeoutMS=3000)
    results=[]
    try:
        bank=Bank(client[args.database])
        if args.apply: bank.initialize()
        else: bank.check_storage()
        query={'id':{'$in':args.player_id}} if args.player_id else {}
        for row in bank.db.players.find(query,{'id':1}):
            owner = str(row['id'])
            try:
                results.append(bank.migrate(owner, apply=args.apply,
                                            expected_balance=expected.get(owner) if expected is not None else None))
            except EconomyError as exc: results.append({'owner_id':str(row['id']),'status':'blocked','code':exc.code})
        seen={row['owner_id'] for row in results}
        for missing in set(args.player_id or [])-seen: results.append({'owner_id':missing,'status':'blocked','code':'OWNER_NOT_FOUND'})
        with path.open('x',encoding='utf-8') as stream: json.dump({'database':args.database,'applied':args.apply,'results':results},stream,indent=2)
        print('Migration report saved. No invalid balance was rounded.')
    finally: client.close()
if __name__=='__main__': main()
