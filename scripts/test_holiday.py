import sys
import os
from datetime import date

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.market_schedule import MarketSchedule

def test_dates():
    test_cases = [
        (date(2026, 2, 13), True, "Today (Friday)"),
        (date(2026, 2, 14), False, "Weekend (Saturday)"),
        (date(2026, 2, 15), False, "Weekend (Sunday)"),
        (date(2026, 2, 16), False, "Holiday (Seollal)"),
        (date(2026, 2, 17), False, "Holiday (Seollal)"),
        (date(2026, 3, 1), False, "Holiday (Samiljeol) - Sunday"),
        (date(2026, 3, 2), False, "Holiday (Samiljeol Substitute)"),
        (date(2026, 5, 5), False, "Holiday (Children's Day)"),
        (date(2026, 5, 25), False, "Holiday (Buddha Substitute)"),
    ]

    all_passed = True
    print(f"{'Date':<12} | {'Expected':<8} | {'Actual':<8} | {'Result':<6} | {'Description'}")
    print("-" * 60)
    
    for d, expected, desc in test_cases:
        actual = MarketSchedule.is_market_open(d)
        result = "PASS" if actual == expected else "FAIL"
        if actual != expected:
            all_passed = False
        print(f"{d} | {str(expected):<8} | {str(actual):<8} | {result:<6} | {desc}")

    if all_passed:
        print("\n✅ All holiday tests passed!")
    else:
        print("\n❌ Some tests failed!")

if __name__ == "__main__":
    test_dates()
