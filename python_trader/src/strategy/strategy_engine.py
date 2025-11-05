"""
Core strategy logic for false breakout detection.
Ported from FMS_Strategy.mqh
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
import pandas as pd
from src.models.data_models import (
    BreakoutState, UnifiedBreakoutState, FourHourCandle, CandleData, TradeSignal,
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

        # Unified breakout state tracking
        self.unified_state = UnifiedBreakoutState()

        # Legacy breakout state (kept for backward compatibility during migration)
        self.breakout_state = BreakoutState()

        # Volume tracking - DEPRECATED (moved to UnifiedBreakoutState)
        # Kept for backward compatibility during migration
        self.false_breakout_volume = 0
        self.false_reversal_volume = 0
        self.true_breakout_volume = 0
        self.true_continuation_volume = 0
    
    def check_for_signal(self) -> Optional[TradeSignal]:
        """
        UNIFIED BREAKOUT DETECTION APPROACH

        Stage 1: Detect breakout once (above 4H high OR below 4H low)
        Stage 2: Classify for both strategies simultaneously based on volume
        Stage 3: Wait for reversal (FALSE BREAKOUT) or continuation (TRUE BREAKOUT)
        Stage 4: Generate signal when confirmations pass

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

        # === STAGE 1: UNIFIED BREAKOUT DETECTION ===
        self._detect_breakout(candle_4h, candle_5m)

        # === STAGE 2: STRATEGY CLASSIFICATION ===
        # Classify which strategies can proceed based on volume
        self._classify_strategies(candle_5m)

        # === STAGE 3 & 4: CHECK FOR SIGNALS ===
        # Check if any strategy has generated a signal
        signal = self._check_all_strategies(candle_4h, candle_5m)
        if signal:
            return signal

        # === CLEANUP: Reset if both strategies rejected ===
        if self.unified_state.both_strategies_rejected():
            self.logger.info(">>> BOTH STRATEGIES REJECTED - Resetting <<<", self.symbol)
            self.unified_state.reset_all()

        return None

    def _detect_breakout(self, candle_4h: FourHourCandle, candle_5m: CandleData):
        """
        STAGE 1: Unified breakout detection.

        Detects when price breaks above 4H high or below 4H low.
        Stores breakout volume WITHOUT checking confirmations yet.

        Also checks for breakout timeout - if a breakout is older than the configured
        timeout period (default 24 candles = 2 hours), it's considered stale and reset.
        """
        # Check for timeout on existing breakouts
        self._check_breakout_timeout(candle_5m)

        # Check for breakout ABOVE 4H high
        if not self.unified_state.breakout_above_detected:
            if candle_5m.close > candle_4h.high:
                self.unified_state.breakout_above_detected = True
                self.unified_state.breakout_above_volume = candle_5m.volume
                self.unified_state.breakout_above_time = candle_5m.time

                self.logger.info("=" * 60, self.symbol)
                self.logger.info(">>> BREAKOUT ABOVE 4H HIGH DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {candle_5m.volume}", self.symbol)
                self.logger.info("=" * 60, self.symbol)

        # Check for breakout BELOW 4H low
        if not self.unified_state.breakout_below_detected:
            if candle_5m.close < candle_4h.low:
                self.unified_state.breakout_below_detected = True
                self.unified_state.breakout_below_volume = candle_5m.volume
                self.unified_state.breakout_below_time = candle_5m.time

                self.logger.info("=" * 60, self.symbol)
                self.logger.info(">>> BREAKOUT BELOW 4H LOW DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {candle_5m.volume}", self.symbol)
                self.logger.info("=" * 60, self.symbol)

    def _check_breakout_timeout(self, candle_5m: CandleData):
        """
        Check if existing breakouts have timed out.

        Breakouts older than breakout_timeout_candles (default 24 = 2 hours) are
        considered stale and reset to prevent trading on old momentum.

        Args:
            candle_5m: Current 5M candle with timestamp
        """
        timeout_minutes = self.symbol_params.breakout_timeout_candles * 5  # Convert candles to minutes
        timeout_delta = timedelta(minutes=timeout_minutes)

        # Check breakout ABOVE timeout
        if self.unified_state.breakout_above_detected and self.unified_state.breakout_above_time:
            age = candle_5m.time - self.unified_state.breakout_above_time
            if age > timeout_delta:
                age_minutes = int(age.total_seconds() / 60)
                self.logger.info("=" * 60, self.symbol)
                self.logger.info(">>> BREAKOUT ABOVE TIMEOUT - Resetting <<<", self.symbol)
                self.logger.info(f"Breakout Age: {age_minutes} minutes ({age_minutes // 60}h {age_minutes % 60}m)", self.symbol)
                self.logger.info(f"Timeout Limit: {timeout_minutes} minutes ({self.symbol_params.breakout_timeout_candles} candles)", self.symbol)
                self.logger.info("Reason: Breakout too old, momentum lost", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                self.unified_state.reset_breakout_above()

        # Check breakout BELOW timeout
        if self.unified_state.breakout_below_detected and self.unified_state.breakout_below_time:
            age = candle_5m.time - self.unified_state.breakout_below_time
            if age > timeout_delta:
                age_minutes = int(age.total_seconds() / 60)
                self.logger.info("=" * 60, self.symbol)
                self.logger.info(">>> BREAKOUT BELOW TIMEOUT - Resetting <<<", self.symbol)
                self.logger.info(f"Breakout Age: {age_minutes} minutes ({age_minutes // 60}h {age_minutes % 60}m)", self.symbol)
                self.logger.info(f"Timeout Limit: {timeout_minutes} minutes ({self.symbol_params.breakout_timeout_candles} candles)", self.symbol)
                self.logger.info("Reason: Breakout too old, momentum lost", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                self.unified_state.reset_breakout_below()

    def _classify_strategies(self, candle_5m: CandleData):
        """
        STAGE 2: Strategy classification and confirmation tracking.

        Determines which strategies can proceed and tracks confirmations:
        - FALSE BREAKOUT: Prefers LOW breakout volume
        - TRUE BREAKOUT: Prefers HIGH breakout volume

        Confirmations are TRACKED but NOT REQUIRED for trade execution.
        This allows analysis of which confirmations correlate with winning trades.
        """
        # Get 5M candles for average volume calculation
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # === CLASSIFY BREAKOUT ABOVE (TRUE BUY / FALSE SELL) ===
        if self.unified_state.breakout_above_detected and not self.unified_state.true_buy_qualified and not self.unified_state.false_sell_qualified:
            volume = self.unified_state.breakout_above_volume

            # Check if qualifies for TRUE BUY (high volume continuation)
            if self.symbol_params.enable_true_breakout_strategy:
                # Check volume confirmation (tracked but not required)
                is_high_volume = self.indicators.is_true_breakout_volume_high(
                    volume, avg_volume,
                    self.symbol_params.true_breakout_volume_min,
                    self.symbol
                )

                # Always qualify, but track volume confirmation status
                self.unified_state.true_buy_qualified = True
                self.unified_state.true_buy_volume_ok = is_high_volume

                if is_high_volume:
                    self.logger.info(">>> TRUE BUY QUALIFIED (High Volume ✓) <<<", self.symbol)
                else:
                    self.logger.info(">>> TRUE BUY QUALIFIED (Volume not high ✗) <<<", self.symbol)
                self.logger.info("Waiting for continuation above 4H High...", self.symbol)

            # Check if qualifies for FALSE SELL (low volume reversal)
            if self.symbol_params.enable_false_breakout_strategy:
                # Check volume confirmation (tracked but not required)
                is_low_volume = self.indicators.is_breakout_volume_low(
                    volume, avg_volume,
                    self.symbol_params.breakout_volume_max,
                    self.symbol
                )

                # Check divergence (tracked but not required)
                divergence_ok = self._check_sell_divergence()

                # Always qualify, but track confirmation status
                self.unified_state.false_sell_qualified = True
                self.unified_state.false_sell_volume_ok = is_low_volume
                self.unified_state.false_sell_divergence_ok = divergence_ok

                # Log confirmation status
                vol_status = "✓" if is_low_volume else "✗"
                div_status = "✓" if divergence_ok else "✗"
                self.logger.info(f">>> FALSE SELL QUALIFIED (Low Vol {vol_status}, Div {div_status}) <<<", self.symbol)
                self.logger.info("Waiting for reversal back below 4H High...", self.symbol)

        # === CLASSIFY BREAKOUT BELOW (TRUE SELL / FALSE BUY) ===
        if self.unified_state.breakout_below_detected and not self.unified_state.true_sell_qualified and not self.unified_state.false_buy_qualified:
            volume = self.unified_state.breakout_below_volume

            # Check if qualifies for TRUE SELL (high volume continuation)
            if self.symbol_params.enable_true_breakout_strategy:
                # Check volume confirmation (tracked but not required)
                is_high_volume = self.indicators.is_true_breakout_volume_high(
                    volume, avg_volume,
                    self.symbol_params.true_breakout_volume_min,
                    self.symbol
                )

                # Always qualify, but track volume confirmation status
                self.unified_state.true_sell_qualified = True
                self.unified_state.true_sell_volume_ok = is_high_volume

                if is_high_volume:
                    self.logger.info(">>> TRUE SELL QUALIFIED (High Volume ✓) <<<", self.symbol)
                else:
                    self.logger.info(">>> TRUE SELL QUALIFIED (Volume not high ✗) <<<", self.symbol)
                self.logger.info("Waiting for continuation below 4H Low...", self.symbol)

            # Check if qualifies for FALSE BUY (low volume reversal)
            if self.symbol_params.enable_false_breakout_strategy:
                # Check volume confirmation (tracked but not required)
                is_low_volume = self.indicators.is_breakout_volume_low(
                    volume, avg_volume,
                    self.symbol_params.breakout_volume_max,
                    self.symbol
                )

                # Check divergence (tracked but not required)
                divergence_ok = self._check_buy_divergence()

                # Always qualify, but track confirmation status
                self.unified_state.false_buy_qualified = True
                self.unified_state.false_buy_volume_ok = is_low_volume
                self.unified_state.false_buy_divergence_ok = divergence_ok

                # Log confirmation status
                vol_status = "✓" if is_low_volume else "✗"
                div_status = "✓" if divergence_ok else "✗"
                self.logger.info(f">>> FALSE BUY QUALIFIED (Low Vol {vol_status}, Div {div_status}) <<<", self.symbol)
                self.logger.info("Waiting for reversal back above 4H Low...", self.symbol)

    def _check_all_strategies(self, candle_4h: FourHourCandle, candle_5m: CandleData) -> Optional[TradeSignal]:
        """
        STAGE 3 & 4: Check all qualified strategies for signals.

        Checks for:
        - FALSE BUY: Reversal back above 4H low (if qualified)
        - FALSE SELL: Reversal back below 4H high (if qualified)
        - TRUE BUY: Continuation above 4H high (if qualified)
        - TRUE SELL: Continuation below 4H low (if qualified)
        """
        # === FALSE BUY: Check for reversal back above 4H low ===
        if self.unified_state.false_buy_qualified and not self.unified_state.false_buy_reversal_detected:
            if candle_5m.close > candle_4h.low:
                self.unified_state.false_buy_reversal_detected = True
                self.unified_state.false_buy_reversal_volume = candle_5m.volume

                # Check reversal volume (tracked but not required)
                reversal_volume_ok = self._check_unified_reversal_volume(candle_5m.volume)
                self.unified_state.false_buy_reversal_volume_ok = reversal_volume_ok

                vol_status = "✓" if reversal_volume_ok else "✗"
                self.logger.info(f">>> FALSE BUY REVERSAL DETECTED (Rev Vol {vol_status}) <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {candle_5m.volume}", self.symbol)

                # Always generate signal (confirmations tracked in signal)
                self.logger.info("*** FALSE BUY SIGNAL GENERATED ***", self.symbol)
                return self._generate_buy_signal(candle_4h, candle_5m)

        # === FALSE SELL: Check for reversal back below 4H high ===
        if self.unified_state.false_sell_qualified and not self.unified_state.false_sell_reversal_detected:
            if candle_5m.close < candle_4h.high:
                self.unified_state.false_sell_reversal_detected = True
                self.unified_state.false_sell_reversal_volume = candle_5m.volume

                # Check reversal volume (tracked but not required)
                reversal_volume_ok = self._check_unified_reversal_volume(candle_5m.volume)
                self.unified_state.false_sell_reversal_volume_ok = reversal_volume_ok

                vol_status = "✓" if reversal_volume_ok else "✗"
                self.logger.info(f">>> FALSE SELL REVERSAL DETECTED (Rev Vol {vol_status}) <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {candle_5m.volume}", self.symbol)

                # Always generate signal (confirmations tracked in signal)
                self.logger.info("*** FALSE SELL SIGNAL GENERATED ***", self.symbol)
                return self._generate_sell_signal(candle_4h, candle_5m)

        # === TRUE BUY: Check for retest and continuation above 4H high ===
        if self.unified_state.true_buy_qualified and not self.unified_state.true_buy_continuation_detected:
            # First, check if we need to detect a retest
            if not self.unified_state.true_buy_retest_detected:
                # Retest: Price pulls back close to 4H high but stays above
                # We consider it a retest if price comes within a small range of the breakout level
                retest_range = candle_4h.high * 0.0005  # 0.05% range for retest detection
                if candle_4h.high <= candle_5m.close <= (candle_4h.high + retest_range):
                    self.unified_state.true_buy_retest_detected = True
                    self.unified_state.true_buy_retest_ok = True
                    self.logger.info(f">>> TRUE BUY RETEST DETECTED (Retest ✓) <<<", self.symbol)
                    self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                    self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                    self.logger.info(f"Retest Range: {retest_range:.5f}", self.symbol)
                    self.logger.info("Waiting for continuation above 4H High...", self.symbol)

            # After retest (or if retest not required), check for continuation
            # Only generate signal if retest occurred OR if price moved significantly above breakout
            if self.unified_state.true_buy_retest_detected or candle_5m.close > (candle_4h.high * 1.001):
                if candle_5m.close > candle_4h.high:
                    self.unified_state.true_buy_continuation_detected = True
                    self.unified_state.true_buy_continuation_volume = candle_5m.volume

                    # Check continuation volume (tracked but not required)
                    continuation_volume_ok = self._check_unified_continuation_volume(candle_5m.volume)
                    self.unified_state.true_buy_continuation_volume_ok = continuation_volume_ok

                    # Track retest status
                    retest_status = "✓" if self.unified_state.true_buy_retest_ok else "✗"
                    vol_status = "✓" if continuation_volume_ok else "✗"

                    self.logger.info(f">>> TRUE BUY CONTINUATION DETECTED (Retest {retest_status}, Cont Vol {vol_status}) <<<", self.symbol)
                    self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                    self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                    self.logger.info(f"Continuation Volume: {candle_5m.volume}", self.symbol)

                    # Always generate signal (confirmations tracked in signal)
                    self.logger.info("*** TRUE BUY SIGNAL GENERATED ***", self.symbol)
                    return self._generate_true_buy_signal(candle_4h, candle_5m)

        # === TRUE SELL: Check for retest and continuation below 4H low ===
        if self.unified_state.true_sell_qualified and not self.unified_state.true_sell_continuation_detected:
            # First, check if we need to detect a retest
            if not self.unified_state.true_sell_retest_detected:
                # Retest: Price pulls back close to 4H low but stays below
                # We consider it a retest if price comes within a small range of the breakout level
                retest_range = candle_4h.low * 0.0005  # 0.05% range for retest detection
                if (candle_4h.low - retest_range) <= candle_5m.close <= candle_4h.low:
                    self.unified_state.true_sell_retest_detected = True
                    self.unified_state.true_sell_retest_ok = True
                    self.logger.info(f">>> TRUE SELL RETEST DETECTED (Retest ✓) <<<", self.symbol)
                    self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                    self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                    self.logger.info(f"Retest Range: {retest_range:.5f}", self.symbol)
                    self.logger.info("Waiting for continuation below 4H Low...", self.symbol)

            # After retest (or if retest not required), check for continuation
            # Only generate signal if retest occurred OR if price moved significantly below breakout
            if self.unified_state.true_sell_retest_detected or candle_5m.close < (candle_4h.low * 0.999):
                if candle_5m.close < candle_4h.low:
                    self.unified_state.true_sell_continuation_detected = True
                    self.unified_state.true_sell_continuation_volume = candle_5m.volume

                    # Check continuation volume (tracked but not required)
                    continuation_volume_ok = self._check_unified_continuation_volume(candle_5m.volume)
                    self.unified_state.true_sell_continuation_volume_ok = continuation_volume_ok

                    # Track retest status
                    retest_status = "✓" if self.unified_state.true_sell_retest_ok else "✗"
                    vol_status = "✓" if continuation_volume_ok else "✗"

                    self.logger.info(f">>> TRUE SELL CONTINUATION DETECTED (Retest {retest_status}, Cont Vol {vol_status}) <<<", self.symbol)
                    self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                    self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                    self.logger.info(f"Continuation Volume: {candle_5m.volume}", self.symbol)

                    # Always generate signal (confirmations tracked in signal)
                    self.logger.info("*** TRUE SELL SIGNAL GENERATED ***", self.symbol)
                    return self._generate_true_sell_signal(candle_4h, candle_5m)

        return None

    def _check_unified_reversal_volume(self, volume: int) -> bool:
        """Check if reversal volume is HIGH (for FALSE BREAKOUT)"""
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        return self.indicators.is_reversal_volume_high(
            volume, avg_volume,
            self.symbol_params.reversal_volume_min,
            self.symbol
        )

    def _check_unified_continuation_volume(self, volume: int) -> bool:
        """Check if continuation volume is HIGH (for TRUE BREAKOUT)"""
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        return self.indicators.is_continuation_volume_high(
            volume, avg_volume,
            self.symbol_params.continuation_volume_min,
            self.symbol
        )

    # ========================================================================
    # LEGACY METHODS - Kept for backward compatibility during migration
    # ========================================================================

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
                # Store breakout volume (FALSE BREAKOUT specific)
                self.false_breakout_volume = candle_5m.volume

                # Log breakout detection
                self.logger.info(">>> BUY BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.false_breakout_volume}", self.symbol)

                # Check BREAKOUT confirmations (volume LOW + divergence)
                # This matches MQL5: confirmations are checked at BREAKOUT stage, not reversal!
                if not self._check_buy_breakout_confirmations():
                    self.logger.info(">>> BUY BREAKOUT CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_buy()
                    return None

                # Breakout confirmed - set flag and wait for reversal
                self.breakout_state.buy_breakout_confirmed = True
                self.logger.info("*** BUY BREAKOUT CONFIRMED (Low Volume + Bullish Divergence) ***", self.symbol)
                self.logger.info("Waiting for reversal back above 4H Low...", self.symbol)

            return None

        # Step 2: Check for reversal (5M close back above 4H low)
        if self.breakout_state.buy_breakout_confirmed and not self.breakout_state.buy_reversal_confirmed:
            if candle_5m.close > candle_4h.low:
                # Store reversal volume (FALSE BREAKOUT specific)
                self.false_reversal_volume = candle_5m.volume

                # Log reversal detection
                self.logger.info(">>> BUY REVERSAL DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {self.false_reversal_volume}", self.symbol)

                # Check REVERSAL confirmations (volume HIGH)
                # This matches MQL5: reversal volume is checked at REVERSAL stage
                if not self._check_buy_reversal_confirmations():
                    self.logger.info(">>> BUY REVERSAL CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_buy()
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
                # Store breakout volume (FALSE BREAKOUT specific)
                self.false_breakout_volume = candle_5m.volume

                # Log breakout detection
                self.logger.info(">>> SELL BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.false_breakout_volume}", self.symbol)

                # Check BREAKOUT confirmations (volume LOW + divergence)
                # This matches MQL5: confirmations are checked at BREAKOUT stage, not reversal!
                if not self._check_sell_breakout_confirmations():
                    self.logger.info(">>> SELL BREAKOUT CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_sell()
                    return None

                # Breakout confirmed - set flag and wait for reversal
                self.breakout_state.sell_breakout_confirmed = True
                self.logger.info("*** SELL BREAKOUT CONFIRMED (Low Volume + Bearish Divergence) ***", self.symbol)
                self.logger.info("Waiting for reversal back below 4H High...", self.symbol)

            return None

        # Step 2: Check for reversal (5M close back below 4H high)
        if self.breakout_state.sell_breakout_confirmed and not self.breakout_state.sell_reversal_confirmed:
            if candle_5m.close < candle_4h.high:
                # Store reversal volume (FALSE BREAKOUT specific)
                self.false_reversal_volume = candle_5m.volume

                # Log reversal detection
                self.logger.info(">>> SELL REVERSAL DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {self.false_reversal_volume}", self.symbol)

                # Check REVERSAL confirmations (volume HIGH)
                # This matches MQL5: reversal volume is checked at REVERSAL stage
                if not self._check_sell_reversal_confirmations():
                    self.logger.info(">>> SELL REVERSAL CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_sell()
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
        """Check breakout volume is LOW (for FALSE BREAKOUT strategy)"""
        # Get 5M candles for average volume
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # Check breakout volume is LOW (using FALSE BREAKOUT volume)
        return self.indicators.is_breakout_volume_low(
            self.false_breakout_volume,
            avg_volume,
            self.symbol_params.breakout_volume_max,
            self.symbol
        )

    def _check_reversal_volume(self) -> bool:
        """Check reversal volume is HIGH (for FALSE BREAKOUT strategy)"""
        # Get 5M candles for average volume
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # Check reversal volume is HIGH (using FALSE BREAKOUT volume)
        return self.indicators.is_reversal_volume_high(
            self.false_reversal_volume,
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

    # ========== TRUE BREAKOUT STRATEGY METHODS ==========

    def _check_true_buy_signal(self, candle_4h: FourHourCandle,
                               candle_5m: CandleData) -> Optional[TradeSignal]:
        """
        Check for TRUE BUY signal (strong breakout above 4H high with continuation).

        Logic:
        1. Wait for 5M candle to close ABOVE 4H high (breakout) with HIGH volume
        2. Next 5M candle continues ABOVE 4H high (continuation) with HIGH volume
        3. Enter BUY in the breakout direction

        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle

        Returns:
            TradeSignal if TRUE BUY signal detected
        """
        # Step 1: Check for breakout (5M close above 4H high)
        if not self.breakout_state.true_buy_breakout_confirmed:
            if candle_5m.close > candle_4h.high:
                # Store breakout volume (TRUE BREAKOUT specific)
                self.true_breakout_volume = candle_5m.volume

                # Log breakout detection
                self.logger.info(">>> TRUE BUY BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.true_breakout_volume}", self.symbol)

                # Check BREAKOUT confirmations (volume HIGH)
                if not self._check_true_buy_breakout_confirmations():
                    self.logger.info(">>> TRUE BUY BREAKOUT CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_true_buy()
                    return None

                # Breakout confirmed - set flag and wait for continuation
                self.breakout_state.true_buy_breakout_confirmed = True
                self.logger.info("*** TRUE BUY BREAKOUT CONFIRMED (High Volume) ***", self.symbol)
                self.logger.info("Waiting for continuation above 4H High...", self.symbol)

            return None

        # Step 2: Check for continuation (5M close still above 4H high)
        if self.breakout_state.true_buy_breakout_confirmed and not self.breakout_state.true_buy_continuation_confirmed:
            if candle_5m.close > candle_4h.high:
                # Store continuation volume (TRUE BREAKOUT specific)
                self.true_continuation_volume = candle_5m.volume

                # Log continuation detection
                self.logger.info(">>> TRUE BUY CONTINUATION DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Continuation Volume: {self.true_continuation_volume}", self.symbol)

                # Check CONTINUATION confirmations (volume HIGH)
                if not self._check_true_buy_continuation_confirmations():
                    self.logger.info(">>> TRUE BUY CONTINUATION CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_true_buy()
                    return None

                # Continuation confirmed - generate signal
                self.breakout_state.true_buy_continuation_confirmed = True
                self.logger.info("*** TRUE BUY CONTINUATION CONFIRMED (High Volume) ***", self.symbol)
                self.logger.info("=== GENERATING TRUE BUY SIGNAL ===", self.symbol)

                # Generate signal
                signal = self._generate_true_buy_signal(candle_4h, candle_5m)

                # Reset state after signal generation
                self.breakout_state.reset_true_buy()

                return signal
            else:
                # Price fell back below 4H high - breakout failed
                self.logger.info(">>> TRUE BUY BREAKOUT FAILED - Price fell back below 4H High <<<", self.symbol)
                self.breakout_state.reset_true_buy()
                return None

        return None

    def _check_true_buy_breakout_confirmations(self) -> bool:
        """Check TRUE BUY BREAKOUT confirmations (volume HIGH)"""
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check breakout volume is HIGH
            if not self._check_true_breakout_volume():
                return False
        return True

    def _check_true_buy_continuation_confirmations(self) -> bool:
        """Check TRUE BUY CONTINUATION confirmations (volume HIGH)"""
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check continuation volume is HIGH
            if not self._check_continuation_volume():
                return False
        return True

    def _check_true_breakout_volume(self) -> bool:
        """Check true breakout volume is HIGH (for TRUE BREAKOUT strategy)"""
        # Get 5M candles for average volume
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # Check breakout volume is HIGH (using TRUE BREAKOUT volume)
        return self.indicators.is_true_breakout_volume_high(
            self.true_breakout_volume,
            avg_volume,
            self.symbol_params.true_breakout_volume_min,
            self.symbol
        )

    def _check_continuation_volume(self) -> bool:
        """Check continuation volume is HIGH (for TRUE BREAKOUT strategy)"""
        # Get 5M candles for average volume
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # Check continuation volume is HIGH (using TRUE BREAKOUT volume)
        return self.indicators.is_continuation_volume_high(
            self.true_continuation_volume,
            avg_volume,
            self.symbol_params.continuation_volume_min,
            self.symbol
        )

    def _check_true_sell_signal(self, candle_4h: FourHourCandle,
                                candle_5m: CandleData) -> Optional[TradeSignal]:
        """
        Check for TRUE SELL signal (strong breakout below 4H low with continuation).

        Logic:
        1. Wait for 5M candle to close BELOW 4H low (breakout) with HIGH volume
        2. Next 5M candle continues BELOW 4H low (continuation) with HIGH volume
        3. Enter SELL in the breakout direction

        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle

        Returns:
            TradeSignal if TRUE SELL signal detected
        """
        # Step 1: Check for breakout (5M close below 4H low)
        if not self.breakout_state.true_sell_breakout_confirmed:
            if candle_5m.close < candle_4h.low:
                # Store breakout volume (TRUE BREAKOUT specific)
                self.true_breakout_volume = candle_5m.volume

                # Log breakout detection
                self.logger.info(">>> TRUE SELL BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.true_breakout_volume}", self.symbol)

                # Check BREAKOUT confirmations (volume HIGH)
                if not self._check_true_sell_breakout_confirmations():
                    self.logger.info(">>> TRUE SELL BREAKOUT CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_true_sell()
                    return None

                # Breakout confirmed - set flag and wait for continuation
                self.breakout_state.true_sell_breakout_confirmed = True
                self.logger.info("*** TRUE SELL BREAKOUT CONFIRMED (High Volume) ***", self.symbol)
                self.logger.info("Waiting for continuation below 4H Low...", self.symbol)

            return None

        # Step 2: Check for continuation (5M close still below 4H low)
        if self.breakout_state.true_sell_breakout_confirmed and not self.breakout_state.true_sell_continuation_confirmed:
            if candle_5m.close < candle_4h.low:
                # Store continuation volume (TRUE BREAKOUT specific)
                self.true_continuation_volume = candle_5m.volume

                # Log continuation detection
                self.logger.info(">>> TRUE SELL CONTINUATION DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Continuation Volume: {self.true_continuation_volume}", self.symbol)

                # Check CONTINUATION confirmations (volume HIGH)
                if not self._check_true_sell_continuation_confirmations():
                    self.logger.info(">>> TRUE SELL CONTINUATION CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_true_sell()
                    return None

                # Continuation confirmed - generate signal
                self.breakout_state.true_sell_continuation_confirmed = True
                self.logger.info("*** TRUE SELL CONTINUATION CONFIRMED (High Volume) ***", self.symbol)
                self.logger.info("=== GENERATING TRUE SELL SIGNAL ===", self.symbol)

                # Generate signal
                signal = self._generate_true_sell_signal(candle_4h, candle_5m)

                # Reset state after signal generation
                self.breakout_state.reset_true_sell()

                return signal
            else:
                # Price rose back above 4H low - breakout failed
                self.logger.info(">>> TRUE SELL BREAKOUT FAILED - Price rose back above 4H Low <<<", self.symbol)
                self.breakout_state.reset_true_sell()
                return None

        return None

    def _check_true_sell_breakout_confirmations(self) -> bool:
        """Check TRUE SELL BREAKOUT confirmations (volume HIGH)"""
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check breakout volume is HIGH
            if not self._check_true_breakout_volume():
                return False
        return True

    def _check_true_sell_continuation_confirmations(self) -> bool:
        """Check TRUE SELL CONTINUATION confirmations (volume HIGH)"""
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            # Check continuation volume is HIGH
            if not self._check_continuation_volume():
                return False
        return True

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

        # Track confirmations from unified state (always checked, not required)
        # Volume confirmed = both breakout volume LOW and reversal volume HIGH
        volume_confirmed = (self.unified_state.false_buy_volume_ok and
                          self.unified_state.false_buy_reversal_volume_ok)

        # Divergence confirmed = divergence was present at breakout
        divergence_confirmed = self.unified_state.false_buy_divergence_ok

        signal = TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.BUY,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_5m.time,
            reason="False breakout below 4H low with reversal",
            max_spread_percent=self.symbol_params.max_spread_percent,
            volume_confirmed=volume_confirmed,
            divergence_confirmed=divergence_confirmed
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

        # Track confirmations from unified state (always checked, not required)
        # Volume confirmed = both breakout volume LOW and reversal volume HIGH
        volume_confirmed = (self.unified_state.false_sell_volume_ok and
                          self.unified_state.false_sell_reversal_volume_ok)

        # Divergence confirmed = divergence was present at breakout
        divergence_confirmed = self.unified_state.false_sell_divergence_ok

        signal = TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.SELL,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_5m.time,
            reason="False breakout above 4H high with reversal",
            max_spread_percent=self.symbol_params.max_spread_percent,
            volume_confirmed=volume_confirmed,
            divergence_confirmed=divergence_confirmed
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

    def _generate_true_buy_signal(self, candle_4h: FourHourCandle,
                                  candle_5m: CandleData) -> TradeSignal:
        """
        Generate TRUE BUY trade signal (continuation upward).

        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle

        Returns:
            TradeSignal for TRUE BUY
        """
        # Entry: Will use current ASK price at execution
        entry_price = candle_5m.close

        # Stop Loss: Below the 4H high (the breakout level)
        sl_offset = self._calculate_sl_offset(candle_4h.high)

        # Add spread to SL
        spread_price = 0.0
        if self.connector is not None:
            symbol_info = self.connector.get_symbol_info(self.symbol)
            if symbol_info is not None:
                spread_points = self.connector.get_spread(self.symbol)
                if spread_points is not None:
                    point = symbol_info['point']
                    spread_price = spread_points * point

        stop_loss = candle_4h.high - sl_offset - spread_price

        # Take Profit: Based on R:R ratio
        risk = entry_price - stop_loss
        reward = risk * self.strategy_config.risk_reward_ratio
        take_profit = entry_price + reward

        # Track confirmations from unified state (always checked, not required)
        # Volume confirmed = breakout volume HIGH + retest occurred + continuation volume HIGH
        volume_confirmed = (self.unified_state.true_buy_volume_ok and
                          self.unified_state.true_buy_retest_ok and
                          self.unified_state.true_buy_continuation_volume_ok)

        signal = TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.BUY,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_5m.time,
            reason="True breakout above 4H high with continuation",
            max_spread_percent=self.symbol_params.max_spread_percent,
            is_true_breakout=True,
            volume_confirmed=volume_confirmed,
            divergence_confirmed=False  # Not used for true breakouts
        )

        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** TRUE BUY SIGNAL GENERATED ***", self.symbol)
        self.logger.info(f"4H High (breakout level): {candle_4h.high:.5f}", self.symbol)
        self.logger.info(f"SL Offset: {sl_offset:.5f}", self.symbol)
        if spread_price > 0:
            self.logger.info(f"Spread Adjustment: {spread_price:.5f}", self.symbol)
        self.logger.info(f"Entry (reference): {entry_price:.5f} (actual entry will be current ASK)", self.symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f} (below 4H high)", self.symbol)
        self.logger.info(f"Take Profit (reference): {take_profit:.5f}", self.symbol)
        self.logger.info(f"Risk (estimated): {risk:.5f}", self.symbol)
        self.logger.info(f"Reward (estimated): {reward:.5f}", self.symbol)
        self.logger.info(f"R:R Ratio: 1:{self.strategy_config.risk_reward_ratio}", self.symbol)
        self.logger.info("=" * 60, self.symbol)

        return signal

    def _generate_true_sell_signal(self, candle_4h: FourHourCandle,
                                   candle_5m: CandleData) -> TradeSignal:
        """
        Generate TRUE SELL trade signal (continuation downward).

        Args:
            candle_4h: 4H candle
            candle_5m: Latest 5M candle

        Returns:
            TradeSignal for TRUE SELL
        """
        # Entry: Will use current BID price at execution
        entry_price = candle_5m.close

        # Stop Loss: Above the 4H low (the breakout level)
        sl_offset = self._calculate_sl_offset(candle_4h.low)

        # Add spread to SL
        spread_price = 0.0
        if self.connector is not None:
            symbol_info = self.connector.get_symbol_info(self.symbol)
            if symbol_info is not None:
                spread_points = self.connector.get_spread(self.symbol)
                if spread_points is not None:
                    point = symbol_info['point']
                    spread_price = spread_points * point

        stop_loss = candle_4h.low + sl_offset + spread_price

        # Take Profit: Based on R:R ratio
        risk = stop_loss - entry_price
        reward = risk * self.strategy_config.risk_reward_ratio
        take_profit = entry_price - reward

        # Track confirmations from unified state (always checked, not required)
        # Volume confirmed = breakout volume HIGH + retest occurred + continuation volume HIGH
        volume_confirmed = (self.unified_state.true_sell_volume_ok and
                          self.unified_state.true_sell_retest_ok and
                          self.unified_state.true_sell_continuation_volume_ok)

        signal = TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.SELL,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_5m.time,
            reason="True breakout below 4H low with continuation",
            max_spread_percent=self.symbol_params.max_spread_percent,
            is_true_breakout=True,
            volume_confirmed=volume_confirmed,
            divergence_confirmed=False  # Not used for true breakouts
        )

        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** TRUE SELL SIGNAL GENERATED ***", self.symbol)
        self.logger.info(f"4H Low (breakout level): {candle_4h.low:.5f}", self.symbol)
        self.logger.info(f"SL Offset: {sl_offset:.5f}", self.symbol)
        if spread_price > 0:
            self.logger.info(f"Spread Adjustment: {spread_price:.5f}", self.symbol)
        self.logger.info(f"Entry (reference): {entry_price:.5f} (actual entry will be current BID)", self.symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f} (above 4H low)", self.symbol)
        self.logger.info(f"Take Profit (reference): {take_profit:.5f}", self.symbol)
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
        """Reset all breakout states (unified + legacy)"""
        # Reset unified state
        self.unified_state.reset_all()

        # Reset legacy state (for backward compatibility)
        self.breakout_state.reset_buy()
        self.breakout_state.reset_sell()
        self.breakout_state.reset_true_buy()
        self.breakout_state.reset_true_sell()

        # Reset legacy volume tracking
        self.false_breakout_volume = 0
        self.false_reversal_volume = 0
        self.true_breakout_volume = 0
        self.true_continuation_volume = 0

        self.logger.info("Strategy state reset", self.symbol)

