"""
Historical data loader for backtesting.
Loads candle data from MT5 for specified date ranges.
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from src.utils.logger import get_logger


class HistoricalDataLoader:
    """Loads historical data from MT5 for backtesting"""
    
    def __init__(self, connector):
        """
        Initialize historical data loader.
        
        Args:
            connector: MT5Connector instance (must be connected)
        """
        self.connector = connector
        self.logger = get_logger()
        
        # Cache for loaded data
        self.data_cache: Dict[str, pd.DataFrame] = {}
    
    def load_data(self, symbol: str, timeframe: str, 
                  start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Load historical candle data for a symbol.
        
        Args:
            symbol: Symbol name
            timeframe: Timeframe ('M5', 'H4', etc.)
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            DataFrame with OHLCV data or None if error
        """
        cache_key = f"{symbol}_{timeframe}_{start_date}_{end_date}"
        
        # Check cache first
        if cache_key in self.data_cache:
            self.logger.info(f"Loading {symbol} {timeframe} from cache")
            return self.data_cache[cache_key]
        
        if not self.connector.is_connected:
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
            self.logger.info(f"Loading {symbol} {timeframe} data from {start_date} to {end_date}")
            
            # Get candles from MT5
            rates = mt5.copy_rates_range(symbol, tf, start_date, end_date)
            
            if rates is None or len(rates) == 0:
                self.logger.error(f"Failed to get candles for {symbol} {timeframe}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Sort by time
            df = df.sort_values('time').reset_index(drop=True)
            
            self.logger.info(f"Loaded {len(df)} candles for {symbol} {timeframe}")
            
            # Cache the data
            self.data_cache[cache_key] = df
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading data for {symbol}: {e}")
            return None
    
    def load_multiple_symbols(self, symbols: List[str], timeframe: str,
                             start_date: datetime, end_date: datetime) -> Dict[str, pd.DataFrame]:
        """
        Load historical data for multiple symbols.
        
        Args:
            symbols: List of symbol names
            timeframe: Timeframe ('M5', 'H4', etc.)
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        data = {}
        
        for symbol in symbols:
            df = self.load_data(symbol, timeframe, start_date, end_date)
            if df is not None:
                data[symbol] = df
            else:
                self.logger.warning(f"Failed to load data for {symbol}")
        
        return data
    
    def get_candle_at_time(self, df: pd.DataFrame, target_time: datetime) -> Optional[pd.Series]:
        """
        Get the candle at a specific time.
        
        Args:
            df: DataFrame with candle data
            target_time: Target time
            
        Returns:
            Series with candle data or None
        """
        # Find candle with matching time
        mask = df['time'] == target_time
        if mask.any():
            return df[mask].iloc[0]
        
        # If exact match not found, find closest candle before target time
        mask = df['time'] <= target_time
        if mask.any():
            return df[mask].iloc[-1]
        
        return None
    
    def get_candles_up_to_time(self, df: pd.DataFrame, target_time: datetime, 
                               count: int = 100) -> Optional[pd.DataFrame]:
        """
        Get candles up to a specific time.
        
        Args:
            df: DataFrame with candle data
            target_time: Target time
            count: Number of candles to retrieve
            
        Returns:
            DataFrame with candles or None
        """
        # Get all candles up to target time
        mask = df['time'] <= target_time
        if not mask.any():
            return None
        
        candles = df[mask].tail(count)
        return candles.reset_index(drop=True)
    
    def clear_cache(self):
        """Clear the data cache"""
        self.data_cache.clear()
        self.logger.info("Data cache cleared")

