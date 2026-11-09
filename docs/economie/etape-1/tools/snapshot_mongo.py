"""Explicit-target economic export; no Django startup and no database writes."""
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from baseline import save, reconcile

TABLES=['market_item_references','market_cities','market_categories','city_market_modifiers',
        'market_type_configs','merchant_counters','merchant_counter_items','calculated_market_prices',
        'market_transactions','market_withdrawals','market_economy_config','market_activity_modifiers',
        'price_calculation_runs','temporary_market_modifiers']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True);parser.add_argument('--database',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args(); target=Path(args.out)
    if target.exists(): parser.error('Output directory already exists.')
    from dotenv import dotenv_values
    from pymongo import MongoClient
    from bson.json_util import dumps
    config=dotenv_values(args.env_file)
    if config.get('MONGO_DB_NAME')!=args.database: parser.error('Explicit database must match MONGO_DB_NAME in the selected file.')
    uri=config.get('MONGO_URI')
    if not uri: parser.error('MONGO_URI is missing.')
    # Never echo URI, exception strings or configuration secrets.
    start=datetime.now(timezone.utc).isoformat()
    client=MongoClient(uri,serverSelectionTimeoutMS=3000,connectTimeoutMS=3000,socketTimeoutMS=10000,appname='RenbloodReadOnlyEconomicExport')
    target.mkdir(parents=True)
    try:
        db=client[args.database]; existing=set(db.list_collection_names()); files=[]
        missing=[]; bank=[]
        for name in ['players']+TABLES:
            if name not in existing: missing.append(name); continue
            projection={'_id':1,'id':1,'id_minecraft':1,'money':1} if name=='players' else {'_id':0}
            f=target/(name+'.jsonl'); count=0
            with f.open('x',encoding='utf-8') as stream:
                for row in db[name].find({},projection).batch_size(200):
                    stream.write(dumps(row)+'\n');count+=1
                    if name=='players': bank.append({'id':str(row.get('id',row.get('_id',''))),'minecraft_uuid':row.get('id_minecraft'),'amount':str(row.get('money'))})
            files.append({'file':f.name,'rows':count,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
        save(target/'reconciliation-bank.json',reconcile({'bank':bank} if 'players' in existing else {}))
        save(target/'manifest.json',{'database':args.database,'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),'consistency':'non_atomic_diagnostic_read','files':files,'missing_collections':missing,'world_snapshot':'not_collected'})
        print('Read-only export finished. Missing collections:',len(missing))
    except Exception as exc:
        save(target/'INCOMPLETE.json',{'status':'incomplete','error_type':type(exc).__name__,'database':args.database})
        print('Export incomplete; inspect INCOMPLETE.json. No database writes performed.',file=sys.stderr)
        return 1
    finally: client.close()
    return 0
if __name__=='__main__': sys.exit(main())
