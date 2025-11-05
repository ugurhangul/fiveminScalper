#!/usr/bin/env python3
"""
Test restricted trading period logic for multi-range configurations.
"""
from datetime import datetime, timezone, time as dt_time
from src.models.data_models import RangeConfig

def test_restricted_period_logic():
    """Test the restricted period calculation logic"""
    print("\n" + "=" * 70)
    print("RESTRICTED PERIOD LOGIC TEST")
    print("=" * 70 + "\n")
    
    # Test cases: (range_config, test_times, expected_results)
    test_cases = [
        {
            "name": "4H candle at 04:00 UTC",
            "config": RangeConfig(
                range_id="4H_5M",
                reference_timeframe="H4",
                reference_time=dt_time(4, 0),
                breakout_timeframe="M5",
                use_specific_time=True
            ),
            "tests": [
                (dt_time(3, 59), False, "Before start"),
                (dt_time(4, 0), True, "At start"),
                (dt_time(5, 30), True, "Middle of period"),
                (dt_time(7, 59), True, "Just before end"),
                (dt_time(8, 0), False, "At end (candle closed)"),
                (dt_time(10, 0), False, "After end"),
            ]
        },
        {
            "name": "15M candle at 04:30 UTC",
            "config": RangeConfig(
                range_id="15M_1M",
                reference_timeframe="M15",
                reference_time=dt_time(4, 30),
                breakout_timeframe="M1",
                use_specific_time=True
            ),
            "tests": [
                (dt_time(4, 29), False, "Before start"),
                (dt_time(4, 30), True, "At start"),
                (dt_time(4, 40), True, "Middle of period"),
                (dt_time(4, 44), True, "Just before end"),
                (dt_time(4, 45), False, "At end (candle closed)"),
                (dt_time(5, 0), False, "After end"),
            ]
        },
        {
            "name": "1H candle at 23:00 UTC (crosses midnight)",
            "config": RangeConfig(
                range_id="H1_M5",
                reference_timeframe="H1",
                reference_time=dt_time(23, 0),
                breakout_timeframe="M5",
                use_specific_time=True
            ),
            "tests": [
                (dt_time(22, 59), False, "Before start"),
                (dt_time(23, 0), True, "At start"),
                (dt_time(23, 30), True, "Middle of period"),
                (dt_time(23, 59), True, "Just before midnight"),
                (dt_time(0, 0), False, "At end (next day)"),
                (dt_time(1, 0), False, "After end"),
            ]
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print("-" * 70)
        config = test_case['config']
        
        # Calculate duration
        timeframe = config.reference_timeframe
        if timeframe.startswith('H'):
            duration_minutes = int(timeframe[1:]) * 60
        elif timeframe.startswith('M'):
            duration_minutes = int(timeframe[1:])
        
        ref_start_minutes = config.reference_time.hour * 60 + config.reference_time.minute
        ref_end_minutes = ref_start_minutes + duration_minutes
        
        end_hour = (ref_end_minutes // 60) % 24
        end_minute = ref_end_minutes % 60
        
        print(f"Reference candle: {config.reference_time.hour:02d}:{config.reference_time.minute:02d} - "
              f"{end_hour:02d}:{end_minute:02d} UTC ({duration_minutes} minutes)")
        print()
        
        for test_time, expected_restricted, description in test_case['tests']:
            # Calculate if in restricted period
            current_minutes = test_time.hour * 60 + test_time.minute
            
            if ref_end_minutes >= 1440:  # Crosses midnight
                in_period = (current_minutes >= ref_start_minutes) or (current_minutes < (ref_end_minutes - 1440))
            else:
                in_period = (current_minutes >= ref_start_minutes) and (current_minutes < ref_end_minutes)
            
            status = "RESTRICTED" if in_period else "ALLOWED"
            expected_status = "RESTRICTED" if expected_restricted else "ALLOWED"
            
            if in_period == expected_restricted:
                result = "✓ PASS"
            else:
                result = "✗ FAIL"
                all_passed = False
            
            print(f"  {test_time.hour:02d}:{test_time.minute:02d} - {status:10s} (expected: {expected_status:10s}) - {description:20s} {result}")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    test_restricted_period_logic()

