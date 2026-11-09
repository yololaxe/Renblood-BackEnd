"""Read-only source inventory, local GET baseline and offline reconciliation."""
import argparse, hashlib, json, re, statistics, time, uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

MAX = 9223372036854775807
ROOTS = ['Renblood-BackEnd', 'renblood-website/renblood-website/src',
         'mods/CoinMod2025/MedievalCoins/src', 'mods/MedievalStructures/MedievalStructures/src',
         'mods/NpcShopkeeperDev/NpcShopkeeper/src', 'mods/TestClientAdmin/TestClientAdmin/src']
PATTERN = re.compile(r'money|balance|deposit|withdraw|coin|payment|price|reward|stock|tax|trade', re.I)
EXCLUDE = {'.git','node_modules','.venv','__pycache__','migrations','build','dist','.idea'}

def now(): return datetime.now(timezone.utc).isoformat()
def save(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')

def scan(root):
    root=Path(root); records=[]; counts={}; missing=[]
    for part in ROOTS:
        base=root/part
        if not base.is_dir(): missing.append(part); continue
        counts[part]=0
        for f in sorted(base.rglob('*')):
            if not f.is_file() or f.suffix not in {'.py','.java','.js','.jsx'} or EXCLUDE.intersection(f.parts): continue
            if f.name.startswith('test') or f.name.endswith('Test.java'): continue
            counts[part]+=1
            content=f.read_bytes(); text=content.decode('utf-8',errors='replace')
            lines=[i for i,line in enumerate(text.splitlines(),1) if PATTERN.search(line)]
            if lines: records.append({'path':f.relative_to(root).as_posix(),'sha256':hashlib.sha256(content).hexdigest(),'candidate_lines':lines})
    return {'created_at':now(),'kind':'source-candidates-not-complete-callgraph','files_scanned':counts,'missing_roots':missing,'records':records}

def amount_status(value, negative_allowed=False):
    if isinstance(value,bool) or value is None: return 'invalid'
    try: number=Decimal(str(value))
    except InvalidOperation: return 'invalid'
    if not number.is_finite(): return 'invalid'
    if number!=number.to_integral_value(): return 'fraction'
    if abs(number)>MAX: return 'overflow'
    if number<0: return 'debt' if negative_allowed else 'negative'
    return 'valid'

def reconcile(data):
    issues=[]; totals={}; coverage={}
    for pocket in ['bank','cashboxes','room_balances','pending_operations']:
        coverage[pocket]='provided' if pocket in data else 'not_provided'
        if pocket not in data: continue
        if not isinstance(data[pocket],list): raise ValueError(f'{pocket} must be a list')
        if pocket=='pending_operations':
            ids=set()
            for i,row in enumerate(data[pocket]):
                ident=row.get('id')
                if not ident or ident in ids: issues.append({'pocket':pocket,'row':i,'code':'missing_or_duplicate_id'})
                ids.add(ident)
            continue
        total=0; ids=set(); minecraft=set()
        for i,row in enumerate(data[pocket]):
            ident=row.get('id'); status=amount_status(row.get('amount'), pocket=='room_balances')
            duplicate=not ident or ident in ids
            if duplicate: issues.append({'pocket':pocket,'row':i,'code':'missing_or_duplicate_id'})
            ids.add(ident)
            if status!='valid': issues.append({'pocket':pocket,'row':i,'code':status})
            if status=='valid' and not duplicate: total+=int(Decimal(str(row['amount'])))
            if pocket=='bank':
                mc=row.get('minecraft_uuid')
                try:
                    parsed=str(uuid.UUID(str(mc)))
                    if parsed in minecraft: issues.append({'pocket':pocket,'row':i,'code':'duplicate_minecraft_uuid'})
                    minecraft.add(parsed)
                except (ValueError,TypeError,AttributeError): issues.append({'pocket':pocket,'row':i,'code':'invalid_or_unlinked_minecraft_uuid'})
            if pocket=='cashboxes' and not row.get('owner'): issues.append({'pocket':pocket,'row':i,'code':'missing_owner'})
        totals[pocket]={'valid_unique_nonnegative_subtotal':str(total),'rows':len(data[pocket]),'add_to_wealth':pocket!='room_balances'}
    return {'created_at':now(),'coverage':coverage,'totals':totals,'issues':issues,'note':'Subtotals exclude invalid/duplicate rows; no corrections performed. Not a total money supply. Room advances/debts are not cashboxes.'}

def probe():
    rows=[]
    for url in ['http://127.0.0.1:8000/ping','http://127.0.0.1:8000/api/public/market-prices','http://localhost:5173/']:
        samples=[]
        for _ in range(3):
            started=time.perf_counter(); status=None; size=None; error=None
            try:
                with urlopen(url,timeout=2) as response:
                    status=response.status; size=len(response.read(8*1024*1024+1))
            except HTTPError as exc:
                status=exc.code; error='http_error'
            except (URLError,TimeoutError,OSError): error='unreachable_or_timeout'
            samples.append({'ms':round((time.perf_counter()-started)*1000,2),'status':status,'bytes':size,'error':error})
        ok=[s['ms'] for s in samples if s['status'] is not None and 200<=s['status']<300]
        rows.append({'url':url,'samples':samples,'successful_median_ms':statistics.median(ok) if ok else None})
    return {'created_at':now(),'scope':'local-http-only-no-game-ticks-no-query-counts','results':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('scan'); a.add_argument('--root',required=True); a.add_argument('--out',required=True)
    a=sub.add_parser('probe'); a.add_argument('--out',required=True)
    a=sub.add_parser('reconcile'); a.add_argument('--input',required=True); a.add_argument('--out',required=True)
    args=parser.parse_args()
    if Path(args.out).exists(): parser.error('Output already exists; choose a new path.')
    if args.cmd=='scan': result=scan(args.root)
    elif args.cmd=='probe': result=probe()
    else: result=reconcile(json.loads(Path(args.input).read_text(encoding='utf-8-sig')))
    save(args.out,result)
    print('Report written:',args.out)
