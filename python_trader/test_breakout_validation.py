#!/usr/bin/env python3
"""
Test script to validate breakout detection logic.

Tests that breakouts are only detected when:
1. Open is INSIDE the 4H range
2. Close is OUTSIDE the 4H range

This prevents gap moves from being detected as breakouts.
"""

from datetime import datetime, timezone
from src.models.data_models import CandleData, FourHourCandle

# Test 4H candle
candle_4h = FourHourCandle(
    time=datetime(2025, 11, 5, 4, 0, tzinfo=timezone.utc),
    high=100.0,
    low=90.0,
    open=92.0,
    close=98.0
)

print("=" * 60)
print("4H Candle Range:")
print(f"  High: {candle_4h.high}")
print(f"  Low: {candle_4h.low}")
print("=" * 60)
print()

# Test cases
test_cases = [
    {
        "name": "Valid Bullish Breakout",
        "candle": CandleData(
            time=datetime(2025, 11, 5, 14, 45, tzinfo=timezone.utc),
            open=95.0,   # Inside range (90-100)
            high=105.0,
            low=94.0,
            close=102.0,  # Above high (100)
            volume=1000
        ),
        "expected_above": True,
        "expected_below": False
    },
    {
        "name": "Valid Bearish Breakout",
        "candle": CandleData(
            time=datetime(2025, 11, 5, 14, 50, tzinfo=timezone.utc),
            open=95.0,   # Inside range (90-100)
            high=96.0,
            low=85.0,
            close=88.0,  # Below low (90)
            volume=1000
        ),
        "expected_above": False,
        "expected_below": True
    },
    {
        "name": "Gap Up (INVALID - should reject)",
        "candle": CandleData(
            time=datetime(2025, 11, 5, 14, 55, tzinfo=timezone.utc),
            open=105.0,  # OUTSIDE range (above 100)
            high=110.0,
            low=104.0,
            close=108.0,  # Above high (100)
            volume=1000
        ),
        "expected_above": False,  # Should be rejected
        "expected_below": False
    },
    {
        "name": "Gap Down (INVALID - should reject)",
        "candle": CandleData(
            time=datetime(2025, 11, 5, 15, 0, tzinfo=timezone.utc),
            open=85.0,   # OUTSIDE range (below 90)
            high=88.0,
            low=82.0,
            close=84.0,  # Below low (90)
            volume=1000
        ),
        "expected_above": False,
        "expected_below": False  # Should be rejected
    },
    {
        "name": "Inside Range (no breakout)",
        "candle": CandleData(
            time=datetime(2025, 11, 5, 15, 5, tzinfo=timezone.utc),
            open=95.0,   # Inside range
            high=98.0,
            low=92.0,
            close=96.0,  # Inside range
            volume=1000
        ),
        "expected_above": False,
        "expected_below": False
    }
]

# Run tests
print("Testing Breakout Detection Logic:")
print()

for test in test_cases:
    candle = test["candle"]
    
    # Check breakout ABOVE
    open_inside_range = candle.open >= candle_4h.low and candle.open <= candle_4h.high
    close_above_high = candle.close > candle_4h.high
    breakout_above = open_inside_range and close_above_high
    
    # Check breakout BELOW
    close_below_low = candle.close < candle_4h.low
    breakout_below = open_inside_range and close_below_low
    
    # Validate results
    passed = (breakout_above == test["expected_above"] and 
              breakout_below == test["expected_below"])
    
    status = "✓ PASS" if passed else "✗ FAIL"
    
    print(f"{status} - {test['name']}")
    print(f"  5M Open: {candle.open:.2f} | Close: {candle.close:.2f}")
    print(f"  Open inside range: {open_inside_range}")
    print(f"  Close above high: {close_above_high}")
    print(f"  Close below low: {close_below_low}")
    print(f"  Breakout Above: {breakout_above} (expected: {test['expected_above']})")
    print(f"  Breakout Below: {breakout_below} (expected: {test['expected_below']})")
    print()

print("=" * 60)
print("Test Summary:")
print(f"Total tests: {len(test_cases)}")
passed_count = sum(1 for test in test_cases 
                   if ((candle := test["candle"]) and
                       (open_inside := candle.open >= candle_4h.low and candle.open <= candle_4h.high) and
                       ((open_inside and candle.close > candle_4h.high) == test["expected_above"]) and
                       ((open_inside and candle.close < candle_4h.low) == test["expected_below"])))
print(f"Passed: {passed_count}")
print(f"Failed: {len(test_cases) - passed_count}")
print("=" * 60)

