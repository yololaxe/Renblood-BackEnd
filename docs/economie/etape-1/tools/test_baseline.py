import unittest
from baseline import amount_status, reconcile, MAX

class ReconciliationTests(unittest.TestCase):
    def test_fraction_and_debt_are_not_spendable(self):
        report=reconcile({'bank':[{'id':'a','amount':'1.5'}], 'room_balances':[{'id':'r','amount':'-64'}]})
        self.assertEqual(report['totals']['bank']['valid_unique_nonnegative_subtotal'],'0')
        self.assertFalse(report['totals']['room_balances']['add_to_wealth'])
        self.assertIn('debt',[issue['code'] for issue in report['issues']])
    def test_no_duplicate_balance_added(self):
        report=reconcile({'cashboxes':[{'id':'x','owner':'a','amount':'64'},{'id':'x','owner':'a','amount':'64'}]})
        self.assertEqual(report['totals']['cashboxes']['valid_unique_nonnegative_subtotal'],'64')
    def test_limits_and_invalid_values(self):
        self.assertEqual(amount_status(str(MAX)),'valid')
        for value in [True,None,'NaN','Infinity','abc']:
            self.assertEqual(amount_status(value),'invalid')
        self.assertEqual(amount_status(str(MAX+1)),'overflow')
    def test_missing_sources_not_zero(self):
        report=reconcile({})
        self.assertEqual(report['coverage']['bank'],'not_provided')
        self.assertEqual(report['totals'],{})
    def test_duplicate_pending_is_flagged(self):
        report=reconcile({'pending_operations':[{'id':'x'},{'id':'x'}]})
        self.assertEqual(len(report['issues']),1)
if __name__=='__main__': unittest.main()
