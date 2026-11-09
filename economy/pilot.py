"""Offline shadow calculation. This module has no database or publication capability."""
import argparse,json
from pathlib import Path
from .domain import MAX_MONEY

def shadow_price(row):
    fields=['base_price','current_price','target_stock','observed_stock','trades']
    if any(type(row.get(k)) is not int for k in fields):raise ValueError('Integer observations required')
    base,current,target,stock,trades=(row[k] for k in fields)
    if not 0<base<=MAX_MONEY or not 0<current<=MAX_MONEY or target<=0 or stock<0 or trades<0:raise ValueError('Invalid observation')
    low=max(1,(base*8000+9999)//10000);high=min(MAX_MONEY,base*12000//10000)
    if not low<=current<=high:raise ValueError('Current price outside pilot limits')
    if trades<20:return {**row,'proposed_price':str(current),'applied':False,'reason':'INSUFFICIENT_SAMPLE'}
    # Demand proxy: shortage raises the indicative price, oversupply lowers it.
    variation=max(-500,min(500,(target-stock)*1000//target))
    proposed=max(low,min(high,current*(10000+variation)//10000))
    return {**row,'proposed_price':str(proposed),'applied':False,'reason':'SHADOW_ONLY','variation_bps':variation}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
    source=json.loads(Path(args.input).read_text(encoding='utf-8'))
    result={'mode':'SHADOW_ONLY','applied':False,'city':source['city'],'synthetic':source.get('synthetic',True),'observations':[shadow_price(row) for row in source['observations']]}
    Path(args.report).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Shadow report written; no prices published.')
if __name__=='__main__':main()
