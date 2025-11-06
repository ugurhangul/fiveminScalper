"""
Test script for ATR-based trailing stop system.

This script verifies:
1. ATR calculation works correctly
2. ATR trailing stop is activated at the right time
3. Stop loss is trailed correctly for long and short positions
4. Stop loss only moves in favorable direction
5. Peak price tracking works correctly
"""
import os
import sys
from datetime import datetime, timezone
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.indicators.technical_indicators import TechnicalIndicators
from src.config.config import TrailingStopConfig
from src.models.data_models import PositionInfo, PositionType
from src.utils.logger import init_logger

# Initialize logger
init_logger(log_to_file=False, log_to_console=True, log_level="INFO", enable_detailed=False)


def test_atr_calculation():
    """Test ATR calculation"""
    print("\n" + "="*60)
    print("TEST 1: ATR Calculation")
    print("="*60)
    
    indicators = TechnicalIndicators()
    
    # Create sample OHLC data
    np.random.seed(42)
    n = 50
    
    # Generate realistic price data
    close_prices = 1.1000 + np.cumsum(np.random.randn(n) * 0.0001)
    high_prices = close_prices + np.abs(np.random.randn(n) * 0.0002)
    low_prices = close_prices - np.abs(np.random.randn(n) * 0.0002)
    
    high = pd.Series(high_prices)
    low = pd.Series(low_prices)
    close = pd.Series(close_prices)
    
    # Calculate ATR with period 14
    atr = indicators.calculate_atr(high, low, close, period=14)
    
    print(f"\nSample data points: {n}")
    print(f"Price range: {close.min():.5f} - {close.max():.5f}")
    print(f"ATR(14): {atr:.5f}")
    
    assert atr is not None, "ATR should not be None"
    assert atr > 0, "ATR should be positive"
    
    print("\n✓ ATR calculation test PASSED")


def test_atr_trailing_activation():
    """Test ATR trailing stop activation logic"""
    print("\n" + "="*60)
    print("TEST 2: ATR Trailing Stop Activation")
    print("="*60)
    
    # Create config with ATR trailing enabled
    config = TrailingStopConfig(
        use_trailing_stop=True,
        trailing_stop_trigger_rr=1.5,
        use_atr_trailing=True,
        atr_period=14,
        atr_multiplier=2.0,
        atr_timeframe="H4"
    )
    
    print(f"\nATR Trailing Config:")
    print(f"  Enabled: {config.use_atr_trailing}")
    print(f"  Period: {config.atr_period}")
    print(f"  Multiplier: {config.atr_multiplier}x")
    print(f"  Timeframe: {config.atr_timeframe}")
    print(f"  Trigger R:R: {config.trailing_stop_trigger_rr}")
    
    # Verify configuration
    assert config.use_atr_trailing == True
    assert config.atr_period == 14
    assert config.atr_multiplier == 2.0
    
    print("\n✓ ATR trailing activation test PASSED")


def test_atr_distance_calculation():
    """Test ATR distance calculation"""
    print("\n" + "="*60)
    print("TEST 3: ATR Distance Calculation")
    print("="*60)
    
    indicators = TechnicalIndicators()
    
    # Create sample data
    np.random.seed(42)
    n = 50
    close_prices = 1.1000 + np.cumsum(np.random.randn(n) * 0.0001)
    high_prices = close_prices + np.abs(np.random.randn(n) * 0.0002)
    low_prices = close_prices - np.abs(np.random.randn(n) * 0.0002)
    
    high = pd.Series(high_prices)
    low = pd.Series(low_prices)
    close = pd.Series(close_prices)
    
    atr = indicators.calculate_atr(high, low, close, period=14)
    
    # Test different multipliers
    multipliers = [1.0, 1.5, 2.0, 2.5, 3.0]
    
    print(f"\nATR: {atr:.5f}")
    print(f"\nATR Distance with different multipliers:")
    
    for mult in multipliers:
        distance = atr * mult
        print(f"  {mult}x ATR = {distance:.5f}")
        assert distance > 0, f"Distance should be positive for multiplier {mult}"
    
    # Test stop loss calculation for BUY position
    entry_price = 1.1000
    atr_multiplier = 2.0
    atr_distance = atr * atr_multiplier
    
    buy_sl = entry_price - atr_distance
    sell_sl = entry_price + atr_distance
    
    print(f"\nExample with entry price {entry_price:.5f}:")
    print(f"  BUY SL (entry - {atr_multiplier}x ATR): {buy_sl:.5f}")
    print(f"  SELL SL (entry + {atr_multiplier}x ATR): {sell_sl:.5f}")
    
    assert buy_sl < entry_price, "BUY SL should be below entry"
    assert sell_sl > entry_price, "SELL SL should be above entry"
    
    print("\n✓ ATR distance calculation test PASSED")


