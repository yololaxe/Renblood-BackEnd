"""Synthetic query/payload comparison; never writes to the real game database."""
import os,sys,uuid,json,time,statistics
from pathlib import Path
from datetime import datetime,timezone,timedelta
from dotenv import dotenv_values
from pymongo import MongoClient
R=Path('D:/Projets/Projet/DEVELOPPEMENT');B=R/'Renblood-BackEnd';sys.path.insert(0,str(B))
from economy.store import Bank
from economy.desk import page_operations
values=dotenv_values(B/'.env.local');client=MongoClient(values.get('MONGO_URI') or values.get('MONGODB_URI'),serverSelectionTimeoutMS=5000)
name='rb_econ_test_'+uuid.uuid4().hex[:16];db=client[name]
try:
 bank=Bank(db);bank.initialize();now=datetime.now(timezone.utc)
 db.economy_operations.insert_many([{'_id':f'receipt-{i:06d}','operation_id':f'receipt-{i:06d}','owner_id':'synthetic','actor_id':'synthetic','key':str(i),'created_at':(now+timedelta(seconds=i)).isoformat(),'state':'CONFIRMED','type':'COMMERCE','amount':64,'item_nbt':'x'*8192} for i in range(2000)])
 def sample(projection):
  durations=[];rows=[]
  for _ in range(12):
   start=time.perf_counter();rows=list(bank.operations.find({},projection).sort([('created_at',-1),('_id',-1)]).limit(51));durations.append((time.perf_counter()-start)*1000)
  return {'median_ms':round(statistics.median(durations),2),'p95_ms':round(sorted(durations)[-1],2),'payload_bytes':len(json.dumps(rows).encode()),'iterations':12}
 full=sample(None);projected=sample({'item_nbt':0})
 explain=db.command('explain',{'find':'economy_operations','filter':{},'projection':{'item_nbt':0},'sort':{'created_at':-1,'_id':-1},'limit':51},verbosity='executionStats')
 stats=explain['executionStats']
 page=page_operations(bank,{});second=page_operations(bank,{'before':page['next_cursor']})
 assert not(set(r['operation_id'] for r in page['operations'])&set(r['operation_id'] for r in second['operations']))
 result={'synthetic':True,'records':2000,'nbt_bytes_per_record':8192,'page_size':50,'full_document_51':full,'projected_51':projected,'payload_reduction_percent':round((1-projected['payload_bytes']/full['payload_bytes'])*100,2),'execution':{key:stats[key] for key in ['nReturned','totalKeysExamined','totalDocsExamined']},'winning_plan':explain['queryPlanner']['winningPlan'],'http_baseline':'Local back was stopped; no HTTP latency comparison claimed.','minecraft':'No world available; runtime save/tick latency not measured.'}
 (Path(__file__).parent/'performance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='winning_plan'},ensure_ascii=False))
finally:
 assert name.startswith('rb_econ_test_') and len(name)==29
 client.drop_database(name);client.close()
