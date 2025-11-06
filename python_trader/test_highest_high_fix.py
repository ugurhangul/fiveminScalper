"""
Test script to verify the highest_high / lowest_low fix.
This simulates what should happen for position 277307678.
"""
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os
from datetime import datetime, time as dt_time
import pandas as pd

from src.core.mt5_connector import MT5Connector
from src.config.config import MT5Config, RangeConfig
from src.strategy.multi_range_candle_processor import MultiRangeCandleProcessor
from src.strategy.multi_range_strategy_engine import MultiRangeStrategyEngine
from src.indicators.technical_indicators import TechnicalIndicators
from src.config.config import StrategyConfig, SymbolParameters

# Load environment
load_dotenv()

def test_highest_high_calculation():
    """Test that highest_high is calculated correctly"""
    
    print("\n" + "="*70)
    print("TEST: Highest High Calculation Fix")
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
    
    # Test symbol
    symbol = "XZNUSDr"
    
    # Define range configurations
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
    print("Initializing candle processor...")
    processor = MultiRangeCandleProcessor(
        symbol=symbol,
        connector=connector,
        range_configs=ranges
    )
    print("✓ Processor initialized\n")
    
    # Create strategy engine
    print("Initializing strategy engine...")
    indicators = TechnicalIndicators()
    strategy_config = StrategyConfig()
    symbol_params = SymbolParameters()
    
    engine = MultiRangeStrategyEngine(
        symbol=symbol,
        candle_processor=processor,
        indicators=indicators,
        strategy_config=strategy_config,
        symbol_params=symbol_params,
        connector=connector
    )
    print("✓ Engine initialized\n")
    
    # Get last 10 M5 candles
    print("="*70)
    print("FETCHING LAST 10 M5 CANDLES")
    print("="*70 + "\n")
    
    df = processor.get_breakout_candles("4H_5M", count=10)
    if df is None or len(df) == 0:
        print("Failed to get M5 candles")
        connector.disconnect()
        return
    
    print(f"Retrieved {len(df)} M5 candles:\n")
    print(df[['time', 'open', 'high', 'low', 'close']].to_string())
    
    # Calculate highest high
    print("\n" + "="*70)
    print("CALCULATING HIGHEST HIGH")
    print("="*70 + "\n")
    
    highest_high = df['high'].max()
    print(f"Highest High (using df['high'].max()): {highest_high:.2f}")
    
    # Test the engine's method
    reference_high = 3069.71  # The 4H high from the logs
    result = engine._find_highest_high_in_pattern("4H_5M", reference_high)
    
    print(f"\nEngine's _find_highest_high_in_pattern() result: {result:.2f}")
    print(f"Reference High (4H high): {reference_high:.2f}")
    
    # Verify
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70 + "\n")
    
    if result is not None:
        print(f"✓ Function returned a value: {result:.2f}")
        print(f"✓ Matches df['high'].max(): {result == highest_high}")
        
        # Expected for position 277307678
        expected_hh = 3059.96
        print(f"\nExpected HH for position 277307678: {expected_hh:.2f}")
        print(f"Actual HH from current data: {result:.2f}")
        
        if abs(result - expected_hh) < 1.0:
            print("✓ Result is close to expected value (within 1.0)")
        else:
            print(f"⚠ Result differs from expected by {abs(result - expected_hh):.2f}")
            print("  (This is OK if market has moved since the position was opened)")
    else:
        print("✗ Function returned None - this is the bug!")
    
    # Cleanup
    connector.disconnect()
    print("\n✓ Test complete\n")

if __name__ == "__main__":
    test_highest_high_calculation()

