"""
Trade management for breakeven and trailing stops.
Ported from FMS_TradeManagement.mqh
"""
from typing import List, Set, Dict, Optional
from src.models.data_models import PositionInfo, PositionType
from src.execution.order_manager import OrderManager
from src.core.mt5_connector import MT5Connector
from src.config.config import TrailingStopConfig
from src.utils.logger import get_logger


class TradeManager:
    """Manages open positions (breakeven, trailing stop)"""

    def __init__(self, connector: MT5Connector, order_manager: OrderManager,
                 trailing_config: TrailingStopConfig, use_breakeven: bool,
                 breakeven_trigger_rr: float, indicators=None):
        """
        Initialize trade manager.

        Args:
            connector: MT5 connector instance
            order_manager: Order manager instance
            trailing_config: Trailing stop configuration
            use_breakeven: Enable breakeven management
            breakeven_trigger_rr: R:R ratio to trigger breakeven
            indicators: TechnicalIndicators instance (optional, needed for ATR trailing)
        """
        self.connector = connector
        self.order_manager = order_manager
        self.trailing_config = trailing_config
        self.use_breakeven = use_breakeven
        self.breakeven_trigger_rr = breakeven_trigger_rr
        self.indicators = indicators
        self.logger = get_logger()

        # Track positions that have been moved to breakeven
        self.breakeven_positions: Set[int] = set()

        # Track positions with trailing stop activated
        self.trailing_positions: Set[int] = set()

        # Track ATR trailing stop data per position
        # Format: {ticket: {'peak_price': float, 'atr': float}}
        self.atr_trailing_data: Dict[int, Dict[str, float]] = {}
    
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

        # Use ATR-based trailing if enabled
        if self.trailing_config.use_atr_trailing:
            self._check_atr_trailing_stop(pos)
        else:
            self._check_fixed_trailing_stop(pos)

    def _check_fixed_trailing_stop(self, pos: PositionInfo):
        """
        Check fixed-distance trailing stop.

        Args:
            pos: Position info
        """
        # Mark as trailing if not already
        if pos.ticket not in self.trailing_positions:
            self.trailing_positions.add(pos.ticket)
            self.logger.info(
                f"Fixed trailing stop ACTIVATED for position {pos.ticket}",
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
                        f"Fixed trailing stop updated for BUY position {pos.ticket}",
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
                        f"Fixed trailing stop updated for SELL position {pos.ticket}",
                        pos.symbol
                    )
                    self.logger.info(
                        f"New SL: {new_sl:.5f} (was {pos.sl:.5f})",
                        pos.symbol
                    )

    def _check_atr_trailing_stop(self, pos: PositionInfo):
        """
        Check ATR-based trailing stop.

        Args:
            pos: Position info
        """
        if self.indicators is None:
            self.logger.warning("ATR trailing enabled but no indicators instance provided", pos.symbol)
            return

        # Get candle data for ATR calculation
        df = self.connector.get_candles(
            pos.symbol,
            self.trailing_config.atr_timeframe,
            count=self.trailing_config.atr_period + 50
        )

        if df is None or len(df) < self.trailing_config.atr_period + 1:
            self.logger.warning(
                f"Insufficient data for ATR calculation: need {self.trailing_config.atr_period + 1}, have {len(df) if df is not None else 0}",
                pos.symbol
            )
            return

        # Calculate ATR
        atr = self.indicators.calculate_atr(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            period=self.trailing_config.atr_period
        )

        if atr is None:
            self.logger.warning("ATR calculation failed", pos.symbol)
            return

        # Get symbol info for point value
        symbol_info = self.connector.get_symbol_info(pos.symbol)
        if symbol_info is None:
            return

        point = symbol_info['point']

        # Calculate ATR distance in price
        atr_distance = atr * self.trailing_config.atr_multiplier

        # Initialize or update tracking data
        if pos.ticket not in self.atr_trailing_data:
            # First time - initialize with current price as peak
            self.atr_trailing_data[pos.ticket] = {
                'peak_price': pos.current_price,
                'atr': atr
            }
            self.trailing_positions.add(pos.ticket)

            # Calculate initial stop based on entry
            if pos.position_type == PositionType.BUY:
                initial_sl = pos.open_price - atr_distance
            else:
                initial_sl = pos.open_price + atr_distance

            self.logger.info(
                f"ATR trailing stop ACTIVATED for position {pos.ticket}",
                pos.symbol
            )
            self.logger.info(
                f"ATR({self.trailing_config.atr_period}): {atr:.5f} | Multiplier: {self.trailing_config.atr_multiplier}x",
                pos.symbol
            )
            self.logger.info(
                f"ATR Distance: {atr_distance:.5f} ({atr_distance/point:.1f} points)",
                pos.symbol
            )
            self.logger.info(
                f"Initial SL would be: {initial_sl:.5f}",
                pos.symbol
            )

        # Update peak price and trail stop
        tracking = self.atr_trailing_data[pos.ticket]

        if pos.position_type == PositionType.BUY:
            # For BUY, update peak if price made new high
            if pos.current_price > tracking['peak_price']:
                tracking['peak_price'] = pos.current_price
                tracking['atr'] = atr

            # Calculate new SL based on peak price
            new_sl = tracking['peak_price'] - atr_distance

            # Only move SL up, never down
            if new_sl > pos.sl:
                success = self.order_manager.modify_position(
                    ticket=pos.ticket,
                    sl=new_sl,
                    tp=pos.tp
                )

                if success:
                    self.logger.info(
                        f"ATR trailing stop updated for BUY position {pos.ticket}",
                        pos.symbol
                    )
                    self.logger.info(
                        f"Peak: {tracking['peak_price']:.5f} | ATR: {atr:.5f} | Distance: {atr_distance:.5f}",
                        pos.symbol
                    )
                    self.logger.info(
                        f"New SL: {new_sl:.5f} (was {pos.sl:.5f}) | Distance in points: {atr_distance/point:.1f}",
                        pos.symbol
                    )

        else:  # SELL
            # For SELL, update peak if price made new low
            if pos.current_price < tracking['peak_price']:
                tracking['peak_price'] = pos.current_price
                tracking['atr'] = atr

            # Calculate new SL based on peak price (lowest price for SELL)
            new_sl = tracking['peak_price'] + atr_distance

            # Only move SL down, never up
            if new_sl < pos.sl or pos.sl == 0:
                success = self.order_manager.modify_position(
                    ticket=pos.ticket,
                    sl=new_sl,
                    tp=pos.tp
                )

                if success:
                    self.logger.info(
                        f"ATR trailing stop updated for SELL position {pos.ticket}",
                        pos.symbol
                    )
                    self.logger.info(
                        f"Peak: {tracking['peak_price']:.5f} | ATR: {atr:.5f} | Distance: {atr_distance:.5f}",
                        pos.symbol
                    )
                    self.logger.info(
                        f"New SL: {new_sl:.5f} (was {pos.sl:.5f}) | Distance in points: {atr_distance/point:.1f}",
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

        # Remove ATR tracking data
        if ticket in self.atr_trailing_data:
            del self.atr_trailing_data[ticket]

    def reset(self):
        """Reset all tracking"""
        self.breakeven_positions.clear()
        self.trailing_positions.clear()
        self.atr_trailing_data.clear()
        self.logger.info("Trade manager reset")

