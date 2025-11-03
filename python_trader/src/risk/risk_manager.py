"""
Risk management and position sizing.
Ported from FMS_TradeExecution.mqh
"""
from typing import Optional, Tuple
from src.core.mt5_connector import MT5Connector
from src.config.config import RiskConfig
from src.models.data_models import PositionType
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
        contract_size = symbol_info['contract_size']
        currency_profit = symbol_info.get('currency_profit', 'UNKNOWN')
        currency_base = symbol_info.get('currency_base', 'UNKNOWN')

        # Get account currency
        account_currency = self.connector.get_account_currency()

        # Log symbol info for debugging
        self.logger.debug(
            f"Symbol Info: Point={point}, TickValue={tick_value:.5f}, "
            f"ContractSize={contract_size}, Digits={symbol_info['digits']}, "
            f"CurrencyBase={currency_base}, CurrencyProfit={currency_profit}, "
            f"AccountCurrency={account_currency}",
            symbol
        )

        # Convert tick value to account currency if needed
        original_tick_value = tick_value
        if currency_profit != account_currency and account_currency and currency_profit != 'UNKNOWN':
            conversion_rate = self.connector.get_currency_conversion_rate(currency_profit, account_currency)
            if conversion_rate is not None:
                tick_value = tick_value * conversion_rate
                self.logger.info(
                    f"Currency conversion applied: {currency_profit} -> {account_currency}, "
                    f"Rate={conversion_rate:.5f}, TickValue: {original_tick_value:.5f} -> {tick_value:.5f}",
                    symbol
                )
            else:
                self.logger.error(
                    f"Failed to get conversion rate from {currency_profit} to {account_currency}. "
                    f"Risk calculation may be incorrect!",
                    symbol
                )
                # Continue with original tick_value but log the issue

        # Calculate stop loss distance in points
        # This matches MQL5: stopLossPoints = MathAbs(entryPrice - stopLoss) / point
        sl_distance_in_points = sl_distance / point if point > 0 else sl_distance

        if tick_value <= 0 or sl_distance_in_points <= 0:
            self.logger.error("Invalid tick value or SL distance", symbol)
            return 0.0

        # Calculate lot size
        # This matches MQL5: lotSize = riskAmount / (stopLossPoints * tickValue)
        # tick_value already represents the value per lot per point
        lot_size_raw = risk_amount / (sl_distance_in_points * tick_value)

        # Normalize to lot step
        min_lot = symbol_info['min_lot']
        max_lot = symbol_info['max_lot']
        lot_step = symbol_info['lot_step']

        self.logger.debug(
            f"Lot size calculation: raw={lot_size_raw:.4f}, lot_step={lot_step}, "
            f"symbol_min={min_lot}, symbol_max={max_lot}",
            symbol
        )

        # Round to lot step
        lot_size = round(lot_size_raw / lot_step) * lot_step
        self.logger.debug(f"After rounding to lot_step: {lot_size:.4f}", symbol)

        # Apply min/max constraints
        lot_size_before_symbol_clamp = lot_size
        lot_size = max(min_lot, min(max_lot, lot_size))
        if lot_size != lot_size_before_symbol_clamp:
            self.logger.debug(
                f"After symbol min/max clamp: {lot_size_before_symbol_clamp:.4f} -> {lot_size:.4f}",
                symbol
            )

        # Apply user-defined min/max
        # Note: If min_lot_size is 0 or negative, use symbol's min_lot
        user_min_lot = self.risk_config.min_lot_size if self.risk_config.min_lot_size > 0 else min_lot
        lot_size_before_user_min = lot_size
        lot_size = max(user_min_lot, lot_size)
        if lot_size != lot_size_before_user_min:
            self.logger.debug(
                f"After user min clamp ({user_min_lot:.4f}): {lot_size_before_user_min:.4f} -> {lot_size:.4f}",
                symbol
            )

        if self.risk_config.max_lot_size > 0:
            lot_size_before_user_max = lot_size
            lot_size = min(self.risk_config.max_lot_size, lot_size)
            if lot_size != lot_size_before_user_max:
                self.logger.debug(
                    f"After user max clamp ({self.risk_config.max_lot_size:.4f}): "
                    f"{lot_size_before_user_max:.4f} -> {lot_size:.4f}",
                    symbol
                )
            else:
                self.logger.debug(
                    f"User max lot ({self.risk_config.max_lot_size:.4f}) not applied - "
                    f"lot size {lot_size:.4f} is already below max",
                    symbol
                )
        
        # Log calculation
        self.logger.info("=== Position Sizing ===", symbol)
        self.logger.info(f"Account Balance: ${balance:.2f}", symbol)
        self.logger.info(f"Risk Per Trade: {self.risk_config.risk_percent_per_trade}%", symbol)
        self.logger.info(f"Risk Amount: ${risk_amount:.2f}", symbol)
        self.logger.info(f"Entry Price: {entry_price:.5f}", symbol)
        self.logger.info(f"Stop Loss: {stop_loss:.5f}", symbol)
        self.logger.info(f"SL Distance: {sl_distance:.5f} ({sl_distance_in_points:.1f} points)", symbol)
        self.logger.info(f"Tick Value: ${tick_value:.2f}", symbol)
        self.logger.info(f"Calculated Lot Size: {lot_size:.2f}", symbol)
        self.logger.info(f"Symbol Min/Max Lot: {min_lot:.2f} / {max_lot:.2f}", symbol)
        if self.risk_config.min_lot_size > 0:
            self.logger.info(f"User Min Lot: {self.risk_config.min_lot_size:.2f}", symbol)
        else:
            self.logger.info(f"User Min Lot: MIN (using symbol minimum)", symbol)
        if self.risk_config.max_lot_size > 0:
            self.logger.info(f"User Max Lot: {self.risk_config.max_lot_size:.2f}", symbol)
        else:
            self.logger.info(f"User Max Lot: UNLIMITED", symbol)
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
                           entry_price: float, stop_loss: float) -> Tuple[bool, str, float]:
        """
        Validate if trade meets risk requirements.
        If risk exceeds maximum, automatically recalculates a smaller lot size.

        Args:
            symbol: Symbol name
            lot_size: Lot size
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            Tuple of (is_valid, error_message, adjusted_lot_size)
            - is_valid: True if trade can proceed (possibly with adjusted lot size)
            - error_message: Error description if is_valid is False, empty string otherwise
            - adjusted_lot_size: The lot size to use (may be reduced from original)
        """
        # Check lot size
        symbol_info = self.connector.get_symbol_info(symbol)
        if symbol_info is None:
            return False, "Failed to get symbol info", 0.0

        min_lot = symbol_info['min_lot']
        max_lot = symbol_info['max_lot']
        lot_step = symbol_info['lot_step']

        if lot_size < min_lot:
            return False, f"Lot size {lot_size:.2f} below minimum {min_lot:.2f}", 0.0

        if lot_size > max_lot:
            return False, f"Lot size {lot_size:.2f} above maximum {max_lot:.2f}", 0.0

        # Check SL distance
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return False, "Invalid stop loss distance", 0.0

        # Calculate risk amount
        balance = self.connector.get_account_balance()
        point = symbol_info['point']
        tick_value = symbol_info['tick_value']
        currency_profit = symbol_info.get('currency_profit', 'UNKNOWN')

        # Get account currency and convert tick value if needed
        account_currency = self.connector.get_account_currency()
        original_tick_value = tick_value

        if currency_profit != account_currency and account_currency and currency_profit != 'UNKNOWN':
            conversion_rate = self.connector.get_currency_conversion_rate(currency_profit, account_currency)
            if conversion_rate is not None:
                tick_value = tick_value * conversion_rate
                self.logger.debug(
                    f"Risk validation currency conversion: {currency_profit} -> {account_currency}, "
                    f"Rate={conversion_rate:.5f}, TickValue: {original_tick_value:.5f} -> {tick_value:.5f}",
                    symbol
                )

        # Calculate SL distance in points (matches MQL5 formula)
        sl_distance_in_points = sl_distance / point if point > 0 else sl_distance

        # Calculate risk amount: stopLossPoints * tickValue * lotSize
        # This matches the inverse of the lot size calculation
        risk_amount = sl_distance_in_points * tick_value * lot_size
        risk_percent = (risk_amount / balance) * 100.0 if balance > 0 else 0

        # Log detailed risk calculation for debugging
        self.logger.debug(
            f"Risk Validation: Balance={balance:.2f}, Entry={entry_price:.5f}, "
            f"SL={stop_loss:.5f}, SL_Dist={sl_distance:.5f}, Point={point}, "
            f"SL_Points={sl_distance_in_points:.2f}, TickValue={tick_value:.5f}, "
            f"LotSize={lot_size:.2f}, RiskAmount={risk_amount:.2f}, "
            f"RiskPercent={risk_percent:.2f}%",
            symbol
        )

        # Check if risk exceeds maximum
        max_risk = self.risk_config.risk_percent_per_trade * 1.5  # Allow 50% tolerance
        if risk_percent > max_risk:
            # Instead of rejecting, recalculate lot size to target the configured risk percent
            self.logger.warning(
                f"Risk {risk_percent:.2f}% exceeds maximum {max_risk:.2f}%. "
                f"Automatically reducing lot size...",
                symbol
            )

            # Calculate new lot size targeting the configured risk percent (not the max tolerance)
            target_risk_amount = balance * (self.risk_config.risk_percent_per_trade / 100.0)

            # Recalculate lot size: lotSize = riskAmount / (stopLossPoints * tickValue)
            adjusted_lot_size = target_risk_amount / (sl_distance_in_points * tick_value)

            # Normalize to lot step
            adjusted_lot_size = round(adjusted_lot_size / lot_step) * lot_step

            # Apply min/max constraints
            adjusted_lot_size = max(min_lot, min(max_lot, adjusted_lot_size))

            # Apply user-defined minimum
            user_min_lot = self.risk_config.min_lot_size if self.risk_config.min_lot_size > 0 else min_lot
            adjusted_lot_size = max(user_min_lot, adjusted_lot_size)

            # Check if adjusted lot size is still below minimum
            if adjusted_lot_size < min_lot or adjusted_lot_size < user_min_lot:
                return False, f"Adjusted lot size {adjusted_lot_size:.2f} below minimum {max(min_lot, user_min_lot):.2f}", 0.0

            # Recalculate risk with adjusted lot size
            adjusted_risk_amount = sl_distance_in_points * tick_value * adjusted_lot_size
            adjusted_risk_percent = (adjusted_risk_amount / balance) * 100.0 if balance > 0 else 0

            # Log the adjustment
            self.logger.warning(
                f"Lot size adjusted: {lot_size:.2f} -> {adjusted_lot_size:.2f} | "
                f"Risk: {risk_percent:.2f}% -> {adjusted_risk_percent:.2f}% | "
                f"Target: {self.risk_config.risk_percent_per_trade:.2f}%",
                symbol
            )

            return True, "", adjusted_lot_size

        # Risk is within acceptable limits, return original lot size
        return True, "", lot_size
    
    def get_max_positions(self) -> int:
        """
        Get maximum number of concurrent positions allowed.
        
        Returns:
            Maximum positions
        """
        return self.risk_config.max_positions
    
    def can_open_new_position(self, magic_number: int, symbol: Optional[str] = None,
                             position_type: Optional[PositionType] = None,
                             all_confirmations_met: bool = False) -> Tuple[bool, str]:
        """
        Check if we can open a new position.

        Args:
            magic_number: Magic number to filter positions
            symbol: Symbol to check for existing positions (optional)
            position_type: Position type (BUY/SELL) to check for duplicates (optional)
            all_confirmations_met: If True, allows second position of same type (optional)

        Returns:
            Tuple of (can_open, reason)
        """
        # Get current positions
        positions = self.connector.get_positions(magic_number=magic_number)

        # Check max positions
        if len(positions) >= self.risk_config.max_positions:
            return False, f"Maximum positions ({self.risk_config.max_positions}) reached"

        # Check if position of same type already exists for this symbol
        if symbol and position_type:
            same_type_positions = [
                pos for pos in positions
                if pos.symbol == symbol and pos.position_type == position_type
            ]

            if len(same_type_positions) > 0:
                pos_type_str = "BUY" if position_type == PositionType.BUY else "SELL"

                # If all confirmations are met, allow up to 2 positions of same type
                if all_confirmations_met and len(same_type_positions) < 2:
                    self.logger.info(
                        f"Allowing second {pos_type_str} position for {symbol} - all confirmations met",
                        symbol
                    )
                    return True, ""

                # Otherwise, reject if any position exists
                if len(same_type_positions) >= 2:
                    return False, f"Maximum 2 {pos_type_str} positions already exist for {symbol}"
                else:
                    return False, f"{pos_type_str} position already exists for {symbol} (confirmations not met)"

        # Check account balance is valid
        balance = self.connector.get_account_balance()

        if balance <= 0:
            return False, "Invalid account balance"

        return True, ""

