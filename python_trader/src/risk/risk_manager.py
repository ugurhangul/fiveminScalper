"""
Risk management and position sizing.
Ported from FMS_TradeExecution.mqh
"""
from typing import Optional, Tuple
from src.core.mt5_connector import MT5Connector
from src.config.config import RiskConfig
from src.utils.logger import get_logger


class RiskManager:
    """Manages risk and position sizing"""
    
    def __init__(self, connector: MT5Connector, risk_config: RiskConfig):
        """
        Initialize risk manager.
        
        Args:
            connector: MT5 connector instance
            risk_config: Risk configuration
        """
        self.connector = connector
        self.risk_config = risk_config
        self.logger = get_logger()
    
    def calculate_lot_size(self, symbol: str, entry_price: float, 
                          stop_loss: float) -> float:
        """
        Calculate lot size based on risk percentage.
        
        Args:
            symbol: Symbol name
            entry_price: Entry price
            stop_loss: Stop loss price
            
        Returns:
            Lot size
        """
        # Get account balance
        balance = self.connector.get_account_balance()
        if balance <= 0:
            self.logger.error("Invalid account balance", symbol)
            return 0.0
        
        # Get symbol info
        symbol_info = self.connector.get_symbol_info(symbol)
        if symbol_info is None:
            self.logger.error("Failed to get symbol info", symbol)
            return 0.0
        
        # Calculate risk amount in account currency
        risk_amount = balance * (self.risk_config.risk_percent_per_trade / 100.0)
        
        # Calculate stop loss distance in points
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            self.logger.error("Invalid stop loss distance", symbol)
            return 0.0
        
        # Get point value and contract size
        point = symbol_info['point']
        tick_value = symbol_info['tick_value']
        tick_size = symbol_info['tick_size']
        contract_size = symbol_info['contract_size']
        
        # Calculate pip value per lot
        # For forex: pip_value = (tick_value / tick_size) * point
        # For other instruments, we use tick_value directly
        pip_value_per_lot = (tick_value / tick_size) * point if tick_size > 0 else tick_value
        
        # Calculate lot size
        # lot_size = risk_amount / (sl_distance_in_pips * pip_value_per_lot)
        sl_distance_in_pips = sl_distance / point if point > 0 else sl_distance
        
        if pip_value_per_lot <= 0 or sl_distance_in_pips <= 0:
            self.logger.error("Invalid pip value or SL distance", symbol)
            return 0.0
        
        lot_size = risk_amount / (sl_distance_in_pips * pip_value_per_lot)
        
        # Normalize to lot step
        min_lot = symbol_info['min_lot']
        max_lot = symbol_info['max_lot']
        lot_step = symbol_info['lot_step']
        
        # Round to lot step
        lot_size = round(lot_size / lot_step) * lot_step
        
        # Apply min/max constraints
        lot_size = max(min_lot, min(max_lot, lot_size))
        
        # Apply user-defined min/max
        if self.risk_config.min_lot_size > 0:
            lot_size = max(self.risk_config.min_lot_size, lot_size)
        if self.risk_config.max_lot_size > 0:
            lot_size = min(self.risk_config.max_lot_size, lot_size)
        
        # Log calculation
        self.logger.info("=== Position Sizing ===", symbol)
        self.logger.info(f"Account Balance: ${balance:.2f}", symbol)
        self.logger.info(f"Risk Per Trade: {self.risk_config.risk_percent_per_trade}%", symbol)
        self.logger.info(f"Risk Amount: ${risk_amount:.2f}", symbol)
        self.logger.info(f"Entry Price: {entry_price:.5f}", symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f}", symbol)
        self.logger.info(f"SL Distance: {sl_distance:.5f} ({sl_distance_in_pips:.1f} pips)", symbol)
        self.logger.info(f"Pip Value/Lot: ${pip_value_per_lot:.2f}", symbol)
        self.logger.info(f"Calculated Lot Size: {lot_size:.2f}", symbol)
        self.logger.info(f"Min/Max Lot: {min_lot:.2f} / {max_lot:.2f}", symbol)
        self.logger.separator()
        
        return lot_size
    
    def calculate_stop_loss(self, symbol: str, entry_price: float, 
                           is_buy: bool, offset_points: int) -> float:
        """
        Calculate stop loss price.
        
        Args:
            symbol: Symbol name
            entry_price: Entry price
            is_buy: True for BUY, False for SELL
            offset_points: Offset in points from entry
            
        Returns:
            Stop loss price
        """
        symbol_info = self.connector.get_symbol_info(symbol)
        if symbol_info is None:
            return 0.0
        
        point = symbol_info['point']
        offset = offset_points * point
        
        if is_buy:
            # For BUY, SL is below entry
            sl = entry_price - offset
        else:
            # For SELL, SL is above entry
            sl = entry_price + offset
        
        # Normalize
        digits = symbol_info['digits']
        sl = round(sl, digits)
        
        return sl
    
    def calculate_take_profit(self, symbol: str, entry_price: float, 
                             stop_loss: float, risk_reward_ratio: float) -> float:
        """
        Calculate take profit based on R:R ratio.
        
        Args:
            symbol: Symbol name
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_reward_ratio: Risk/reward ratio (e.g., 2.0 for 1:2)
            
        Returns:
            Take profit price
        """
        symbol_info = self.connector.get_symbol_info(symbol)
        if symbol_info is None:
            return 0.0
        
        # Calculate risk distance
        risk_distance = abs(entry_price - stop_loss)
        
        # Calculate reward distance
        reward_distance = risk_distance * risk_reward_ratio
        
        # Determine TP based on direction
        if entry_price > stop_loss:
            # BUY position
            tp = entry_price + reward_distance
        else:
            # SELL position
            tp = entry_price - reward_distance
        
        # Normalize
        digits = symbol_info['digits']
        tp = round(tp, digits)
        
        return tp
    
    def validate_trade_risk(self, symbol: str, lot_size: float, 
                           entry_price: float, stop_loss: float) -> Tuple[bool, str]:
        """
        Validate if trade meets risk requirements.
        
        Args:
            symbol: Symbol name
            lot_size: Lot size
            entry_price: Entry price
            stop_loss: Stop loss price
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check lot size
        symbol_info = self.connector.get_symbol_info(symbol)
        if symbol_info is None:
            return False, "Failed to get symbol info"
        
        min_lot = symbol_info['min_lot']
        max_lot = symbol_info['max_lot']
        
        if lot_size < min_lot:
            return False, f"Lot size {lot_size:.2f} below minimum {min_lot:.2f}"
        
        if lot_size > max_lot:
            return False, f"Lot size {lot_size:.2f} above maximum {max_lot:.2f}"
        
        # Check SL distance
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return False, "Invalid stop loss distance"
        
        # Calculate risk amount
        balance = self.connector.get_account_balance()
        point = symbol_info['point']
        tick_value = symbol_info['tick_value']
        tick_size = symbol_info['tick_size']
        
        pip_value_per_lot = (tick_value / tick_size) * point if tick_size > 0 else tick_value
        sl_distance_in_pips = sl_distance / point if point > 0 else sl_distance
        
        risk_amount = sl_distance_in_pips * pip_value_per_lot * lot_size
        risk_percent = (risk_amount / balance) * 100.0 if balance > 0 else 0
        
        # Check if risk exceeds maximum
        max_risk = self.risk_config.risk_percent_per_trade * 1.5  # Allow 50% tolerance
        if risk_percent > max_risk:
            return False, f"Risk {risk_percent:.2f}% exceeds maximum {max_risk:.2f}%"
        
        return True, ""
    
    def get_max_positions(self) -> int:
        """
        Get maximum number of concurrent positions allowed.
        
        Returns:
            Maximum positions
        """
        return self.risk_config.max_positions
    
    def can_open_new_position(self, magic_number: int) -> Tuple[bool, str]:
        """
        Check if we can open a new position.
        
        Args:
            magic_number: Magic number to filter positions
            
        Returns:
            Tuple of (can_open, reason)
        """
        # Get current positions
        positions = self.connector.get_positions(magic_number=magic_number)
        
        # Check max positions
        if len(positions) >= self.risk_config.max_positions:
            return False, f"Maximum positions ({self.risk_config.max_positions}) reached"
        
        # Check account equity
        equity = self.connector.get_account_equity()
        balance = self.connector.get_account_balance()
        
        if equity <= 0 or balance <= 0:
            return False, "Invalid account equity or balance"
        
        # Check drawdown
        drawdown_percent = ((balance - equity) / balance) * 100.0 if balance > 0 else 0
        
        if drawdown_percent > 20.0:  # Example: 20% max drawdown
            return False, f"Drawdown too high: {drawdown_percent:.2f}%"
        
        return True, ""

