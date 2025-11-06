#!/usr/bin/env python3
"""
Test script for constructing stats from MT5 history.

This script demonstrates:
1. Reading closed trades from MT5 history
2. Constructing symbol stats from historical trades
3. Saving constructed stats to persistence
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config.config import TradingConfig
from src.core.mt5_connector import MT5Connector
from src.strategy.symbol_performance_persistence import SymbolPerformancePersistence
from src.utils.logger import init_logger

# Initialize logger
init_logger(log_to_file=False, log_to_console=True, log_level="INFO", enable_detailed=False)


def main():
    """Test stats construction from MT5 history"""
    print("\n" + "="*80)
    print("TEST: Construct Stats from MT5 History")
    print("="*80)
    
    # Load config
    config = TradingConfig()
    
    # Connect to MT5
    connector = MT5Connector(config.mt5)
    if not connector.connect():
        print("❌ Failed to connect to MT5")
        return
    
    print("✓ Connected to MT5")
    
    # Create persistence
    test_dir = "test_data_history"
    Path(test_dir).mkdir(exist_ok=True)
    persistence = SymbolPerformancePersistence(data_dir=test_dir)
    
    # Test with a symbol (you can change this to any symbol you've traded)
    test_symbol = "EURUSD"
    
    print(f"\nAttempting to construct stats for {test_symbol} from MT5 history...")
    print(f"Magic number: {config.advanced.magic_number}")
    print(f"Looking back: 30 days")
    
    # Construct stats from history
    stats = persistence.construct_stats_from_mt5_history(
        symbol=test_symbol,
        connector=connector,
        magic_number=config.advanced.magic_number,
        days_back=30
    )
    
    if stats:
        print("\n" + "="*80)
        print("✓ Successfully constructed stats from history!")
        print("="*80)
        print(f"\nSymbol: {test_symbol}")
        print(f"Total Trades: {stats.total_trades}")
        print(f"Winning Trades: {stats.winning_trades}")
        print(f"Losing Trades: {stats.losing_trades}")
        print(f"Win Rate: {stats.win_rate:.1f}%")
        print(f"Total Profit: ${stats.total_profit:.2f}")
        print(f"Total Loss: ${stats.total_loss:.2f}")
        print(f"Net P/L: ${stats.net_profit:.2f}")
        print(f"Consecutive Losses: {stats.consecutive_losses}")
        print(f"Consecutive Wins: {stats.consecutive_wins}")
        print(f"Peak Equity: ${stats.peak_equity:.2f}")
        print(f"Current Drawdown: ${stats.current_drawdown:.2f} ({stats.current_drawdown_percent:.2f}%)")
        print(f"Max Drawdown: ${stats.max_drawdown:.2f} ({stats.max_drawdown_percent:.2f}%)")
        
        # Save to persistence
        print(f"\nSaving stats to {test_dir}/symbol_stats.json...")
        persistence.save_symbol_stats(test_symbol, stats)
        print("✓ Stats saved successfully")
        
        # Verify by loading
        print("\nVerifying by loading stats back...")
        loaded_stats = persistence.load_symbol_stats(test_symbol)
        if loaded_stats:
            print("✓ Stats loaded successfully")
            print(f"  Total trades: {loaded_stats.total_trades}")
            print(f"  Net P/L: ${loaded_stats.net_profit:.2f}")
        else:
            print("❌ Failed to load stats")
    else:
        print("\n❌ No history found or failed to construct stats")
        print(f"   This could mean:")
        print(f"   - No trades exist for {test_symbol} in the last 30 days")
        print(f"   - No trades with magic number {config.advanced.magic_number}")
        print(f"   - MT5 history is not available")
    
    # Disconnect
    connector.disconnect()
    print("\n✓ Disconnected from MT5")


if __name__ == "__main__":
    main()

