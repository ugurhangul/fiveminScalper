"""
Test script for enhanced logging functionality.

This script demonstrates:
1. Symbol disabling logging with deduplication
2. Enhanced error logging with context
3. Spread warning logging
4. Liquidity warning logging
5. Symbol condition warnings
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import init_logger

def test_enhanced_logging():
    """Test all enhanced logging features"""
    
    # Initialize logger
    logger = init_logger(
        log_to_file=True,
        log_to_console=True,
        log_level="INFO",
        enable_detailed=True
    )
    
    logger.header("ENHANCED LOGGING TEST")
    logger.info("Testing new logging features...")
    logger.separator()
    
    # Test 1: Symbol Disabling Log (with deduplication)
    logger.info("\n=== TEST 1: Symbol Disabling (with deduplication) ===")
    
    stats = {
        'total_trades': 10,
        'wins': 3,
        'losses': 7,
        'win_rate': 30.0,
        'net_pnl': -150.50,
        'consecutive_losses': 5,
        'cooling_days': 1,
        'reenable_date': '2025-11-06 19:00:00 UTC'
    }
    
    # First disable - should log
    logger.symbol_disabled("EURUSD", "Win rate 30.0% below minimum 40.0%", stats)
    
    # Second disable - should NOT log (duplicate)
    logger.symbol_disabled("EURUSD", "Win rate 30.0% below minimum 40.0%", stats)
    
    # Different symbol - should log
    logger.symbol_disabled("GBPUSD", "Consecutive losses 5 reached maximum 5", stats)
    
    logger.info("✓ Symbol disabling test complete")
    logger.separator()
    
    # Test 2: Symbol Re-enabling
    logger.info("\n=== TEST 2: Symbol Re-enabling ===")
    
    old_stats = {
        'total_trades': 10,
        'net_pnl': -150.50,
        'disable_reason': 'Performance criteria not met'
    }
    
    logger.symbol_reenabled("EURUSD", old_stats)
    logger.info("✓ Symbol re-enabling test complete")
    logger.separator()
    
    # Test 3: Trade Errors with Context
    logger.info("\n=== TEST 3: Trade Errors with Context ===")
    
    logger.trade_error(
        symbol="BTCUSD",
        error_type="Trade Execution",
        error_message="Order rejected by broker: Insufficient margin",
        context={
            "retcode": 10019,
            "order_type": "BUY",
            "volume": 0.5,
            "price": 45000.00,
            "sl": 44500.00,
            "tp": 46000.00
        }
    )
    
    logger.trade_error(
        symbol="XAUUSD",
        error_type="Data Retrieval",
        error_message="Failed to get 4H candles from MT5",
        context={
            "timeframe": "4H",
            "count": 100,
            "mt5_error": "(1, 'Market is closed')"
        }
    )
    
    logger.info("✓ Trade error logging test complete")
    logger.separator()
    
    # Test 4: Spread Warnings
    logger.info("\n=== TEST 4: Spread Warnings ===")
    
    # Rejected spread
    logger.spread_warning(
        symbol="SEKDKK",
        current_spread_percent=0.128,
        current_spread_points=873.0,
        threshold_percent=0.100,
        is_rejected=True
    )
    
    # Elevated but acceptable spread
    logger.spread_warning(
        symbol="EURUSD",
        current_spread_percent=0.008,
        current_spread_points=0.8,
        threshold_percent=0.010,
        is_rejected=False
    )
    
    logger.info("✓ Spread warning test complete")
    logger.separator()
    
    # Test 5: Liquidity Warnings
    logger.info("\n=== TEST 5: Liquidity Warnings ===")
    
    logger.liquidity_warning(
        symbol="USDTRY",
        volume=50,
        avg_volume=150,
        reason="Volume significantly below average"
    )
    
    logger.info("✓ Liquidity warning test complete")
    logger.separator()
    
    # Test 6: Symbol Condition Warnings
    logger.info("\n=== TEST 6: Symbol Condition Warnings ===")
    
    logger.symbol_condition_warning(
        symbol="USDJPY",
        condition="Market Hours",
        details="Trading outside of optimal market hours (low liquidity expected)"
    )
    
    logger.symbol_condition_warning(
        symbol="NZDUSD",
        condition="Trading Disabled",
        details="Trading is disabled for this symbol in MT5"
    )
    
    logger.info("✓ Symbol condition warning test complete")
    logger.separator()
    
    # Summary
    logger.header("TEST SUMMARY")
    logger.info("All enhanced logging tests completed successfully!")
    logger.info("")
    logger.info("Check the following log files:")
    
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_dir = Path("logs") / date_str
    
    logger.info(f"  - Main log: {log_dir / 'main.log'}")
    logger.info(f"  - Disable log: {log_dir / 'disable.log'}")
    logger.info(f"  - Symbol logs: {log_dir / 'EURUSD.log'}, etc.")
    logger.separator()
    
    # Display disable.log content
    disable_log = log_dir / "disable.log"
    if disable_log.exists():
        logger.info("\n=== DISABLE.LOG CONTENT ===")
        with open(disable_log, 'r', encoding='utf-8') as f:
            content = f.read()
            print(content)
        logger.separator()

if __name__ == "__main__":
    test_enhanced_logging()

