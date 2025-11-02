"""
Order execution and management.
Ported from FMS_TradeExecution.mqh
"""
import MetaTrader5 as mt5
from typing import Optional, Tuple
from src.models.data_models import PositionType, TradeSignal
from src.core.mt5_connector import MT5Connector
from src.utils.logger import get_logger


class OrderManager:
    """Manages order execution and modification"""
    
    def __init__(self, connector: MT5Connector, magic_number: int, trade_comment: str):
        """
        Initialize order manager.
        
        Args:
            connector: MT5 connector instance
            magic_number: Magic number for orders
            trade_comment: Comment for trades
        """
        self.connector = connector
        self.magic_number = magic_number
        self.trade_comment = trade_comment
        self.logger = get_logger()
        self.deviation = 10  # Price deviation in points
    
    def normalize_price(self, symbol: str, price: float) -> float:
        """
        Normalize price to symbol's digits.
        
        Args:
            symbol: Symbol name
            price: Price to normalize
            
        Returns:
            Normalized price
        """
        info = self.connector.get_symbol_info(symbol)
        if info is None:
            return price
        
        digits = info['digits']
        return round(price, digits)
    
    def normalize_volume(self, symbol: str, volume: float) -> float:
        """
        Normalize volume to symbol's lot step.
        
        Args:
            symbol: Symbol name
            volume: Volume to normalize
            
        Returns:
            Normalized volume
        """
        info = self.connector.get_symbol_info(symbol)
        if info is None:
            return volume
        
        min_lot = info['min_lot']
        max_lot = info['max_lot']
        lot_step = info['lot_step']
        
        # Round to lot step
        volume = round(volume / lot_step) * lot_step
        
        # Clamp to min/max
        volume = max(min_lot, min(max_lot, volume))
        
        return volume
    
    def execute_signal(self, signal: TradeSignal) -> Optional[int]:
        """
        Execute a trade signal.
        
        Args:
            signal: TradeSignal object
            
        Returns:
            Ticket number if successful, None otherwise
        """
        symbol = signal.symbol
        
        # Normalize prices and volume
        entry_price = self.normalize_price(symbol, signal.entry_price)
        sl = self.normalize_price(symbol, signal.stop_loss)
        tp = self.normalize_price(symbol, signal.take_profit)
        volume = self.normalize_volume(symbol, signal.lot_size)
        
        # Determine order type
        if signal.signal_type == PositionType.BUY:
            order_type = mt5.ORDER_TYPE_BUY
            price = self.connector.get_current_price(symbol, 'ask')
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = self.connector.get_current_price(symbol, 'bid')
        
        if price is None:
            self.logger.error(f"Failed to get current price for {symbol}", symbol)
            return None
        
        # Log signal
        self.logger.trade_signal(
            signal_type=signal.signal_type.value.upper(),
            symbol=symbol,
            entry=price,
            sl=sl,
            tp=tp,
            lot_size=volume
        )
        
        # Create order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.deviation,
            "magic": self.magic_number,
            "comment": self.trade_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        try:
            result = mt5.order_send(request)
            
            if result is None:
                self.logger.error(f"order_send failed, no result returned", symbol)
                return None
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(
                    f"Order failed: {result.retcode} - {result.comment}",
                    symbol
                )
                return None
            
            # Log success
            self.logger.position_opened(
                ticket=result.order,
                symbol=symbol,
                position_type=signal.signal_type.value.upper(),
                volume=volume,
                price=result.price,
                sl=sl,
                tp=tp
            )
            
            return result.order
            
        except Exception as e:
            self.logger.error(f"Error executing order: {e}", symbol)
            return None
    
    def modify_position(self, ticket: int, sl: Optional[float] = None, 
                       tp: Optional[float] = None) -> bool:
        """
        Modify position SL/TP.
        
        Args:
            ticket: Position ticket
            sl: New stop loss (None to keep current)
            tp: New take profit (None to keep current)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current position
            position = mt5.positions_get(ticket=ticket)
            if not position or len(position) == 0:
                self.logger.error(f"Position {ticket} not found")
                return False
            
            pos = position[0]
            symbol = pos.symbol
            
            # Use current values if not specified
            new_sl = sl if sl is not None else pos.sl
            new_tp = tp if tp is not None else pos.tp
            
            # Normalize prices
            new_sl = self.normalize_price(symbol, new_sl) if new_sl > 0 else 0
            new_tp = self.normalize_price(symbol, new_tp) if new_tp > 0 else 0
            
            # Create modification request
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": new_sl,
                "tp": new_tp,
            }
            
            # Send modification
            result = mt5.order_send(request)
            
            if result is None:
                self.logger.error(f"Modify failed for position {ticket}, no result")
                return False
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(
                    f"Modify failed for position {ticket}: {result.retcode} - {result.comment}"
                )
                return False
            
            self.logger.debug(
                f"Position {ticket} modified - SL: {new_sl:.5f}, TP: {new_tp:.5f}",
                symbol
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error modifying position {ticket}: {e}")
            return False
    
    def close_position(self, ticket: int) -> bool:
        """
        Close a position.
        
        Args:
            ticket: Position ticket
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get position
            position = mt5.positions_get(ticket=ticket)
            if not position or len(position) == 0:
                self.logger.error(f"Position {ticket} not found")
                return False
            
            pos = position[0]
            symbol = pos.symbol
            volume = pos.volume
            
            # Determine close order type (opposite of position type)
            if pos.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = self.connector.get_current_price(symbol, 'bid')
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = self.connector.get_current_price(symbol, 'ask')
            
            if price is None:
                self.logger.error(f"Failed to get price for closing {ticket}")
                return False
            
            # Create close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "deviation": self.deviation,
                "magic": self.magic_number,
                "comment": f"Close {self.trade_comment}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send close order
            result = mt5.order_send(request)
            
            if result is None:
                self.logger.error(f"Close failed for position {ticket}, no result")
                return False
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(
                    f"Close failed for position {ticket}: {result.retcode} - {result.comment}"
                )
                return False
            
            self.logger.info(f"Position {ticket} closed at {price:.5f}", symbol)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing position {ticket}: {e}")
            return False

