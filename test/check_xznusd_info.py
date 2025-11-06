"""
Diagnostic script to check XZNUSDr symbol information from MT5.
This will help verify if there's a bug in point/pip calculations.
"""
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os

# Load environment
load_dotenv()

def check_symbol_info(symbol: str):
    """Check and display all relevant symbol information"""
    
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
    
    print(f"\n{'='*70}")
    print(f"SYMBOL INFORMATION: {symbol}")
    print(f"{'='*70}\n")
    
    # Get symbol info
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"Failed to get symbol info for {symbol}")
        mt5.shutdown()
        return
    
    # Display key information
    print(f"Basic Info:")
    print(f"  Name: {info.name}")
    print(f"  Description: {info.description}")
    print(f"  Path: {info.path}")
    print(f"  Currency Base: {info.currency_base}")
    print(f"  Currency Profit: {info.currency_profit}")
    print(f"  Currency Margin: {info.currency_margin}")
    
    print(f"\nPrice Precision:")
    print(f"  Point: {info.point}")
    print(f"  Digits: {info.digits}")
    print(f"  Tick Size: {info.trade_tick_size}")
    print(f"  Tick Value: {info.trade_tick_value}")
    
    print(f"\nStop Levels (CRITICAL):")
    print(f"  Stops Level: {info.trade_stops_level} points")
    print(f"  Freeze Level: {info.trade_freeze_level} points")
    
    # Calculate what stops_level means in price terms
    stops_level_price = info.trade_stops_level * info.point
    freeze_level_price = info.trade_freeze_level * info.point
    
    print(f"\nStop Levels in Price Terms:")
    print(f"  Stops Level: {stops_level_price:.2f} price units")
    print(f"  Freeze Level: {freeze_level_price:.2f} price units")
    
    print(f"\nVolume Settings:")
    print(f"  Min Lot: {info.volume_min}")
    print(f"  Max Lot: {info.volume_max}")
    print(f"  Lot Step: {info.volume_step}")
    print(f"  Contract Size: {info.trade_contract_size}")
    
    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        print(f"\nCurrent Prices:")
        print(f"  Bid: {tick.bid}")
        print(f"  Ask: {tick.ask}")
        spread_price = tick.ask - tick.bid
        spread_points = spread_price / info.point if info.point > 0 else 0
        print(f"  Spread: {spread_points:.1f} points ({spread_price:.5f} price units)")
    
    # Example calculation for position 277307678
    print(f"\n{'='*70}")
    print(f"EXAMPLE: Position 277307678 Analysis")
    print(f"{'='*70}\n")
    
    entry = 3057.1
    hh = 3059.96
    actual_sl = 3070.32
    
    print(f"Position Details:")
    print(f"  Entry: {entry}")
    print(f"  Highest High: {hh}")
    print(f"  Actual SL: {actual_sl}")
    
    print(f"\nExpected Calculation (with offset=0):")
    expected_sl = hh + 0  # offset = 0
    print(f"  Expected SL: {expected_sl:.2f}")
    print(f"  Distance from entry: {expected_sl - entry:.2f} price units")
    
    print(f"\nActual Result:")
    print(f"  Actual SL: {actual_sl}")
    print(f"  Distance from entry: {actual_sl - entry:.2f} price units")
    
    print(f"\nBroker's Minimum Stop Distance:")
    min_distance = info.trade_stops_level * info.point
    print(f"  {info.trade_stops_level} points × {info.point} = {min_distance:.2f} price units")
    
    print(f"\nVerification:")
    if (expected_sl - entry) < min_distance:
        print(f"  ✓ Expected SL ({expected_sl - entry:.2f}) < Broker Min ({min_distance:.2f})")
        print(f"  ✓ Order manager would adjust SL to: {entry + min_distance:.2f}")
        print(f"  ✓ This matches actual SL: {actual_sl}")
    else:
        print(f"  ✗ Expected SL ({expected_sl - entry:.2f}) >= Broker Min ({min_distance:.2f})")
        print(f"  ✗ SL should NOT have been adjusted!")
    
    # Shutdown
    mt5.shutdown()

if __name__ == "__main__":
    check_symbol_info("XZNUSDr")

