"""
MetaTrader 5 connection and data feed handler.
Manages connection to MT5 and provides real-time data for multiple symbols.
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from src.models.data_models import CandleData, PositionInfo, PositionType
from src.config.config import MT5Config
from src.utils.logger import get_logger


class MT5Connector:
    """Manages connection to MetaTrader 5 and data retrieval"""
    
    def __init__(self, config: MT5Config):
        """
        Initialize MT5 connector.
        
        Args:
            config: MT5 configuration
        """
        self.config = config
        self.logger = get_logger()
        self.is_connected = False
        self._symbol_info_cache: Dict[str, dict] = {}
    
    def connect(self) -> bool:
        """
        Connect to MetaTrader 5.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Initialize MT5
            if not mt5.initialize():
                self.logger.error(f"MT5 initialize() failed, error code: {mt5.last_error()}")
                return False
            
            # Login to account
            authorized = mt5.login(
                login=self.config.login,
                password=self.config.password,
                server=self.config.server,
                timeout=self.config.timeout
            )
            
            if not authorized:
                error = mt5.last_error()
                self.logger.error(f"MT5 login failed, error code: {error}")
                mt5.shutdown()
                return False
            
            self.is_connected = True
            
            # Log account info
            account_info = mt5.account_info()
            if account_info:
                self.logger.info("=== MT5 Connection Successful ===")
                self.logger.info(f"Account: {account_info.login}")
                self.logger.info(f"Server: {account_info.server}")
                self.logger.info(f"Balance: ${account_info.balance:.2f}")
                self.logger.info(f"Equity: ${account_info.equity:.2f}")
                self.logger.info(f"Currency: {account_info.currency}")
                self.logger.separator()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to MT5: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MetaTrader 5"""
        if self.is_connected:
            mt5.shutdown()
            self.is_connected = False
            self.logger.info("Disconnected from MT5")
    
    def get_candles(self, symbol: str, timeframe: str, count: int = 100) -> Optional[pd.DataFrame]:
        """
        Get historical candles for a symbol.
        
        Args:
            symbol: Symbol name
            timeframe: Timeframe ('M5', 'H4', etc.)
            count: Number of candles to retrieve
            
        Returns:
            DataFrame with OHLCV data or None if error
        """
        if not self.is_connected:
            self.logger.error("Not connected to MT5")
            return None
        
        # Map timeframe string to MT5 constant
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
        }
        
        tf = timeframe_map.get(timeframe)
        if tf is None:
            self.logger.error(f"Invalid timeframe: {timeframe}")
            return None
        
        try:
            # Get candles
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)

            if rates is None or len(rates) == 0:
                self.logger.trade_error(
                    symbol=symbol,
                    error_type="Data Retrieval",
                    error_message=f"Failed to get {timeframe} candles from MT5",
                    context={
                        "timeframe": timeframe,
                        "count": count,
                        "mt5_error": str(mt5.last_error())
                    }
                )
                return None

            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')

            return df

        except Exception as e:
            self.logger.trade_error(
                symbol=symbol,
                error_type="Data Retrieval",
                error_message=f"Exception while getting {timeframe} candles: {str(e)}",
                context={
                    "timeframe": timeframe,
                    "count": count,
                    "exception_type": type(e).__name__
                }
            )
            return None
    
    def get_latest_candle(self, symbol: str, timeframe: str) -> Optional[CandleData]:
        """
        Get the latest closed candle.
        
        Args:
            symbol: Symbol name
            timeframe: Timeframe
            
        Returns:
            CandleData object or None
        """
        df = self.get_candles(symbol, timeframe, count=2)
        if df is None or len(df) < 2:
            return None
        
        # Get the second-to-last candle (last closed candle)
        candle = df.iloc[-2]
        
        return CandleData(
            time=candle['time'],
            open=candle['open'],
            high=candle['high'],
            low=candle['low'],
            close=candle['close'],
            volume=int(candle['tick_volume'])
        )
    
    def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """
        Get symbol information (cached).
        
        Args:
            symbol: Symbol name
            
        Returns:
            Dictionary with symbol info or None
        """
        # Check cache first
        if symbol in self._symbol_info_cache:
            return self._symbol_info_cache[symbol]
        
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                self.logger.error(f"Failed to get symbol info for {symbol}")
                return None
            
            symbol_dict = {
                'point': info.point,
                'digits': info.digits,
                'tick_value': info.trade_tick_value,
                'tick_size': info.trade_tick_size,
                'min_lot': info.volume_min,
                'max_lot': info.volume_max,
                'lot_step': info.volume_step,
                'contract_size': info.trade_contract_size,
                'filling_mode': info.filling_mode,
                'stops_level': info.trade_stops_level,
                'freeze_level': info.trade_freeze_level,
                'trade_mode': info.trade_mode,
                'currency_base': info.currency_base,
                'currency_profit': info.currency_profit,
                'currency_margin': info.currency_margin,
                'category': info.category,  # MT5 native category (e.g., 'Majors', 'Crypto', etc.)
            }
            
            # Cache it
            self._symbol_info_cache[symbol] = symbol_dict
            
            return symbol_dict
            
        except Exception as e:
            self.logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None

    def clear_symbol_info_cache(self, symbol: Optional[str] = None):
        """
        Clear symbol info cache.

        Args:
            symbol: Symbol to clear from cache, or None to clear all
        """
        if symbol:
            self._symbol_info_cache.pop(symbol, None)
        else:
            self._symbol_info_cache.clear()

    def get_account_balance(self) -> float:
        """Get current account balance"""
        if not self.is_connected:
            return 0.0
        
        account_info = mt5.account_info()
        return account_info.balance if account_info else 0.0
    
    def get_account_equity(self) -> float:
        """Get current account equity"""
        if not self.is_connected:
            return 0.0

        account_info = mt5.account_info()
        return account_info.equity if account_info else 0.0

    def get_account_currency(self) -> str:
        """Get account currency"""
        if not self.is_connected:
            return ""

        account_info = mt5.account_info()
        return account_info.currency if account_info else ""

    def get_currency_conversion_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Get conversion rate from one currency to another.

        Args:
            from_currency: Source currency (e.g., 'THB')
            to_currency: Target currency (e.g., 'USD')

        Returns:
            Conversion rate or None if not available
        """
        if from_currency == to_currency:
            return 1.0

        # Try direct pair: FROMTO (e.g., THBUSD)
        direct_pair = f"{from_currency}{to_currency}"
        tick = mt5.symbol_info_tick(direct_pair)
        if tick is not None:
            # Use bid price for conversion
            return tick.bid

        # Try inverse pair: TOFROM (e.g., USDTHB)
        inverse_pair = f"{to_currency}{from_currency}"
        tick = mt5.symbol_info_tick(inverse_pair)
        if tick is not None:
            # Use inverse of ask price for conversion
            return 1.0 / tick.ask if tick.ask > 0 else None

        # Try with common separators
        for separator in ['/', '.', '_', '']:
            if separator:
                direct_pair_sep = f"{from_currency}{separator}{to_currency}"
                tick = mt5.symbol_info_tick(direct_pair_sep)
                if tick is not None:
                    return tick.bid

                inverse_pair_sep = f"{to_currency}{separator}{from_currency}"
                tick = mt5.symbol_info_tick(inverse_pair_sep)
                if tick is not None:
                    return 1.0 / tick.ask if tick.ask > 0 else None

        self.logger.warning(
            f"Could not find conversion rate for {from_currency} to {to_currency}. "
            f"Tried: {direct_pair}, {inverse_pair}"
        )
        return None

    def get_positions(self, symbol: Optional[str] = None, magic_number: Optional[int] = None) -> List[PositionInfo]:
        """
        Get open positions.

        Args:
            symbol: Filter by symbol (optional)
            magic_number: Filter by magic number (optional)

        Returns:
            List of PositionInfo objects
        """
        if not self.is_connected:
            return []

        try:
            # Get all positions or filter by symbol
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()

            if positions is None:
                return []

            result = []
            for pos in positions:
                # Filter by magic number if specified
                if magic_number is not None and pos.magic != magic_number:
                    continue

                pos_info = PositionInfo(
                    ticket=pos.ticket,
                    symbol=pos.symbol,
                    position_type=PositionType.BUY if pos.type == mt5.ORDER_TYPE_BUY else PositionType.SELL,
                    volume=pos.volume,
                    open_price=pos.price_open,
                    current_price=pos.price_current,
                    sl=pos.sl,
                    tp=pos.tp,
                    profit=pos.profit,
                    open_time=datetime.fromtimestamp(pos.time),
                    magic_number=pos.magic,
                    comment=pos.comment
                )
                result.append(pos_info)

            return result

        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []

    def get_closed_position_info(self, ticket: int) -> Optional[Tuple[str, float]]:
        """
        Get information about a closed position from history.

        Args:
            ticket: Position ticket

        Returns:
            Tuple of (symbol, profit) or None if not found
        """
        if not self.is_connected:
            return None

        try:
            # Request history for the last 7 days
            from_date = datetime.now() - timedelta(days=7)
            to_date = datetime.now()

            # Get history deals
            if not mt5.history_deals_get(from_date, to_date):
                self.logger.warning(f"Failed to get history deals for ticket {ticket}")
                return None

            # Get all deals
            deals = mt5.history_deals_get(from_date, to_date)
            if deals is None or len(deals) == 0:
                return None

            # Find the OUT deal for this position
            for deal in deals:
                # Check if this is an OUT deal (position closure) for our ticket
                if (deal.position_id == ticket and
                    deal.entry == mt5.DEAL_ENTRY_OUT):

                    symbol = deal.symbol
                    profit = deal.profit

                    return (symbol, profit)

            return None

        except Exception as e:
            self.logger.error(f"Error getting closed position info for ticket {ticket}: {e}")
            return None

    def get_current_price(self, symbol: str, price_type: str = 'bid') -> Optional[float]:
        """
        Get current price for symbol.

        Args:
            symbol: Symbol name
            price_type: 'bid' or 'ask'

        Returns:
            Current price or None
        """
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None

            return tick.bid if price_type == 'bid' else tick.ask

        except Exception as e:
            self.logger.error(f"Error getting price for {symbol}: {e}")
            return None

    def get_spread(self, symbol: str) -> Optional[float]:
        """
        Get current spread for symbol in points.

        Args:
            symbol: Symbol name

        Returns:
            Spread in points or None
        """
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None

            symbol_info = self.get_symbol_info(symbol)
            if symbol_info is None:
                return None

            # Calculate spread in points
            point = symbol_info['point']
            spread_price = tick.ask - tick.bid
            spread_points = spread_price / point if point > 0 else 0

            return spread_points

        except Exception as e:
            self.logger.error(f"Error getting spread for {symbol}: {e}")
            return None

    def get_spread_percent(self, symbol: str) -> Optional[float]:
        """
        Get current spread as percentage of price.

        Args:
            symbol: Symbol name

        Returns:
            Spread as percentage (e.g., 0.05 = 0.05%) or None
        """
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None

            # Calculate spread as percentage of mid price
            spread_price = tick.ask - tick.bid
            mid_price = (tick.ask + tick.bid) / 2

            if mid_price == 0:
                return None

            spread_percent = (spread_price / mid_price) * 100

            return spread_percent

        except Exception as e:
            self.logger.error(f"Error getting spread percent for {symbol}: {e}")
            return None

    def is_autotrading_enabled(self) -> bool:
        """
        Check if AutoTrading is enabled in MT5 terminal.

        Returns:
            True if AutoTrading is enabled, False otherwise
        """
        try:
            if not self.is_connected:
                return False

            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                self.logger.error("Failed to get terminal info")
                return False

            # Check if trade is allowed in terminal
            return terminal_info.trade_allowed

        except Exception as e:
            self.logger.error(f"Error checking AutoTrading status: {e}")
            return False

    def is_trading_enabled(self, symbol: str) -> bool:
        """
        Check if trading is enabled for a symbol.

        Args:
            symbol: Symbol name

        Returns:
            True if trading is enabled, False otherwise
        """
        try:
            symbol_info = self.get_symbol_info(symbol)
            if symbol_info is None:
                return False

            # trade_mode values:
            # 0 = SYMBOL_TRADE_MODE_DISABLED - trading disabled
            # 1 = SYMBOL_TRADE_MODE_LONGONLY - only long positions allowed
            # 2 = SYMBOL_TRADE_MODE_SHORTONLY - only short positions allowed
            # 3 = SYMBOL_TRADE_MODE_CLOSEONLY - only position closing allowed
            # 4 = SYMBOL_TRADE_MODE_FULL - no restrictions
            trade_mode = symbol_info.get('trade_mode', 0)

            # Trading is enabled if mode is not DISABLED (0)
            return trade_mode != 0

        except Exception as e:
            self.logger.error(f"Error checking if trading enabled for {symbol}: {e}")
            return False

    def get_market_watch_symbols(self) -> List[str]:
        """
        Get all symbols from MetaTrader's Market Watch list.

        Returns:
            List of symbol names currently in Market Watch
        """
        if not self.is_connected:
            self.logger.error("Not connected to MT5")
            return []

        try:
            symbols = []
            total = mt5.symbols_total()

            if total == 0:
                self.logger.warning("No symbols found in Market Watch")
                return []

            # Get all symbols
            for i in range(total):
                symbol_info = mt5.symbol_info(mt5.symbols_get()[i].name)
                if symbol_info is not None and symbol_info.visible:
                    symbols.append(symbol_info.name)

            self.logger.info(f"Found {len(symbols)} symbols in Market Watch")
            return symbols

        except Exception as e:
            self.logger.error(f"Error getting Market Watch symbols: {e}")
            return []

