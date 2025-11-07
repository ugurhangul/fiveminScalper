"""
Multi-range strategy engine for breakout detection.
Supports multiple independent range configurations operating simultaneously.
"""
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import pandas as pd
from src.models.data_models import (
    MultiRangeBreakoutState, UnifiedBreakoutState, ReferenceCandle, CandleData,
    TradeSignal, PositionType, SymbolParameters, RangeConfig
)
from src.strategy.multi_range_candle_processor import MultiRangeCandleProcessor
from src.indicators.technical_indicators import TechnicalIndicators
from src.strategy.signal_generator import SignalGenerator
from src.config.config import StrategyConfig
from src.utils.logger import get_logger
from src.utils.timeframe_converter import TimeframeConverter
from src.constants import RETEST_RANGE_PERCENT


class MultiRangeStrategyEngine:
    """
    Implements breakout strategy logic for multiple range configurations.
    
    Each range configuration operates independently with its own:
    - Breakout detection
    - Strategy classification
    - Signal generation
    """
    
    def __init__(self, symbol: str, candle_processor: MultiRangeCandleProcessor,
                 indicators: TechnicalIndicators, strategy_config: StrategyConfig,
                 symbol_params: SymbolParameters, connector=None):
        """
        Initialize multi-range strategy engine.

        Args:
            symbol: Symbol name
            candle_processor: Multi-range candle processor instance
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

        # Signal generator for consistent signal creation
        self.signal_generator = SignalGenerator(
            symbol=symbol,
            symbol_params=symbol_params,
            logger=self.logger,
            connector=connector
        )

        # Multi-range breakout state tracking
        self.multi_range_state = MultiRangeBreakoutState()
    
    def check_for_signal(self) -> Optional[TradeSignal]:
        """
        Check all range configurations for signals.
        
        Processes each range independently:
        - Stage 1: Detect breakout
        - Stage 2: Classify strategies
        - Stage 3 & 4: Check for signals
        
        Returns:
            TradeSignal if any range generates a signal, None otherwise
        """
        # Check each range configuration
        for range_id in self.candle_processor.get_all_range_ids():
            # Check if we're in a restricted trading period for this range
            if self._is_in_restricted_period(range_id):
                continue
            
            # Must have a reference candle to trade from
            if not self.candle_processor.has_reference_candle(range_id):
                self.logger.debug(f"No reference candle available yet for {range_id}", self.symbol)
                continue
            
            # Get current reference candle
            candle_ref = self.candle_processor.get_current_reference_candle(range_id)
            if candle_ref is None:
                continue
            
            # Get latest breakout candle
            candle_breakout = self.candle_processor.get_latest_breakout_candle(range_id)
            if candle_breakout is None:
                continue
            
            # Get or create state for this range
            state = self.multi_range_state.get_or_create_state(range_id)
            
            # === STAGE 1: UNIFIED BREAKOUT DETECTION ===
            self._detect_breakout(range_id, state, candle_ref, candle_breakout)
            
            # === STAGE 2: STRATEGY CLASSIFICATION ===
            self._classify_strategies(range_id, state, candle_breakout)
            
            # === STAGE 3 & 4: CHECK FOR SIGNALS ===
            signal = self._check_all_strategies(range_id, state, candle_ref, candle_breakout)
            if signal:
                return signal
            
            # === CLEANUP: Reset if both strategies rejected ===
            if state.both_strategies_rejected():
                self.logger.info(f">>> BOTH STRATEGIES REJECTED [{range_id}] - Resetting <<<", self.symbol)
                state.reset_all()
        
        return None
    
    def _is_in_restricted_period(self, range_id: str) -> bool:
        """
        Check if we're in a restricted trading period for a specific range.
        
        For ranges with specific reference times, trading is suspended while
        the reference candle is forming.
        
        Args:
            range_id: Range configuration identifier
            
        Returns:
            True if in restricted period
        """
        # Get range configuration
        config = self.candle_processor.range_configs.get(range_id)
        if not config or not config.use_specific_time or not config.reference_time:
            return False
        
        current_time = datetime.now(timezone.utc)
        
        # Calculate reference candle duration based on timeframe
        # H4 = 4 hours, M15 = 15 minutes, etc.
        timeframe = config.reference_timeframe
        if timeframe.startswith('H'):
            hours = int(timeframe[1:])
            duration_hours = hours
        elif timeframe.startswith('M'):
            minutes = int(timeframe[1:])
            duration_hours = minutes / 60.0
        else:
            # Unknown timeframe, no restriction
            return False
        
        # Calculate start and end times in minutes since midnight for easier comparison
        ref_start_minutes = config.reference_time.hour * 60 + config.reference_time.minute

        # Calculate duration in minutes
        if timeframe.startswith('H'):
            hours = int(timeframe[1:])
            duration_minutes = hours * 60
        elif timeframe.startswith('M'):
            duration_minutes = int(timeframe[1:])
        else:
            return False

        ref_end_minutes = ref_start_minutes + duration_minutes

        # Current time in minutes since midnight
        current_minutes = current_time.hour * 60 + current_time.minute

        # Check if current time is within the reference candle formation period
        # Handle day wrap-around
        if ref_end_minutes >= 1440:  # 24 hours = 1440 minutes
            # Candle crosses midnight
            in_period = (current_minutes >= ref_start_minutes) or (current_minutes < (ref_end_minutes - 1440))
        else:
            # Normal case - same day
            in_period = (current_minutes >= ref_start_minutes) and (current_minutes < ref_end_minutes)

        if in_period:
            end_hour = (ref_start_minutes + duration_minutes) // 60
            end_minute = (ref_start_minutes + duration_minutes) % 60
            if end_hour >= 24:
                end_hour -= 24
            self.logger.debug(
                f"Trading suspended for {range_id} - Reference candle forming "
                f"({config.reference_time.hour:02d}:{config.reference_time.minute:02d} - "
                f"{end_hour:02d}:{end_minute:02d} UTC)",
                self.symbol
            )

        return in_period
    
    def _detect_breakout(self, range_id: str, state: UnifiedBreakoutState, 
                        candle_ref: ReferenceCandle, candle_breakout: CandleData):
        """
        STAGE 1: Unified breakout detection for a specific range.
        
        Args:
            range_id: Range configuration identifier
            state: Breakout state for this range
            candle_ref: Reference candle (establishes the range)
            candle_breakout: Breakout detection candle
        """
        # Check for timeout on existing breakouts FIRST
        self._check_breakout_timeout(range_id, state, candle_breakout)
        
        # Check for breakout ABOVE reference high
        if not state.breakout_above_detected:
            # Validate: Open INSIDE range AND Close ABOVE high
            open_inside_range = candle_breakout.open >= candle_ref.low and candle_breakout.open <= candle_ref.high
            close_above_high = candle_breakout.close > candle_ref.high
            
            if open_inside_range and close_above_high:
                state.breakout_above_detected = True
                state.breakout_above_volume = candle_breakout.volume
                state.breakout_above_time = candle_breakout.time
                
                self.logger.info("=" * 60, self.symbol)
                self.logger.info(f">>> BREAKOUT ABOVE HIGH DETECTED [{range_id}] <<<", self.symbol)
                self.logger.info(f"Breakout Open: {candle_breakout.open:.5f} (inside range ✓)", self.symbol)
                self.logger.info(f"Breakout Close: {candle_breakout.close:.5f} (above high ✓)", self.symbol)
                self.logger.info(f"Reference High: {candle_ref.high:.5f}", self.symbol)
                self.logger.info(f"Reference Low: {candle_ref.low:.5f}", self.symbol)
                self.logger.info(f"Reference Time: {candle_ref.time}", self.symbol)
                self.logger.info(f"Breakout Time: {candle_breakout.time}", self.symbol)
                self.logger.info(f"Breakout Volume: {candle_breakout.volume}", self.symbol)
                self.logger.info(f"Timeout at: {candle_breakout.time + timedelta(minutes=self.symbol_params.breakout_timeout_candles * 5)}", self.symbol)
                self.logger.info("=" * 60, self.symbol)
        
        # Check for breakout BELOW reference low
        if not state.breakout_below_detected:
            # Validate: Open INSIDE range AND Close BELOW low
            open_inside_range = candle_breakout.open >= candle_ref.low and candle_breakout.open <= candle_ref.high
            close_below_low = candle_breakout.close < candle_ref.low
            
            if open_inside_range and close_below_low:
                state.breakout_below_detected = True
                state.breakout_below_volume = candle_breakout.volume
                state.breakout_below_time = candle_breakout.time
                
                self.logger.info("=" * 60, self.symbol)
                self.logger.info(f">>> BREAKOUT BELOW LOW DETECTED [{range_id}] <<<", self.symbol)
                self.logger.info(f"Breakout Open: {candle_breakout.open:.5f} (inside range ✓)", self.symbol)
                self.logger.info(f"Breakout Close: {candle_breakout.close:.5f} (below low ✓)", self.symbol)
                self.logger.info(f"Reference High: {candle_ref.high:.5f}", self.symbol)
                self.logger.info(f"Reference Low: {candle_ref.low:.5f}", self.symbol)
                self.logger.info(f"Reference Time: {candle_ref.time}", self.symbol)
                self.logger.info(f"Breakout Time: {candle_breakout.time}", self.symbol)
                self.logger.info(f"Breakout Volume: {candle_breakout.volume}", self.symbol)
                # Calculate timeout using TimeframeConverter
                config = self.candle_processor.range_configs.get(range_id)
                if config:
                    minutes_per_candle = TimeframeConverter.get_minutes_per_candle(config.breakout_timeframe)
                    timeout_minutes = self.symbol_params.breakout_timeout_candles * minutes_per_candle
                    self.logger.info(f"Timeout at: {candle_breakout.time + timedelta(minutes=timeout_minutes)}", self.symbol)
                else:
                    self.logger.info(f"Timeout at: {candle_breakout.time + timedelta(minutes=self.symbol_params.breakout_timeout_candles * 5)}", self.symbol)
                self.logger.info("=" * 60, self.symbol)
    
    def _check_breakout_timeout(self, range_id: str, state: UnifiedBreakoutState, candle_breakout: CandleData):
        """
        Check if existing breakouts have timed out for a specific range.
        
        Args:
            range_id: Range configuration identifier
            state: Breakout state for this range
            candle_breakout: Current breakout candle with timestamp
        """
        # Get breakout timeframe to calculate timeout
        config = self.candle_processor.range_configs.get(range_id)
        if not config:
            return

        # Calculate timeout using TimeframeConverter
        minutes_per_candle = TimeframeConverter.get_minutes_per_candle(config.breakout_timeframe)
        timeout_minutes = self.symbol_params.breakout_timeout_candles * minutes_per_candle
        timeout_delta = timedelta(minutes=timeout_minutes)
        
        # Check breakout ABOVE timeout
        if state.breakout_above_detected and state.breakout_above_time:
            age = candle_breakout.time - state.breakout_above_time
            age_minutes = int(age.total_seconds() / 60)
            
            self.logger.info(f"[TIMEOUT CHECK ABOVE {range_id}] Age={age_minutes}min, Limit={timeout_minutes}min", self.symbol)
            
            if age.total_seconds() < 0:
                self.logger.warning(f"Negative breakout age detected: {age.total_seconds()}s - possible timezone issue", self.symbol)
                return
            
            if age > timeout_delta:
                self.logger.info("=" * 60, self.symbol)
                self.logger.info(f">>> BREAKOUT ABOVE TIMEOUT [{range_id}] - Resetting <<<", self.symbol)
                self.logger.info(f"Breakout Age: {age_minutes} minutes", self.symbol)
                self.logger.info(f"Timeout Limit: {timeout_minutes} minutes", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                state.reset_breakout_above()
            else:
                self.logger.info(f"[TIMEOUT CHECK ABOVE {range_id}] Breakout still valid ({age_minutes}/{timeout_minutes} min)", self.symbol)
        
        # Check breakout BELOW timeout
        if state.breakout_below_detected and state.breakout_below_time:
            age = candle_breakout.time - state.breakout_below_time
            age_minutes = int(age.total_seconds() / 60)
            
            self.logger.info(f"[TIMEOUT CHECK BELOW {range_id}] Age={age_minutes}min, Limit={timeout_minutes}min", self.symbol)
            
            if age.total_seconds() < 0:
                self.logger.warning(f"Negative breakout age detected: {age.total_seconds()}s - possible timezone issue", self.symbol)
                return
            
            if age > timeout_delta:
                self.logger.info("=" * 60, self.symbol)
                self.logger.info(f">>> BREAKOUT BELOW TIMEOUT [{range_id}] - Resetting <<<", self.symbol)
                self.logger.info(f"Breakout Age: {age_minutes} minutes", self.symbol)
                self.logger.info(f"Timeout Limit: {timeout_minutes} minutes", self.symbol)
                self.logger.info("=" * 60, self.symbol)
                state.reset_breakout_below()
            else:
                self.logger.info(f"[TIMEOUT CHECK BELOW {range_id}] Breakout still valid ({age_minutes}/{timeout_minutes} min)", self.symbol)

    def _classify_strategies(self, range_id: str, state: UnifiedBreakoutState, candle_breakout: CandleData):
        """
        STAGE 2: Strategy classification for a specific range.

        Args:
            range_id: Range configuration identifier
            state: Breakout state for this range
            candle_breakout: Current breakout candle
        """
        # Get breakout candles for average volume calculation
        df = self.candle_processor.get_breakout_candles(range_id, count=100)
        if df is None:
            return

        # Calculate average volume
        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        # === CLASSIFY BREAKOUT ABOVE (TRUE BUY / FALSE SELL) ===
        if state.breakout_above_detected and not state.true_buy_qualified and not state.false_sell_qualified:
            volume = state.breakout_above_volume

            # Check if qualifies for TRUE BUY (high volume continuation)
            if self.symbol_params.enable_true_breakout_strategy:
                is_high_volume = self.indicators.is_true_breakout_volume_high(
                    volume, avg_volume,
                    self.symbol_params.true_breakout_volume_min,
                    self.symbol
                )

                state.true_buy_qualified = True
                state.true_buy_volume_ok = is_high_volume

                vol_status = "✓" if is_high_volume else "✗"
                self.logger.info(f">>> TRUE BUY QUALIFIED [{range_id}] (High Vol {vol_status}) <<<", self.symbol)
                self.logger.info("Waiting for continuation above reference high...", self.symbol)

            # Check if qualifies for FALSE SELL (low volume reversal)
            if self.symbol_params.enable_false_breakout_strategy:
                is_low_volume = self.indicators.is_breakout_volume_low(
                    volume, avg_volume,
                    self.symbol_params.breakout_volume_max,
                    self.symbol
                )

                # Check divergence (tracked but not required)
                divergence_ok = self._check_sell_divergence(range_id)

                state.false_sell_qualified = True
                state.false_sell_volume_ok = is_low_volume
                state.false_sell_divergence_ok = divergence_ok

                vol_status = "✓" if is_low_volume else "✗"
                div_status = "✓" if divergence_ok else "✗"
                self.logger.info(f">>> FALSE SELL QUALIFIED [{range_id}] (Low Vol {vol_status}, Div {div_status}) <<<", self.symbol)
                self.logger.info("Waiting for reversal back below reference high...", self.symbol)

        # === CLASSIFY BREAKOUT BELOW (TRUE SELL / FALSE BUY) ===
        if state.breakout_below_detected and not state.true_sell_qualified and not state.false_buy_qualified:
            volume = state.breakout_below_volume

            # Check if qualifies for TRUE SELL (high volume continuation)
            if self.symbol_params.enable_true_breakout_strategy:
                is_high_volume = self.indicators.is_true_breakout_volume_high(
                    volume, avg_volume,
                    self.symbol_params.true_breakout_volume_min,
                    self.symbol
                )

                state.true_sell_qualified = True
                state.true_sell_volume_ok = is_high_volume

                vol_status = "✓" if is_high_volume else "✗"
                self.logger.info(f">>> TRUE SELL QUALIFIED [{range_id}] (High Vol {vol_status}) <<<", self.symbol)
                self.logger.info("Waiting for continuation below reference low...", self.symbol)

            # Check if qualifies for FALSE BUY (low volume reversal)
            if self.symbol_params.enable_false_breakout_strategy:
                is_low_volume = self.indicators.is_breakout_volume_low(
                    volume, avg_volume,
                    self.symbol_params.breakout_volume_max,
                    self.symbol
                )

                # Check divergence (tracked but not required)
                divergence_ok = self._check_buy_divergence(range_id)

                state.false_buy_qualified = True
                state.false_buy_volume_ok = is_low_volume
                state.false_buy_divergence_ok = divergence_ok

                vol_status = "✓" if is_low_volume else "✗"
                div_status = "✓" if divergence_ok else "✗"
                self.logger.info(f">>> FALSE BUY QUALIFIED [{range_id}] (Low Vol {vol_status}, Div {div_status}) <<<", self.symbol)
                self.logger.info("Waiting for reversal back above reference low...", self.symbol)

    def _check_all_strategies(self, range_id: str, state: UnifiedBreakoutState,
                             candle_ref: ReferenceCandle, candle_breakout: CandleData) -> Optional[TradeSignal]:
        """
        STAGE 3 & 4: Check all qualified strategies for signals.

        Args:
            range_id: Range configuration identifier
            state: Breakout state for this range
            candle_ref: Reference candle
            candle_breakout: Current breakout candle

        Returns:
            TradeSignal if signal generated, None otherwise
        """
        # === FALSE BUY: Check for reversal back above reference low ===
        if state.false_buy_qualified and not state.false_buy_reversal_detected:
            if candle_breakout.close > candle_ref.low:
                state.false_buy_reversal_detected = True
                state.false_buy_reversal_volume = candle_breakout.volume

                # Check reversal volume (tracked but not required)
                reversal_volume_ok = self._check_unified_reversal_volume(range_id, candle_breakout.volume)
                state.false_buy_reversal_volume_ok = reversal_volume_ok

                vol_status = "✓" if reversal_volume_ok else "✗"
                self.logger.info(f">>> FALSE BUY REVERSAL DETECTED [{range_id}] (Rev Vol {vol_status}) <<<", self.symbol)
                self.logger.info(f"Breakout Close: {candle_breakout.close:.5f}", self.symbol)
                self.logger.info(f"Reference Low: {candle_ref.low:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {candle_breakout.volume}", self.symbol)
                self.logger.info(f"Waiting for next candle to confirm reversal direction...", self.symbol)

        # === FALSE BUY: Check for confirmation candle after reversal ===
        elif state.false_buy_reversal_detected and not state.false_buy_reversal_confirmed:
            # Confirmation: next candle continues in reversal direction (stays above reference low)
            if candle_breakout.close > candle_ref.low:
                state.false_buy_reversal_confirmed = True

                self.logger.info(f">>> FALSE BUY REVERSAL CONFIRMED [{range_id}] <<<", self.symbol)
                self.logger.info(f"Confirmation Close: {candle_breakout.close:.5f}", self.symbol)
                self.logger.info(f"Reference Low: {candle_ref.low:.5f}", self.symbol)
                self.logger.info(f"*** FALSE BUY SIGNAL GENERATED [{range_id}] ***", self.symbol)
                return self._generate_buy_signal(range_id, candle_ref, candle_breakout, is_true_breakout=False)
            else:
                # Reversal failed - price went back below reference low
                self.logger.info(f">>> FALSE BUY REVERSAL FAILED [{range_id}] - Price back below reference low <<<", self.symbol)
                self.logger.info(f"Resetting false buy state...", self.symbol)
                state.false_buy_qualified = False
                state.false_buy_reversal_detected = False
                state.false_buy_reversal_volume = 0
                state.false_buy_volume_ok = False
                state.false_buy_reversal_volume_ok = False

        # === FALSE SELL: Check for reversal back below reference high ===
        if state.false_sell_qualified and not state.false_sell_reversal_detected:
            if candle_breakout.close < candle_ref.high:
                state.false_sell_reversal_detected = True
                state.false_sell_reversal_volume = candle_breakout.volume

                # Check reversal volume (tracked but not required)
                reversal_volume_ok = self._check_unified_reversal_volume(range_id, candle_breakout.volume)
                state.false_sell_reversal_volume_ok = reversal_volume_ok

                vol_status = "✓" if reversal_volume_ok else "✗"
                self.logger.info(f">>> FALSE SELL REVERSAL DETECTED [{range_id}] (Rev Vol {vol_status}) <<<", self.symbol)
                self.logger.info(f"Breakout Close: {candle_breakout.close:.5f}", self.symbol)
                self.logger.info(f"Reference High: {candle_ref.high:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {candle_breakout.volume}", self.symbol)
                self.logger.info(f"Waiting for next candle to confirm reversal direction...", self.symbol)

        # === FALSE SELL: Check for confirmation candle after reversal ===
        elif state.false_sell_reversal_detected and not state.false_sell_reversal_confirmed:
            # Confirmation: next candle continues in reversal direction (stays below reference high)
            if candle_breakout.close < candle_ref.high:
                state.false_sell_reversal_confirmed = True

                self.logger.info(f">>> FALSE SELL REVERSAL CONFIRMED [{range_id}] <<<", self.symbol)
                self.logger.info(f"Confirmation Close: {candle_breakout.close:.5f}", self.symbol)
                self.logger.info(f"Reference High: {candle_ref.high:.5f}", self.symbol)
                self.logger.info(f"*** FALSE SELL SIGNAL GENERATED [{range_id}] ***", self.symbol)
                return self._generate_sell_signal(range_id, candle_ref, candle_breakout, is_true_breakout=False)
            else:
                # Reversal failed - price went back above reference high
                self.logger.info(f">>> FALSE SELL REVERSAL FAILED [{range_id}] - Price back above reference high <<<", self.symbol)
                self.logger.info(f"Resetting false sell state...", self.symbol)
                state.false_sell_qualified = False
                state.false_sell_reversal_detected = False
                state.false_sell_reversal_volume = 0
                state.false_sell_volume_ok = False
                state.false_sell_reversal_volume_ok = False

        # === TRUE BUY: Check for retest and continuation ===
        if state.true_buy_qualified:
            # First check for retest (pullback to reference high)
            if not state.true_buy_retest_detected:
                retest_range = candle_ref.high * RETEST_RANGE_PERCENT
                if abs(candle_breakout.close - candle_ref.high) <= retest_range:
                    state.true_buy_retest_detected = True
                    state.true_buy_retest_ok = True
                    self.logger.info(f">>> TRUE BUY RETEST DETECTED [{range_id}] <<<", self.symbol)
                    self.logger.info(f"Breakout Close: {candle_breakout.close:.5f}", self.symbol)
                    self.logger.info(f"Reference High: {candle_ref.high:.5f}", self.symbol)
                    self.logger.info(f"Retest Range: {retest_range:.5f}", self.symbol)

            # Then check for continuation above reference high
            if not state.true_buy_continuation_detected:
                if candle_breakout.close > candle_ref.high:
                    state.true_buy_continuation_detected = True
                    state.true_buy_continuation_volume = candle_breakout.volume

                    # Check continuation volume (tracked but not required)
                    continuation_volume_ok = self._check_unified_continuation_volume(range_id, candle_breakout.volume)
                    state.true_buy_continuation_volume_ok = continuation_volume_ok

                    vol_status = "✓" if continuation_volume_ok else "✗"
                    self.logger.info(f">>> TRUE BUY CONTINUATION DETECTED [{range_id}] (Cont Vol {vol_status}) <<<", self.symbol)
                    self.logger.info(f"Breakout Close: {candle_breakout.close:.5f}", self.symbol)
                    self.logger.info(f"Reference High: {candle_ref.high:.5f}", self.symbol)
                    self.logger.info(f"Continuation Volume: {candle_breakout.volume}", self.symbol)

                    self.logger.info(f"*** TRUE BUY SIGNAL GENERATED [{range_id}] ***", self.symbol)
                    return self._generate_buy_signal(range_id, candle_ref, candle_breakout, is_true_breakout=True)

        # === TRUE SELL: Check for retest and continuation ===
        if state.true_sell_qualified:
            # First check for retest (pullback to reference low)
            if not state.true_sell_retest_detected:
                retest_range = candle_ref.low * RETEST_RANGE_PERCENT
                if abs(candle_breakout.close - candle_ref.low) <= retest_range:
                    state.true_sell_retest_detected = True
                    state.true_sell_retest_ok = True
                    self.logger.info(f">>> TRUE SELL RETEST DETECTED [{range_id}] <<<", self.symbol)
                    self.logger.info(f"Breakout Close: {candle_breakout.close:.5f}", self.symbol)
                    self.logger.info(f"Reference Low: {candle_ref.low:.5f}", self.symbol)
                    self.logger.info(f"Retest Range: {retest_range:.5f}", self.symbol)

            # Then check for continuation below reference low
            if not state.true_sell_continuation_detected:
                if candle_breakout.close < candle_ref.low:
                    state.true_sell_continuation_detected = True
                    state.true_sell_continuation_volume = candle_breakout.volume

                    # Check continuation volume (tracked but not required)
                    continuation_volume_ok = self._check_unified_continuation_volume(range_id, candle_breakout.volume)
                    state.true_sell_continuation_volume_ok = continuation_volume_ok

                    vol_status = "✓" if continuation_volume_ok else "✗"
                    self.logger.info(f">>> TRUE SELL CONTINUATION DETECTED [{range_id}] (Cont Vol {vol_status}) <<<", self.symbol)
                    self.logger.info(f"Breakout Close: {candle_breakout.close:.5f}", self.symbol)
                    self.logger.info(f"Reference Low: {candle_ref.low:.5f}", self.symbol)
                    self.logger.info(f"Continuation Volume: {candle_breakout.volume}", self.symbol)

                    self.logger.info(f"*** TRUE SELL SIGNAL GENERATED [{range_id}] ***", self.symbol)
                    return self._generate_sell_signal(range_id, candle_ref, candle_breakout, is_true_breakout=True)

        return None

    def _check_unified_reversal_volume(self, range_id: str, reversal_volume: int) -> bool:
        """Check if reversal volume is high (tracked but not required)."""
        df = self.candle_processor.get_breakout_candles(range_id, count=100)
        if df is None:
            return False

        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        return self.indicators.is_reversal_volume_high(
            reversal_volume, avg_volume,
            self.symbol_params.reversal_volume_min,
            self.symbol
        )

    def _check_unified_continuation_volume(self, range_id: str, continuation_volume: int) -> bool:
        """Check if continuation volume is high (tracked but not required)."""
        df = self.candle_processor.get_breakout_candles(range_id, count=100)
        if df is None:
            return False

        avg_volume = self.indicators.calculate_average_volume(
            df['tick_volume'],
            self.symbol_params.volume_average_period
        )

        return self.indicators.is_continuation_volume_high(
            continuation_volume, avg_volume,
            self.symbol_params.continuation_volume_min,
            self.symbol
        )

    def _check_buy_divergence(self, range_id: str) -> bool:
        """Check for bullish divergence (tracked but not required)."""
        df = self.candle_processor.get_breakout_candles(range_id, count=100)
        if df is None:
            return False

        # Check RSI divergence (only RSI is used, matching original StrategyEngine)
        return self.indicators.detect_bullish_rsi_divergence(
            df,
            self.symbol_params.rsi_period,
            self.symbol_params.divergence_lookback,
            self.symbol
        )

    def _check_sell_divergence(self, range_id: str) -> bool:
        """Check for bearish divergence (tracked but not required)."""
        df = self.candle_processor.get_breakout_candles(range_id, count=100)
        if df is None:
            return False

        # Check RSI divergence (only RSI is used, matching original StrategyEngine)
        return self.indicators.detect_bearish_rsi_divergence(
            df,
            self.symbol_params.rsi_period,
            self.symbol_params.divergence_lookback,
            self.symbol
        )

    def _find_lowest_low_in_pattern(self, range_id: str, reference_low: float) -> Optional[float]:
        """
        Find the LOWEST LOW among the last 10 confirmation candles.
        Uses the appropriate timeframe based on range_id:
        - 4H_5M: Uses M5 candles
        - 15M_1M: Uses M1 candles

        Args:
            range_id: Range identifier (e.g., "4H_5M", "15M_1M")
            reference_low: The reference candle's low price (for logging only)

        Returns:
            Lowest low price, or None if no valid candles found
        """
        # Get last 10 confirmation candles for this range
        df = self.candle_processor.get_breakout_candles(range_id, count=10)

        # Delegate to SignalGenerator for pattern detection
        return self.signal_generator.find_lowest_low_in_pattern(df, reference_low)

    def _find_highest_high_in_pattern(self, range_id: str, reference_high: float) -> Optional[float]:
        """
        Find the HIGHEST HIGH among the last 10 confirmation candles.
        Uses the appropriate timeframe based on range_id:
        - 4H_5M: Uses M5 candles
        - 15M_1M: Uses M1 candles

        Args:
            range_id: Range identifier (e.g., "4H_5M", "15M_1M")
            reference_high: The reference candle's high price (for logging only)

        Returns:
            Highest high price, or None if no valid candles found
        """
        # Get last 10 confirmation candles for this range
        df = self.candle_processor.get_breakout_candles(range_id, count=10)

        # Delegate to SignalGenerator for pattern detection
        return self.signal_generator.find_highest_high_in_pattern(df, reference_high)

    def _calculate_sl_offset(self, reference_price: float) -> float:
        """
        Calculate stop loss offset based on configuration.
        Matches the main StrategyEngine logic.

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

        # Fallback to percentage-based calculation
        sl_offset = reference_price * (self.strategy_config.stop_loss_offset_percent / 100.0)
        self.logger.debug(
            f"SL offset (percentage-based): {self.strategy_config.stop_loss_offset_percent}% = {sl_offset:.5f}",
            self.symbol
        )
        return sl_offset

    def _generate_buy_signal(self, range_id: str, candle_ref: ReferenceCandle,
                            candle_breakout: CandleData, is_true_breakout: bool = False) -> TradeSignal:
        """Generate BUY signal for a specific range.

        Args:
            range_id: Range identifier
            candle_ref: Reference candle
            candle_breakout: Breakout candle
            is_true_breakout: True if this is a true breakout (continuation), False if false breakout (reversal)
        """
        # Find the LOWEST LOW among the last 10 candles that closed BELOW reference low
        # This matches the main StrategyEngine logic
        lowest_low = self._find_lowest_low_in_pattern(range_id, candle_ref.low)

        if lowest_low is None:
            self.logger.warning(f"No valid lowest low found for BUY signal [{range_id}]", self.symbol)
            lowest_low = candle_ref.low  # Fallback to reference low

        # Entry: Will use current ASK price at execution
        entry = candle_breakout.close

        # Stop Loss: Below the LOWEST LOW (same logic for both TRUE and FALSE strategies)
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
                        f"Adding spread to BUY SL [{range_id}]: {spread_points:.1f} points = {spread_price:.5f}",
                        self.symbol
                    )

        sl = lowest_low - sl_offset - spread_price

        # Take Profit: Based on R:R ratio
        # Note: TP will be recalculated in order_manager using actual execution price
        risk = entry - sl
        tp = entry + (risk * self.strategy_config.risk_reward_ratio)

        # Get state for this range to track confirmations
        state = self.multi_range_state.get_state(range_id)

        # Determine confirmation status based on strategy type
        if is_true_breakout:
            # TRUE BREAKOUT: Volume confirmed = breakout volume HIGH + retest occurred + continuation volume HIGH
            volume_confirmed = (state.true_buy_volume_ok and
                              state.true_buy_retest_ok and
                              state.true_buy_continuation_volume_ok)
            divergence_confirmed = False  # Not used for true breakouts
        else:
            # FALSE BREAKOUT: Volume confirmed = breakout volume LOW + reversal volume HIGH
            volume_confirmed = (state.false_buy_volume_ok and
                              state.false_buy_reversal_volume_ok)
            divergence_confirmed = state.false_buy_divergence_ok

        return TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.BUY,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_breakout.time,
            range_id=range_id,
            reason=f"{'True' if is_true_breakout else 'False'} breakout strategy - Range: {range_id}",
            max_spread_percent=self.symbol_params.max_spread_percent,
            is_true_breakout=is_true_breakout,
            volume_confirmed=volume_confirmed,
            divergence_confirmed=divergence_confirmed
        )

    def _generate_sell_signal(self, range_id: str, candle_ref: ReferenceCandle,
                             candle_breakout: CandleData, is_true_breakout: bool = False) -> TradeSignal:
        """Generate SELL signal for a specific range.

        Args:
            range_id: Range identifier
            candle_ref: Reference candle
            candle_breakout: Breakout candle
            is_true_breakout: True if this is a true breakout (continuation), False if false breakout (reversal)
        """
        # Find the HIGHEST HIGH among the last 10 candles that closed ABOVE reference high
        # This matches the main StrategyEngine logic
        highest_high = self._find_highest_high_in_pattern(range_id, candle_ref.high)

        if highest_high is None:
            self.logger.warning(f"No valid highest high found for SELL signal [{range_id}]", self.symbol)
            highest_high = candle_ref.high  # Fallback to reference high

        # Entry: Will use current BID price at execution
        entry = candle_breakout.close

        # Stop Loss: Above the HIGHEST HIGH (same logic for both TRUE and FALSE strategies)
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
                        f"Adding spread to SELL SL [{range_id}]: {spread_points:.1f} points = {spread_price:.5f}",
                        self.symbol
                    )

        sl = highest_high + sl_offset + spread_price

        # Take Profit: Based on R:R ratio
        # Note: TP will be recalculated in order_manager using actual execution price
        risk = sl - entry
        tp = entry - (risk * self.strategy_config.risk_reward_ratio)

        # Get state for this range to track confirmations
        state = self.multi_range_state.get_state(range_id)

        # Determine confirmation status based on strategy type
        if is_true_breakout:
            # TRUE BREAKOUT: Volume confirmed = breakout volume HIGH + retest occurred + continuation volume HIGH
            volume_confirmed = (state.true_sell_volume_ok and
                              state.true_sell_retest_ok and
                              state.true_sell_continuation_volume_ok)
            divergence_confirmed = False  # Not used for true breakouts
        else:
            # FALSE BREAKOUT: Volume confirmed = breakout volume LOW + reversal volume HIGH
            volume_confirmed = (state.false_sell_volume_ok and
                              state.false_sell_reversal_volume_ok)
            divergence_confirmed = state.false_sell_divergence_ok

        return TradeSignal(
            symbol=self.symbol,
            signal_type=PositionType.SELL,
            entry_price=entry,
            stop_loss=sl,
            take_profit=tp,
            lot_size=0.0,  # Will be calculated by risk manager
            timestamp=candle_breakout.time,
            range_id=range_id,
            reason=f"{'True' if is_true_breakout else 'False'} breakout strategy - Range: {range_id}",
            max_spread_percent=self.symbol_params.max_spread_percent,
            is_true_breakout=is_true_breakout,
            volume_confirmed=volume_confirmed,
            divergence_confirmed=divergence_confirmed
        )

    def reset_range(self, range_id: str):
        """Reset state for a specific range configuration."""
        self.multi_range_state.reset_range(range_id)
        self.logger.info(f"Range state reset for {range_id}", self.symbol)

    def reset_all_ranges(self):
        """Reset all range states."""
        self.multi_range_state.reset_all()
        self.logger.info("All range states reset", self.symbol)

