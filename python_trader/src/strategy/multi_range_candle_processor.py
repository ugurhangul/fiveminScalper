"""
Multi-range candle processing and detection logic.
Supports multiple independent range configurations operating simultaneously.
"""
from datetime import datetime, timedelta, timezone, time as dt_time
from typing import Optional, Dict, List
import pandas as pd
from src.models.data_models import CandleData, ReferenceCandle, RangeConfig
from src.core.mt5_connector import MT5Connector
from src.utils.logger import get_logger


class MultiRangeCandleProcessor:
    """
    Processes and detects candles for multiple range configurations.
    
    Each range configuration can have:
    - Different reference timeframes (e.g., 4H, 15M)
    - Different reference times (e.g., 04:00, 04:30)
    - Different breakout timeframes (e.g., 5M, 1M)
    """
    
    def __init__(self, symbol: str, connector: MT5Connector, range_configs: List[RangeConfig]):
        """
        Initialize multi-range candle processor.

        Args:
            symbol: Symbol name
            connector: MT5 connector instance
            range_configs: List of range configurations to track
        """
        self.symbol = symbol
        self.connector = connector
        self.range_configs = {config.range_id: config for config in range_configs}
        self.logger = get_logger()

        # Track last processed candles per range configuration
        # Format: {range_id: {timeframe: last_candle_time}}
        self.last_candle_times: Dict[str, Dict[str, Optional[datetime]]] = {}
        
        # Current reference candles per range configuration
        # Format: {range_id: ReferenceCandle}
        self.current_reference_candles: Dict[str, Optional[ReferenceCandle]] = {}
        
        # Initialize tracking for each range
        for range_id in self.range_configs:
            self.last_candle_times[range_id] = {
                'reference': None,
                'breakout': None
            }
            self.current_reference_candles[range_id] = None
        
        # Initialize all ranges
        self._initialize_all_ranges()
    
    def is_new_reference_candle(self, range_id: str) -> bool:
        """
        Check if a new reference candle has formed for a specific range.
        
        Args:
            range_id: Range configuration identifier
            
        Returns:
            True if new reference candle detected
        """
        if range_id not in self.range_configs:
            return False
        
        config = self.range_configs[range_id]
        
        # Get latest reference candle
        df = self.connector.get_candles(self.symbol, config.reference_timeframe, count=2)
        if df is None or len(df) < 2:
            return False
        
        # Get the last closed candle
        last_candle = df.iloc[-2]
        candle_time = last_candle['time']
        
        # Check if this is a new candle
        last_time = self.last_candle_times[range_id]['reference']
        if last_time is None or candle_time > last_time:
            # If using specific time, verify it matches
            if config.use_specific_time and config.reference_time:
                if candle_time.hour == config.reference_time.hour and candle_time.minute == config.reference_time.minute:
                    self.last_candle_times[range_id]['reference'] = candle_time
                    self._update_reference_candle(range_id, last_candle, config.reference_timeframe)
                    
                    self.logger.info("=" * 60, self.symbol)
                    self.logger.info(f"*** NEW REFERENCE CANDLE DETECTED [{config}] ***", self.symbol)
                    self.logger.info(f"Time: {candle_time}", self.symbol)
                    self.logger.info(f"High: {last_candle['high']:.5f}", self.symbol)
                    self.logger.info(f"Low: {last_candle['low']:.5f}", self.symbol)
                    self.logger.info(f"Range: {self.current_reference_candles[range_id].range:.5f} points", self.symbol)
                    self.logger.info("=" * 60, self.symbol)
                    
                    return True
            else:
                # Use any candle of this timeframe
                self.last_candle_times[range_id]['reference'] = candle_time
                self._update_reference_candle(range_id, last_candle, config.reference_timeframe)
                
                self.logger.info("=" * 60, self.symbol)
                self.logger.info(f"*** NEW REFERENCE CANDLE DETECTED [{config}] ***", self.symbol)
                self.logger.info(f"Time: {candle_time}", self.symbol)
                self.logger.info(f"High: {last_candle['high']:.5f}", self.symbol)
                self.logger.info(f"Low: {last_candle['low']:.5f}", self.symbol)
                self.logger.info(f"Range: {self.current_reference_candles[range_id].range:.5f} points", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                
                return True
        
        return False
    
    def is_new_breakout_candle(self, range_id: str) -> bool:
        """
        Check if a new breakout candle has formed for a specific range.
        
        Args:
            range_id: Range configuration identifier
            
        Returns:
            True if new breakout candle detected
        """
        if range_id not in self.range_configs:
            return False
        
        config = self.range_configs[range_id]
        
        # Get latest breakout candle
        df = self.connector.get_candles(self.symbol, config.breakout_timeframe, count=2)
        if df is None or len(df) < 2:
            return False
        
        # Get the last closed candle
        last_candle = df.iloc[-2]
        candle_time = last_candle['time']
        
        # Check if this is a new candle
        last_time = self.last_candle_times[range_id]['breakout']
        if last_time is None or candle_time > last_time:
            self.last_candle_times[range_id]['breakout'] = candle_time
            
            self.logger.debug(f"New breakout candle for {config} at {candle_time}", self.symbol)
            
            return True
        
        return False
    
    def get_latest_breakout_candle(self, range_id: str) -> Optional[CandleData]:
        """
        Get the latest closed breakout candle for a specific range.
        
        Args:
            range_id: Range configuration identifier
            
        Returns:
            CandleData object or None
        """
        if range_id not in self.range_configs:
            return None
        
        config = self.range_configs[range_id]
        return self.connector.get_latest_candle(self.symbol, config.breakout_timeframe)
    
    def get_breakout_candles(self, range_id: str, count: int = 100) -> Optional[pd.DataFrame]:
        """
        Get historical breakout candles for a specific range.
        
        Args:
            range_id: Range configuration identifier
            count: Number of candles to retrieve
            
        Returns:
            DataFrame with candle data or None
        """
        if range_id not in self.range_configs:
            return None
        
        config = self.range_configs[range_id]
        return self.connector.get_candles(self.symbol, config.breakout_timeframe, count=count)
    
    def get_current_reference_candle(self, range_id: str) -> Optional[ReferenceCandle]:
        """
        Get the current reference candle being tracked for a specific range.

        Args:
            range_id: Range configuration identifier

        Returns:
            ReferenceCandle object or None
        """
        return self.current_reference_candles.get(range_id)
    
    def has_reference_candle(self, range_id: str) -> bool:
        """
        Check if we have a valid reference candle for a specific range.

        Args:
            range_id: Range configuration identifier

        Returns:
            True if reference candle is available
        """
        return self.current_reference_candles.get(range_id) is not None

    def get_all_range_ids(self) -> List[str]:
        """
        Get all configured range IDs.

        Returns:
            List of range identifiers
        """
        return list(self.range_configs.keys())
    
    def _initialize_all_ranges(self):
        """Initialize all range configurations on startup."""
        for range_id, config in self.range_configs.items():
            self._initialize_reference_candle(range_id, config)
            self._initialize_breakout_candle(range_id, config)
    
    def _initialize_reference_candle(self, range_id: str, config: RangeConfig):
        """
        Initialize with the most recent valid reference candle for a specific range.

        Args:
            range_id: Range configuration identifier
            config: Range configuration
        """
        # Calculate lookback count based on timeframe to cover at least 24 hours
        # For H4: 24 hours / 4 hours = 6 candles, use 10 for safety
        # For M15: 24 hours / 15 minutes = 96 candles, use 100 for safety
        if config.reference_timeframe.startswith('H'):
            hours = int(config.reference_timeframe[1:])
            lookback_count = max(10, int(24 / hours) + 5)
        elif config.reference_timeframe.startswith('M'):
            minutes = int(config.reference_timeframe[1:])
            lookback_count = max(100, int((24 * 60) / minutes) + 10)
        else:
            lookback_count = 100  # Default

        # Get recent reference candles
        df = self.connector.get_candles(self.symbol, config.reference_timeframe, count=lookback_count)
        if df is None or len(df) < 2:
            self.logger.warning(f"Could not retrieve {config.reference_timeframe} candles for initialization [{config}]", self.symbol)
            return

        # Search backwards for the most recent valid candle
        for i in range(1, min(lookback_count, len(df))):
            candle = df.iloc[-(i+1)]  # Get candle from end, skipping current
            candle_time = candle['time']

            if config.use_specific_time and config.reference_time:
                # Check if this matches the specific time
                if candle_time.hour == config.reference_time.hour and candle_time.minute == config.reference_time.minute:
                    self.last_candle_times[range_id]['reference'] = candle_time
                    self._update_reference_candle(range_id, candle, config.reference_timeframe)

                    self.logger.info("=" * 60, self.symbol)
                    self.logger.info(f"*** INITIALIZED WITH REFERENCE CANDLE [{config}] ***", self.symbol)
                    self.logger.info(f"Time: {candle_time}", self.symbol)
                    self.logger.info(f"High: {candle['high']:.5f}", self.symbol)
                    self.logger.info(f"Low: {candle['low']:.5f}", self.symbol)
                    self.logger.info(f"Range: {self.current_reference_candles[range_id].range:.5f} points", self.symbol)
                    self.logger.info("=" * 60, self.symbol)
                    return
            else:
                # Use the most recent closed candle
                self.last_candle_times[range_id]['reference'] = candle_time
                self._update_reference_candle(range_id, candle, config.reference_timeframe)

                self.logger.info("=" * 60, self.symbol)
                self.logger.info(f"*** INITIALIZED WITH REFERENCE CANDLE [{config}] ***", self.symbol)
                self.logger.info(f"Time: {candle_time}", self.symbol)
                self.logger.info(f"High: {candle['high']:.5f}", self.symbol)
                self.logger.info(f"Low: {candle['low']:.5f}", self.symbol)
                self.logger.info(f"Range: {self.current_reference_candles[range_id].range:.5f} points", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                return

        # If we get here and use_specific_time is True, we didn't find a valid candle
        if config.use_specific_time:
            self.logger.warning(
                f"No reference candle found for {config} in last {lookback_count} candles - waiting for next one",
                self.symbol
            )
    
    def _initialize_breakout_candle(self, range_id: str, config: RangeConfig):
        """
        Initialize breakout candle tracking on startup for a specific range.

        Args:
            range_id: Range configuration identifier
            config: Range configuration
        """
        # Get latest breakout candle
        df = self.connector.get_candles(self.symbol, config.breakout_timeframe, count=2)
        if df is None or len(df) < 2:
            self.logger.warning(f"Could not retrieve {config.breakout_timeframe} candles for initialization [{config}]", self.symbol)
            return

        # Get the last closed candle
        last_candle = df.iloc[-2]
        candle_time = last_candle['time']

        # Set as last processed to skip it
        self.last_candle_times[range_id]['breakout'] = candle_time

        self.logger.info(f"Breakout candle tracking initialized for {config} at {candle_time}", self.symbol)
        self.logger.info("Will only process NEW candles that form after this time", self.symbol)
    
    def _update_reference_candle(self, range_id: str, candle_data, timeframe: str):
        """
        Update the current reference candle for a specific range.

        Args:
            range_id: Range configuration identifier
            candle_data: Pandas Series with candle data
            timeframe: Timeframe string (e.g., "H4", "M15")
        """
        self.current_reference_candles[range_id] = ReferenceCandle(
            time=candle_data['time'],
            open=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close'],
            timeframe=timeframe
        )
    
    def reset_reference_candle(self, range_id: str):
        """
        Reset the reference candle for a specific range.
        
        Args:
            range_id: Range configuration identifier
        """
        if range_id in self.current_reference_candles:
            self.current_reference_candles[range_id] = None
            self.logger.info(f"Reference candle reset for {self.range_configs[range_id]}", self.symbol)
    
    def get_all_range_ids(self) -> List[str]:
        """Get list of all range configuration IDs."""
        return list(self.range_configs.keys())

