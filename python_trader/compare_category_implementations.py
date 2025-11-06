"""
Compare MT5 native category field vs custom SymbolOptimizer implementation.
"""
import os
import MetaTrader5 as mt5
from dotenv import load_dotenv
from src.config.symbol_optimizer import SymbolOptimizer, SymbolCategory

# Load environment variables
load_dotenv()

def compare_implementations():
    """Compare MT5 native vs custom category detection"""
    
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
    
    print(f"\n{'='*100}")
    print("COMPARISON: MT5 Native Category vs Custom SymbolOptimizer")
    print(f"{'='*100}\n")
    
    # Get all symbols
    symbols = mt5.symbols_get()
    if not symbols:
        print("❌ No symbols found")
        mt5.shutdown()
        return
    
    # Mapping from MT5 categories to our custom categories
    mt5_to_custom_mapping = {
        'Majors': SymbolCategory.MAJOR_FOREX,
        'Minors': SymbolCategory.MINOR_FOREX,
        'Exotic': SymbolCategory.EXOTIC_FOREX,
        'Metals': SymbolCategory.METALS,
        'Indices': SymbolCategory.INDICES,
        'Crypto': SymbolCategory.CRYPTO,
        'Energies': SymbolCategory.COMMODITIES,
        'Stocks': SymbolCategory.UNKNOWN,  # We don't have a stocks category
        'Other': SymbolCategory.UNKNOWN,
        'Heartbeat': SymbolCategory.UNKNOWN,
    }
    
    matches = 0
    mismatches = 0
    mt5_has_custom_missing = 0
    custom_unknown = 0
    
    mismatched_symbols = []
    
    for symbol_info in symbols:
        symbol_name = symbol_info.name
        mt5_category = getattr(symbol_info, 'category', '')
        custom_category = SymbolOptimizer.detect_category(symbol_name)
        
        # Expected custom category based on MT5 category
        expected_custom = mt5_to_custom_mapping.get(mt5_category, SymbolCategory.UNKNOWN)
        
        if custom_category == SymbolCategory.UNKNOWN:
            custom_unknown += 1
            if mt5_category and mt5_category not in ['Heartbeat', 'Other', 'Stocks']:
                mt5_has_custom_missing += 1
                mismatched_symbols.append({
                    'symbol': symbol_name,
                    'mt5': mt5_category,
                    'custom': custom_category.value,
                    'reason': 'Custom returns UNKNOWN but MT5 has category'
                })
        elif custom_category == expected_custom:
            matches += 1
        else:
            mismatches += 1
            mismatched_symbols.append({
                'symbol': symbol_name,
                'mt5': mt5_category,
                'custom': custom_category.value,
                'expected': expected_custom.value,
                'reason': 'Category mismatch'
            })
    
    # Display results
    print(f"Total symbols analyzed: {len(symbols)}\n")
    print(f"✅ Matches:                    {matches}")
    print(f"❌ Mismatches:                 {mismatches}")
    print(f"⚠️  Custom returns UNKNOWN:     {custom_unknown}")
    print(f"📊 MT5 has, Custom missing:    {mt5_has_custom_missing}")
    
    accuracy = (matches / len(symbols) * 100) if len(symbols) > 0 else 0
    print(f"\n🎯 Accuracy: {accuracy:.1f}%")
    
    # Show mismatches
    if mismatched_symbols:
        print(f"\n{'='*100}")
        print(f"MISMATCHED SYMBOLS (showing first 20)")
        print(f"{'='*100}\n")
        
        for item in mismatched_symbols[:20]:
            print(f"{item['symbol']:15} | MT5: {item['mt5']:15} | Custom: {item['custom']:20} | {item['reason']}")
        
        if len(mismatched_symbols) > 20:
            print(f"\n... and {len(mismatched_symbols) - 20} more mismatches")
    
    mt5.shutdown()

if __name__ == "__main__":
    compare_implementations()

