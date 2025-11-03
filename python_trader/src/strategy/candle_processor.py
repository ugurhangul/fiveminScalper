"""
Candle processing and detection logic.
Ported from FMS_CandleProcessing.mqh
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import pandas as pd
from src.models.data_models import CandleData, FourHourCandle
from src.core.mt5_connector import MT5Connector
from src.utils.logger import get_logger


class CandleProcessor:
    """Processes and detects 4H and 5M candles"""
    
    def __init__(self, symbol: str, connector: MT5Connector, use_only_00_utc: bool = True):
        """
        Initialize candle processor.

        Args:
            symbol: Symbol name
            connector: MT5 connector instance
            use_only_00_utc: If True, only use second 4H candle (04:00-08:00 UTC)
        """
        self.symbol = symbol
        self.connector = connector
        self.use_only_00_utc = use_only_00_utc
        self.logger = get_logger()

        # Track last processed candles
        self.last_4h_candle_time: Optional[datetime] = None
        self.last_5m_candle_time: Optional[datetime] = None

        # Current 4H candle
        self.current_4h_candle: Optional[FourHourCandle] = None

        # Initialize with existing 4H candle on startup
        self._initialize_4h_candle()
    
    def is_new_4h_candle(self) -> bool:
        """
        Check if a new 4H candle has formed.
        
        Returns:
            True if new 4H candle detected
        """
        # Get latest 4H candle
        df = self.connector.get_candles(self.symbol, 'H4', count=2)
        if df is None or len(df) < 2:
            return False
        
        # Get the last closed 4H candle
        last_candle = df.iloc[-2]
        candle_time = last_candle['time']
        
        # Check if this is a new candle
        if self.last_4h_candle_time is None or candle_time > self.last_4h_candle_time:
            # If using only second 4H candle, verify it's the correct candle of the day
            if self.use_only_00_utc:
                # The second 4H candle opens at 04:00 UTC and closes at 08:00 UTC
                # Chart displays opening time (04:00 UTC)
                # This matches the MQL5 code which checks for hour == 4
                if candle_time.hour == 4 and candle_time.minute == 0:
                    self.last_4h_candle_time = candle_time
                    self._update_4h_candle(last_candle)

                    self.logger.info("=" * 60, self.symbol)
                    self.logger.info("*** NEW 4H CANDLE DETECTED (04:00 UTC) ***", self.symbol)
                    self.logger.info(f"Time: {candle_time} (opens 04:00, closes 08:00 UTC)", self.symbol)
                    self.logger.info(f"High: {last_candle['high']:.5f}", self.symbol)
                    self.logger.info(f"Low: {last_candle['low']:.5f}", self.symbol)
                    self.logger.info(f"Range: {self.current_4h_candle.range:.5f} points", self.symbol)
                    self.logger.info("=" * 60, self.symbol)

                    return True
            else:
                # Use any 4H candle
                self.last_4h_candle_time = candle_time
                self._update_4h_candle(last_candle)
                
                self.logger.info("=" * 60, self.symbol)
                self.logger.info("*** NEW 4H CANDLE DETECTED ***", self.symbol)
                self.logger.info(f"Time: {candle_time}", self.symbol)
                self.logger.info(f"High: {last_candle['high']:.5f}", self.symbol)
                self.logger.info(f"Low: {last_candle['low']:.5f}", self.symbol)
                self.logger.info(f"Range: {self.current_4h_candle.range:.5f} points", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                
                return True
        
        return False
    
    def is_new_5m_candle(self) -> bool:
        """
        Check if a new 5M candle has formed.
        
        Returns:
            True if new 5M candle detected
        """
        # Get latest 5M candle
        df = self.connector.get_candles(self.symbol, 'M5', count=2)
        if df is None or len(df) < 2:
            return False
        
        # Get the last closed 5M candle
        last_candle = df.iloc[-2]
        candle_time = last_candle['time']
        
        # Check if this is a new candle
        if self.last_5m_candle_time is None or candle_time > self.last_5m_candle_time:
            self.last_5m_candle_time = candle_time
            
            self.logger.debug(f"New 5M candle at {candle_time}", self.symbol)
            
            return True
        
        return False
    
    def get_latest_5m_candle(self) -> Optional[CandleData]:
        """
        Get the latest closed 5M candle.
        
        Returns:
            CandleData object or None
        """
        return self.connector.get_latest_candle(self.symbol, 'M5')
    
    def get_5m_candles(self, count: int = 100) -> Optional[pd.DataFrame]:
        """
        Get historical 5M candles.
        
        Args:
            count: Number of candles to retrieve
            
        Returns:
            DataFrame with candle data or None
        """
        return self.connector.get_candles(self.symbol, 'M5', count=count)
    
    def get_current_4h_candle(self) -> Optional[FourHourCandle]:
        """
        Get the current 4H candle being tracked.
        
        Returns:
            FourHourCandle object or None
        """
        return self.current_4h_candle
    
    def has_4h_candle(self) -> bool:
        """
        Check if we have a valid 4H candle to trade from.
        
        Returns:
            True if 4H candle is available
        """
        return self.current_4h_candle is not None
    
    def _initialize_4h_candle(self):
        """
        Initialize with the most recent valid 4H candle on startup.
        Searches backwards up to 24 hours (6 x 4H candles) for the second 4H candle of the day.
        NOTE: We look for the candle that opens at 04:00 UTC (chart shows 04:00, closes at 08:00 UTC).
        """
        # Get recent 4H candles
        df = self.connector.get_candles(self.symbol, 'H4', count=7)
        if df is None or len(df) < 2:
            self.logger.warning("Could not retrieve 4H candles for initialization", self.symbol)
            return

        # Search backwards for the most recent valid candle
        # Skip index 0 (current forming candle), start from index 1 (last closed)
        for i in range(1, min(7, len(df))):
            candle = df.iloc[-(i+1)]  # Get candle from end, skipping current
            candle_time = candle['time']

            if self.use_only_00_utc:
                # Check if this is the second 4H candle (opens 04:00, closes 08:00)
                # Chart shows opening time (04:00 UTC)
                # This matches the MQL5 code which checks for hour == 4
                if candle_time.hour == 4 and candle_time.minute == 0:
                    self.last_4h_candle_time = candle_time
                    self._update_4h_candle(candle)

                    self.logger.info("=" * 60, self.symbol)
                    self.logger.info("*** INITIALIZED WITH 04:00 UTC 4H CANDLE ***", self.symbol)
                    self.logger.info(f"Time: {candle_time}", self.symbol)
                    self.logger.info(f"High: {candle['high']:.5f}", self.symbol)
                    self.logger.info(f"Low: {candle['low']:.5f}", self.symbol)
                    self.logger.info(f"Range: {self.current_4h_candle.range:.5f} points", self.symbol)
                    self.logger.info("=" * 60, self.symbol)
                    return
            else:
                # Use the most recent closed candle
                self.last_4h_candle_time = candle_time
                self._update_4h_candle(candle)

                self.logger.info("=" * 60, self.symbol)
                self.logger.info("*** INITIALIZED WITH 4H CANDLE ***", self.symbol)
                self.logger.info(f"Time: {candle_time}", self.symbol)
                self.logger.info(f"High: {candle['high']:.5f}", self.symbol)
                self.logger.info(f"Low: {candle['low']:.5f}", self.symbol)
                self.logger.info(f"Range: {self.current_4h_candle.range:.5f} points", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                return

        # If we get here and use_only_00_utc is True, we didn't find a valid candle
        if self.use_only_00_utc:
            self.logger.warning(
                "No second 4H candle (04:00 UTC) found in last 24 hours - waiting for next one",
                self.symbol
            )

    def _update_4h_candle(self, candle_data):
        """
        Update the current 4H candle.

        Args:
            candle_data: Pandas Series with candle data
        """
        self.current_4h_candle = FourHourCandle(
            time=candle_data['time'],
            open=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close']
        )
    
    def reset_4h_candle(self):
        """Reset the 4H candle (e.g., after a trade or at end of day)"""
        self.current_4h_candle = None
        self.logger.info("4H candle reset", self.symbol)
    
    def is_midnight_crossing(self) -> bool:
        """
        Check if we've crossed midnight UTC (new trading day).

        Returns:
            True if midnight has been crossed
        """
        current_time = datetime.now(timezone.utc)

        # Check if it's within the first 5 minutes of a new day
        if current_time.hour == 0 and current_time.minute < 5:
            return True

        return False

    def is_in_candle_formation_period(self) -> bool:
        """
        Check if we're in the restricted trading period (04:00-08:00 UTC).
        Trading is suspended while the second 4H candle of the day is forming.

        Returns:
            True if in restricted period (04:00-08:00 UTC)
        """
        current_time = datetime.now(timezone.utc)
        return current_time.hour >= 4 and current_time.hour < 8
    
    def get_time_until_next_4h_candle(self) -> Optional[timedelta]:
        """
        Calculate time until the next 4H candle.

        Returns:
            Timedelta until next 4H candle or None
        """
        if not self.use_only_00_utc:
            # Next 4H candle is at 00:00, 04:00, 08:00, 12:00, 16:00, or 20:00
            current_time = datetime.now(timezone.utc)
            current_hour = current_time.hour

            # Find next 4H boundary
            next_hour = ((current_hour // 4) + 1) * 4
            if next_hour >= 24:
                next_hour = 0
                next_day = current_time + timedelta(days=1)
                next_candle_time = next_day.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            else:
                next_candle_time = current_time.replace(hour=next_hour, minute=0, second=0, microsecond=0)

            return next_candle_time - current_time
        else:
            # Next candle is at 00:00 UTC tomorrow
            current_time = datetime.now(timezone.utc)
            tomorrow = current_time + timedelta(days=1)
            next_candle_time = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

            return next_candle_time - current_time
    
    def log_candle_status(self):
        """Log current candle status"""
        self.logger.info("=== Candle Status ===", self.symbol)
        
        if self.current_4h_candle:
            self.logger.info(f"4H Candle Time: {self.current_4h_candle.time}", self.symbol)
            self.logger.info(f"4H High: {self.current_4h_candle.high:.5f}", self.symbol)
            self.logger.info(f"4H Low: {self.current_4h_candle.low:.5f}", self.symbol)
            self.logger.info(f"4H Range: {self.current_4h_candle.range:.5f}", self.symbol)
        else:
            self.logger.info("No 4H candle available", self.symbol)
        
        if self.last_5m_candle_time:
            self.logger.info(f"Last 5M Candle: {self.last_5m_candle_time}", self.symbol)
        
        time_until_next = self.get_time_until_next_4h_candle()
        if time_until_next:
            hours = int(time_until_next.total_seconds() // 3600)
            minutes = int((time_until_next.total_seconds() % 3600) // 60)
            self.logger.info(f"Time until next 4H candle: {hours}h {minutes}m", self.symbol)
        
        self.logger.separator()

