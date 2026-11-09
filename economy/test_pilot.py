from unittest import TestCase
from .pilot import shadow_price
class ShadowPriceTests(TestCase):
    def row(self,**kw):return dict(base_price=100,current_price=100,target_stock=100,observed_stock=100,trades=30,**kw)
    def test_under_sample_does_not_move(self):
        row=self.row();row.update(trades=19,observed_stock=0);self.assertEqual(shadow_price(row)['proposed_price'],'100')
    def test_shortage_and_oversupply_are_limited_to_five_percent(self):
        row=self.row();row['observed_stock']=0;self.assertEqual(shadow_price(row)['proposed_price'],'105')
        row['observed_stock']=1000;self.assertEqual(shadow_price(row)['proposed_price'],'95')
    def test_absolute_bounds_never_drift_beyond_twenty_percent(self):
        row=self.row();row.update(current_price=120,observed_stock=0);self.assertEqual(shadow_price(row)['proposed_price'],'120')
        row.update(current_price=80,observed_stock=1000);self.assertEqual(shadow_price(row)['proposed_price'],'80')
    def test_invalid_or_fractional_observations_are_rejected(self):
        for field,value in [('trades',True),('base_price',1.5),('target_stock',0),('observed_stock',-1)]:
            row=self.row();row[field]=value
            with self.assertRaises(ValueError):shadow_price(row)
    def test_does_not_mutate_input_or_claim_application(self):
        row=self.row();original=dict(row);self.assertFalse(shadow_price(row)['applied']);self.assertEqual(row,original)
