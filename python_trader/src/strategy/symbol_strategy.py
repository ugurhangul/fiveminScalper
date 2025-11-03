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
from src.strategy.adaptive_filter import AdaptiveFilter
from src.strategy.symbol_tracker import SymbolTracker
from src.risk.risk_manager import RiskManager
from src.config.config import config
from src.config.symbol_optimizer import SymbolOptimizer
from src.utils.logger import get_logger


class SymbolStrategy:
    """Manages trading strategy for a single symbol"""
    
    def __init__(self, symbol: str, connector: MT5Connector, 
                 order_manager: OrderManager, risk_manager: RiskManager,
                 trade_manager: TradeManager, indicators: TechnicalIndicators):
        """
        Initialize symbol strategy.
        
        Args:
            symbol: Symbol name
            connector: MT5 connector instance
            order_manager: Order manager instance
            risk_manager: Risk manager instance
            trade_manager: Trade manager instance
            indicators: Technical indicators instance
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
        
        # Initialize components
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
            config=config.symbol_adaptation
        )
        
        # State
        self.is_initialized = False
        self.last_check_time: Optional[datetime] = None
    
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
            
            # Log initialization
            self.logger.info("=" * 60, self.symbol)
            self.logger.info(f"Initializing strategy for {self.symbol}", self.symbol)
            self.logger.info(f"Category: {SymbolOptimizer.get_category_name(self.category)}", self.symbol)
            self.logger.info(f"Volume confirmation: {self.symbol_params.volume_confirmation_enabled}", self.symbol)
            self.logger.info(f"Divergence confirmation: {self.symbol_params.divergence_confirmation_enabled}", self.symbol)
            self.logger.info("=" * 60, self.symbol)
            
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
        
        # Check for new 5M candle
        if self.candle_processor.is_new_5m_candle():
            self.on_5m_candle()
        
        # Manage open positions
        self._manage_positions()
    
    def on_5m_candle(self):
        """Process new 5-minute candle"""
        # Check for new 4H candle first
        if self.candle_processor.is_new_4h_candle():
            self.on_4h_candle()
        
        # Check for trade signal
        signal = self.strategy_engine.check_for_signal()
        
        if signal:
            self._execute_signal(signal)
    
    def on_4h_candle(self):
        """Process new 4H candle"""
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
        
        # Check if we can open new position
        can_open, reason = self.risk_manager.can_open_new_position(
            config.advanced.magic_number
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
        
        # Update signal with lot size
        signal.lot_size = lot_size
        
        # Validate trade risk
        is_valid, error = self.risk_manager.validate_trade_risk(
            symbol=self.symbol,
            lot_size=lot_size,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )
        
        if not is_valid:
            self.logger.error(f"Trade validation failed: {error}", self.symbol)
            return
        
        # Execute the order
        ticket = self.order_manager.execute_signal(signal)
        
        if ticket:
            self.logger.info(f"Trade executed successfully! Ticket: {ticket}", self.symbol)
            
            # Reset 4H candle after successful trade
            self.candle_processor.reset_4h_candle()
        else:
            self.logger.error("Failed to execute trade", self.symbol)
    
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
    
    def on_position_closed(self, ticket: int, profit: float):
        """
        Called when a position is closed.
        
        Args:
            ticket: Position ticket
            profit: Position profit
        """
        # Update symbol tracker
        self.symbol_tracker.on_trade_closed(profit)
        
        # Update adaptive filter
        is_win = profit > 0
        self.adaptive_filter.on_trade_result(is_win)
        
        # Notify trade manager
        self.trade_manager.on_position_closed(ticket)
        
        # Log result
        result = "WIN" if is_win else "LOSS"
        self.logger.position_closed(
            ticket=ticket,
            symbol=self.symbol,
            profit=profit,
            result=result
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

