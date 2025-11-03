"""
Test all spreads from Market Watch symbols
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.mt5_connector import MT5Connector
from src.config.config import TradingConfig
from src.config.symbol_optimizer import SymbolOptimizer
from src.models.data_models import SymbolParameters

def main():
    """Test all symbols from Market Watch"""

    # Initialize MT5 connection
    config = TradingConfig()
    connector = MT5Connector(config.mt5)

    if not connector.connect():
        print("❌ Failed to connect to MT5")
        return

    print("=" * 80)
    print("SPREAD LIMIT TESTS - All Market Watch Symbols")
    print("=" * 80)

    # Get all symbols from Market Watch
    symbols = connector.get_market_watch_symbols()
    if not symbols:
        print("❌ No symbols found in Market Watch")
        connector.disconnect()
        return

    print(f"\nFound {len(symbols)} symbols in Market Watch\n")

    # Category limits
    category_limits = {
        "Major Forex": 0.05,
        "Minor Forex": 0.2,
        "Exotic Forex": 0.4,
        "Precious Metals": 0.05,
        "Stock Indices": 0.1,
        "Cryptocurrencies": 0.5,
        "Commodities": 0.1,
        "Unknown": 0.1
    }

    # Test each symbol
    results = []
    rejected_count = 0
    accepted_count = 0
    error_count = 0

    for symbol in symbols:
        try:
            # Get spread percentage
            spread_percent = connector.get_spread_percent(symbol)
            if spread_percent is None:
                error_count += 1
                continue

            # Get spread in points for display
            spread_points = connector.get_spread(symbol)

            # Get current price
            tick = connector.connector.symbol_info_tick(symbol) if hasattr(connector, 'connector') else None
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(symbol)
            mid_price = (tick.ask + tick.bid) / 2 if tick else 0

            # Detect category and get limit
            category, params = SymbolOptimizer.get_symbol_parameters(symbol, SymbolParameters())
            category_name = SymbolOptimizer.get_category_name(category)
            limit = params.max_spread_percent

            # Check if rejected
            is_rejected = spread_percent > limit

            if is_rejected:
                rejected_count += 1
                status = "❌ REJECTED"
            else:
                accepted_count += 1
                status = "✅ ACCEPTED"

            results.append({
                'symbol': symbol,
                'category': category_name,
                'price': mid_price,
                'spread_points': spread_points,
                'spread_percent': spread_percent,
                'limit': limit,
                'rejected': is_rejected
            })

            # Print result
            print(f"{symbol:15} | {category_name:18} | "
                  f"Price: {mid_price:12.5f} | "
                  f"Spread: {spread_points:8.1f} pts ({spread_percent:6.3f}%) | "
                  f"Limit: {limit:5.2f}% | {status}")

        except Exception as e:
            error_count += 1
            print(f"{symbol:15} | ERROR: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nTotal Symbols: {len(symbols)}")
    print(f"  ✅ Accepted: {accepted_count}")
    print(f"  ❌ Rejected: {rejected_count}")
    print(f"  ⚠️  Errors:   {error_count}")

    print("\nCategory Limits:")
    for cat, limit in category_limits.items():
        print(f"  {cat:18}: {limit}%")

    # Show rejected symbols
    if rejected_count > 0:
        print(f"\n❌ Rejected Symbols ({rejected_count}):")
        for r in results:
            if r['rejected']:
                print(f"  {r['symbol']:15} ({r['category']:18}): "
                      f"{r['spread_percent']:.3f}% > {r['limit']:.2f}%")

    # Disconnect
    connector.disconnect()
    print("\n✅ Test completed")

if __name__ == "__main__":
    main()

