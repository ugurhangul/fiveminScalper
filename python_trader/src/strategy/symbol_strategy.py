"""
Per-symbol strategy orchestrator.
Combines all components for trading a single symbol.
"""
from typing import Optional
from datetime import datetime

from src.models.data_models import TradeSignal, SymbolParameters, SymbolCategory
from src.core.mt5_connector import MT5Connector
from src.execution.order_manager import OrderManager
from src.execution.trade_manager import TradeManager
from src.indicators.technical_indicators import TechnicalIndicators
from src.strategy.candle_processor import CandleProcessor
from src.strategy.strategy_engine import StrategyEngine
from src.strategy.multi_range_candle_processor import MultiRangeCandleProcessor
from src.strategy.multi_range_strategy_engine import MultiRangeStrategyEngine
from src.strategy.adaptive_filter import AdaptiveFilter
from src.strategy.symbol_tracker import SymbolTracker
from src.strategy.symbol_performance_persistence import SymbolPerformancePersistence
from src.risk.risk_manager import RiskManager
from src.config.config import config
from src.config.symbol_optimizer import SymbolOptimizer
from src.utils.logger import get_logger


class SymbolStrategy:
    """Manages trading strategy for a single symbol"""

    def __init__(self, symbol: str, connector: MT5Connector,
                 order_manager: OrderManager, risk_manager: RiskManager,
                 trade_manager: TradeManager, indicators: TechnicalIndicators,
                 symbol_persistence: Optional[SymbolPerformancePersistence] = None):
        """
        Initialize symbol strategy.

        Args:
            symbol: Symbol name
            connector: MT5 connector instance
            order_manager: Order manager instance
            risk_manager: Risk manager instance
            trade_manager: Trade manager instance
            indicators: Technical indicators instance
            symbol_persistence: Symbol performance persistence instance (optional)
        """
        self.symbol = symbol
        self.connector = connector
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.trade_manager = trade_manager
        self.indicators = indicators
        self.logger = get_logger()
        
        # Detect symbol category and get optimized parameters
        self.category, self.symbol_params = SymbolOptimizer.get_symbol_parameters(
            symbol,
            SymbolParameters()  # Default parameters
        )

        # Set initial confirmation states based on config
        # Adaptive filter will manage these based on performance
        self.symbol_params.volume_confirmation_enabled = config.adaptive_filters.start_with_filters_enabled
        self.symbol_params.divergence_confirmation_enabled = config.adaptive_filters.start_with_filters_enabled

        self.logger.info(f"Symbol category: {SymbolOptimizer.get_category_name(self.category)}", symbol)

        # Initialize components based on multi-range mode
        if config.advanced.use_multi_range_mode and config.range_config.enabled:
            # Multi-range mode: Use new multi-range processors
            self.logger.info("Initializing MULTI-RANGE mode", symbol)
            self.logger.info(f"Active ranges: {len(config.range_config.ranges)}", symbol)
            for range_cfg in config.range_config.ranges:
                self.logger.info(f"  - {range_cfg}", symbol)

            self.candle_processor = MultiRangeCandleProcessor(
                symbol=symbol,
                connector=connector,
                range_configs=config.range_config.ranges
            )

            self.strategy_engine = MultiRangeStrategyEngine(
                symbol=symbol,
                candle_processor=self.candle_processor,
                indicators=indicators,
                strategy_config=config.strategy,
                symbol_params=self.symbol_params,
                connector=connector
            )
        else:
            # Legacy single-range mode: Use original processors
            self.logger.info("Initializing SINGLE-RANGE mode (legacy)", symbol)

            self.candle_processor = CandleProcessor(
                symbol=symbol,
                connector=connector,
                use_only_00_utc=config.advanced.use_only_00_utc_candle
            )

            self.strategy_engine = StrategyEngine(
                symbol=symbol,
                candle_processor=self.candle_processor,
                indicators=indicators,
                strategy_config=config.strategy,
                symbol_params=self.symbol_params,
                connector=connector
            )
        
        self.adaptive_filter = AdaptiveFilter(
            symbol=symbol,
            config=config.adaptive_filters,
            symbol_params=self.symbol_params
        )

        self.symbol_tracker = SymbolTracker(
            symbol=symbol,
            config=config.symbol_adaptation,
            persistence=symbol_persistence
        )

        # State
        self.is_initialized = False
        self.last_check_time: Optional[datetime] = None
        self.is_multi_range_mode = config.advanced.use_multi_range_mode and config.range_config.enabled
    
    def initialize(self) -> bool:
        """
        Initialize the strategy.
        
        Returns:
            True if initialization successful
        """
        try:
            # Verify symbol exists
            symbol_info = self.connector.get_symbol_info(self.symbol)
            if symbol_info is None:
                self.logger.error(f"Symbol {self.symbol} not found in MT5")
                return False
            

            
            self.is_initialized = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing strategy: {e}", self.symbol)
            return False
    
    def on_tick(self):
        """Process tick event (called every second or on price update)"""
        if not self.is_initialized:
            return

        # Check if symbol can trade
        if not self.symbol_tracker.can_trade():
            return

        if self.is_multi_range_mode:
            # Multi-range mode: Check each range independently
            self._check_multi_range_candles()
        else:
            # Legacy single-range mode
            if self.candle_processor.is_new_5m_candle():
                self.on_5m_candle()

        # Manage open positions
        self._manage_positions()

    def _check_multi_range_candles(self):
        """Check for new candles in multi-range mode"""
        # In multi-range mode, we check for new breakout candles for each range
        # and let the strategy engine handle the logic
        for range_id in self.candle_processor.get_all_range_ids():
            # Check for new reference candle
            if self.candle_processor.is_new_reference_candle(range_id):
                self._on_new_reference_candle(range_id)

            # Check for new breakout candle
            if self.candle_processor.is_new_breakout_candle(range_id):
                self._on_new_breakout_candle(range_id)

    def _on_new_reference_candle(self, range_id: str):
        """Process new reference candle for a specific range"""
        # Reset strategy state for this range
        if hasattr(self.strategy_engine, 'reset_range'):
            self.strategy_engine.reset_range(range_id)

    def _on_new_breakout_candle(self, range_id: str):
        """Process new breakout candle for a specific range"""
        # Check for trade signal
        signal = self.strategy_engine.check_for_signal()

        if signal:
            self._execute_signal(signal)

    def on_5m_candle(self):
        """Process new 5-minute candle (legacy single-range mode)"""
        # Check for new 4H candle first
        if self.candle_processor.is_new_4h_candle():
            self.on_4h_candle()

        # Check for trade signal
        signal = self.strategy_engine.check_for_signal()

        if signal:
            self._execute_signal(signal)

    def on_4h_candle(self):
        """Process new 4H candle (legacy single-range mode)"""
        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** NEW 4H CANDLE ***", self.symbol)
        self.logger.info("=" * 60, self.symbol)

        # Reset strategy state for new 4H candle
        self.strategy_engine.reset_state()

        # Log candle status
        self.candle_processor.log_candle_status()
    
    def _execute_signal(self, signal: TradeSignal):
        """
        Execute a trade signal.

        Args:
            signal: Trade signal to execute
        """
        self.logger.info("=" * 60, self.symbol)
        self.logger.info("*** TRADE SIGNAL RECEIVED ***", self.symbol)
        self.logger.info("=" * 60, self.symbol)

        # Log confirmation status
        if signal.all_confirmations_met:
            self.logger.info(">>> ALL CONFIRMATIONS MET <<<", self.symbol)
            self.logger.info(f"Volume Confirmed: {signal.volume_confirmed}", self.symbol)
            self.logger.info(f"Divergence Confirmed: {signal.divergence_confirmed}", self.symbol)
        else:
            self.logger.info("Confirmations status:", self.symbol)
            self.logger.info(f"Volume Confirmed: {signal.volume_confirmed}", self.symbol)
            self.logger.info(f"Divergence Confirmed: {signal.divergence_confirmed}", self.symbol)

        # Check if we can open new position
        # Allows up to 2 positions of same type if all confirmations are met
        can_open, reason = self.risk_manager.can_open_new_position(
            magic_number=config.advanced.magic_number,
            symbol=self.symbol,
            position_type=signal.signal_type,
            all_confirmations_met=signal.all_confirmations_met
        )

        if not can_open:
            self.logger.warning(f"Cannot open position: {reason}", self.symbol)
            return
        
        # Calculate lot size
        lot_size = self.risk_manager.calculate_lot_size(
            symbol=self.symbol,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )
        
        if lot_size <= 0:
            self.logger.error("Invalid lot size calculated", self.symbol)
            return
        
        # Validate trade risk (may adjust lot size if risk is too high)
        is_valid, error, adjusted_lot_size = self.risk_manager.validate_trade_risk(
            symbol=self.symbol,
            lot_size=lot_size,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )

        if not is_valid:
            self.logger.error(f"Trade validation failed: {error}", self.symbol)
            return

        # Use the adjusted lot size (may be same as original or reduced)
        signal.lot_size = adjusted_lot_size
        
        # Execute the order
        ticket = self.order_manager.execute_signal(signal)

        if ticket:
            self.logger.info(f"Trade executed successfully! Ticket: {ticket}", self.symbol)
        else:
            self.logger.trade_error(
                symbol=self.symbol,
                error_type="Trade Execution",
                error_message="Failed to execute trade signal",
                context={
                    "signal_type": signal.signal_type.value.upper(),
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "lot_size": signal.lot_size
                }
            )
    
    def _manage_positions(self):
        """Manage open positions for this symbol"""
        # Get positions for this symbol
        positions = self.connector.get_positions(
            symbol=self.symbol,
            magic_number=config.advanced.magic_number
        )
        
        if not positions:
            return
        
        # Manage each position
        self.trade_manager.manage_positions(positions)
    
    def on_position_closed(self, ticket: int, profit: float, rr_achieved: float = 0.0):
        """
        Called when a position is closed.

        Args:
            ticket: Position ticket
            profit: Position profit
            rr_achieved: Risk/reward ratio achieved (optional)
        """
        # Update symbol tracker
        self.symbol_tracker.on_trade_closed(profit)

        # Update adaptive filter
        is_win = profit > 0
        self.adaptive_filter.on_trade_result(is_win)

        # Notify trade manager
        self.trade_manager.on_position_closed(ticket)

        # Log result
        self.logger.position_closed(
            ticket=ticket,
            symbol=self.symbol,
            profit=profit,
            is_win=is_win,
            rr_achieved=rr_achieved
        )
    
    def get_status(self) -> dict:
        """
        Get current strategy status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'symbol': self.symbol,
            'category': SymbolOptimizer.get_category_name(self.category),
            'can_trade': self.symbol_tracker.can_trade(),
            'has_4h_candle': self.candle_processor.has_4h_candle(),
            'stats': self.symbol_tracker.get_stats(),
            'filter_status': self.adaptive_filter.get_filter_status()
        }
    
    def shutdown(self):
        """Shutdown the strategy"""
        self.logger.info(f"Shutting down strategy for {self.symbol}", self.symbol)
        self.is_initialized = False

