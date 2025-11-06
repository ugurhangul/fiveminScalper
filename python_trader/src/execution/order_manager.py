"""
Order execution and management.
Ported from FMS_TradeExecution.mqh
"""
import MetaTrader5 as mt5
from typing import Optional, Tuple
from src.models.data_models import PositionType, TradeSignal
from src.core.mt5_connector import MT5Connector
from src.execution.position_persistence import PositionPersistence
from src.utils.logger import get_logger
from src.utils.autotrading_cooldown import AutoTradingCooldown


class OrderManager:
    """Manages order execution and modification"""

    def __init__(self, connector: MT5Connector, magic_number: int, trade_comment: str,
                 persistence: Optional[PositionPersistence] = None,
                 cooldown_manager: Optional[AutoTradingCooldown] = None):
        """
        Initialize order manager.

        Args:
            connector: MT5 connector instance
            magic_number: Magic number for orders
            trade_comment: Comment for trades
            persistence: Position persistence instance (optional)
            cooldown_manager: AutoTrading cooldown manager (optional)
        """
        self.connector = connector
        self.magic_number = magic_number
        self.trade_comment = trade_comment
        self.logger = get_logger()
        self.deviation = 10  # Price deviation in points

        # Position persistence
        self.persistence = persistence if persistence is not None else PositionPersistence()

        # AutoTrading cooldown manager
        self.cooldown = cooldown_manager if cooldown_manager is not None else AutoTradingCooldown()
    
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

        # Check if in cooldown period
        if self.cooldown.is_in_cooldown():
            remaining = self.cooldown.get_remaining_time()
            if remaining:
                minutes = int(remaining.total_seconds() / 60)
                seconds = int(remaining.total_seconds() % 60)
                self.logger.debug(
                    f"Trade rejected - cooldown active ({minutes}m {seconds}s remaining)",
                    symbol
                )
            return None

        # Check if AutoTrading is enabled in terminal
        if not self.connector.is_autotrading_enabled():
            self.logger.trade_error(
                symbol=symbol,
                error_type="AutoTrading Check",
                error_message="AutoTrading is DISABLED in MT5 terminal",
                context={"action": "Trade rejected - Enable AutoTrading in MT5"}
            )
            return None

        # Check if trading is enabled for this symbol
        if not self.connector.is_trading_enabled(symbol):
            self.logger.symbol_condition_warning(
                symbol=symbol,
                condition="Trading Disabled",
                details="Trading is disabled for this symbol in MT5 - Trade rejected"
            )
            return None

        # Normalize prices and volume
        sl = self.normalize_price(symbol, signal.stop_loss)
        volume = self.normalize_volume(symbol, signal.lot_size)

        # Determine order type and get current market price
        if signal.signal_type == PositionType.BUY:
            order_type = mt5.ORDER_TYPE_BUY
            price = self.connector.get_current_price(symbol, 'ask')
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = self.connector.get_current_price(symbol, 'bid')

        if price is None:
            self.logger.trade_error(
                symbol=symbol,
                error_type="Price Retrieval",
                error_message="Failed to get current market price",
                context={
                    "order_type": "BUY" if signal.signal_type == PositionType.BUY else "SELL",
                    "action": "Trade rejected"
                }
            )
            return None

        # Recalculate TP based on actual execution price (market price)
        # This ensures the R:R ratio is maintained with the actual entry
        # Use the configured R:R ratio (default 2.0)
        configured_rr = 2.0  # Always use 2:1 ratio

        risk = abs(price - sl)
        reward = risk * configured_rr

        self.logger.debug(f"TP Calculation: Entry={price:.5f}, SL={sl:.5f}, Risk={risk:.5f}, Reward={reward:.5f}, R:R={configured_rr}", symbol)

        if signal.signal_type == PositionType.BUY:
            tp = price + reward
        else:
            tp = price - reward

        # Normalize the recalculated TP
        tp = self.normalize_price(symbol, tp)

        self.logger.debug(f"Final TP: {tp:.5f} (before normalize: {price + reward if signal.signal_type == PositionType.BUY else price - reward:.5f})", symbol)

        # Get symbol info to validate stops
        symbol_info = self.connector.get_symbol_info(symbol)
        if symbol_info is None:
            self.logger.trade_error(
                symbol=symbol,
                error_type="Symbol Info Retrieval",
                error_message="Failed to get symbol information from MT5",
                context={"action": "Trade rejected"}
            )
            return None

        # Validate and adjust SL/TP to meet minimum stop level requirements
        sl, tp = self._validate_stops(symbol, price, sl, tp, signal.signal_type, symbol_info)

        # Log signal
        self.logger.trade_signal(
            signal_type=signal.signal_type.value.upper(),
            symbol=symbol,
            entry=price,
            sl=sl,
            tp=tp,
            lot_size=volume
        )

        # Determine filling mode based on symbol's supported modes
        filling_mode = self._get_filling_mode(symbol_info)

        # Log the filling mode being used
        filling_mode_name = {
            mt5.ORDER_FILLING_FOK: "FOK",
            mt5.ORDER_FILLING_IOC: "IOC",
            mt5.ORDER_FILLING_RETURN: "RETURN"
        }.get(filling_mode, "UNKNOWN")
        self.logger.debug(f"Using filling mode: {filling_mode_name}", symbol)

        # Generate informative trade comment
        trade_comment = self._generate_trade_comment(signal)
        self.logger.info(f"Trade Comment: {trade_comment}", symbol)

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
            "comment": trade_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        # Send order
        try:
            result = mt5.order_send(request)

            if result is None:
                self.logger.trade_error(
                    symbol=symbol,
                    error_type="Trade Execution",
                    error_message="order_send failed, no result returned from MT5",
                    context={
                        "order_type": signal.signal_type.value.upper(),
                        "volume": volume,
                        "price": price
                    }
                )
                return None

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                # Check for AutoTrading disabled by server
                if result.retcode == 10026:
                    self.logger.warning(
                        f"Trade rejected - AutoTrading disabled by server (retcode 10026)",
                        symbol
                    )
                    # Activate cooldown to prevent spam
                    self.cooldown.activate_cooldown("AutoTrading disabled by server (error 10026)")
                    return None

                # Other errors
                self.logger.trade_error(
                    symbol=symbol,
                    error_type="Trade Execution",
                    error_message=f"Order rejected by broker: {result.comment}",
                    context={
                        "retcode": result.retcode,
                        "order_type": signal.signal_type.value.upper(),
                        "volume": volume,
                        "price": price,
                        "sl": sl,
                        "tp": tp
                    }
                )
                return None

            # Log success
            try:
                self.logger.position_opened(
                    ticket=result.order,
                    symbol=symbol,
                    position_type=signal.signal_type.value.upper(),
                    volume=volume,
                    price=result.price,
                    sl=sl,
                    tp=tp
                )
            except Exception as log_error:
                self.logger.error(f"Failed to log position opened: {log_error}", symbol)
                # Continue anyway - logging failure shouldn't prevent position tracking

            # Add position to persistence
            try:
                from src.models.data_models import PositionInfo
                from datetime import datetime, timezone

                position = PositionInfo(
                    ticket=result.order,
                    symbol=symbol,
                    position_type=signal.signal_type,
                    volume=volume,
                    open_price=result.price,
                    current_price=result.price,
                    sl=sl,
                    tp=tp,
                    profit=0.0,
                    open_time=datetime.now(timezone.utc),
                    magic_number=self.magic_number,
                    comment=trade_comment
                )
                self.persistence.add_position(position)
            except Exception as persist_error:
                self.logger.error(f"Failed to add position to persistence: {persist_error}", symbol)
                self.logger.error(f"Position {result.order} opened in MT5 but not tracked in bot!", symbol)

            return result.order

        except Exception as e:
            self.logger.trade_error(
                symbol=symbol,
                error_type="Trade Execution",
                error_message=f"Exception during order execution: {str(e)}",
                context={
                    "order_type": signal.signal_type.value.upper(),
                    "volume": volume,
                    "exception_type": type(e).__name__
                }
            )
            return None

    def _validate_stops(self, symbol: str, price: float, sl: float, tp: float,
                        signal_type: PositionType, symbol_info: dict) -> tuple:
        """
        Validate and adjust SL/TP to meet MT5 minimum stop level requirements.

        Args:
            symbol: Symbol name
            price: Entry price
            sl: Stop loss price
            tp: Take profit price
            signal_type: BUY or SELL
            symbol_info: Symbol information dictionary

        Returns:
            Tuple of (adjusted_sl, adjusted_tp)
        """
        point = symbol_info['point']
        stops_level = symbol_info.get('stops_level', 0)
        freeze_level = symbol_info.get('freeze_level', 0)

        # Log broker requirements for debugging
        self.logger.debug(
            f"Broker Stop Requirements: stops_level={stops_level} points, "
            f"freeze_level={freeze_level} points, point={point}",
            symbol
        )

        # Calculate current distances
        sl_distance = abs(price - sl)
        tp_distance = abs(price - tp)
        sl_distance_points = sl_distance / point if point > 0 else 0
        tp_distance_points = tp_distance / point if point > 0 else 0

        self.logger.debug(
            f"Current Stops: Entry={price:.5f}, SL={sl:.5f} ({sl_distance_points:.0f} pts), "
            f"TP={tp:.5f} ({tp_distance_points:.0f} pts)",
            symbol
        )

        # If stops_level is 0, no minimum distance required
        if stops_level == 0:
            self.logger.debug("No minimum stop level required (stops_level=0)", symbol)
            return sl, tp

        # Calculate minimum distance in price
        min_distance = stops_level * point

        self.logger.debug(
            f"Minimum required distance: {min_distance:.5f} ({stops_level} points)",
            symbol
        )

        # Check and adjust SL
        if sl_distance < min_distance:
            self.logger.warning(
                f"SL too close to entry: {sl_distance:.5f} ({sl_distance_points:.0f} pts) < "
                f"{min_distance:.5f} ({stops_level} pts). Adjusting...",
                symbol
            )
            if signal_type == PositionType.BUY:
                sl = price - min_distance
            else:
                sl = price + min_distance
            sl = self.normalize_price(symbol, sl)
            self.logger.info(f"Adjusted SL: {sl:.5f}", symbol)

        # Check and adjust TP
        if tp_distance < min_distance:
            self.logger.warning(
                f"TP too close to entry: {tp_distance:.5f} ({tp_distance_points:.0f} pts) < "
                f"{min_distance:.5f} ({stops_level} pts). Adjusting...",
                symbol
            )
            if signal_type == PositionType.BUY:
                tp = price + min_distance
            else:
                tp = price - min_distance
            tp = self.normalize_price(symbol, tp)
            self.logger.info(f"Adjusted TP: {tp:.5f}", symbol)

        # Verify SL is on correct side
        if signal_type == PositionType.BUY:
            if sl >= price:
                self.logger.error(f"Invalid BUY SL: {sl:.5f} >= Entry: {price:.5f}", symbol)
                sl = price - min_distance
                sl = self.normalize_price(symbol, sl)
                self.logger.info(f"Corrected SL: {sl:.5f}", symbol)
            if tp <= price:
                self.logger.error(f"Invalid BUY TP: {tp:.5f} <= Entry: {price:.5f}", symbol)
                tp = price + min_distance
                tp = self.normalize_price(symbol, tp)
                self.logger.info(f"Corrected TP: {tp:.5f}", symbol)
        else:  # SELL
            if sl <= price:
                self.logger.error(f"Invalid SELL SL: {sl:.5f} <= Entry: {price:.5f}", symbol)
                sl = price + min_distance
                sl = self.normalize_price(symbol, sl)
                self.logger.info(f"Corrected SL: {sl:.5f}", symbol)
            if tp >= price:
                self.logger.error(f"Invalid SELL TP: {tp:.5f} >= Entry: {price:.5f}", symbol)
                tp = price - min_distance
                tp = self.normalize_price(symbol, tp)
                self.logger.info(f"Corrected TP: {tp:.5f}", symbol)

        # Log final validated stops
        final_sl_distance = abs(price - sl)
        final_tp_distance = abs(price - tp)
        final_sl_distance_points = final_sl_distance / point if point > 0 else 0
        final_tp_distance_points = final_tp_distance / point if point > 0 else 0

        self.logger.debug(
            f"Final Validated Stops: SL={sl:.5f} ({final_sl_distance_points:.0f} pts), "
            f"TP={tp:.5f} ({final_tp_distance_points:.0f} pts)",
            symbol
        )

        return sl, tp

    def _generate_trade_comment(self, signal: TradeSignal) -> str:
        """
        Generate informative trade comment based on signal details.

        Args:
            signal: TradeSignal object

        Returns:
            Formatted comment string (max 31 characters for MT5)
        """
        # Determine strategy type
        if signal.is_true_breakout:
            strategy = "TB"  # True Breakout
        else:
            strategy = "FB"  # False Breakout

        # Determine confirmations
        confirmations = []
        if signal.volume_confirmed:
            confirmations.append("V")
        if signal.divergence_confirmed:
            confirmations.append("D")

        conf_str = "".join(confirmations) if confirmations else "NC"

        # Include range ID if not default (for multi-range mode)
        range_info = ""
        if signal.range_id and signal.range_id != "default":
            # Extract meaningful range identifier (e.g., "4H_5M" -> "4H5M")
            range_info = signal.range_id.replace("_", "")

        # Build comment: Strategy|Direction|Confirmations|Range
        # Example: "TB|BUY|V|4H5M" or "FB|SELL|VD|15M1M"
        if range_info:
            comment = f"{strategy}|{signal.signal_type.value.upper()}|{conf_str}|{range_info}"
        else:
            comment = f"{strategy}|{signal.signal_type.value.upper()}|{conf_str}"

        # MT5 has a 31 character limit for comments
        if len(comment) > 31:
            comment = comment[:31]

        return comment

    def _get_filling_mode(self, symbol_info: dict) -> int:
        """
        Determine the appropriate filling mode for the symbol.

        Args:
            symbol_info: Symbol information dictionary

        Returns:
            MT5 filling mode constant
        """
        # Get symbol's filling mode flags
        filling_mode = symbol_info.get('filling_mode', 0)

        # If filling_mode is 0, it means it wasn't retrieved - default to FOK
        if filling_mode == 0:
            self.logger.warning(f"Filling mode not available, defaulting to FOK")
            return mt5.ORDER_FILLING_FOK

        # Check supported modes in order of preference: FOK > IOC > RETURN
        # FOK (Fill or Kill) - most restrictive, best for market orders
        if filling_mode & 1:  # SYMBOL_FILLING_FOK (bit 0)
            return mt5.ORDER_FILLING_FOK

        # IOC (Immediate or Cancel) - partial fills allowed
        elif filling_mode & 2:  # SYMBOL_FILLING_IOC (bit 1)
            return mt5.ORDER_FILLING_IOC

        # RETURN - can remain in order book
        elif filling_mode & 4:  # SYMBOL_FILLING_RETURN (bit 2)
            return mt5.ORDER_FILLING_RETURN

        # Fallback to FOK if no mode is supported (shouldn't happen)
        else:
            self.logger.warning(f"No filling mode supported (flags: {filling_mode}), defaulting to FOK")
            return mt5.ORDER_FILLING_FOK
    
    def modify_position(self, ticket: int, sl: Optional[float] = None,
                       tp: Optional[float] = None):
        """
        Modify position SL/TP.

        Args:
            ticket: Position ticket
            sl: New stop loss (None to keep current)
            tp: New take profit (None to keep current)

        Returns:
            True if successful
            False if failed (permanent error)
            "RETRY" if temporarily blocked by server (should retry later)
        """
        try:
            # Check if in cooldown period
            if self.cooldown.is_in_cooldown():
                # Return RETRY to keep position in tracking
                return "RETRY"

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
            # Ensure values are always float type for MT5 compatibility
            new_sl = self.normalize_price(symbol, new_sl) if new_sl > 0 else 0.0
            new_tp = self.normalize_price(symbol, new_tp) if new_tp > 0 else 0.0

            # Check if values actually changed after normalization
            # MT5 returns error 10025 "No changes" if SL/TP are identical
            # Use tolerance-based comparison to avoid floating-point precision issues
            symbol_info = self.connector.get_symbol_info(symbol)
            if symbol_info is None:
                self.logger.error(f"Failed to get symbol info for modifying position {ticket}")
                return False

            point = symbol_info['point']
            tolerance = point * 0.1  # Use 0.1 point as tolerance

            sl_unchanged = abs(new_sl - pos.sl) < tolerance
            tp_unchanged = abs(new_tp - pos.tp) < tolerance

            if sl_unchanged and tp_unchanged:
                self.logger.debug(
                    f"Position {ticket} modification skipped - no changes after normalization "
                    f"(SL: {new_sl:.5f}, TP: {new_tp:.5f})",
                    symbol
                )
                return True  # Return True since position is already in desired state

            # Get current market price for logging
            current_price = self.connector.get_current_price(symbol, 'bid' if pos.type == mt5.POSITION_TYPE_BUY else 'ask')
            if current_price is None:
                self.logger.error(f"Failed to get current price for modifying position {ticket}")
                return False

            # Log modification details
            self.logger.debug(
                f"Modifying position {ticket}: Current price={current_price:.5f}, "
                f"SL: {pos.sl:.5f} -> {new_sl:.5f}, TP: {pos.tp:.5f} -> {new_tp:.5f}",
                symbol
            )

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
                # Get last error from MT5
                last_error = mt5.last_error()
                self.logger.error(
                    f"Modify failed for position {ticket}, no result returned from MT5. "
                    f"Last error: {last_error}",
                    symbol
                )
                return False

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                # Log additional context for common errors
                if result.retcode == 10016:  # Invalid stops
                    self.logger.error(
                        f"Modify failed for position {ticket}: retcode={result.retcode}, "
                        f"comment='{result.comment}'",
                        symbol
                    )
                    point = symbol_info['point']
                    stops_level = symbol_info.get('stops_level', 0)
                    freeze_level = symbol_info.get('freeze_level', 0)

                    sl_distance = abs(current_price - new_sl) if new_sl > 0 else 0
                    tp_distance = abs(current_price - new_tp) if new_tp > 0 else 0
                    sl_distance_points = sl_distance / point if point > 0 else 0
                    tp_distance_points = tp_distance / point if point > 0 else 0

                    self.logger.error(
                        f"  stops_level={stops_level} pts, freeze_level={freeze_level} pts",
                        symbol
                    )
                    self.logger.error(
                        f"  SL distance: {sl_distance_points:.0f} pts, TP distance: {tp_distance_points:.0f} pts",
                        symbol
                    )
                elif result.retcode == 10026:  # AutoTrading disabled by server
                    self.logger.warning(
                        f"Modify blocked - AutoTrading disabled by server (retcode 10026)",
                        symbol
                    )
                    # Activate cooldown to prevent spam
                    self.cooldown.activate_cooldown("AutoTrading disabled by server (error 10026)")
                    # Return RETRY to keep position in tracking
                    return "RETRY"
                elif result.retcode == 10027:  # Autotrading disabled by terminal
                    self.logger.error(
                        f"Modify failed for position {ticket}: retcode={result.retcode}, "
                        f"comment='{result.comment}'",
                        symbol
                    )
                    self.logger.error("  Autotrading is disabled on this account", symbol)
                elif result.retcode == 10025:  # No changes
                    self.logger.debug(
                        f"Modify skipped for position {ticket}: No changes detected by broker",
                        symbol
                    )
                    # Return True since position is already in desired state
                    return True
                else:
                    self.logger.error(
                        f"Modify failed for position {ticket}: retcode={result.retcode}, "
                        f"comment='{result.comment}'",
                        symbol
                    )

                return False

            self.logger.debug(
                f"Position {ticket} modified - SL: {new_sl:.5f} (was {pos.sl:.5f}), TP: {new_tp:.5f} (was {pos.tp:.5f})",
                symbol
            )

            # Update position in persistence
            self.persistence.update_position(ticket, sl=new_sl, tp=new_tp)

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

            # Get symbol info to determine filling mode
            symbol_info = self.connector.get_symbol_info(symbol)
            if symbol_info is None:
                self.logger.error(f"Failed to get symbol info for closing {ticket}")
                return False

            filling_mode = self._get_filling_mode(symbol_info)

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
                "type_filling": filling_mode,
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

            # Remove position from persistence
            self.persistence.remove_position(ticket)

            return True

        except Exception as e:
            self.logger.error(f"Error closing position {ticket}: {e}")
            return False