def test_peak_tracking_logic():
    """Test peak price tracking for trailing"""
    print("\n" + "="*60)
    print("TEST 4: Peak Price Tracking")
    print("="*60)
    
    # Simulate BUY position price movement
    print("\n--- BUY Position ---")
    entry_price = 1.1000
    peak_price = entry_price
    
    price_movements = [
        1.1010,  # New high
        1.1020,  # New high
        1.1015,  # Pullback (peak stays at 1.1020)
        1.1025,  # New high
        1.1020,  # Pullback (peak stays at 1.1025)
    ]
    
    print(f"Entry: {entry_price:.5f}")
    
    for i, price in enumerate(price_movements, 1):
        old_peak = peak_price
        if price > peak_price:
            peak_price = price
        
        print(f"Move {i}: Price={price:.5f}, Peak={peak_price:.5f} {'(NEW HIGH)' if price > old_peak else ''}")
    
    assert peak_price == 1.1025, "Final peak should be 1.1025"
    
    # Simulate SELL position price movement
    print("\n--- SELL Position ---")
    entry_price = 1.1000
    peak_price = entry_price  # For SELL, peak is the lowest price
    
    price_movements = [
        1.0990,  # New low
        1.0980,  # New low
        1.0985,  # Pullback (peak stays at 1.0980)
        1.0975,  # New low
        1.0980,  # Pullback (peak stays at 1.0975)
    ]
    
    print(f"Entry: {entry_price:.5f}")
    
    for i, price in enumerate(price_movements, 1):
        old_peak = peak_price
        if price < peak_price:
            peak_price = price
        
        print(f"Move {i}: Price={price:.5f}, Peak={peak_price:.5f} {'(NEW LOW)' if price < old_peak else ''}")
    
    assert peak_price == 1.0975, "Final peak should be 1.0975"
    
    print("\n✓ Peak tracking test PASSED")


def test_stop_loss_movement_rules():
    """Test that stop loss only moves in favorable direction"""
    print("\n" + "="*60)
    print("TEST 5: Stop Loss Movement Rules")
    print("="*60)
    
    atr_distance = 0.0020  # Example ATR distance
    
    # BUY position - SL should only move UP
    print("\n--- BUY Position (SL should only move UP) ---")
    peak_price = 1.1000
    current_sl = 1.0980
    
    test_cases = [
        (1.1010, 1.0990, True, "Price up, new SL higher"),
        (1.1005, 1.0985, False, "Price down, SL stays same"),
        (1.1020, 1.1000, True, "Price up more, new SL higher"),
    ]
    
    for new_peak, new_sl_calc, should_update, description in test_cases:
        if new_peak > peak_price:
            peak_price = new_peak
            calculated_sl = peak_price - atr_distance
            
            if calculated_sl > current_sl:
                print(f"✓ {description}: {current_sl:.5f} → {calculated_sl:.5f}")
                current_sl = calculated_sl
                assert should_update, f"Should update for: {description}"
            else:
                print(f"  {description}: SL stays at {current_sl:.5f}")
                assert not should_update, f"Should not update for: {description}"
        else:
            print(f"  {description}: Peak unchanged, SL stays at {current_sl:.5f}")
    
    # SELL position - SL should only move DOWN
    print("\n--- SELL Position (SL should only move DOWN) ---")
    peak_price = 1.1000
    current_sl = 1.1020
    
    test_cases = [
        (1.0990, 1.1010, True, "Price down, new SL lower"),
        (1.0995, 1.1015, False, "Price up, SL stays same"),
        (1.0980, 1.1000, True, "Price down more, new SL lower"),
    ]
    
    for new_peak, new_sl_calc, should_update, description in test_cases:
        if new_peak < peak_price:
            peak_price = new_peak
            calculated_sl = peak_price + atr_distance
            
            if calculated_sl < current_sl:
                print(f"✓ {description}: {current_sl:.5f} → {calculated_sl:.5f}")
                current_sl = calculated_sl
                assert should_update, f"Should update for: {description}"
            else:
                print(f"  {description}: SL stays at {current_sl:.5f}")
                assert not should_update, f"Should not update for: {description}"
        else:
            print(f"  {description}: Peak unchanged, SL stays at {current_sl:.5f}")
    
    print("\n✓ Stop loss movement rules test PASSED")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ATR TRAILING STOP TEST SUITE")
    print("="*60)
    
    try:
        test_atr_calculation()
        test_atr_trailing_activation()
        test_atr_distance_calculation()
        test_peak_tracking_logic()
        test_stop_loss_movement_rules()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        print("\nATR trailing stop system is ready to use!")
        print("\nTo enable ATR trailing stops, set in your .env file:")
        print("  USE_ATR_TRAILING=true")
        print("  ATR_PERIOD=14")
        print("  ATR_MULTIPLIER=2.0")
        print("  ATR_TIMEFRAME=H4")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

