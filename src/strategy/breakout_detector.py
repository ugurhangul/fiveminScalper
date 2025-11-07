"""
Breakout Detection Service

Provides reusable breakout detection logic to eliminate duplication between
StrategyEngine and MultiRangeStrategyEngine.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple, TYPE_CHECKING
from src.models.data_models import CandleData, UnifiedBreakoutState
from src.constants import LOG_SEPARATOR_CHAR, LOG_SEPARATOR_LENGTH

if TYPE_CHECKING:
    from src.utils.logger import TradingLogger


class BreakoutDetector:
    """
    Service for detecting price breakouts from a defined range.

    This class provides methods to:
    - Detect breakouts above/below a price range
    - Validate breakout conditions (open inside, close outside)
    - Check for breakout timeouts
    - Log breakout events consistently
    """

    def __init__(self, logger: 'TradingLogger', symbol: str):
        """
        Initialize breakout detector.
        
        Args:
            logger: Logger instance for logging breakout events
            symbol: Symbol name for logging context
        """
        self.logger = logger
        self.symbol = symbol
    
    def detect_breakout_above(
        self,
        state: UnifiedBreakoutState,
        candle: CandleData,
        range_high: float,
        range_low: float,
        range_time: datetime,
        range_id: str = "default"
    ) -> bool:
        """
        Detect breakout above the range high.
        
        A valid breakout requires BOTH:
        1. Open INSIDE the range (open >= range_low AND open <= range_high)
        2. Close OUTSIDE the range (close > range_high)
        
        This filters out gap moves where the candle opens outside the range.
        
        Args:
            state: Breakout state to update
            candle: Current candle to check
            range_high: High of the reference range
            range_low: Low of the reference range
            range_time: Time of the reference candle
            range_id: Identifier for the range (for logging)
            
        Returns:
            True if breakout detected, False otherwise
        """
        if state.breakout_above_detected:
            return False
        
        # Validate: Open INSIDE range AND Close ABOVE high
        open_inside_range = candle.open >= range_low and candle.open <= range_high
        close_above_high = candle.close > range_high
        
        if open_inside_range and close_above_high:
            # Update state
            state.breakout_above_detected = True
            state.breakout_above_volume = candle.volume
            state.breakout_above_time = candle.time
            
            # Log breakout event
            self._log_breakout_above(
                candle, range_high, range_low, range_time, range_id
            )
            
            return True
        
        return False
    
    def detect_breakout_below(
        self,
        state: UnifiedBreakoutState,
        candle: CandleData,
        range_high: float,
        range_low: float,
        range_time: datetime,
        range_id: str = "default"
    ) -> bool:
        """
        Detect breakout below the range low.
        
        A valid breakout requires BOTH:
        1. Open INSIDE the range (open >= range_low AND open <= range_high)
        2. Close OUTSIDE the range (close < range_low)
        
        This filters out gap moves where the candle opens outside the range.
        
        Args:
            state: Breakout state to update
            candle: Current candle to check
            range_high: High of the reference range
            range_low: Low of the reference range
            range_time: Time of the reference candle
            range_id: Identifier for the range (for logging)
            
        Returns:
            True if breakout detected, False otherwise
        """
        if state.breakout_below_detected:
            return False
        
        # Validate: Open INSIDE range AND Close BELOW low
        open_inside_range = candle.open >= range_low and candle.open <= range_high
        close_below_low = candle.close < range_low
        
        if open_inside_range and close_below_low:
            # Update state
            state.breakout_below_detected = True
            state.breakout_below_volume = candle.volume
            state.breakout_below_time = candle.time
            
            # Log breakout event
            self._log_breakout_below(
                candle, range_high, range_low, range_time, range_id
            )
            
            return True
        
        return False
    
    def check_breakout_timeout(
        self,
        state: UnifiedBreakoutState,
        current_time: datetime,
        timeout_candles: int,
        minutes_per_candle: int,
        range_id: str = "default"
    ) -> Tuple[bool, bool]:
        """
        Check if existing breakouts have timed out.
        
        Breakouts older than timeout_candles are considered stale and reset
        to prevent trading on old momentum.
        
        Args:
            state: Breakout state to check
            current_time: Current candle time
            timeout_candles: Number of candles before timeout
            minutes_per_candle: Minutes per candle (e.g., 5 for M5, 1 for M1)
            range_id: Identifier for the range (for logging)
            
        Returns:
            Tuple of (above_timed_out, below_timed_out)
        """
        timeout_minutes = timeout_candles * minutes_per_candle
        timeout_delta = timedelta(minutes=timeout_minutes)
        
        above_timed_out = False
        below_timed_out = False
        
        # Check breakout ABOVE timeout
        if state.breakout_above_detected and state.breakout_above_time:
            age = current_time - state.breakout_above_time
            age_minutes = int(age.total_seconds() / 60)
            
            # Log timeout check
            self.logger.info(
                f"[TIMEOUT CHECK ABOVE {range_id}] Age={age_minutes}min, "
                f"Limit={timeout_minutes}min, Breakout={state.breakout_above_time}, "
                f"Current={current_time}",
                self.symbol
            )
            
            # Validate age is positive (handle timezone issues)
            if age.total_seconds() < 0:
                self.logger.warning(
                    f"Negative breakout age detected: {age.total_seconds()}s - "
                    f"possible timezone issue",
                    self.symbol
                )
                self.logger.warning(
                    f"Current time: {current_time}, "
                    f"Breakout time: {state.breakout_above_time}",
                    self.symbol
                )
            elif age > timeout_delta:
                # Timeout occurred
                self._log_timeout_above(
                    age_minutes, timeout_minutes, timeout_candles,
                    state.breakout_above_time, current_time, range_id
                )
                state.reset_breakout_above()
                above_timed_out = True
            else:
                self.logger.info(
                    f"[TIMEOUT CHECK ABOVE {range_id}] Breakout still valid "
                    f"({age_minutes}/{timeout_minutes} min)",
                    self.symbol
                )
        
        # Check breakout BELOW timeout
        if state.breakout_below_detected and state.breakout_below_time:
            age = current_time - state.breakout_below_time
            age_minutes = int(age.total_seconds() / 60)
            
            # Log timeout check
            self.logger.info(
                f"[TIMEOUT CHECK BELOW {range_id}] Age={age_minutes}min, "
                f"Limit={timeout_minutes}min, Breakout={state.breakout_below_time}, "
                f"Current={current_time}",
                self.symbol
            )
            
            # Validate age is positive (handle timezone issues)
            if age.total_seconds() < 0:
                self.logger.warning(
                    f"Negative breakout age detected: {age.total_seconds()}s - "
                    f"possible timezone issue",
                    self.symbol
                )
                self.logger.warning(
                    f"Current time: {current_time}, "
                    f"Breakout time: {state.breakout_below_time}",
                    self.symbol
                )
            elif age > timeout_delta:
                # Timeout occurred
                self._log_timeout_below(
                    age_minutes, timeout_minutes, timeout_candles,
                    state.breakout_below_time, current_time, range_id
                )
                state.reset_breakout_below()
                below_timed_out = True
            else:
                self.logger.info(
                    f"[TIMEOUT CHECK BELOW {range_id}] Breakout still valid "
                    f"({age_minutes}/{timeout_minutes} min)",
                    self.symbol
                )
        
        return above_timed_out, below_timed_out
    
    def _log_breakout_above(
        self,
        candle: CandleData,
        range_high: float,
        range_low: float,
        range_time: datetime,
        range_id: str
    ):
        """Log breakout above event."""
        separator = LOG_SEPARATOR_CHAR * LOG_SEPARATOR_LENGTH
        
        self.logger.info(separator, self.symbol)
        self.logger.info(f">>> BREAKOUT ABOVE HIGH DETECTED [{range_id}] <<<", self.symbol)
        self.logger.info(f"Breakout Open: {candle.open:.5f} (inside range ✓)", self.symbol)
        self.logger.info(f"Breakout Close: {candle.close:.5f} (above high ✓)", self.symbol)
        self.logger.info(f"Range High: {range_high:.5f}", self.symbol)
        self.logger.info(f"Range Low: {range_low:.5f}", self.symbol)
        self.logger.info(f"Range Time: {range_time}", self.symbol)
        self.logger.info(f"Breakout Time: {candle.time}", self.symbol)
        self.logger.info(f"Breakout Volume: {candle.volume}", self.symbol)
        self.logger.info(separator, self.symbol)
    
    def _log_breakout_below(
        self,
        candle: CandleData,
        range_high: float,
        range_low: float,
        range_time: datetime,
        range_id: str
    ):
        """Log breakout below event."""
        separator = LOG_SEPARATOR_CHAR * LOG_SEPARATOR_LENGTH
        
        self.logger.info(separator, self.symbol)
        self.logger.info(f">>> BREAKOUT BELOW LOW DETECTED [{range_id}] <<<", self.symbol)
        self.logger.info(f"Breakout Open: {candle.open:.5f} (inside range ✓)", self.symbol)
        self.logger.info(f"Breakout Close: {candle.close:.5f} (below low ✓)", self.symbol)
        self.logger.info(f"Range High: {range_high:.5f}", self.symbol)
        self.logger.info(f"Range Low: {range_low:.5f}", self.symbol)
        self.logger.info(f"Range Time: {range_time}", self.symbol)
        self.logger.info(f"Breakout Time: {candle.time}", self.symbol)
        self.logger.info(f"Breakout Volume: {candle.volume}", self.symbol)
        self.logger.info(separator, self.symbol)
    
    def _log_timeout_above(
        self,
        age_minutes: int,
        timeout_minutes: int,
        timeout_candles: int,
        breakout_time: datetime,
        current_time: datetime,
        range_id: str
    ):
        """Log breakout above timeout event."""
        separator = LOG_SEPARATOR_CHAR * LOG_SEPARATOR_LENGTH
        
        self.logger.info(separator, self.symbol)
        self.logger.info(f">>> BREAKOUT ABOVE TIMEOUT [{range_id}] - Resetting <<<", self.symbol)
        self.logger.info(
            f"Breakout Age: {age_minutes} minutes ({age_minutes // 60}h {age_minutes % 60}m)",
            self.symbol
        )
        self.logger.info(
            f"Timeout Limit: {timeout_minutes} minutes ({timeout_candles} candles)",
            self.symbol
        )
        self.logger.info(f"Breakout Time: {breakout_time}", self.symbol)
        self.logger.info(f"Current Time: {current_time}", self.symbol)
        self.logger.info("Reason: Breakout too old, momentum lost", self.symbol)
        self.logger.info(separator, self.symbol)
    
    def _log_timeout_below(
        self,
        age_minutes: int,
        timeout_minutes: int,
        timeout_candles: int,
        breakout_time: datetime,
        current_time: datetime,
        range_id: str
    ):
        """Log breakout below timeout event."""
        separator = LOG_SEPARATOR_CHAR * LOG_SEPARATOR_LENGTH
        
        self.logger.info(separator, self.symbol)
        self.logger.info(f">>> BREAKOUT BELOW TIMEOUT [{range_id}] - Resetting <<<", self.symbol)
        self.logger.info(
            f"Breakout Age: {age_minutes} minutes ({age_minutes // 60}h {age_minutes % 60}m)",
            self.symbol
        )
        self.logger.info(
            f"Timeout Limit: {timeout_minutes} minutes ({timeout_candles} candles)",
            self.symbol
        )
        self.logger.info(f"Breakout Time: {breakout_time}", self.symbol)
        self.logger.info(f"Current Time: {current_time}", self.symbol)
        self.logger.info("Reason: Breakout too old, momentum lost", self.symbol)
        self.logger.info(separator, self.symbol)

