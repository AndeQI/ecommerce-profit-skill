import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'calculate.py'
spec = importlib.util.spec_from_file_location('calc', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CalculatorTest(unittest.TestCase):
    def test_normal_case(self):
        x = mod.evaluate({'seller_revenue':'34.90','costs':[{'name':'采购','amount':'18'},{'name':'包装','amount':'1'},{'name':'运费','amount':'4'},{'name':'平台固定费','amount':'1.2'},{'name':'推广','amount':'5'}]})
        self.assertEqual(x['known_contribution'],'5.70')
        self.assertEqual(x['known_contribution_rate'],'16.33%')
        self.assertEqual(x['known_cost_breakeven_seller_revenue'],'29.20')
    def test_percentage_fee_and_threshold(self):
        x = mod.evaluate({'seller_revenue':'20','costs':[{'name':'货款成本','amount':'10'}],'percentage_fees':[{'name':'费','rate':'10%','base':'seller_revenue'}]})
        self.assertEqual(x['known_contribution'],'8.00')
        self.assertEqual(x['known_cost_breakeven_seller_revenue'],'11.11')
    def test_missing_cost_never_zero(self):
        x=mod.evaluate({'seller_revenue':'50'})
        self.assertEqual(x['status'],'insufficient')
    def test_missing_revenue(self):
        x=mod.evaluate({'costs':[{'name':'采购','amount':'5'}]})
        self.assertEqual(x['status'],'insufficient')
    def test_zero_revenue(self):
        x=mod.evaluate({'seller_revenue':'0','costs':[{'name':'采购','amount':'5'}]})
        self.assertIsNone(x['known_contribution_rate'])
        self.assertEqual(x['known_contribution'],'-5.00')
    def test_wrong_fee_base(self):
        with self.assertRaises(mod.InputError):
            mod.evaluate({'seller_revenue':'50','percentage_fees':[{'name':'平台费','rate':'5%','base':'buyer_paid'}]})
    def test_duplicate_fee(self):
        with self.assertRaises(mod.InputError):
            mod.evaluate({'seller_revenue':'50','costs':[{'name':'运费','amount':'5'},{'name':'运费','amount':'3'}]})
    def test_negative_cost(self):
        with self.assertRaises(mod.InputError):
            mod.evaluate({'seller_revenue':'50','costs':[{'name':'退款','amount':'-3'}]})
    def test_percent_format_must_be_explicit(self):
        with self.assertRaises(mod.InputError):
            mod.evaluate({'seller_revenue':'50','percentage_fees':[{'name':'服务费','rate':'5','base':'seller_revenue'}]})
    def test_fee_sum_ge_one(self):
        x=mod.evaluate({'seller_revenue':'10','percentage_fees':[{'name':'费用A','rate':'60%','base':'seller_revenue'},{'name':'费用B','rate':'50%','base':'seller_revenue'}]})
        self.assertIsNone(x['known_cost_breakeven_seller_revenue'])
    def test_overprecision_rejected(self):
        with self.assertRaises(mod.InputError):
            mod.evaluate({'seller_revenue':'1.001','costs':[{'name':'采购','amount':'1'}]})

if __name__=='__main__':
    unittest.main()
