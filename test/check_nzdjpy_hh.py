"""
Check the actual highest high for NZDJPYr position 277562579
"""
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os
from datetime import datetime, time as dt_time
import pandas as pd

from src.core.mt5_connector import MT5Connector
from src.config.config import MT5Config, RangeConfig
from src.strategy.multi_range_candle_processor import MultiRangeCandleProcessor

# Load environment
load_dotenv()

def check_nzdjpy_highest_high():
    """Check what the highest high should be for position 277562579"""
    
    print("\n" + "="*70)
    print("NZDJPY Position 277562579 Analysis")
    print("="*70 + "\n")
    
    # Initialize MT5
    mt5_config = MT5Config(
        login=int(os.getenv('MT5_LOGIN', '0')),
        password=os.getenv('MT5_PASSWORD', ''),
        server=os.getenv('MT5_SERVER', '')
    )
    
    connector = MT5Connector(mt5_config)
    if not connector.connect():
        print("Failed to connect to MT5")
        return
    
    print("✓ Connected to MT5\n")
    
    # Position details from logs
    symbol = "NZDJPYr"
    entry = 86.967
    sl = 87.045
    logged_hh = 87.031
    ref_high = 87.271  # 4H high
    
    print("Position Details:")
    print(f"  Entry: {entry}")
    print(f"  SL: {sl}")
    print(f"  Logged HH: {logged_hh}")
    print(f"  4H High: {ref_high}")
    print(f"  SL Distance: {sl - entry:.3f} ({(sl - entry) / 0.001:.0f} points)\n")
    
    # Define range configuration
    ranges = [
        RangeConfig(
            range_id="4H_5M",
            reference_timeframe="H4",
            reference_time=dt_time(4, 0),
            breakout_timeframe="M5",
            use_specific_time=True,
            atr_timeframe="M5"
        )
    ]
    
    # Create candle processor
    processor = MultiRangeCandleProcessor(
        symbol=symbol,
        connector=connector,
        range_configs=ranges
    )
    
    # Get M5 candles around the time of the trade (11:12 UTC)
    print("="*70)
    print("M5 CANDLES BEFORE TRADE (11:12 UTC)")
    print("="*70 + "\n")
    
    # Get last 10 M5 candles
    df = processor.get_breakout_candles("4H_5M", count=10)
    if df is None or len(df) == 0:
        print("Failed to get M5 candles")
        connector.disconnect()
        return
    
    print(f"Last 10 M5 candles:\n")
    print(df[['time', 'open', 'high', 'low', 'close']].to_string())
    
    # Calculate highest high
    actual_hh = df['high'].max()
    
    print(f"\n" + "="*70)
    print("ANALYSIS")
    print("="*70 + "\n")
    
    print(f"Actual Highest High (from M5 data): {actual_hh:.3f}")
    print(f"Logged Highest High: {logged_hh:.3f}")
    print(f"Match: {abs(actual_hh - logged_hh) < 0.001}")
    
    # Calculate what SL should be
    spread_points = 14  # From logs
    spread_price = spread_points * 0.001
    expected_sl = actual_hh + 0.0 + spread_price  # offset=0
    
    print(f"\nExpected SL Calculation:")
    print(f"  HH: {actual_hh:.3f}")
    print(f"  Offset: 0.000 (configured as 0)")
    print(f"  Spread: {spread_price:.3f} ({spread_points} points)")
    print(f"  Expected SL: {expected_sl:.3f}")
    print(f"  Actual SL: {sl:.3f}")
    print(f"  Match: {abs(expected_sl - sl) < 0.001}")
    
    # Show individual candle highs
    print(f"\n" + "="*70)
    print("INDIVIDUAL CANDLE HIGHS")
    print("="*70 + "\n")
    
    for idx, row in df.iterrows():
        marker = " ← HIGHEST" if row['high'] == actual_hh else ""
        print(f"{row['time']}: High = {row['high']:.3f}{marker}")
    
    connector.disconnect()
    print("\n✓ Analysis complete\n")

if __name__ == "__main__":
    check_nzdjpy_highest_high()

