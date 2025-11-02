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
                 symbol_params: SymbolParameters):
        """
        Initialize strategy engine.
        
        Args:
            symbol: Symbol name
            candle_processor: Candle processor instance
            indicators: Technical indicators instance
            strategy_config: Strategy configuration
            symbol_params: Symbol-specific parameters
        """
        self.symbol = symbol
        self.candle_processor = candle_processor
        self.indicators = indicators
        self.strategy_config = strategy_config
        self.symbol_params = symbol_params
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
                self.breakout_state.buy_breakout_confirmed = True
                self.breakout_volume = candle_5m.volume
                
                self.logger.info(">>> BUY BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.breakout_volume}", self.symbol)
                self.logger.info("Waiting for reversal confirmation...", self.symbol)
                
            return None
        
        # Step 2: Check for reversal (5M close back above 4H low)
        if self.breakout_state.buy_breakout_confirmed and not self.breakout_state.buy_reversal_confirmed:
            if candle_5m.close > candle_4h.low:
                self.breakout_state.buy_reversal_confirmed = True
                self.reversal_volume = candle_5m.volume
                
                self.logger.info(">>> BUY REVERSAL DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H Low: {candle_4h.low:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {self.reversal_volume}", self.symbol)
                
                # Now check confirmations
                if self._check_buy_confirmations():
                    # Generate signal
                    signal = self._generate_buy_signal(candle_4h, candle_5m)
                    
                    # Reset state after signal
                    self.breakout_state.reset_buy()
                    
                    return signal
                else:
                    # Confirmations failed, reset and wait for next opportunity
                    self.logger.info(">>> BUY CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_buy()
        
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
                self.breakout_state.sell_breakout_confirmed = True
                self.breakout_volume = candle_5m.volume
                
                self.logger.info(">>> SELL BREAKOUT DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Breakout Volume: {self.breakout_volume}", self.symbol)
                self.logger.info("Waiting for reversal confirmation...", self.symbol)
                
            return None
        
        # Step 2: Check for reversal (5M close back below 4H high)
        if self.breakout_state.sell_breakout_confirmed and not self.breakout_state.sell_reversal_confirmed:
            if candle_5m.close < candle_4h.high:
                self.breakout_state.sell_reversal_confirmed = True
                self.reversal_volume = candle_5m.volume
                
                self.logger.info(">>> SELL REVERSAL DETECTED <<<", self.symbol)
                self.logger.info(f"5M Close: {candle_5m.close:.5f}", self.symbol)
                self.logger.info(f"4H High: {candle_4h.high:.5f}", self.symbol)
                self.logger.info(f"Reversal Volume: {self.reversal_volume}", self.symbol)
                
                # Now check confirmations
                if self._check_sell_confirmations():
                    # Generate signal
                    signal = self._generate_sell_signal(candle_4h, candle_5m)
                    
                    # Reset state after signal
                    self.breakout_state.reset_sell()
                    
                    return signal
                else:
                    # Confirmations failed, reset and wait for next opportunity
                    self.logger.info(">>> SELL CONFIRMATIONS FAILED - Resetting <<<", self.symbol)
                    self.breakout_state.reset_sell()
        
        return None
    
    def _check_buy_confirmations(self) -> bool:
        """Check all confirmations for BUY signal"""
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            if not self._check_volume_confirmation():
                return False
        
        # Divergence confirmation (if enabled)
        if self.symbol_params.divergence_confirmation_enabled:
            if not self._check_buy_divergence():
                return False
        
        return True
    
    def _check_sell_confirmations(self) -> bool:
        """Check all confirmations for SELL signal"""
        # Volume confirmation (if enabled)
        if self.symbol_params.volume_confirmation_enabled:
            if not self._check_volume_confirmation():
                return False
        
        # Divergence confirmation (if enabled)
        if self.symbol_params.divergence_confirmation_enabled:
            if not self._check_sell_divergence():
                return False
        
        return True
    
    def _check_volume_confirmation(self) -> bool:
        """Check volume confirmation"""
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
        breakout_low = self.indicators.is_breakout_volume_low(
            self.breakout_volume,
            avg_volume,
            self.symbol_params.breakout_volume_max,
            self.symbol
        )

        if not breakout_low:
            return False

        # Check reversal volume is HIGH
        reversal_high = self.indicators.is_reversal_volume_high(
            self.reversal_volume,
            avg_volume,
            self.symbol_params.reversal_volume_min,
            self.symbol
        )
        
        return reversal_high
    
    def _check_buy_divergence(self) -> bool:
        """Check for bullish divergence"""
        df = self.candle_processor.get_5m_candles(count=100)
        if df is None:
            return False
        
        return self.indicators.detect_bullish_rsi_divergence(
            df,
            self.symbol_params.rsi_period,
            self.symbol_params.divergence_lookback_period,
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
            self.symbol_params.divergence_lookback_period,
            self.symbol
        )

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
        # Entry: Current 5M close (or slightly above 4H low)
        entry_price = max(candle_5m.close, candle_4h.low + self.strategy_config.entry_offset_points * 0.00001)

        # Stop Loss: Below 4H low
        stop_loss = candle_4h.low - self.strategy_config.stop_loss_offset_points * 0.00001

        # Take Profit: Based on R:R ratio
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
            reason="False breakout below 4H low with reversal"
        )

        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** BUY SIGNAL GENERATED ***", self.symbol)
        self.logger.info(f"Entry: {entry_price:.5f}", self.symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f}", self.symbol)
        self.logger.info(f"Take Profit: {take_profit:.5f}", self.symbol)
        self.logger.info(f"Risk: {risk:.5f}", self.symbol)
        self.logger.info(f"Reward: {reward:.5f}", self.symbol)
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
        # Entry: Current 5M close (or slightly below 4H high)
        entry_price = min(candle_5m.close, candle_4h.high - self.strategy_config.entry_offset_points * 0.00001)

        # Stop Loss: Above 4H high
        stop_loss = candle_4h.high + self.strategy_config.stop_loss_offset_points * 0.00001

        # Take Profit: Based on R:R ratio
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
            reason="False breakout above 4H high with reversal"
        )

        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** SELL SIGNAL GENERATED ***", self.symbol)
        self.logger.info(f"Entry: {entry_price:.5f}", self.symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f}", self.symbol)
        self.logger.info(f"Take Profit: {take_profit:.5f}", self.symbol)
        self.logger.info(f"Risk: {risk:.5f}", self.symbol)
        self.logger.info(f"Reward: {reward:.5f}", self.symbol)
        self.logger.info(f"R:R Ratio: 1:{self.strategy_config.risk_reward_ratio}", self.symbol)
        self.logger.info("=" * 60, self.symbol)

        return signal

    def reset_state(self):
        """Reset breakout state"""
        self.breakout_state.reset_buy()
        self.breakout_state.reset_sell()
        self.breakout_volume = 0
        self.reversal_volume = 0
        self.logger.info("Strategy state reset", self.symbol)

