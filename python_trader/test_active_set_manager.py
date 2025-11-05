"""
Test script for active.set management functionality.

This script demonstrates:
1. Loading symbols from active.set
2. Automatic removal of symbols with persistent errors
3. Logging removed symbols to disable.log
4. Preserving symbols with temporary errors (no money, market closed)
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import init_logger
from src.utils.active_set_manager import get_active_set_manager


def test_active_set_manager():
    """Test active.set management functionality"""
    
    # Initialize logger
    logger = init_logger(
        log_to_file=True,
        log_to_console=True,
        log_level="INFO",
        enable_detailed=True
    )
    
    logger.header("ACTIVE.SET MANAGER TEST")
    logger.info("Testing automatic symbol removal from active.set...")
    logger.separator()
    
    # Get manager instance
    manager = get_active_set_manager()
    
    # Load current symbols
    symbols = manager.load_symbols()
    logger.info(f"Loaded {len(symbols)} symbols from active.set")
    logger.info(f"First 10 symbols: {', '.join(symbols[:10])}")
    logger.separator()
    
    # Test 1: Errors that should NOT remove symbols (temporary conditions)
    logger.info("\n=== TEST 1: Temporary Errors (Should NOT Remove) ===")
    
    temporary_errors = [
        "Insufficient margin to open position",
        "No money to execute trade",
        "Market is closed",
        "Off quotes - no prices available",
        "Requote received from broker"
    ]
    
    for error in temporary_errors:
        should_remove = manager.should_remove_symbol(error)
        status = "❌ REMOVE" if should_remove else "✓ KEEP"
        logger.info(f"{status}: {error}")
    
    logger.separator()
    
    # Test 2: Errors that SHOULD remove symbols (persistent issues)
    logger.info("\n=== TEST 2: Persistent Errors (SHOULD Remove) ===")
    
    persistent_errors = [
        "Trading is disabled for this symbol",
        "Spread too high: 0.128% (max: 0.100%)",
        "Symbol not found in MT5",
        "Failed to get symbol info from MT5",
        "Failed to get spread for symbol",
        "Failed to get 4H candles from MT5"
    ]
    
    for error in persistent_errors:
        should_remove = manager.should_remove_symbol(error)
        status = "✓ REMOVE" if should_remove else "❌ KEEP"
        logger.info(f"{status}: {error}")
    
    logger.separator()
    
    # Test 3: Simulate removing a symbol
    logger.info("\n=== TEST 3: Symbol Removal Simulation ===")
    
    # Pick a test symbol (use one that exists in the list)
    if symbols:
        test_symbol = symbols[0]
        logger.info(f"Test symbol: {test_symbol}")
        
        # Simulate trade error that should remove symbol
        logger.trade_error(
            symbol=test_symbol,
            error_type="Trade Execution",
            error_message="Trading is disabled for this symbol in MT5",
            context={
                "action": "Symbol will be removed from active.set"
            }
        )
        
        # Reload symbols to verify removal
        updated_symbols = manager.load_symbols()
        
        if test_symbol not in updated_symbols:
            logger.info(f"✓ Symbol {test_symbol} successfully removed from active.set")
            logger.info(f"Symbols count: {len(symbols)} → {len(updated_symbols)}")
        else:
            logger.warning(f"❌ Symbol {test_symbol} was NOT removed")
        
        # Restore the symbol for next test
        manager.symbols.append(test_symbol)
        manager.save_symbols()
        logger.info(f"Symbol {test_symbol} restored to active.set")
    
    logger.separator()
    
    # Test 4: Simulate spread rejection
    logger.info("\n=== TEST 4: Spread Rejection Simulation ===")
    
    if len(symbols) > 1:
        test_symbol = symbols[1]
        logger.info(f"Test symbol: {test_symbol}")
        
        # Simulate spread warning with rejection
        logger.spread_warning(
            symbol=test_symbol,
            current_spread_percent=0.128,
            current_spread_points=873.0,
            threshold_percent=0.100,
            is_rejected=True
        )
        
        # Reload symbols to verify removal
        updated_symbols = manager.load_symbols()
        
        if test_symbol not in updated_symbols:
            logger.info(f"✓ Symbol {test_symbol} successfully removed due to excessive spread")
            logger.info(f"Symbols count: {len(symbols)} → {len(updated_symbols)}")
        else:
            logger.warning(f"❌ Symbol {test_symbol} was NOT removed")
        
        # Restore the symbol
        manager.symbols.append(test_symbol)
        manager.save_symbols()
        logger.info(f"Symbol {test_symbol} restored to active.set")
    
    logger.separator()
    
    # Test 5: Simulate trading disabled
    logger.info("\n=== TEST 5: Trading Disabled Simulation ===")
    
    if len(symbols) > 2:
        test_symbol = symbols[2]
        logger.info(f"Test symbol: {test_symbol}")
        
        # Simulate trading disabled warning
        logger.symbol_condition_warning(
            symbol=test_symbol,
            condition="Trading Disabled",
            details="Trading is disabled for this symbol in MT5 - Trade rejected"
        )
        
        # Reload symbols to verify removal
        updated_symbols = manager.load_symbols()
        
        if test_symbol not in updated_symbols:
            logger.info(f"✓ Symbol {test_symbol} successfully removed (trading disabled)")
            logger.info(f"Symbols count: {len(symbols)} → {len(updated_symbols)}")
        else:
            logger.warning(f"❌ Symbol {test_symbol} was NOT removed")
        
        # Restore the symbol
        manager.symbols.append(test_symbol)
        manager.save_symbols()
        logger.info(f"Symbol {test_symbol} restored to active.set")
    
    logger.separator()
    
    # Summary
    logger.header("TEST SUMMARY")
    logger.info("All active.set management tests completed!")
    logger.info("")
    logger.info("Check the following files:")
    
    from datetime import datetime, timezone
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_dir = Path("logs") / date_str
    
    logger.info(f"  - Active symbols: python_trader/data/active.set")
    logger.info(f"  - Disable log: {log_dir / 'disable.log'}")
    logger.info(f"  - Main log: {log_dir / 'main.log'}")
    logger.separator()
    
    # Display disable.log content
    disable_log = log_dir / "disable.log"
    if disable_log.exists():
        logger.info("\n=== DISABLE.LOG CONTENT ===")
        with open(disable_log, 'r', encoding='utf-8') as f:
            content = f.read()
            print(content)
        logger.separator()
    
    # Display current active.set count
    final_symbols = manager.load_symbols()
    logger.info(f"\nFinal symbol count in active.set: {len(final_symbols)}")


if __name__ == "__main__":
    test_active_set_manager()

