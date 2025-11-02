"""
Trade management for breakeven and trailing stops.
Ported from FMS_TradeManagement.mqh
"""
from typing import List, Set
from src.models.data_models import PositionInfo, PositionType
from src.execution.order_manager import OrderManager
from src.core.mt5_connector import MT5Connector
from src.config.config import TrailingStopConfig
from src.utils.logger import get_logger


class TradeManager:
    """Manages open positions (breakeven, trailing stop)"""
    
    def __init__(self, connector: MT5Connector, order_manager: OrderManager,
                 trailing_config: TrailingStopConfig, use_breakeven: bool,
                 breakeven_trigger_rr: float):
        """
        Initialize trade manager.
        
        Args:
            connector: MT5 connector instance
            order_manager: Order manager instance
            trailing_config: Trailing stop configuration
            use_breakeven: Enable breakeven management
            breakeven_trigger_rr: R:R ratio to trigger breakeven
        """
        self.connector = connector
        self.order_manager = order_manager
        self.trailing_config = trailing_config
        self.use_breakeven = use_breakeven
        self.breakeven_trigger_rr = breakeven_trigger_rr
        self.logger = get_logger()
        
        # Track positions that have been moved to breakeven
        self.breakeven_positions: Set[int] = set()
        
        # Track positions with trailing stop activated
        self.trailing_positions: Set[int] = set()
    
    def manage_positions(self, positions: List[PositionInfo]):
        """
        Manage all open positions.
        
        Args:
            positions: List of open positions
        """
        for pos in positions:
            # Check breakeven
            if self.use_breakeven and pos.ticket not in self.breakeven_positions:
                self._check_breakeven(pos)
            
            # Check trailing stop
            if self.trailing_config.use_trailing_stop:
                self._check_trailing_stop(pos)
    
    def _check_breakeven(self, pos: PositionInfo):
        """
        Check if position should be moved to breakeven.
        
        Args:
            pos: Position info
        """
        # Check if position has reached breakeven trigger
        if pos.current_rr >= self.breakeven_trigger_rr:
            # Move SL to breakeven (entry price)
            success = self.order_manager.modify_position(
                ticket=pos.ticket,
                sl=pos.open_price,
                tp=pos.tp
            )
            
            if success:
                self.breakeven_positions.add(pos.ticket)
                self.logger.info(
                    f"Position {pos.ticket} moved to BREAKEVEN at {pos.open_price:.5f}",
                    pos.symbol
                )
                self.logger.info(
                    f"Triggered at {pos.current_rr:.2f} R:R (trigger: {self.breakeven_trigger_rr})",
                    pos.symbol
                )
    
    def _check_trailing_stop(self, pos: PositionInfo):
        """
        Check if trailing stop should be applied.
        
        Args:
            pos: Position info
        """
        # Check if position has reached trailing trigger
        if pos.current_rr < self.trailing_config.trailing_stop_trigger_rr:
            return
        
        # Mark as trailing if not already
        if pos.ticket not in self.trailing_positions:
            self.trailing_positions.add(pos.ticket)
            self.logger.info(
                f"Trailing stop ACTIVATED for position {pos.ticket}",
                pos.symbol
            )
        
        # Get symbol info for point value
        symbol_info = self.connector.get_symbol_info(pos.symbol)
        if symbol_info is None:
            return
        
        point = symbol_info['point']
        trailing_distance = self.trailing_config.trailing_stop_distance * point
        
        # Calculate new SL based on position type
        if pos.position_type == PositionType.BUY:
            # For BUY, trail below current price
            new_sl = pos.current_price - trailing_distance
            
            # Only move SL up, never down
            if new_sl > pos.sl:
                success = self.order_manager.modify_position(
                    ticket=pos.ticket,
                    sl=new_sl,
                    tp=pos.tp
                )
                
                if success:
                    self.logger.info(
                        f"Trailing stop updated for BUY position {pos.ticket}",
                        pos.symbol
                    )
                    self.logger.info(
                        f"New SL: {new_sl:.5f} (was {pos.sl:.5f})",
                        pos.symbol
                    )
        
        else:  # SELL
            # For SELL, trail above current price
            new_sl = pos.current_price + trailing_distance
            
            # Only move SL down, never up
            if new_sl < pos.sl or pos.sl == 0:
                success = self.order_manager.modify_position(
                    ticket=pos.ticket,
                    sl=new_sl,
                    tp=pos.tp
                )
                
                if success:
                    self.logger.info(
                        f"Trailing stop updated for SELL position {pos.ticket}",
                        pos.symbol
                    )
                    self.logger.info(
                        f"New SL: {new_sl:.5f} (was {pos.sl:.5f})",
                        pos.symbol
                    )
    
    def on_position_closed(self, ticket: int):
        """
        Called when a position is closed.
        
        Args:
            ticket: Position ticket
        """
        # Remove from tracking sets
        self.breakeven_positions.discard(ticket)
        self.trailing_positions.discard(ticket)
    
    def reset(self):
        """Reset all tracking"""
        self.breakeven_positions.clear()
        self.trailing_positions.clear()
        self.logger.info("Trade manager reset")

