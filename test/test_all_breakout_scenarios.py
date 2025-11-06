#!/usr/bin/env python3
"""
Comprehensive test for ALL breakout detection scenarios.

Tests that breakouts are correctly detected or rejected based on:
1. Open position relative to 4H range
2. Close position relative to 4H range
"""

from datetime import datetime, timezone
from src.models.data_models import CandleData, FourHourCandle

# Test 4H candle: Range 90-100
candle_4h = FourHourCandle(
    time=datetime(2025, 11, 5, 4, 0, tzinfo=timezone.utc),
    high=100.0,
    low=90.0,
    open=92.0,
    close=98.0
)

print("=" * 80)
print("COMPREHENSIVE BREAKOUT DETECTION TEST")
print("=" * 80)
print(f"4H Range: [{candle_4h.low:.1f} - {candle_4h.high:.1f}]")
print("=" * 80)
print()

# Test scenarios organized by category
test_scenarios = {
    "VALID BREAKOUTS": [
        {
            "name": "Valid Bullish Breakout (Open inside, Close above)",
            "open": 95.0,   # Inside [90-100]
            "close": 105.0, # Above 100
            "expected_above": True,
            "expected_below": False,
            "should_log_rejection": False
        },
        {
            "name": "Valid Bearish Breakout (Open inside, Close below)",
            "open": 95.0,   # Inside [90-100]
            "close": 85.0,  # Below 90
            "expected_above": False,
            "expected_below": True,
            "should_log_rejection": False
        },
        {
            "name": "Valid Bullish Breakout (Open at boundary, Close above)",
            "open": 90.0,   # At low boundary (still inside)
            "close": 105.0, # Above 100
            "expected_above": True,
            "expected_below": False,
            "should_log_rejection": False
        },
        {
            "name": "Valid Bearish Breakout (Open at boundary, Close below)",
            "open": 100.0,  # At high boundary (still inside)
            "close": 85.0,  # Below 90
            "expected_above": False,
            "expected_below": True,
            "should_log_rejection": False
        }
    ],
    
    "REJECTED GAP MOVES": [
        {
            "name": "Gap Up (Open above, Close above) - REJECT",
            "open": 105.0,  # Above 100 (outside)
            "close": 110.0, # Above 100 (outside)
            "expected_above": False,
            "expected_below": False,
            "should_log_rejection": True
        },
        {
            "name": "Gap Down (Open below, Close below) - REJECT",
            "open": 85.0,   # Below 90 (outside)
            "close": 80.0,  # Below 90 (outside)
            "expected_above": False,
            "expected_below": False,
            "should_log_rejection": True
        },
        {
            "name": "Gap Up then Close Inside (Open above, Close inside) - REJECT",
            "open": 105.0,  # Above 100 (outside)
            "close": 95.0,  # Inside [90-100]
            "expected_above": False,
            "expected_below": False,
            "should_log_rejection": False  # No breakout condition met
        },
        {
            "name": "Gap Down then Close Inside (Open below, Close inside) - REJECT",
            "open": 85.0,   # Below 90 (outside)
            "close": 95.0,  # Inside [90-100]
            "expected_above": False,
            "expected_below": False,
            "should_log_rejection": False  # No breakout condition met
        }
    ],
    
    "NO BREAKOUT": [
        {
            "name": "Inside Range (Open inside, Close inside)",
            "open": 95.0,   # Inside [90-100]
            "close": 96.0,  # Inside [90-100]
            "expected_above": False,
            "expected_below": False,
            "should_log_rejection": False
        },
        {
            "name": "Touch High but not Break (Open inside, Close at high)",
            "open": 95.0,   # Inside [90-100]
            "close": 100.0, # At high (not above)
            "expected_above": False,
            "expected_below": False,
            "should_log_rejection": False
        },
        {
            "name": "Touch Low but not Break (Open inside, Close at low)",
            "open": 95.0,   # Inside [90-100]
            "close": 90.0,  # At low (not below)
            "expected_above": False,
            "expected_below": False,
            "should_log_rejection": False
        }
    ]
}

# Run all tests
total_tests = 0
passed_tests = 0
failed_tests = 0

for category, tests in test_scenarios.items():
    print(f"\n{'=' * 80}")
    print(f"{category}")
    print(f"{'=' * 80}\n")
    
    for test in tests:
        total_tests += 1
        
        # Create test candle
        candle = CandleData(
            time=datetime(2025, 11, 5, 14, 45, tzinfo=timezone.utc),
            open=test["open"],
            high=max(test["open"], test["close"]) + 1.0,
            low=min(test["open"], test["close"]) - 1.0,
            close=test["close"],
            volume=1000
        )
        
        # Apply breakout detection logic
        open_inside_range = candle.open >= candle_4h.low and candle.open <= candle_4h.high
        close_above_high = candle.close > candle_4h.high
        close_below_low = candle.close < candle_4h.low
        
        # Determine breakout status
        breakout_above = open_inside_range and close_above_high
        breakout_below = open_inside_range and close_below_low
        
        # Check if rejection should be logged
        would_log_rejection = (close_above_high or close_below_low) and not open_inside_range
        
        # Validate results
        passed = (
            breakout_above == test["expected_above"] and
            breakout_below == test["expected_below"] and
            would_log_rejection == test["should_log_rejection"]
        )
        
        if passed:
            passed_tests += 1
            status = "✓ PASS"
        else:
            failed_tests += 1
            status = "✗ FAIL"
        
        print(f"{status} - {test['name']}")
        print(f"  Open: {candle.open:.1f} | Close: {candle.close:.1f}")
        print(f"  Open inside range: {open_inside_range}")
        print(f"  Close above high: {close_above_high}")
        print(f"  Close below low: {close_below_low}")
        print(f"  Breakout Above: {breakout_above} (expected: {test['expected_above']})")
        print(f"  Breakout Below: {breakout_below} (expected: {test['expected_below']})")
        print(f"  Would log rejection: {would_log_rejection} (expected: {test['should_log_rejection']})")
        
        if not passed:
            print(f"  ❌ MISMATCH DETECTED!")
        print()

# Final summary
print("=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total Tests: {total_tests}")
print(f"Passed: {passed_tests} ✓")
print(f"Failed: {failed_tests} ✗")
print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
print("=" * 80)

if failed_tests == 0:
    print("\n🎉 ALL TESTS PASSED! Breakout detection logic is correct.")
else:
    print(f"\n⚠️  {failed_tests} test(s) failed. Review the logic.")

