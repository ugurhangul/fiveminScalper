"""
Test script to check MT5 native category field for ALL symbols in Market Watch.
"""
import os
import MetaTrader5 as mt5
from dotenv import load_dotenv
from collections import defaultdict

# Load environment variables
load_dotenv()

def test_all_symbol_categories():
    """Test MT5 category field for all symbols in Market Watch"""
    
    # Initialize MT5
    if not mt5.initialize():
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    # Login
    login = int(os.getenv('MT5_LOGIN', '0'))
    password = os.getenv('MT5_PASSWORD', '')
    server = os.getenv('MT5_SERVER', '')
    
    if not mt5.login(login, password, server):
        print(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return
    
    print(f"\n{'='*80}")
    print("MT5 NATIVE CATEGORY FIELD - ALL MARKET WATCH SYMBOLS")
    print(f"{'='*80}\n")
    
    # Get all symbols from Market Watch
    symbols = mt5.symbols_get()
    if not symbols:
        print("❌ No symbols found")
        mt5.shutdown()
        return
    
    print(f"Total symbols: {len(symbols)}\n")
    
    # Group symbols by category
    category_groups = defaultdict(list)
    empty_category_count = 0
    
    for symbol_info in symbols:
        category = getattr(symbol_info, 'category', '')
        
        if not category or category.strip() == '':
            empty_category_count += 1
            category = '(EMPTY)'
        
        category_groups[category].append(symbol_info.name)
    
    # Display results
    print(f"{'='*80}")
    print(f"CATEGORIES FOUND: {len(category_groups)}")
    print(f"{'='*80}\n")
    
    for category in sorted(category_groups.keys()):
        symbols_in_cat = category_groups[category]
        print(f"\n{category} ({len(symbols_in_cat)} symbols)")
        print("-" * 80)
        
        # Show first 10 symbols in each category
        for symbol in sorted(symbols_in_cat)[:10]:
            print(f"  {symbol}")
        
        if len(symbols_in_cat) > 10:
            print(f"  ... and {len(symbols_in_cat) - 10} more")
    
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total symbols:           {len(symbols)}")
    print(f"Unique categories:       {len(category_groups)}")
    print(f"Symbols with empty cat:  {empty_category_count}")
    print(f"Coverage:                {((len(symbols) - empty_category_count) / len(symbols) * 100):.1f}%")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_all_symbol_categories()

