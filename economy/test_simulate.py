import unittest
from .simulate import simulate

class SimulationTests(unittest.TestCase):
    def test_tags_choose_lowest_real_cost_and_preserve_exact_margin(self):
        recipes={'test:planks':{'type':'minecraft:crafting_shapeless','ingredients':[{'tag':'minecraft:logs'}],
            'result':{'item':'minecraft:oak_planks','count':4}}}
        prices=[{'item_id':'minecraft:oak_log','buy_price':10,'sell_price':8},
                {'item_id':'minecraft:oak_planks','buy_price':5,'sell_price':4}]
        report=simulate(prices,recipes,{'minecraft:logs':['minecraft:oak_log']})
        self.assertEqual(report['crafting_opportunities'][0]['gross_margin'],'6')
        self.assertFalse(report['applied'])

    def test_missing_ingredient_is_not_free_and_tag_cycles_terminate(self):
        recipes={'test:free':{'type':'minecraft:crafting_shapeless','ingredients':[{'tag':'test:loop'}],
            'result':{'item':'minecraft:oak_planks','count':64}}}
        prices=[{'item_id':'minecraft:oak_planks','buy_price':5,'sell_price':4}]
        report=simulate(prices,recipes,{'test:loop':['#test:loop']})
        self.assertEqual(report['recipes_unpriced'],1);self.assertEqual(report['crafting_opportunities'],[])

    def test_proposed_margin_is_simulated_without_mutating_prices(self):
        rows=[{'item_id':'minecraft:iron_ingot','buy_price':10,'sell_price':12}]
        self.assertEqual(len(simulate(rows,{},{} )['direct_buy_resell_opportunities']),1)
        self.assertEqual(simulate(rows,{}, {},7000)['direct_buy_resell_opportunities'],[])
        self.assertEqual(rows[0]['sell_price'],12)
