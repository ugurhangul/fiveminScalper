"""
Technical indicators and analysis.
Ported from FMS_Indicators.mqh
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple
import talib
from src.utils.logger import get_logger


class TechnicalIndicators:
    """Technical indicator calculations"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def calculate_average_volume(self, volumes: pd.Series, period: int) -> float:
        """
        Calculate average volume over a period.
        
        Args:
            volumes: Series of volume data
            period: Period for average
            
        Returns:
            Average volume
        """
        if len(volumes) < period:
            self.logger.warning(f"Not enough data for volume average: {len(volumes)} < {period}")
            return 0.0
        
        avg_volume = volumes.tail(period).mean()
        
        self.logger.debug(f"Volume Analysis:")
        self.logger.debug(f"  Period: {period} candles")
        self.logger.debug(f"  Average volume: {avg_volume:.0f}")
        
        return avg_volume
    
    def is_breakout_volume_low(self, breakout_volume: int, average_volume: float,
                               max_threshold: float, symbol: str) -> bool:
        """
        Check if breakout volume is LOW (weak breakout = good for false breakout).
        
        Args:
            breakout_volume: Volume of breakout candle
            average_volume: Average volume
            max_threshold: Maximum threshold multiplier
            symbol: Symbol name for logging
            
        Returns:
            True if volume is low, False otherwise
        """
        if average_volume <= 0:
            self.logger.warning("Average volume is zero or negative", symbol)
            return False
        
        volume_ratio = breakout_volume / average_volume
        is_low = volume_ratio <= max_threshold
        
        self.logger.info("=== Breakout Volume Check (Want LOW Volume) ===", symbol)
        self.logger.info(f"Breakout Volume: {breakout_volume}", symbol)
        self.logger.info(f"Average Volume: {average_volume:.0f}", symbol)
        self.logger.info(f"Volume Ratio: {volume_ratio:.2f}x", symbol)
        self.logger.info(f"Max Threshold: {max_threshold:.2f}x", symbol)
        self.logger.info(f"Volume is LOW: {'YES' if is_low else 'NO'}", symbol)
        
        if not is_low:
            self.logger.info(">>> VOLUME TOO HIGH - Strong breakout, likely to continue <<<", symbol)
            self.logger.info(">>> Not ideal for false breakout strategy - skipping <<<", symbol)
        else:
            self.logger.info(">>> VOLUME IS LOW - Weak breakout, likely to reverse <<<", symbol)
            self.logger.info(">>> Good candidate for false breakout - proceeding <<<", symbol)
        
        return is_low
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series,
                     period: int = 14) -> Optional[float]:
        """
        Calculate Average True Range (ATR).

        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            period: Period for ATR calculation (default: 14)

        Returns:
            Current ATR value or None if insufficient data
        """
        if len(high) < period + 1 or len(low) < period + 1 or len(close) < period + 1:
            self.logger.warning(f"Not enough data for ATR calculation: need {period + 1}, have {len(close)}")
            return None

        try:
            # Calculate ATR using talib
            atr_values = talib.ATR(high.values, low.values, close.values, timeperiod=period)

            # Get the most recent ATR value
            current_atr = atr_values[-1]

            if np.isnan(current_atr):
                self.logger.warning("ATR calculation returned NaN")
                return None

            self.logger.debug(f"ATR({period}): {current_atr:.5f}")

            return float(current_atr)

        except Exception as e:
            self.logger.error(f"Error calculating ATR: {e}")
            return None

    def is_reversal_volume_high(self, reversal_volume: int, average_volume: float,
                                min_threshold: float, symbol: str) -> bool:
        """
        Check if reversal volume is HIGH (strong reversal = good confirmation).

        Args:
            reversal_volume: Volume of reversal candle
            average_volume: Average volume
            min_threshold: Minimum threshold multiplier
            symbol: Symbol name for logging

        Returns:
            True if volume is high, False otherwise
        """
        if average_volume <= 0:
            self.logger.warning("Average volume is zero or negative", symbol)
            return False

        volume_ratio = reversal_volume / average_volume
        is_high = volume_ratio >= min_threshold

        self.logger.info("=== Reversal Volume Check (Want HIGH Volume) ===", symbol)
        self.logger.info(f"Reversal Volume: {reversal_volume}", symbol)
        self.logger.info(f"Average Volume: {average_volume:.0f}", symbol)
        self.logger.info(f"Volume Ratio: {volume_ratio:.2f}x", symbol)
        self.logger.info(f"Min Threshold: {min_threshold:.2f}x", symbol)
        self.logger.info(f"Volume is HIGH: {'YES' if is_high else 'NO'}", symbol)

        if not is_high:
            self.logger.info(">>> VOLUME TOO LOW - Weak reversal, lacks conviction <<<", symbol)
            self.logger.info(">>> May not be a strong false breakout - skipping <<<", symbol)
        else:
            self.logger.info(">>> VOLUME IS HIGH - Strong reversal confirmation <<<", symbol)
            self.logger.info(">>> Excellent false breakout signal - proceeding <<<", symbol)

        return is_high

    def is_true_breakout_volume_high(self, breakout_volume: int, average_volume: float,
                                     min_threshold: float, symbol: str) -> bool:
        """
        Check if breakout volume is HIGH (strong breakout = good for true breakout).

        Args:
            breakout_volume: Volume of breakout candle
            average_volume: Average volume
            min_threshold: Minimum threshold multiplier
            symbol: Symbol name for logging

        Returns:
            True if volume is high, False otherwise
        """
        if average_volume <= 0:
            self.logger.warning("Average volume is zero or negative", symbol)
            return False

        volume_ratio = breakout_volume / average_volume
        is_high = volume_ratio >= min_threshold

        self.logger.info("=== TRUE Breakout Volume Check (Want HIGH Volume) ===", symbol)
        self.logger.info(f"Breakout Volume: {breakout_volume}", symbol)
        self.logger.info(f"Average Volume: {average_volume:.0f}", symbol)
        self.logger.info(f"Volume Ratio: {volume_ratio:.2f}x", symbol)
        self.logger.info(f"Min Threshold: {min_threshold:.2f}x", symbol)
        self.logger.info(f"Volume is HIGH: {'YES' if is_high else 'NO'}", symbol)

        if not is_high:
            self.logger.info(">>> VOLUME TOO LOW - Weak breakout, may fail <<<", symbol)
            self.logger.info(">>> Not ideal for true breakout strategy - skipping <<<", symbol)
        else:
            self.logger.info(">>> VOLUME IS HIGH - Strong breakout, likely to continue <<<", symbol)
            self.logger.info(">>> Good candidate for true breakout - proceeding <<<", symbol)

        return is_high

    def is_continuation_volume_high(self, continuation_volume: int, average_volume: float,
                                   min_threshold: float, symbol: str) -> bool:
        """
        Check if continuation volume is HIGH (strong continuation = good confirmation).

        Args:
            continuation_volume: Volume of continuation candle
            average_volume: Average volume
            min_threshold: Minimum threshold multiplier
            symbol: Symbol name for logging

        Returns:
            True if volume is high, False otherwise
        """
        if average_volume <= 0:
            self.logger.warning("Average volume is zero or negative", symbol)
            return False

        volume_ratio = continuation_volume / average_volume
        is_high = volume_ratio >= min_threshold

        self.logger.info("=== Continuation Volume Check (Want HIGH Volume) ===", symbol)
        self.logger.info(f"Continuation Volume: {continuation_volume}", symbol)
        self.logger.info(f"Average Volume: {average_volume:.0f}", symbol)
        self.logger.info(f"Volume Ratio: {volume_ratio:.2f}x", symbol)
        self.logger.info(f"Min Threshold: {min_threshold:.2f}x", symbol)
        self.logger.info(f"Volume is HIGH: {'YES' if is_high else 'NO'}", symbol)

        if not is_high:
            self.logger.info(">>> VOLUME TOO LOW - Weak continuation, lacks momentum <<<", symbol)
            self.logger.info(">>> May not be a strong true breakout - skipping <<<", symbol)
        else:
            self.logger.info(">>> VOLUME IS HIGH - Strong continuation confirmation <<<", symbol)
            self.logger.info(">>> Excellent true breakout signal - proceeding <<<", symbol)

        return is_high
    
    def detect_bullish_rsi_divergence(self, df: pd.DataFrame, rsi_period: int,
                                     lookback: int, symbol: str) -> bool:
        """
        Detect bullish RSI divergence (for BUY setup).
        Price makes lower low, RSI makes higher low.
        
        Args:
            df: DataFrame with OHLC data
            rsi_period: RSI period
            lookback: Lookback period for swing points
            symbol: Symbol name for logging
            
        Returns:
            True if bullish divergence detected
        """
        if len(df) < lookback + rsi_period:
            return False
        
        # Calculate RSI
        rsi = talib.RSI(df['close'].values, timeperiod=rsi_period)
        
        # Find recent swing low (excluding current candle)
        lows = df['low'].values
        recent_low_idx = None
        
        for i in range(len(lows) - 3, max(0, len(lows) - lookback - 1), -1):
            if i > 0 and i < len(lows) - 1:
                if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                    recent_low_idx = i
                    break
        
        if recent_low_idx is None:
            self.logger.debug("No swing low found in lookback period", symbol)
            return False
        
        # Current low (last closed candle)
        current_low = lows[-2]
        previous_low = lows[recent_low_idx]
        
        # RSI values
        current_rsi = rsi[-2]
        previous_rsi = rsi[recent_low_idx]
        
        # Bullish divergence: Price lower low, RSI higher low
        price_lower_low = current_low < previous_low
        rsi_higher_low = current_rsi > previous_rsi
        
        if price_lower_low and rsi_higher_low:
            self.logger.info("*** BULLISH RSI DIVERGENCE DETECTED ***", symbol)
            self.logger.info(f"Price: {previous_low:.5f} -> {current_low:.5f} (Lower Low)", symbol)
            self.logger.info(f"RSI: {previous_rsi:.2f} -> {current_rsi:.2f} (Higher Low)", symbol)
            minutes_ago = (len(lows) - 2 - recent_low_idx) * 5
            self.logger.info(f"Swing low found {minutes_ago} minutes ago", symbol)
            return True
        
        self.logger.debug("No bullish RSI divergence", symbol)
        self.logger.debug(f"  Price Lower Low: {'YES' if price_lower_low else 'NO'}", symbol)
        self.logger.debug(f"  RSI Higher Low: {'YES' if rsi_higher_low else 'NO'}", symbol)
        
        return False
    
    def detect_bearish_rsi_divergence(self, df: pd.DataFrame, rsi_period: int,
                                      lookback: int, symbol: str) -> bool:
        """
        Detect bearish RSI divergence (for SELL setup).
        Price makes higher high, RSI makes lower high.
        
        Args:
            df: DataFrame with OHLC data
            rsi_period: RSI period
            lookback: Lookback period for swing points
            symbol: Symbol name for logging
            
        Returns:
            True if bearish divergence detected
        """
        if len(df) < lookback + rsi_period:
            return False
        
        # Calculate RSI
        rsi = talib.RSI(df['close'].values, timeperiod=rsi_period)
        
        # Find recent swing high (excluding current candle)
        highs = df['high'].values
        recent_high_idx = None
        
        for i in range(len(highs) - 3, max(0, len(highs) - lookback - 1), -1):
            if i > 0 and i < len(highs) - 1:
                if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                    recent_high_idx = i
                    break
        
        if recent_high_idx is None:
            self.logger.debug("No swing high found in lookback period", symbol)
            return False
        
        # Current high (last closed candle)
        current_high = highs[-2]
        previous_high = highs[recent_high_idx]
        
        # RSI values
        current_rsi = rsi[-2]
        previous_rsi = rsi[recent_high_idx]
        
        # Bearish divergence: Price higher high, RSI lower high
        price_higher_high = current_high > previous_high
        rsi_lower_high = current_rsi < previous_rsi
        
        if price_higher_high and rsi_lower_high:
            self.logger.info("*** BEARISH RSI DIVERGENCE DETECTED ***", symbol)
            self.logger.info(f"Price: {previous_high:.5f} -> {current_high:.5f} (Higher High)", symbol)
            self.logger.info(f"RSI: {previous_rsi:.2f} -> {current_rsi:.2f} (Lower High)", symbol)
            minutes_ago = (len(highs) - 2 - recent_high_idx) * 5
            self.logger.info(f"Swing high found {minutes_ago} minutes ago", symbol)
            return True
        
        self.logger.debug("No bearish RSI divergence", symbol)
        self.logger.debug(f"  Price Higher High: {'YES' if price_higher_high else 'NO'}", symbol)
        self.logger.debug(f"  RSI Lower High: {'YES' if rsi_lower_high else 'NO'}", symbol)
        
        return False

