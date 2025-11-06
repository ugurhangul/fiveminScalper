#!/usr/bin/env python3
"""
Test per-range ATR timeframe configuration.

This script verifies that:
1. Range configurations include ATR timeframes
2. TradeManager correctly extracts range_id from position comments
3. Correct ATR timeframe is selected based on position's range
"""
from datetime import datetime, timezone, time as dt_time
from src.models.data_models import RangeConfig, PositionInfo, PositionType
from src.execution.trade_manager import TradeManager
from src.config.config import TrailingStopConfig


def test_range_config_atr_timeframes():
    """Test that range configurations have ATR timeframes"""
    print("\n" + "="*70)
    print("TEST 1: Range Configuration ATR Timeframes")
    print("="*70)
    
    # Create range configurations with ATR timeframes
    range1 = RangeConfig(
        range_id="4H_5M",
        reference_timeframe="H4",
        reference_time=dt_time(4, 0),
        breakout_timeframe="M5",
        use_specific_time=True,
        atr_timeframe="M5"
    )
    
    range2 = RangeConfig(
        range_id="15M_1M",
        reference_timeframe="M15",
        reference_time=dt_time(4, 30),
        breakout_timeframe="M1",
        use_specific_time=True,
        atr_timeframe="M1"
    )
    
    print(f"\nRange 1: {range1.range_id}")
    print(f"  Breakout TF: {range1.breakout_timeframe}")
    print(f"  ATR TF: {range1.atr_timeframe}")
    
    print(f"\nRange 2: {range2.range_id}")
    print(f"  Breakout TF: {range2.breakout_timeframe}")
    print(f"  ATR TF: {range2.atr_timeframe}")
    
    assert range1.atr_timeframe == "M5", "Range 1 should use M5 ATR"
    assert range2.atr_timeframe == "M1", "Range 2 should use M1 ATR"
    
    print("\n✓ Range configurations have correct ATR timeframes")
    return [range1, range2]


def test_atr_timeframe_extraction():
    """Test extracting ATR timeframe from position comment"""
    print("\n" + "="*70)
    print("TEST 2: ATR Timeframe Extraction from Position Comment")
    print("="*70)
    
    # Create range configurations
    ranges = [
        RangeConfig(
            range_id="4H_5M",
            reference_timeframe="H4",
            reference_time=dt_time(4, 0),
            breakout_timeframe="M5",
            use_specific_time=True,
            atr_timeframe="M5"
        ),
        RangeConfig(
            range_id="15M_1M",
            reference_timeframe="M15",
            reference_time=dt_time(4, 30),
            breakout_timeframe="M1",
            use_specific_time=True,
            atr_timeframe="M1"
        )
    ]
    
    # Create trailing config
    trailing_config = TrailingStopConfig(
        use_trailing_stop=True,
        trailing_stop_trigger_rr=1.5,
        use_atr_trailing=True,
        atr_period=14,
        atr_multiplier=2.0,
        atr_timeframe="H4"  # Fallback
    )
    
    # Create mock trade manager (without connector/order_manager)
    class MockConnector:
        pass
    
    class MockOrderManager:
        pass
    
    trade_manager = TradeManager(
        connector=MockConnector(),
        order_manager=MockOrderManager(),
        trailing_config=trailing_config,
        use_breakeven=True,
        breakeven_trigger_rr=1.0,
        indicators=None,
        range_configs=ranges
    )
    
    # Test cases
    test_cases = [
        {
            "comment": "TB|BUY|V|4H5M",
            "expected_tf": "M5",
            "description": "4H_5M range (M5 scalping)"
        },
        {
            "comment": "FB|SELL|VD|15M1M",
            "expected_tf": "M1",
            "description": "15M_1M range (M1 scalping)"
        },
        {
            "comment": "TB|BUY|NC",
            "expected_tf": "H4",
            "description": "No range info (fallback to H4)"
        },
        {
            "comment": "",
            "expected_tf": "H4",
            "description": "Empty comment (fallback to H4)"
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['description']}")
        print(f"  Comment: '{test_case['comment']}'")
        
        # Create mock position
        position = PositionInfo(
            ticket=12345,
            symbol="EURUSD",
            position_type=PositionType.BUY,
            volume=0.01,
            open_price=1.10000,
            current_price=1.10050,
            sl=1.09950,
            tp=1.10100,
            profit=5.0,
            open_time=datetime.now(timezone.utc),
            magic_number=123456,
            comment=test_case['comment']
        )
        
        # Get ATR timeframe
        atr_tf = trade_manager._get_atr_timeframe_for_position(position)
        
        # Check result
        if atr_tf == test_case['expected_tf']:
            print(f"  Result: {atr_tf} ✓ PASS")
        else:
            print(f"  Result: {atr_tf} ✗ FAIL (expected {test_case['expected_tf']})")
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ All ATR timeframe extraction tests PASSED")
    else:
        print("✗ Some tests FAILED")
    print("="*70)
    
    return all_passed


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PER-RANGE ATR TIMEFRAME TEST SUITE")
    print("="*70)
    
    try:
        ranges = test_range_config_atr_timeframes()
        all_passed = test_atr_timeframe_extraction()
        
        if all_passed:
            print("\n" + "="*70)
            print("ALL TESTS PASSED ✓")
            print("="*70)
            print("\nPer-range ATR configuration is working correctly!")
            print("\nConfiguration:")
            print("  - 4H_5M range uses M5 ATR (for M5 scalping)")
            print("  - 15M_1M range uses M1 ATR (for M1 scalping)")
        else:
            print("\n" + "="*70)
            print("SOME TESTS FAILED ✗")
            print("="*70)
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

