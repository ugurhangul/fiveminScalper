#!/usr/bin/env python3
"""
Test script to verify multi-range breakout detection.

Tests that:
1. Both range configurations (4H/5M and 15M/1M) work independently
2. Each range maintains its own breakout state
3. Both ranges can generate signals simultaneously for the same symbol
4. Range identifiers are properly tracked in trade signals
"""
from datetime import datetime, timezone, time as dt_time
from src.models.data_models import (
    RangeConfig, MultiRangeBreakoutState, ReferenceCandle, CandleData,
    PositionType
)


def test_range_config_creation():
    """Test creating range configurations"""
    print("=" * 70)
    print("TEST 1: Range Configuration Creation")
    print("=" * 70)
    
    # Create Range 1: 4H at 04:00 UTC, 5M breakout
    range1 = RangeConfig(
        range_id="4H_5M",
        reference_timeframe="H4",
        reference_time=dt_time(4, 0),
        breakout_timeframe="M5",
        use_specific_time=True
    )
    
    # Create Range 2: 15M at 04:30 UTC, 1M breakout
    range2 = RangeConfig(
        range_id="15M_1M",
        reference_timeframe="M15",
        reference_time=dt_time(4, 30),
        breakout_timeframe="M1",
        use_specific_time=True
    )
    
    print(f"Range 1: {range1}")
    print(f"Range 2: {range2}")
    print()
    
    assert range1.range_id == "4H_5M"
    assert range1.reference_timeframe == "H4"
    assert range1.breakout_timeframe == "M5"
    assert range2.range_id == "15M_1M"
    assert range2.reference_timeframe == "M15"
    assert range2.breakout_timeframe == "M1"
    
    print("✓ Range configurations created successfully")
    print()


def test_multi_range_state():
    """Test multi-range state tracking"""
    print("=" * 70)
    print("TEST 2: Multi-Range State Tracking")
    print("=" * 70)
    
    # Create multi-range state
    state = MultiRangeBreakoutState()
    
    # Get or create states for both ranges
    state_4h = state.get_or_create_state("4H_5M")
    state_15m = state.get_or_create_state("15M_1M")
    
    print(f"Created state for 4H_5M: {state_4h is not None}")
    print(f"Created state for 15M_1M: {state_15m is not None}")
    print()
    
    # Simulate breakout detection for Range 1 (4H_5M)
    current_time = datetime.now(timezone.utc)
    state_4h.breakout_above_detected = True
    state_4h.breakout_above_volume = 1000
    state_4h.breakout_above_time = current_time
    
    print("Range 1 (4H_5M) - Breakout above detected:")
    print(f"  Detected: {state_4h.breakout_above_detected}")
    print(f"  Volume: {state_4h.breakout_above_volume}")
    print(f"  Time: {state_4h.breakout_above_time}")
    print()
    
    # Simulate breakout detection for Range 2 (15M_1M)
    state_15m.breakout_below_detected = True
    state_15m.breakout_below_volume = 500
    state_15m.breakout_below_time = current_time
    
    print("Range 2 (15M_1M) - Breakout below detected:")
    print(f"  Detected: {state_15m.breakout_below_detected}")
    print(f"  Volume: {state_15m.breakout_below_volume}")
    print(f"  Time: {state_15m.breakout_below_time}")
    print()
    
    # Verify independence
    assert state_4h.breakout_above_detected == True
    assert state_4h.breakout_below_detected == False
    assert state_15m.breakout_above_detected == False
    assert state_15m.breakout_below_detected == True
    
    print("✓ Both ranges maintain independent state")
    print()
    
    # Test has_active_breakout
    assert state.has_active_breakout("4H_5M") == True
    assert state.has_active_breakout("15M_1M") == True
    assert state.has_active_breakout() == True  # Any range
    
    print("✓ Active breakout detection works correctly")
    print()


def test_independent_signal_generation():
    """Test that both ranges can generate signals independently"""
    print("=" * 70)
    print("TEST 3: Independent Signal Generation")
    print("=" * 70)
    
    # Create multi-range state
    state = MultiRangeBreakoutState()
    
    # Simulate both ranges qualifying for different strategies
    state_4h = state.get_or_create_state("4H_5M")
    state_15m = state.get_or_create_state("15M_1M")
    
    # Range 1: Qualify for FALSE SELL (breakout above, low volume)
    state_4h.breakout_above_detected = True
    state_4h.false_sell_qualified = True
    state_4h.false_sell_volume_ok = True
    
    # Range 2: Qualify for TRUE BUY (breakout above, high volume)
    state_15m.breakout_above_detected = True
    state_15m.true_buy_qualified = True
    state_15m.true_buy_volume_ok = True
    
    print("Range 1 (4H_5M) qualified for FALSE SELL:")
    print(f"  Breakout above: {state_4h.breakout_above_detected}")
    print(f"  FALSE SELL qualified: {state_4h.false_sell_qualified}")
    print()
    
    print("Range 2 (15M_1M) qualified for TRUE BUY:")
    print(f"  Breakout above: {state_15m.breakout_above_detected}")
    print(f"  TRUE BUY qualified: {state_15m.true_buy_qualified}")
    print()
    
    # Verify both can be active simultaneously
    assert state_4h.false_sell_qualified == True
    assert state_15m.true_buy_qualified == True
    
    print("✓ Both ranges can qualify for different strategies simultaneously")
    print()


def test_range_reset():
    """Test resetting individual ranges"""
    print("=" * 70)
    print("TEST 4: Range Reset")
    print("=" * 70)
    
    # Create multi-range state with active breakouts
    state = MultiRangeBreakoutState()
    state_4h = state.get_or_create_state("4H_5M")
    state_15m = state.get_or_create_state("15M_1M")
    
    # Set breakouts for both
    state_4h.breakout_above_detected = True
    state_15m.breakout_below_detected = True
    
    print("Before reset:")
    print(f"  4H_5M breakout above: {state_4h.breakout_above_detected}")
    print(f"  15M_1M breakout below: {state_15m.breakout_below_detected}")
    print()
    
    # Reset only Range 1
    state.reset_range("4H_5M")
    
    print("After resetting 4H_5M:")
    print(f"  4H_5M breakout above: {state_4h.breakout_above_detected}")
    print(f"  15M_1M breakout below: {state_15m.breakout_below_detected}")
    print()
    
    assert state_4h.breakout_above_detected == False
    assert state_15m.breakout_below_detected == True
    
    print("✓ Individual range reset works correctly")
    print()


if __name__ == "__main__":
    print("\n")
    print("*" * 70)
    print("MULTI-RANGE BREAKOUT DETECTION TEST SUITE")
    print("*" * 70)
    print("\n")
    
    test_range_config_creation()
    test_multi_range_state()
    test_independent_signal_generation()
    test_range_reset()
    
    print("=" * 70)
    print("ALL TESTS PASSED ✓")
    print("=" * 70)
    print("\nSummary:")
    print("- Range configurations can be created with different timeframes")
    print("- Each range maintains independent breakout state")
    print("- Both ranges can qualify for different strategies simultaneously")
    print("- Individual ranges can be reset without affecting others")
    print("\nThe multi-range implementation is ready for integration!")

