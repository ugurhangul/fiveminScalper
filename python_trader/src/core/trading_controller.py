"""
Multi-symbol trading controller.
Orchestrates concurrent trading across multiple symbols.
"""
import threading
import time
from typing import Dict, List
from datetime import datetime

from src.core.mt5_connector import MT5Connector
from src.execution.order_manager import OrderManager
from src.execution.trade_manager import TradeManager
from src.indicators.technical_indicators import TechnicalIndicators
from src.risk.risk_manager import RiskManager
from src.strategy.symbol_strategy import SymbolStrategy
from src.config.config import config
from src.utils.logger import get_logger


class TradingController:
    """Controls multi-symbol trading operations"""
    
    def __init__(self, connector: MT5Connector, order_manager: OrderManager,
                 risk_manager: RiskManager, trade_manager: TradeManager,
                 indicators: TechnicalIndicators):
        """
        Initialize trading controller.
        
        Args:
            connector: MT5 connector instance
            order_manager: Order manager instance
            risk_manager: Risk manager instance
            trade_manager: Trade manager instance
            indicators: Technical indicators instance
        """
        self.connector = connector
        self.order_manager = order_manager
        self.risk_manager = risk_manager
        self.trade_manager = trade_manager
        self.indicators = indicators
        self.logger = get_logger()
        
        # Symbol strategies
        self.strategies: Dict[str, SymbolStrategy] = {}
        
        # Threading
        self.threads: Dict[str, threading.Thread] = {}
        self.running = False
        self.lock = threading.Lock()
        
        # Monitoring
        self.last_position_check = datetime.now()
    
    def initialize(self, symbols: List[str]) -> bool:
        """
        Initialize strategies for all symbols.
        
        Args:
            symbols: List of symbol names
            
        Returns:
            True if all strategies initialized successfully
        """
        self.logger.info("=" * 60)
        self.logger.info("Initializing Trading Controller")
        self.logger.info(f"Symbols: {', '.join(symbols)}")
        self.logger.info("=" * 60)
        
        success_count = 0
        
        for symbol in symbols:
            try:
                # Create strategy for symbol
                strategy = SymbolStrategy(
                    symbol=symbol,
                    connector=self.connector,
                    order_manager=self.order_manager,
                    risk_manager=self.risk_manager,
                    trade_manager=self.trade_manager,
                    indicators=self.indicators
                )
                
                # Initialize strategy
                if strategy.initialize():
                    self.strategies[symbol] = strategy
                    success_count += 1
                    self.logger.info(f"✓ {symbol} initialized", symbol)
                else:
                    self.logger.error(f"✗ {symbol} initialization failed", symbol)
                    
            except Exception as e:
                self.logger.error(f"Error initializing {symbol}: {e}", symbol)
        
        self.logger.info("=" * 60)
        self.logger.info(f"Initialized {success_count}/{len(symbols)} symbols")
        self.logger.info("=" * 60)
        
        return success_count > 0
    
    def start(self):
        """Start trading for all symbols"""
        if not self.strategies:
            self.logger.error("No strategies initialized")
            return
        
        self.running = True
        
        self.logger.info("=" * 60)
        self.logger.info("Starting Multi-Symbol Trading")
        self.logger.info(f"Active symbols: {len(self.strategies)}")
        self.logger.info("=" * 60)
        
        # Start a thread for each symbol
        for symbol, strategy in self.strategies.items():
            thread = threading.Thread(
                target=self._symbol_worker,
                args=(symbol, strategy),
                name=f"Strategy-{symbol}",
                daemon=True
            )
            thread.start()
            self.threads[symbol] = thread
            self.logger.info(f"Started thread for {symbol}", symbol)
        
        # Start position monitoring thread
        monitor_thread = threading.Thread(
            target=self._position_monitor,
            name="PositionMonitor",
            daemon=True
        )
        monitor_thread.start()
        self.logger.info("Started position monitor thread")
        
        self.logger.info("=" * 60)
        self.logger.info("All threads started successfully")
        self.logger.info("=" * 60)
    
    def _symbol_worker(self, symbol: str, strategy: SymbolStrategy):
        """
        Worker thread for a single symbol.
        
        Args:
            symbol: Symbol name
            strategy: Symbol strategy instance
        """
        self.logger.info(f"Worker thread started for {symbol}", symbol)
        
        while self.running:
            try:
                # Process tick
                strategy.on_tick()
                
                # Sleep for 1 second
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in worker thread: {e}", symbol)
                time.sleep(5)  # Wait before retrying
        
        self.logger.info(f"Worker thread stopped for {symbol}", symbol)
    
    def _position_monitor(self):
        """Monitor all positions and check for closed trades"""
        self.logger.info("Position monitor thread started")
        
        # Track known positions
        known_positions = set()
        
        while self.running:
            try:
                # Get all positions
                positions = self.connector.get_positions(
                    magic_number=config.advanced.magic_number
                )
                
                # Current position tickets
                current_tickets = {pos.ticket for pos in positions}
                
                # Check for closed positions
                closed_tickets = known_positions - current_tickets
                
                for ticket in closed_tickets:
                    # Position was closed, need to find which symbol it was
                    # We'll check history to get the profit
                    self._handle_closed_position(ticket)
                
                # Update known positions
                known_positions = current_tickets
                
                # Sleep for 5 seconds
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error in position monitor: {e}")
                time.sleep(10)
        
        self.logger.info("Position monitor thread stopped")
    
    def _handle_closed_position(self, ticket: int):
        """
        Handle a closed position.
        
        Args:
            ticket: Position ticket
        """
        # Note: In a real implementation, we would query MT5 history
        # to get the symbol and profit. For now, we'll just log it.
        self.logger.info(f"Position {ticket} closed (detected by monitor)")
        
        # TODO: Query MT5 history to get symbol and profit
        # Then call strategy.on_position_closed(ticket, profit)
    
    def stop(self):
        """Stop all trading"""
        self.logger.info("Stopping trading controller...")
        
        self.running = False
        
        # Wait for all threads to finish
        for symbol, thread in self.threads.items():
            self.logger.info(f"Waiting for {symbol} thread to stop...", symbol)
            thread.join(timeout=5)
        
        # Shutdown all strategies
        for symbol, strategy in self.strategies.items():
            strategy.shutdown()
        
        self.logger.info("Trading controller stopped")
    
    def get_status(self) -> dict:
        """
        Get status of all strategies.
        
        Returns:
            Dictionary with status for each symbol
        """
        with self.lock:
            return {
                symbol: strategy.get_status()
                for symbol, strategy in self.strategies.items()
            }
    
    def log_status(self):
        """Log status of all strategies"""
        status = self.get_status()
        
        self.logger.info("=" * 60)
        self.logger.info("TRADING STATUS")
        self.logger.info("=" * 60)
        
        for symbol, info in status.items():
            self.logger.info(f"\n{symbol}:", symbol)
            self.logger.info(f"  Category: {info['category']}", symbol)
            self.logger.info(f"  Can Trade: {info['can_trade']}", symbol)
            self.logger.info(f"  Has 4H Candle: {info['has_4h_candle']}", symbol)
            
            stats = info['stats']
            self.logger.info(f"  Total Trades: {stats.total_trades}", symbol)
            self.logger.info(f"  Win Rate: {stats.win_rate:.1f}%", symbol)
            self.logger.info(f"  Net Profit: ${stats.net_profit:.2f}", symbol)
            
            filters = info['filter_status']
            self.logger.info(f"  Volume Filter: {'ON' if filters['volume_active'] else 'OFF'}", symbol)
            self.logger.info(f"  Divergence Filter: {'ON' if filters['divergence_active'] else 'OFF'}", symbol)
        
        self.logger.info("=" * 60)

