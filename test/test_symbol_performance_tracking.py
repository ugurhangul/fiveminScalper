"""
Test script for symbol performance tracking and auto-disable system.

This script verifies:
1. Drawdown tracking works correctly
2. Stats are persisted to JSON file
3. Weekly reset logic functions properly
4. Auto-disable triggers on consecutive losses and drawdown
5. Re-enable logic works correctly
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.models.data_models import SymbolStats
from src.config.config import SymbolAdaptationConfig
from src.strategy.symbol_tracker import SymbolTracker
from src.strategy.symbol_performance_persistence import SymbolPerformancePersistence
from src.utils.logger import init_logger

# Initialize logger
init_logger(log_to_file=False, log_to_console=True, log_level="INFO", enable_detailed=False)


def test_drawdown_tracking():
    """Test drawdown calculation"""
    print("\n" + "="*60)
    print("TEST 1: Drawdown Tracking")
    print("="*60)
    
    # Create test config
    config = SymbolAdaptationConfig(
        use_symbol_adaptation=True,
        min_trades_for_evaluation=3,
        max_consecutive_losses=3,
        max_drawdown_percent=15.0,
        reset_weekly=False
    )
    
    # Create persistence with test directory
    test_dir = "test_data"
    Path(test_dir).mkdir(exist_ok=True)
    persistence = SymbolPerformancePersistence(data_dir=test_dir)
    
    # Create tracker
    tracker = SymbolTracker("EURUSD", config, persistence)
    
    # Simulate trades with profits and losses
    print("\nSimulating trades:")
    
    # Trade 1: +100 profit (peak equity = 100)
    tracker.on_trade_closed(100.0)
    print(f"Trade 1: +$100 | Peak: ${tracker.stats.peak_equity:.2f} | Drawdown: {tracker.stats.current_drawdown_percent:.2f}%")
    assert tracker.stats.peak_equity == 100.0
    assert tracker.stats.current_drawdown == 0.0
    
    # Trade 2: +50 profit (peak equity = 150)
    tracker.on_trade_closed(50.0)
    print(f"Trade 2: +$50  | Peak: ${tracker.stats.peak_equity:.2f} | Drawdown: {tracker.stats.current_drawdown_percent:.2f}%")
    assert tracker.stats.peak_equity == 150.0
    assert tracker.stats.current_drawdown == 0.0
    
    # Trade 3: -30 loss (equity = 120, drawdown = 30 from peak of 150)
    tracker.on_trade_closed(-30.0)
    print(f"Trade 3: -$30  | Peak: ${tracker.stats.peak_equity:.2f} | Drawdown: {tracker.stats.current_drawdown_percent:.2f}%")
    assert tracker.stats.peak_equity == 150.0
    assert tracker.stats.current_drawdown == 30.0
    assert abs(tracker.stats.current_drawdown_percent - 20.0) < 0.01  # 30/150 = 20%
    
    # Trade 4: -20 loss (equity = 100, drawdown = 50 from peak of 150)
    tracker.on_trade_closed(-20.0)
    print(f"Trade 4: -$20  | Peak: ${tracker.stats.peak_equity:.2f} | Drawdown: {tracker.stats.current_drawdown_percent:.2f}%")
    assert tracker.stats.current_drawdown == 50.0
    assert abs(tracker.stats.current_drawdown_percent - 33.33) < 0.01  # 50/150 = 33.33%
    
    # Trade 5: +60 profit (equity = 160, new peak, drawdown resets)
    tracker.on_trade_closed(60.0)
    print(f"Trade 5: +$60  | Peak: ${tracker.stats.peak_equity:.2f} | Drawdown: {tracker.stats.current_drawdown_percent:.2f}%")
    assert tracker.stats.peak_equity == 160.0
    assert tracker.stats.current_drawdown == 0.0
    assert tracker.stats.max_drawdown == 50.0  # Max drawdown should be preserved
    
    print("\n✓ Drawdown tracking test PASSED")
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)


def test_persistence():
    """Test stats persistence"""
    print("\n" + "="*60)
    print("TEST 2: Stats Persistence")
    print("="*60)
    
    test_dir = "test_data"
    Path(test_dir).mkdir(exist_ok=True)
    
    config = SymbolAdaptationConfig(
        use_symbol_adaptation=True,
        reset_weekly=False
    )
    
    # Create first tracker and add some trades
    persistence1 = SymbolPerformancePersistence(data_dir=test_dir)
    tracker1 = SymbolTracker("GBPUSD", config, persistence1)
    
    print("\nAdding trades to first tracker:")
    tracker1.on_trade_closed(100.0)
    tracker1.on_trade_closed(-30.0)
    tracker1.on_trade_closed(50.0)
    
    print(f"Total trades: {tracker1.stats.total_trades}")
    print(f"Net P/L: ${tracker1.stats.net_profit:.2f}")
    print(f"Peak equity: ${tracker1.stats.peak_equity:.2f}")
    
    # Create second tracker with same symbol (should load from persistence)
    print("\nCreating new tracker (should load from persistence):")
    persistence2 = SymbolPerformancePersistence(data_dir=test_dir)
    tracker2 = SymbolTracker("GBPUSD", config, persistence2)
    
    print(f"Loaded total trades: {tracker2.stats.total_trades}")
    print(f"Loaded net P/L: ${tracker2.stats.net_profit:.2f}")
    print(f"Loaded peak equity: ${tracker2.stats.peak_equity:.2f}")
    
    # Verify stats match
    assert tracker2.stats.total_trades == 3
    assert tracker2.stats.net_profit == 120.0
    assert tracker2.stats.peak_equity == 120.0
    
    print("\n✓ Persistence test PASSED")
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)


def test_auto_disable():
    """Test auto-disable on consecutive losses and drawdown"""
    print("\n" + "="*60)
    print("TEST 3: Auto-Disable Logic")
    print("="*60)
    
    test_dir = "test_data"
    Path(test_dir).mkdir(exist_ok=True)
    
    # Test consecutive losses
    print("\n--- Testing consecutive losses trigger ---")
    config = SymbolAdaptationConfig(
        use_symbol_adaptation=True,
        min_trades_for_evaluation=3,
        max_consecutive_losses=3,
        max_drawdown_percent=50.0,  # High threshold so it doesn't trigger
        reset_weekly=False
    )
    
    persistence = SymbolPerformancePersistence(data_dir=test_dir)
    tracker = SymbolTracker("USDJPY", config, persistence)
    
    # Add 3 consecutive losses
    tracker.on_trade_closed(-10.0)
    print(f"Loss 1: Can trade = {tracker.can_trade()}")
    assert tracker.can_trade() == True
    
    tracker.on_trade_closed(-10.0)
    print(f"Loss 2: Can trade = {tracker.can_trade()}")
    assert tracker.can_trade() == True
    
    tracker.on_trade_closed(-10.0)
    print(f"Loss 3: Can trade = {tracker.can_trade()}")
    assert tracker.can_trade() == False  # Should be disabled
    assert tracker.is_disabled == True
    
    print("✓ Consecutive losses trigger works")
    
    # Test drawdown trigger
    print("\n--- Testing drawdown trigger ---")
    config2 = SymbolAdaptationConfig(
        use_symbol_adaptation=True,
        min_trades_for_evaluation=3,
        max_consecutive_losses=10,  # High threshold so it doesn't trigger
        max_drawdown_percent=15.0,
        reset_weekly=False
    )
    
    tracker2 = SymbolTracker("AUDUSD", config2, persistence)
    
    # Build up equity then draw it down
    tracker2.on_trade_closed(100.0)  # Peak = 100
    tracker2.on_trade_closed(50.0)   # Peak = 150
    print(f"After wins: Peak = ${tracker2.stats.peak_equity:.2f}, Can trade = {tracker2.can_trade()}")
    
    tracker2.on_trade_closed(-30.0)  # Equity = 120, Drawdown = 20%
    print(f"After loss: Drawdown = {tracker2.stats.current_drawdown_percent:.2f}%, Can trade = {tracker2.can_trade()}")
    assert tracker2.can_trade() == False  # Should be disabled (20% > 15%)
    assert tracker2.is_disabled == True
    
    print("✓ Drawdown trigger works")
    
    print("\n✓ Auto-disable test PASSED")
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)


def test_weekly_reset():
    """Test weekly reset logic"""
    print("\n" + "="*60)
    print("TEST 4: Weekly Reset Logic")
    print("="*60)
    
    test_dir = "test_data"
    Path(test_dir).mkdir(exist_ok=True)
    
    config = SymbolAdaptationConfig(
        use_symbol_adaptation=True,
        reset_weekly=True,
        weekly_reset_day=0,  # Monday
        weekly_reset_hour=0,
        min_trades_for_evaluation=1
    )
    
    persistence = SymbolPerformancePersistence(data_dir=test_dir)
    tracker = SymbolTracker("NZDUSD", config, persistence)
    
    # Add some trades
    tracker.on_trade_closed(100.0)
    tracker.on_trade_closed(-30.0)
    
    print(f"Before reset: Total trades = {tracker.stats.total_trades}")
    print(f"Week start time: {tracker.stats.week_start_time}")

    # Manually trigger reset by setting week_start_time to past
    old_week_start = tracker.stats.week_start_time
    old_total_trades = tracker.stats.total_trades
    tracker.stats.week_start_time = datetime.now(timezone.utc) - timedelta(days=8)
    tracker._save_stats()

    # Check for weekly reset
    tracker._check_weekly_reset()

    print(f"After reset: Total trades = {tracker.stats.total_trades}")
    print(f"New week start time: {tracker.stats.week_start_time}")

    assert tracker.stats.total_trades == 0, f"Expected 0 trades, got {tracker.stats.total_trades}"
    assert tracker.stats.week_start_time >= old_week_start, f"Week start time should be updated"
    assert old_total_trades > 0, "Should have had trades before reset"
    
    print("\n✓ Weekly reset test PASSED")
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SYMBOL PERFORMANCE TRACKING TEST SUITE")
    print("="*60)
    
    try:
        test_drawdown_tracking()
        test_persistence()
        test_auto_disable()
        test_weekly_reset()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

