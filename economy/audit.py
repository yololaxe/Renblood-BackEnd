"""Read-only reconciliation; never fixes a balance or expires a physical receipt."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from dotenv import dotenv_values
from pymongo import MongoClient
from .domain import public


def reconcile(database):
    movements=defaultdict(int);stock_movements=defaultdict(int)
    unlimited_issued = 0
    for operation in database.economy_operations.find({'state':'CONFIRMED'}):
        kind=operation['type'];amount=operation['amount']
        if kind=='COMMERCE':
            unlimited_issued += operation.get('minted_amount', 0)
            for leg in operation['legs']:movements[leg['account_id']]+=leg['amount']*(1 if leg['direction']=='IN' else -1)
            if operation.get('limited_stock'):
                if operation['action'] in {'BUY','STOCK_OUT'}:stock_movements[operation['stock_id']]-=operation['quantity']
                if operation['action'] in {'SELL','STOCK_IN'}:stock_movements[operation['stock_id']]+=operation['quantity']
                if operation['action']=='STOCK_ADJUST':stock_movements[operation['stock_id']]+=operation['stock_delta']
        elif kind in {'DEPOSIT','CREDIT','QUEST_REWARD'}:movements['bank:'+operation['owner_id']]+=amount
        elif kind in {'WITHDRAW','DEBIT'}:movements['bank:'+operation['owner_id']]-=amount
        elif kind=='COMPENSATION':movements['bank:'+operation['owner_id']]+=amount*(1 if operation['direction']=='CREDIT' else -1)
    holds=defaultdict(lambda:{'reserved':0,'incoming':0})
    stock_holds=defaultdict(lambda:{'reserved_stock':0,'incoming_stock':0})
    pending=list(database.economy_operations.find({'state':{'$in':['RESERVED','RECONCILIATION_REQUIRED']}}))
    for operation in pending:
        amount=operation['amount']
        if operation['type']=='COMMERCE':
            for leg in operation['legs']:
                holds[leg['account_id']]['incoming' if leg['direction']=='IN' else 'reserved']+=leg['amount']
            if operation.get('limited_stock'):
                if operation['action'] in {'BUY','STOCK_OUT'}:stock_holds[operation['stock_id']]['reserved_stock']+=operation['quantity']
                if operation['action'] in {'SELL','STOCK_IN'}:stock_holds[operation['stock_id']]['incoming_stock']+=operation['quantity']
        elif operation['type'] in {'DEPOSIT','WITHDRAW'}:
            holds['bank:'+operation['owner_id']]['incoming' if operation['type']=='DEPOSIT' else 'reserved']+=amount
    anomalies=[]; total=0
    seen_accounts = set()
    seen_offers = set()
    for account in database.economy_accounts.find({}):
        seen_accounts.add(account['_id'])
        total+=account['available']+account['reserved']
        book_balance=account.get('opening_balance',0)+movements[account['_id']]
        if account['available']+account['reserved']!=book_balance:
            anomalies.append({'account_id':account['_id'],'code':'LEDGER_MISMATCH','expected':str(book_balance),'recorded':str(account['available']+account['reserved'])})
        for field in ['reserved','incoming']:
            if account.get(field,0)!=holds[account['_id']][field]:
                anomalies.append({'account_id':account['_id'],'field':field,'recorded':str(account.get(field,0)),'expected':str(holds[account['_id']][field])})
        if min(account['available'],account['reserved'],account.get('incoming',0))<0:
            anomalies.append({'account_id':account['_id'],'code':'NEGATIVE_POCKET'})
        holds.pop(account['_id'],None)
    for missing,values in holds.items():
        if any(values.values()):anomalies.append({'account_id':missing,'code':'MISSING_ACCOUNT'})
    for offer in database.economy_offers.find({'stock':{'$ne':None}}):
        seen_offers.add(offer['_id'])
        if offer.get('opening_stock') is not None and offer['stock']+offer['reserved_stock']!=offer['opening_stock']+stock_movements[offer['_id']]:
            anomalies.append({'offer_id':offer['offer_id'],'code':'STOCK_LEDGER_MISMATCH'})
        for field in ['reserved_stock','incoming_stock']:
            if offer[field]!=stock_holds[offer['_id']][field]:anomalies.append({'offer_id':offer['offer_id'],'field':field,'recorded':offer[field],'expected':stock_holds[offer['_id']][field]})
        if min(offer['stock'],offer['reserved_stock'],offer['incoming_stock'])<0:anomalies.append({'offer_id':offer['offer_id'],'code':'NEGATIVE_STOCK'})
        stock_holds.pop(offer['_id'],None)
    for missing,values in stock_holds.items():
        if any(values.values()):anomalies.append({'stock_id':missing,'code':'MISSING_STOCK'})
    for missing in movements.keys() - seen_accounts - holds.keys():
        anomalies.append({'account_id': missing, 'code': 'CONFIRMED_ACCOUNT_MISSING'})
    for missing in stock_movements.keys() - seen_offers - stock_holds.keys():
        anomalies.append({'stock_id': missing, 'code': 'CONFIRMED_STOCK_MISSING'})
    materials=[public(row) for row in database.economy_quest_rewards.find({'material_state':{'$ne':'DELIVERED'}})]
    return {'total_bank_and_cashboxes':str(total),'unlimited_budget_issued':str(unlimited_issued),'pending':[public(row) for row in pending],
            'pending_material_rewards':materials,'anomalies':anomalies}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True);parser.add_argument('--database',required=True);parser.add_argument('--report',required=True)
    args=parser.parse_args();config=dotenv_values(args.env_file)
    if config.get('MONGO_DB_NAME')!=args.database:parser.error('Database mismatch.')
    target=Path(args.report)
    if target.exists():parser.error('Report already exists.')
    with MongoClient(config['MONGO_URI'],serverSelectionTimeoutMS=3000) as client:
        result={'database':args.database,'read_only':True,**reconcile(client[args.database])}
    with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,ensure_ascii=False,default=str)
    print('Read-only reconciliation saved; anomalies:',len(result['anomalies']))
if __name__=='__main__':main()
