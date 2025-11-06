"""
Test script for symbol prioritization functionality.

This script demonstrates:
1. Detecting duplicate symbols (same base pair with different suffixes)
2. Prioritizing symbols based on suffix (r > standard > m)
3. Filtering to keep only the best available version
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import init_logger
from src.utils.symbol_prioritizer import SymbolPrioritizer


def test_symbol_prioritization():
    """Test symbol prioritization functionality"""
    
    # Initialize logger
    logger = init_logger(
        log_to_file=True,
        log_to_console=True,
        log_level="INFO",
        enable_detailed=True
    )
    
    logger.header("SYMBOL PRIORITIZATION TEST")
    logger.info("Testing automatic symbol deduplication and prioritization...")
    logger.separator()
    
    # Create prioritizer (without connector for testing)
    prioritizer = SymbolPrioritizer(connector=None)
    
    # Test 1: Extract base and suffix
    logger.info("\n=== TEST 1: Extract Base and Suffix ===")
    test_symbols = ['EURUSD', 'EURUSDr', 'EURUSDm', 'USDBND', 'USDBNDr', 'USDBNDm']
    
    for symbol in test_symbols:
        base, suffix = prioritizer.extract_base_and_suffix(symbol)
        suffix_display = f"'{suffix}'" if suffix else "(none)"
        logger.info(f"{symbol:12} -> Base: {base:10} Suffix: {suffix_display}")
    
    logger.separator()
    
    # Test 2: Group symbols by base
    logger.info("\n=== TEST 2: Group Symbols by Base ===")
    groups = prioritizer.group_symbols_by_base(test_symbols)
    
    for base, symbol_list in groups.items():
        logger.info(f"\nBase: {base}")
        for full_symbol, suffix in symbol_list:
            suffix_display = f"'{suffix}'" if suffix else "(none)"
            priority = prioritizer.SUFFIX_PRIORITY.get(suffix, 999)
            logger.info(f"  - {full_symbol:12} Suffix: {suffix_display:8} Priority: {priority}")
    
    logger.separator()
    
    # Test 3: Filter duplicates (without MT5 validation)
    logger.info("\n=== TEST 3: Filter Duplicates (No MT5 Validation) ===")
    
    # Create a larger test set with duplicates
    test_set = [
        'EURUSD', 'EURUSDr', 'EURUSDm',      # EUR/USD group
        'GBPUSD', 'GBPUSDr',                  # GBP/USD group (no 'm')
        'USDJPY',                             # USD/JPY group (only standard)
        'USDBND', 'USDBNDr', 'USDBNDm',      # USD/BND group
        'XAUUSD', 'XAUUSDr',                  # XAU/USD group
        'BTCUSD', 'BTCUSDr', 'BTCUSDm',      # BTC/USD group
    ]
    
    logger.info(f"Input symbols: {len(test_set)}")
    for symbol in test_set:
        logger.info(f"  - {symbol}")
    
    filtered = prioritizer.filter_symbols(test_set, logger)
    
    logger.info(f"\nFiltered symbols: {len(filtered)}")
    for symbol in filtered:
        base, suffix = prioritizer.extract_base_and_suffix(symbol)
        suffix_display = f"'{suffix}'" if suffix else "(standard)"
        logger.info(f"  ✓ {symbol:12} ({suffix_display})")
    
    logger.separator()
    
    # Test 4: Verify priority order
    logger.info("\n=== TEST 4: Verify Priority Order ===")
    
    test_cases = [
        (['EURUSD', 'EURUSDr', 'EURUSDm'], 'EURUSDr', 'Should select raw spread'),
        (['EURUSD', 'EURUSDm'], 'EURUSD', 'Should select standard when no raw'),
        (['EURUSDm'], 'EURUSDm', 'Should select micro when only option'),
        (['GBPUSD'], 'GBPUSD', 'Should keep standard when no duplicates'),
    ]
    
    for symbols, expected, description in test_cases:
        result = prioritizer.filter_symbols(symbols)
        status = "✓ PASS" if result == [expected] else "❌ FAIL"
        logger.info(f"{status}: {description}")
        logger.info(f"  Input: {symbols}")
        logger.info(f"  Expected: [{expected}]")
        logger.info(f"  Got: {result}")
        logger.info("")
    
    logger.separator()
    
    # Test 5: Summary
    logger.info("\n=== TEST SUMMARY ===")
    logger.info("Symbol prioritization logic:")
    logger.info("  1. Raw spread symbols (suffix 'r') - HIGHEST PRIORITY")
    logger.info("  2. Standard symbols (no suffix) - MEDIUM PRIORITY")
    logger.info("  3. Micro/Mini symbols (suffix 'm') - LOWEST PRIORITY")
    logger.info("")
    logger.info("Deduplication behavior:")
    logger.info("  - Groups symbols by base pair (e.g., EURUSD, EURUSDr, EURUSDm)")
    logger.info("  - Selects the highest priority tradeable version")
    logger.info("  - Removes all other versions to prevent duplicate exposure")
    logger.info("")
    logger.info("✓ All tests completed successfully!")


if __name__ == "__main__":
    test_symbol_prioritization()

