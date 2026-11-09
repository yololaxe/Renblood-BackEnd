"""Read-only buy/resell and crafting simulation. Proposed margins are never applied."""
import argparse
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from dotenv import dotenv_values
from pymongo import MongoClient
from .domain import legacy_money


def load_data(roots, minecraft_jar=None):
    recipes={};tags={}
    def add(name,value):
        pieces=name.replace('\\','/').split('/')
        if len(pieces)<4 or pieces[0]!='data':return
        namespace=pieces[1]
        if pieces[2]=='recipes':recipes[namespace+':'+('/'.join(pieces[3:])[:-5])]=value
        if pieces[2:4]==['tags','items']:tags[namespace+':'+('/'.join(pieces[4:])[:-5])]=value.get('values',[])
    if minecraft_jar:
        with ZipFile(minecraft_jar) as archive:
            for name in archive.namelist():
                if name.startswith('data/') and name.endswith('.json') and ('/recipes/' in name or '/tags/items/' in name):add(name,json.loads(archive.read(name)))
    for root in roots:
        for path in sorted(Path(root).glob('*/recipes/**/*.json')):add('data/'+path.relative_to(root).as_posix(),json.loads(path.read_text(encoding='utf-8-sig')))
        for path in sorted(Path(root).glob('*/tags/items/**/*.json')):add('data/'+path.relative_to(root).as_posix(),json.loads(path.read_text(encoding='utf-8-sig')))
    return recipes,tags


def simulate(prices, recipes, tags, sell_bps=10000):
    buys={};sells={}
    for row in prices:
        item=row['item_id'];buy=legacy_money(row['buy_price']);sell=legacy_money(row['sell_price'])
        if buy<=0:continue
        if sell_bps<10000:sell=min(sell,buy*sell_bps//10000)
        buys[item]=min(buys.get(item,buy),buy);sells[item]=max(sells.get(item,sell),sell)
    def alternatives(ingredient,seen=frozenset()):
        if isinstance(ingredient,list):return set().union(*(alternatives(entry,seen) for entry in ingredient))
        if not isinstance(ingredient,dict):return set()
        if 'item' in ingredient:return {ingredient['item']}
        tag=ingredient.get('tag')
        if not tag or tag in seen:return set()
        result=set()
        for value in tags.get(tag,[]):
            if isinstance(value,dict):value=value.get('id','')
            if value.startswith('#'):result.update(alternatives({'tag':value[1:]},seen|{tag}))
            elif value:result.add(value)
        return result
    direct=[{'item_id':item,'minimum_buy':str(buy),'maximum_resell':str(sells[item]),'gross_margin':str(sells[item]-buy)}
            for item,buy in buys.items() if sells[item]>buy]
    craft=[];unsupported=Counter();unpriced=0;tested=0
    for name,recipe in recipes.items():
        kind=recipe.get('type');ingredients=[]
        if kind=='minecraft:crafting_shaped':
            counts=Counter(''.join(recipe.get('pattern',[])));counts.pop(' ',None)
            for key,count in counts.items():ingredients.extend([recipe.get('key',{}).get(key,{})]*count)
        elif kind=='minecraft:crafting_shapeless':ingredients=recipe.get('ingredients',[])
        else:unsupported[kind or 'unknown']+=1;continue
        output=recipe.get('result',{})
        if isinstance(output,str):output={'item':output}
        item=output.get('item');count=output.get('count',1)
        if item not in sells or not ingredients:unpriced+=1;continue
        total=0;missing=False;chosen=Counter()
        for ingredient in ingredients:
            options=[value for value in alternatives(ingredient) if value in buys]
            if not options:missing=True;break
            cheapest=min(options,key=lambda value:buys[value]);total+=buys[cheapest];chosen[cheapest]+=1
        if missing:unpriced+=1;continue
        tested+=1;revenue=sells[item]*count
        if revenue>total:craft.append({'recipe':name,'item_id':item,'count':count,'ingredients':dict(chosen),
            'input_cost':str(total),'output_resell':str(revenue),'gross_margin':str(revenue-total)})
    return {'scenario_sell_bps':sell_bps,'applied':False,'priced_items':len(buys),'recipes_loaded':len(recipes),
            'recipes_priced':tested,'recipes_unpriced':unpriced,'unsupported_recipe_types':dict(unsupported),
            'direct_buy_resell_opportunities':sorted(direct,key=lambda row:int(row['gross_margin']),reverse=True),
            'crafting_opportunities':sorted(craft,key=lambda row:int(row['gross_margin']),reverse=True),
            'limits':['Gross margins exclude travel, player time and finite NPC budgets.',
                'Crafting opportunities are balancing signals, not automatic proof of an exploit.',
                'No unpriced ingredient, recipe fuel or material property is treated as free.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True);parser.add_argument('--database',required=True);parser.add_argument('--report',required=True)
    parser.add_argument('--resources-data',action='append',default=[]);parser.add_argument('--minecraft-jar');parser.add_argument('--npc-sell-bps',type=int,default=10000)
    args=parser.parse_args();config=dotenv_values(args.env_file)
    if config.get('MONGO_DB_NAME')!=args.database:parser.error('Database mismatch.')
    if not 0<=args.npc_sell_bps<=10000:parser.error('Sell basis points outside 0..10000.')
    path=Path(args.report)
    if path.exists():parser.error('Report already exists.')
    recipes,tags=load_data(args.resources_data,args.minecraft_jar)
    with MongoClient(config['MONGO_URI'],serverSelectionTimeoutMS=3000) as client:
        database=client[args.database]
        run=database.price_calculation_runs.find_one({'status':'SUCCESS'},sort=[('started_at',-1)])
        version=run['calculation_version'] if run else None
        prices=list(database.calculated_market_prices.find({'calculation_version':version})) if version else []
    result={'database':args.database,'read_only':True,'price_version':version,**simulate(prices,recipes,tags,args.npc_sell_bps)}
    with path.open('x',encoding='utf-8') as file:json.dump(result,file,indent=2,ensure_ascii=False)
    print('Simulation saved:',result['recipes_loaded'],'recipes,',result['recipes_priced'],'fully priced. No rule applied.')
if __name__=='__main__':main()
