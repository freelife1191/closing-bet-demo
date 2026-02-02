
import unittest
import sys
import os

# Add scripts directory to path to import init_data
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from init_data import assign_grade

class TestJonggaGrading(unittest.TestCase):
    def test_grade_S(self):
        """S급: 1조 원 이상 AND 10% 이상 상승 AND 외인+기관 동반 순매수 AND 거래량 5배"""
        data = {
            'trading_value': 1_200_000_000_000,
            'rise_pct': 12.0,
            'foreign_positive': True,
            'inst_positive': True,
            'volume_ratio': 5.5
        }
        self.assertEqual(assign_grade(data), 'S')

    def test_grade_A(self):
        """A급: 5,000억 원 이상 AND 5% 이상 상승 AND (외인 OR 기관) AND 거래량 3배"""
        data = {
            'trading_value': 600_000_000_000,
            'rise_pct': 6.0,
            'foreign_positive': True,
            'inst_positive': False,
            'volume_ratio': 3.5
        }
        self.assertEqual(assign_grade(data), 'A')

    def test_grade_B(self):
        """B급: 1,000억 원 이상 AND 4% 이상 상승 AND (외인 OR 기관) AND 거래량 2배"""
        data = {
            'trading_value': 150_000_000_000,
            'rise_pct': 4.5,
            'foreign_positive': False,
            'inst_positive': True,
            'volume_ratio': 2.5
        }
        self.assertEqual(assign_grade(data), 'B')

    def test_grade_C(self):
        """C급: 500억 이상 AND 5% 이상 상승 AND 거래량 3배+ AND 외인+기관"""
        data = {
            'trading_value': 70_000_000_000,
            'rise_pct': 5.5,
            'foreign_positive': True,
            'inst_positive': True,
            'volume_ratio': 3.2
        }
        self.assertEqual(assign_grade(data), 'C')

    def test_grade_D(self):
        """D급: 500억 이상 AND 4% 이상 상승 AND 거래량 2배"""
        data = {
            'trading_value': 60_000_000_000,
            'rise_pct': 4.2,
            'foreign_positive': False,
            'inst_positive': False,
            'volume_ratio': 2.5
        }
        self.assertEqual(assign_grade(data), 'D')

    def test_no_grade_low_trading_value(self):
        """거래대금 미달 (300억 미만은 아예 init단계에서 걸러지지만, 여기선 500억 미만 체크)"""
        data = {
            'trading_value': 40_000_000_000,
            'rise_pct': 5.0,
            'foreign_positive': True,
            'inst_positive': True,
            'volume_ratio': 2.0
        }
        self.assertIsNone(assign_grade(data))

    def test_no_grade_negative_rise(self):
        """하락 종목"""
        data = {
            'trading_value': 2_000_000_000_000, # 금액 커도 하락하면 탈락
            'rise_pct': -1.0,
            'foreign_positive': True,
            'inst_positive': True,
            'volume_ratio': 5.0
        }
        self.assertIsNone(assign_grade(data))

if __name__ == '__main__':
    unittest.main()
