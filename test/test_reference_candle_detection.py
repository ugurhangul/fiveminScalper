#!/usr/bin/env python3
"""
Diagnostic script to test reference candle detection.
Helps verify that reference candles are being found correctly.
"""
from datetime import datetime, timezone, time as dt_time
from src.models.data_models import RangeConfig
from src.core.mt5_connector import MT5Connector
from src.config.config import config
from src.strategy.multi_range_candle_processor import MultiRangeCandleProcessor
from src.utils.logger import get_logger

def test_reference_candle_detection():
    """Test that reference candles can be found for both ranges"""
    print("\n" + "=" * 70)
    print("REFERENCE CANDLE DETECTION DIAGNOSTIC")
    print("=" * 70 + "\n")
    
    # Initialize MT5 connection
    print("Connecting to MT5...")
    connector = MT5Connector(config.mt5)
    if not connector.connect():
        print("❌ Failed to connect to MT5")
        return False
    print("✓ Connected to MT5\n")
    
    # Get a test symbol from market watch
    symbols = connector.get_market_watch_symbols()
    if not symbols:
        print("❌ No symbols in market watch")
        connector.shutdown()
        return False
    
    test_symbol = symbols[0]
    print(f"Testing with symbol: {test_symbol}\n")
    
    # Define range configurations
    ranges = [
        RangeConfig(
            range_id="4H_5M",
            reference_timeframe="H4",
            reference_time=dt_time(4, 0),
            breakout_timeframe="M5",
            use_specific_time=True
        ),
        RangeConfig(
            range_id="15M_1M",
            reference_timeframe="M15",
            reference_time=dt_time(4, 30),
            breakout_timeframe="M1",
            use_specific_time=True
        )
    ]
    
    # Create candle processor
    print("Initializing multi-range candle processor...")
    processor = MultiRangeCandleProcessor(
        symbol=test_symbol,
        connector=connector,
        range_configs=ranges
    )
    print("✓ Processor initialized\n")
    
    # Check each range
    print("=" * 70)
    print("CHECKING RANGE CONFIGURATIONS")
    print("=" * 70 + "\n")
    
    for range_config in ranges:
        range_id = range_config.range_id
        print(f"Range: {range_config}")
        print("-" * 70)
        
        # Check if reference candle exists
        has_candle = processor.has_reference_candle(range_id)
        print(f"Has reference candle: {has_candle}")
        
        if has_candle:
            ref_candle = processor.get_current_reference_candle(range_id)
            if ref_candle:
                print(f"✓ Reference candle found:")
                print(f"  Time: {ref_candle.time}")
                print(f"  High: {ref_candle.high:.5f}")
                print(f"  Low: {ref_candle.low:.5f}")
                print(f"  Range: {ref_candle.range:.5f} points")
                print(f"  Timeframe: {ref_candle.timeframe}")
            else:
                print("❌ Reference candle is None (unexpected)")
        else:
            print(f"❌ No reference candle found for {range_id}")
            print(f"   This means no {range_config.reference_timeframe} candle at {range_config.reference_time.strftime('%H:%M')} UTC was found in the lookback period")
            
            # Show what candles are available
            print(f"\n   Checking available {range_config.reference_timeframe} candles:")
            df = connector.get_candles(test_symbol, range_config.reference_timeframe, count=10)
            if df is not None and len(df) > 0:
                print(f"   Last 10 {range_config.reference_timeframe} candles:")
                for i in range(min(10, len(df))):
                    candle = df.iloc[-(i+1)]
                    candle_time = candle['time']
                    print(f"     {i+1}. {candle_time} (Hour: {candle_time.hour:02d}, Minute: {candle_time.minute:02d})")
            else:
                print(f"   ❌ Could not retrieve {range_config.reference_timeframe} candles")
        
        print()
    
    # Cleanup
    connector.disconnect()
    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    try:
        test_reference_candle_detection()
    except Exception as e:
        print(f"\n❌ Error during diagnostic: {e}")
        import traceback
        traceback.print_exc()

