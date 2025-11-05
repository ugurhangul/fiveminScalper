"""
Simulated broker for backtesting.
Simulates order execution without sending real trades to MT5.
"""
from typing import Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass
from src.models.data_models import TradeSignal, PositionInfo, PositionType
from src.utils.logger import get_logger


@dataclass
class SimulatedPosition:
    """Simulated position for backtesting"""
    ticket: int
    symbol: str
    position_type: PositionType
    volume: float
    open_price: float
    open_time: datetime
    stop_loss: float
    take_profit: float
    magic_number: int
    comment: str
    
    # Tracking
    current_price: float = 0.0
    profit: float = 0.0
    is_closed: bool = False
    close_price: Optional[float] = None
    close_time: Optional[datetime] = None
    close_reason: str = ""


class SimulatedBroker:
    """Simulates broker operations for backtesting"""
    
    def __init__(self, initial_balance: float = 10000.0, spread_points: int = 10):
        """
        Initialize simulated broker.
        
        Args:
            initial_balance: Starting account balance
            spread_points: Spread in points for all symbols
        """
        self.logger = get_logger()
        
        # Account state
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        
        # Positions
        self.positions: Dict[int, SimulatedPosition] = {}
        self.next_ticket = 1
        
        # Trade history
        self.closed_positions: List[SimulatedPosition] = []
        
        # Settings
        self.spread_points = spread_points
        
        # Symbol info cache
        self.symbol_info_cache: Dict[str, dict] = {}
    
    def set_symbol_info(self, symbol: str, info: dict):
        """
        Set symbol information for calculations.
        
        Args:
            symbol: Symbol name
            info: Symbol info dict (point, tick_value, etc.)
        """
        self.symbol_info_cache[symbol] = info
    
    def execute_order(self, signal: TradeSignal, volume: float, 
                     current_time: datetime, current_price: float) -> Optional[int]:
        """
        Execute a simulated order.
        
        Args:
            signal: Trade signal
            volume: Lot size
            current_time: Current simulation time
            current_price: Current market price
            
        Returns:
            Ticket number if successful, None otherwise
        """
        symbol = signal.symbol
        
        # Get symbol info
        if symbol not in self.symbol_info_cache:
            self.logger.error(f"Symbol info not set for {symbol}")
            return None
        
        symbol_info = self.symbol_info_cache[symbol]
        point = symbol_info.get('point', 0.00001)
        
        # Calculate execution price with spread
        if signal.signal_type == PositionType.BUY:
            # BUY at ASK (add spread)
            execution_price = current_price + (self.spread_points * point)
        else:
            # SELL at BID (no spread adjustment needed, current_price is BID)
            execution_price = current_price
        
        # Create position
        ticket = self.next_ticket
        self.next_ticket += 1
        
        position = SimulatedPosition(
            ticket=ticket,
            symbol=symbol,
            position_type=signal.signal_type,
            volume=volume,
            open_price=execution_price,
            open_time=current_time,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            magic_number=signal.magic_number,
            comment=signal.comment,
            current_price=execution_price
        )
        
        self.positions[ticket] = position
        
        self.logger.info(
            f"[BACKTEST] Position opened: {ticket} {signal.signal_type.value.upper()} "
            f"{volume} {symbol} @ {execution_price:.5f} SL:{signal.stop_loss:.5f} TP:{signal.take_profit:.5f}"
        )
        
        return ticket
    
    def update_positions(self, symbol: str, current_time: datetime, 
                        bid_price: float, ask_price: float):
        """
        Update positions and check for SL/TP hits.
        
        Args:
            symbol: Symbol name
            current_time: Current simulation time
            bid_price: Current BID price
            ask_price: Current ASK price
        """
        if symbol not in self.symbol_info_cache:
            return
        
        symbol_info = self.symbol_info_cache[symbol]
        point = symbol_info.get('point', 0.00001)
        tick_value = symbol_info.get('tick_value', 1.0)
        
        # Check each position for this symbol
        for ticket, position in list(self.positions.items()):
            if position.symbol != symbol or position.is_closed:
                continue
            
            # Update current price
            if position.position_type == PositionType.BUY:
                position.current_price = bid_price  # BUY closes at BID
            else:
                position.current_price = ask_price  # SELL closes at ASK
            
            # Calculate profit
            if position.position_type == PositionType.BUY:
                price_diff = position.current_price - position.open_price
            else:
                price_diff = position.open_price - position.current_price
            
            points = price_diff / point if point > 0 else 0
            position.profit = points * tick_value * position.volume
            
            # Check for SL/TP hit
            close_reason = None
            
            if position.position_type == PositionType.BUY:
                # Check SL (price went down)
                if bid_price <= position.stop_loss:
                    close_reason = "Stop Loss"
                    position.current_price = position.stop_loss
                # Check TP (price went up)
                elif bid_price >= position.take_profit:
                    close_reason = "Take Profit"
                    position.current_price = position.take_profit
            else:  # SELL
                # Check SL (price went up)
                if ask_price >= position.stop_loss:
                    close_reason = "Stop Loss"
                    position.current_price = position.stop_loss
                # Check TP (price went down)
                elif ask_price <= position.take_profit:
                    close_reason = "Take Profit"
                    position.current_price = position.take_profit
            
            # Close position if SL/TP hit
            if close_reason:
                self._close_position(position, current_time, close_reason)
    
    def _close_position(self, position: SimulatedPosition, 
                       close_time: datetime, reason: str):
        """Close a position"""
        position.is_closed = True
        position.close_price = position.current_price
        position.close_time = close_time
        position.close_reason = reason
        
        # Update balance
        self.balance += position.profit
        
        # Move to history
        self.closed_positions.append(position)
        
        # Remove from open positions
        if position.ticket in self.positions:
            del self.positions[position.ticket]
        
        self.logger.info(
            f"[BACKTEST] Position closed: {position.ticket} {position.position_type.value.upper()} "
            f"{position.volume} {position.symbol} @ {position.close_price:.5f} "
            f"Profit: {position.profit:.2f} Reason: {reason}"
        )
    
    def modify_position(self, ticket: int, new_sl: Optional[float] = None, 
                       new_tp: Optional[float] = None) -> bool:
        """
        Modify position SL/TP.
        
        Args:
            ticket: Position ticket
            new_sl: New stop loss (None to keep current)
            new_tp: New take profit (None to keep current)
            
        Returns:
            True if successful
        """
        if ticket not in self.positions:
            return False
        
        position = self.positions[ticket]
        
        if new_sl is not None:
            position.stop_loss = new_sl
        if new_tp is not None:
            position.take_profit = new_tp
        
        return True
    
    def get_open_positions(self, symbol: Optional[str] = None) -> List[SimulatedPosition]:
        """Get open positions, optionally filtered by symbol"""
        if symbol:
            return [p for p in self.positions.values() if p.symbol == symbol]
        return list(self.positions.values())
    
    def get_balance(self) -> float:
        """Get current balance"""
        return self.balance
    
    def get_equity(self) -> float:
        """Get current equity (balance + floating P/L)"""
        floating_pl = sum(p.profit for p in self.positions.values())
        return self.balance + floating_pl
    
    def get_closed_positions(self) -> List[SimulatedPosition]:
        """Get all closed positions"""
        return self.closed_positions
    
    def reset(self):
        """Reset broker to initial state"""
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.positions.clear()
        self.closed_positions.clear()
        self.next_ticket = 1

