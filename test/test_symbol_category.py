"""
Test script to check if MT5 provides a native 'category' field for symbols.
"""
import os
import MetaTrader5 as mt5
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_symbol_category():
    """Test if MT5 symbol_info provides a category field"""
    
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
    print("TESTING MT5 NATIVE CATEGORY FIELD")
    print(f"{'='*80}\n")
    
    # Test symbols from different categories
    test_symbols = [
        'EURUSD',      # Major Forex
        'GBPJPY',      # Minor Forex
        'USDTRY',      # Exotic Forex
        'XAUUSD',      # Metals
        'US500',       # Indices
        'BTCUSD',      # Crypto
        'USOIL',       # Commodities
    ]
    
    for symbol in test_symbols:
        info = mt5.symbol_info(symbol)
        if info is None:
            print(f"❌ {symbol:15} - Not available")
            continue
        
        # Check if category field exists and what it contains
        category = getattr(info, 'category', None)
        path = getattr(info, 'path', None)
        description = getattr(info, 'description', None)
        
        print(f"\n{symbol:15}")
        print(f"  Category:    '{category}'")
        print(f"  Path:        '{path}'")
        print(f"  Description: '{description}'")
    
    print(f"\n{'='*80}")
    print("CHECKING ALL AVAILABLE SYMBOL_INFO FIELDS")
    print(f"{'='*80}\n")
    
    # Get all fields from one symbol
    info = mt5.symbol_info('EURUSD')
    if info:
        info_dict = info._asdict()
        print(f"Total fields: {len(info_dict)}\n")
        
        # Show string fields that might contain category info
        string_fields = ['basis', 'category', 'currency_base', 'currency_profit', 
                        'currency_margin', 'bank', 'description', 'exchange', 
                        'formula', 'isin', 'name', 'page', 'path']
        
        print("String fields:")
        for field in string_fields:
            value = info_dict.get(field, 'N/A')
            print(f"  {field:20} = '{value}'")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_symbol_category()

