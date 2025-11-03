"""
Core strategy logic for false breakout detection.
Ported from FMS_Strategy.mqh
"""
from typing import Optional
import pandas as pd
from src.models.data_models import (
    BreakoutState, FourHourCandle, CandleData, TradeSignal, 
    PositionType, SymbolParameters
)
from src.strategy.candle_processor import CandleProcessor
from src.indicators.technical_indicators import TechnicalIndicators
from src.config.config import StrategyConfig
from src.utils.logger import get_logger


class StrategyEngine:
    """Implements the false breakout strategy logic"""
    
    def __init__(self, symbol: str, candle_processor: CandleProcessor,
                 indicators: TechnicalIndicators, strategy_config: StrategyConfig,
                 symbol_params: SymbolParameters, connector=None):
        """
        Initialize strategy engine.

        Args:
            symbol: Symbol name
            candle_processor: Candle processor instance
            indicators: Technical indicators instance
            strategy_config: Strategy configuration
            symbol_params: Symbol-specific parameters
            connector: MT5 connector for symbol info (optional, for point-based SL)
        """
        self.symbol = symbol
        self.candle_processor = candle_processor
        self.indicators = indicators
        self.strategy_config = strategy_config
        self.symbol_params = symbol_params
        self.connector = connector
        self.logger = get_logger()

        # Breakout state tracking
        self.breakout_state = BreakoutState()

        # Volume tracking
        self.breakout_volume = 0
        self.reversal_volume = 0
    
    def check_for_signal(self) -> Optional[TradeSignal]:
        """
        Check for trade signals on new 5M candle.

        Returns:
            TradeSignal if signal detected, None otherwise
        """
        # Check if we're in the restricted trading period (04:00-08:00 UTC)
        if self.candle_processor.is_in_candle_formation_period():
            self.logger.debug("Trading suspended - Restricted period (04:00-08:00 UTC)", self.symbol)
            return None

        # Must have a 4H candle to trade from
        if not self.candle_processor.has_4h_candle():
            self.logger.debug("No 4H candle available yet", self.symbol)
            return None

        # Get current 4H candle
        candle_4h = self.candle_processor.get_current_4h_candle()
        if candle_4h is None:
            return None

        # Get latest 5M candle
        candle_5m = self.candle_processor.get_latest_5m_candle()
        if candle_5m is None:
            return None
        
        # Check for BUY signal
        buy_signal = self._check_buy_signal(candle_4h, candle_5m)
        if buy_signal:
            return buy_signal
        
        # Check for SELL signal
        sell_signal = self._check_sell_signal(candle_4h, candle_5m)
        if sell_signal:
            return sell_signal
        
        return None
    
    def _check_buy_signal(self, candle_4h: FourHourCandle, 
                         candle_5m: CandleData) -> Optional[TradeSignal]:
        """
        Check for BUY signal (false breakout below 4H low).
        
        Logic:
        1. Wait for 5M candle to close BELOW 4H low (breakout)
        2. Next 5M candle closes ABOVE 4H low (reversal/false breakout)
        3. Optional: Volume confirmation (low breakout, high reversal)
        4. Optional: Divergence confirmation
        
        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle
            
        Returns:
            TradeSignal if BUY signal detected
        """
        # Step 1: Check for breakout (5M close below 4H low)
        if not self.breakout_state.buy_breakout_confirmed:
            if candle_5m.close < candle_4h.low:
                # Store breakout volume
                self.breakout_volume = candle_5m.volume

                # Log breakout detection
                self.logger.info(">>> BUY BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.breakout_volume}", self.symbol)

                # Check BREAKOUT confirmations (volume LOW + divergence)
                # This matches MQL5: confirmations are checked at BREAKOUT stage, not reversal!
                if not self._check_buy_breakout_confirmations():
                    self.logger.info(">>> BUY BREAKOUT CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.reset_state()
                    return None

                # Breakout confirmed - set flag and wait for reversal
                self.breakout_state.buy_breakout_confirmed = True
                self.logger.info("*** BUY BREAKOUT CONFIRMED (Low Volume + Bullish Divergence) ***", self.symbol)
                self.logger.info("Waiting for reversal back above 4H Low...", self.symbol)

            return None
        
        # Step 2: Check for reversal (5M close back above 4H low)
        if self.breakout_state.buy_breakout_confirmed and not self.breakout_state.buy_reversal_confirmed:
            if candle_5m.close > candle_4h.low:
                # Store reversal volume
                self.reversal_volume = candle_5m.volume

                # Log reversal detection
                self.logger.info(">>> BUY REVERSAL DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {self.reversal_volume}", self.symbol)

                # Check REVERSAL confirmations (volume HIGH)
                # This matches MQL5: reversal volume is checked at REVERSAL stage
                if not self._check_buy_reversal_confirmations():
                    self.logger.info(">>> BUY REVERSAL CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.reset_state()
                    return None

                # All confirmations passed
                self.breakout_state.buy_reversal_confirmed = True

                # Generate BUY signal
                return self._generate_buy_signal(candle_4h, candle_5m)

            return None

        return None
    
    def _check_sell_signal(self, candle_4h: FourHourCandle,
                          candle_5m: CandleData) -> Optional[TradeSignal]:
        """
        Check for SELL signal (false breakout above 4H high).
        
        Logic:
        1. Wait for 5M candle to close ABOVE 4H high (breakout)
        2. Next 5M candle closes BELOW 4H high (reversal/false breakout)
        3. Optional: Volume confirmation (low breakout, high reversal)
        4. Optional: Divergence confirmation
        
        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle
            
        Returns:
            TradeSignal if SELL signal detected
        """
        # Step 1: Check for breakout (5M close above 4H high)
        if not self.breakout_state.sell_breakout_confirmed:
            if candle_5m.close > candle_4h.high:
                # Store breakout volume
                self.breakout_volume = candle_5m.volume

                # Log breakout detection
                self.logger.info(">>> SELL BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.breakout_volume}", self.symbol)

                # Check BREAKOUT confirmations (volume LOW + divergence)
                # This matches MQL5: confirmations are checked at BREAKOUT stage, not reversal!
                if not self._check_sell_breakout_confirmations():
                    self.logger.info(">>> SELL BREAKOUT CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.reset_state()
                    return None

                # Breakout confirmed - set flag and wait for reversal
                self.breakout_state.sell_breakout_confirmed = True
                self.logger.info("*** SELL BREAKOUT CONFIRMED (Low Volume + Bearish Divergence) ***", self.symbol)
                self.logger.info("Waiting for reversal back below 4H High...", self.symbol)

            return None
        
        # Step 2: Check for reversal (5M close back below 4H high)
        if self.breakout_state.sell_breakout_confirmed and not self.breakout_state.sell_reversal_confirmed:
            if candle_5m.close < candle_4h.high:
                # Store reversal volume
                self.reversal_volume = candle_5m.volume

                # Log reversal detection
                self.logger.info(">>> SELL REVERSAL DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {self.reversal_volume}", self.symbol)

                # Check REVERSAL confirmations (volume HIGH)
                # This matches MQL5: reversal volume is checked at REVERSAL stage
                if not self._check_sell_reversal_confirmations():
                    self.logger.info(">>> SELL REVERSAL CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.reset_state()
                    return None

                # All confirmations passed
                self.breakout_state.sell_reversal_confirmed = True

                # Generate SELL signal
                return self._generate_sell_signal(candle_4h, candle_5m)

            return None

        return None
    
    def _check_buy_breakout_confirmations(self) -> bool:
        """
        Check BUY BREAKOUT confirmations (volume LOW + divergence).
        This matches MQL5: confirmations are checked at BREAKOUT stage.
        """
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check breakout volume is LOW
            if not self._check_breakout_volume():
                return False

        # Divergence confirmation (if enabled)
        if self.symbol_params.divergence_confirmation_enabled:
            if not self._check_buy_divergence():
                return False

        return True

    def _check_buy_reversal_confirmations(self) -> bool:
        """
        Check BUY REVERSAL confirmations (volume HIGH).
        This matches MQL5: reversal volume is checked at REVERSAL stage.
        """
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check reversal volume is HIGH
            if not self._check_reversal_volume():
                return False

        return True

    def _check_sell_breakout_confirmations(self) -> bool:
        """
        Check SELL BREAKOUT confirmations (volume LOW + divergence).
        This matches MQL5: confirmations are checked at BREAKOUT stage.
        """
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check breakout volume is LOW
            if not self._check_breakout_volume():
                return False

        # Divergence confirmation (if enabled)
        if self.symbol_params.divergence_confirmation_enabled:
            if not self._check_sell_divergence():
                return False

        return True

    def _check_sell_reversal_confirmations(self) -> bool:
        """
        Check SELL REVERSAL confirmations (volume HIGH).
        This matches MQL5: reversal volume is checked at REVERSAL stage.
        """
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check reversal volume is HIGH
            if not self._check_reversal_volume():
                return False

        return True

    def _check_breakout_volume(self) -> bool:
        """Check breakout volume is LOW"""
        # Get 5M candles for average volume
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # Check breakout volume is LOW
        return self.indicators.is_breakout_volume_low(
            self.breakout_volume,
            avg_volume,
            self.symbol_params.breakout_volume_max,
            self.symbol
        )

    def _check_reversal_volume(self) -> bool:
        """Check reversal volume is HIGH"""
        # Get 5M candles for average volume
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # Check reversal volume is HIGH
        return self.indicators.is_reversal_volume_high(
            self.reversal_volume,
            avg_volume,
            self.symbol_params.reversal_volume_min,
            self.symbol
        )
    
    def _check_buy_divergence(self) -> bool:
        """Check for bullish divergence"""
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        return self.indicators.detect_bullish_rsi_divergence(
            df,
            self.symbol_params.rsi_period,
            self.symbol_params.divergence_lookback,
            self.symbol
        )

    def _check_sell_divergence(self) -> bool:
        """Check for bearish divergence"""
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        return self.indicators.detect_bearish_rsi_divergence(
            df,
            self.symbol_params.rsi_period,
            self.symbol_params.divergence_lookback,
            self.symbol
        )

    def _calculate_sl_offset(self, reference_price: float) -> float:
        """
        Calculate stop loss offset based on configuration.

        Uses point-based calculation if enabled (recommended for consistent risk across symbols),
        otherwise falls back to percentage-based calculation.

        Args:
            reference_price: The reference price (lowest_low for BUY, highest_high for SELL)

        Returns:
            Stop loss offset in price units
        """
        if self.strategy_config.use_point_based_sl and self.connector is not None:
            # Point-based calculation (recommended)
            symbol_info = self.connector.get_symbol_info(self.symbol)
            if symbol_info is not None:
                point = symbol_info['point']
                # Convert points to price offset
                sl_offset = self.strategy_config.stop_loss_offset_points * point

                self.logger.debug(
                    f"SL offset (point-based): {self.strategy_config.stop_loss_offset_points} points = {sl_offset:.5f}",
                    self.symbol
                )
                return sl_offset
            else:
                self.logger.warning(
                    "Failed to get symbol info for point-based SL, falling back to percentage",
                    self.symbol
                )

        # Percentage-based calculation (legacy/fallback)
        sl_offset = reference_price * (self.strategy_config.stop_loss_offset_percent / 100.0)
        self.logger.debug(
            f"SL offset (percentage-based): {self.strategy_config.stop_loss_offset_percent}% = {sl_offset:.5f}",
            self.symbol
        )
        return sl_offset

    def _generate_buy_signal(self, candle_4h: FourHourCandle,
                            candle_5m: CandleData) -> TradeSignal:
        """
        Generate BUY trade signal.

        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle

        Returns:
            TradeSignal for BUY
        """
        # Find the LOWEST LOW among the last 10 candles that closed BELOW 4H low
        # This matches MQL5: FindLowestLowInRange()
        lowest_low = self._find_lowest_low_in_pattern(candle_4h.low)

        if lowest_low is None:
            self.logger.warning("No valid lowest low found for BUY signal", self.symbol)
            lowest_low = candle_4h.low  # Fallback to 4H low

        # Entry: Will use current ASK price at execution (matches MQL5)
        # For signal generation, use current 5M close as reference
        entry_price = candle_5m.close

        # Stop Loss: Below the LOWEST LOW (not 4H low!)
        # Use point-based or percentage-based calculation
        sl_offset = self._calculate_sl_offset(lowest_low)

        # Add spread to SL to account for bid-ask spread
        # For BUY: Entry at ASK, SL triggered when BID hits SL
        # So we need to widen SL by spread amount
        spread_price = 0.0
        if self.connector is not None:
            symbol_info = self.connector.get_symbol_info(self.symbol)
            if symbol_info is not None:
                spread_points = self.connector.get_spread(self.symbol)
                if spread_points is not None:
                    point = symbol_info['point']
                    spread_price = spread_points * point
                    self.logger.debug(
                        f"Adding spread to BUY SL: {spread_points:.1f} points = {spread_price:.5f}",
                        self.symbol
                    )

        stop_loss = lowest_low - sl_offset - spread_price

        # Take Profit: Based on R:R ratio
        # Note: TP will be recalculated in order_manager using actual execution price
        risk = entry_price - stop_loss
        reward = risk * self.strategy_config.risk_reward_ratio
        take_profit = entry_price + reward

        signal = TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.BUY,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_5m.time,
            reason="False breakout below 4H low with reversal",
            max_spread_percent=self.symbol_params.max_spread_percent
        )

        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** BUY SIGNAL GENERATED ***", self.symbol)
        self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
        self.logger.info(f"Lowest Low in Pattern: {lowest_low:.5f}", self.symbol)
        self.logger.info(f"SL Offset: {sl_offset:.5f}", self.symbol)
        if spread_price > 0:
            self.logger.info(f"Spread Adjustment: {spread_price:.5f}", self.symbol)
        self.logger.info(f"Entry (reference): {entry_price:.5f} (actual entry will be current ASK)", self.symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f} (includes spread adjustment)", self.symbol)
        self.logger.info(f"Take Profit (reference): {take_profit:.5f} (will be recalculated at execution)", self.symbol)
        self.logger.info(f"Risk (estimated): {risk:.5f}", self.symbol)
        self.logger.info(f"Reward (estimated): {reward:.5f}", self.symbol)
        self.logger.info(f"R:R Ratio: 1:{self.strategy_config.risk_reward_ratio}", self.symbol)
        self.logger.info("=" * 60, self.symbol)

        return signal

    def _generate_sell_signal(self, candle_4h: FourHourCandle,
                             candle_5m: CandleData) -> TradeSignal:
        """
        Generate SELL trade signal.

        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle

        Returns:
            TradeSignal for SELL
        """
        # Find the HIGHEST HIGH among the last 10 candles that closed ABOVE 4H high
        # This matches MQL5: FindHighestHighInRange()
        highest_high = self._find_highest_high_in_pattern(candle_4h.high)

        if highest_high is None:
            self.logger.warning("No valid highest high found for SELL signal", self.symbol)
            highest_high = candle_4h.high  # Fallback to 4H high

        # Entry: Will use current BID price at execution (matches MQL5)
        # For signal generation, use current 5M close as reference
        entry_price = candle_5m.close

        # Stop Loss: Above the HIGHEST HIGH (not 4H high!)
        # Use point-based or percentage-based calculation
        sl_offset = self._calculate_sl_offset(highest_high)

        # Add spread to SL to account for bid-ask spread
        # For SELL: Entry at BID, SL triggered when ASK hits SL
        # So we need to widen SL by spread amount
        spread_price = 0.0
        if self.connector is not None:
            symbol_info = self.connector.get_symbol_info(self.symbol)
            if symbol_info is not None:
                spread_points = self.connector.get_spread(self.symbol)
                if spread_points is not None:
                    point = symbol_info['point']
                    spread_price = spread_points * point
                    self.logger.debug(
                        f"Adding spread to SELL SL: {spread_points:.1f} points = {spread_price:.5f}",
                        self.symbol
                    )

        stop_loss = highest_high + sl_offset + spread_price

        # Take Profit: Based on R:R ratio
        # Note: TP will be recalculated in order_manager using actual execution price
        risk = stop_loss - entry_price
        reward = risk * self.strategy_config.risk_reward_ratio
        take_profit = entry_price - reward

        signal = TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.SELL,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_5m.time,
            reason="False breakout above 4H high with reversal",
            max_spread_percent=self.symbol_params.max_spread_percent
        )

        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** SELL SIGNAL GENERATED ***", self.symbol)
        self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
        self.logger.info(f"Highest High in Pattern: {highest_high:.5f}", self.symbol)
        self.logger.info(f"SL Offset: {sl_offset:.5f}", self.symbol)
        if spread_price > 0:
            self.logger.info(f"Spread Adjustment: {spread_price:.5f}", self.symbol)
        self.logger.info(f"Entry (reference): {entry_price:.5f} (actual entry will be current BID)", self.symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f} (includes spread adjustment)", self.symbol)
        self.logger.info(f"Take Profit (reference): {take_profit:.5f} (will be recalculated at execution)", self.symbol)
        self.logger.info(f"Risk (estimated): {risk:.5f}", self.symbol)
        self.logger.info(f"Reward (estimated): {reward:.5f}", self.symbol)
        self.logger.info(f"R:R Ratio: 1:{self.strategy_config.risk_reward_ratio}", self.symbol)
        self.logger.info("=" * 60, self.symbol)

        return signal

    def _find_lowest_low_in_pattern(self, four_h_low: float) -> Optional[float]:
        """
        Find the LOWEST LOW among the last 10 candles that closed BELOW the 4H low.
        This matches MQL5: FindLowestLowInRange()

        Args:
            four_h_low: The 4H candle's low price

        Returns:
            Lowest low price, or None if no valid candles found
        """
        # Get last 10 5M candles
        df = self.candle_processor.get_5m_candles(count=10)
        if df is None or len(df) == 0:
            return None

        lowest_low = None

        # Find candles that closed BELOW 4H low
        for idx in range(len(df)):
            candle_close = df.iloc[idx]['close']
            candle_low = df.iloc[idx]['low']

            # Only consider candles that closed BELOW 4H low
            if candle_close < four_h_low:
                if lowest_low is None or candle_low < lowest_low:
                    lowest_low = candle_low

        if lowest_low is not None:
            self.logger.info(f"Found lowest low in pattern: {lowest_low:.5f} (4H low: {four_h_low:.5f})", self.symbol)

        return lowest_low

    def _find_highest_high_in_pattern(self, four_h_high: float) -> Optional[float]:
        """
        Find the HIGHEST HIGH among the last 10 candles that closed ABOVE the 4H high.
        This matches MQL5: FindHighestHighInRange()

        Args:
            four_h_high: The 4H candle's high price

        Returns:
            Highest high price, or None if no valid candles found
        """
        # Get last 10 5M candles
        df = self.candle_processor.get_5m_candles(count=10)
        if df is None or len(df) == 0:
            return None

        highest_high = None

        # Find candles that closed ABOVE 4H high
        for idx in range(len(df)):
            candle_close = df.iloc[idx]['close']
            candle_high = df.iloc[idx]['high']

            # Only consider candles that closed ABOVE 4H high
            if candle_close > four_h_high:
                if highest_high is None or candle_high > highest_high:
                    highest_high = candle_high

        if highest_high is not None:
            self.logger.info(f"Found highest high in pattern: {highest_high:.5f} (4H high: {four_h_high:.5f})", self.symbol)

        return highest_high

    def reset_state(self):
        """Reset breakout state"""
        self.breakout_state.reset_buy()
        self.breakout_state.reset_sell()
        self.breakout_volume = 0
        self.reversal_volume = 0
        self.logger.info("Strategy state reset", self.symbol)

