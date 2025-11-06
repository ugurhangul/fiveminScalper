"""
Timeframe Mapper Utility

Handles conversion between timeframe string representations and MT5 timeframe constants.
Centralizes timeframe mapping logic to eliminate duplication.
"""
import MetaTrader5 as mt5
from typing import Optional
from src.constants import MT5Timeframe


class TimeframeMapper:
    """Utility class for mapping timeframe strings to MT5 constants"""
    
    # MT5 timeframe constant mapping
    _TIMEFRAME_TO_MT5 = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
        'W1': mt5.TIMEFRAME_W1,
        'MN1': mt5.TIMEFRAME_MN1,
    }
    
    # Reverse mapping (MT5 constant to string)
    _MT5_TO_TIMEFRAME = {v: k for k, v in _TIMEFRAME_TO_MT5.items()}
    
    @classmethod
    def to_mt5_constant(cls, timeframe: str) -> Optional[int]:
        """
        Convert timeframe string to MT5 constant.
        
        Args:
            timeframe: Timeframe string (e.g., 'M5', 'H4', 'D1')
            
        Returns:
            MT5 timeframe constant or None if invalid
            
        Examples:
            >>> TimeframeMapper.to_mt5_constant('M5')
            5
            >>> TimeframeMapper.to_mt5_constant('H4')
            16388
        """
        return cls._TIMEFRAME_TO_MT5.get(timeframe.upper())
    
    @classmethod
    def to_string(cls, mt5_constant: int) -> Optional[str]:
        """
        Convert MT5 timeframe constant to string.
        
        Args:
            mt5_constant: MT5 timeframe constant
            
        Returns:
            Timeframe string or None if invalid
            
        Examples:
            >>> TimeframeMapper.to_string(5)
            'M5'
            >>> TimeframeMapper.to_string(16388)
            'H4'
        """
        return cls._MT5_TO_TIMEFRAME.get(mt5_constant)
    
    @classmethod
    def is_valid(cls, timeframe: str) -> bool:
        """
        Check if timeframe string is valid.
        
        Args:
            timeframe: Timeframe string to validate
            
        Returns:
            True if valid, False otherwise
            
        Examples:
            >>> TimeframeMapper.is_valid('M5')
            True
            >>> TimeframeMapper.is_valid('M7')
            False
        """
        return timeframe.upper() in cls._TIMEFRAME_TO_MT5
    
    @classmethod
    def get_all_timeframes(cls) -> list:
        """
        Get list of all supported timeframe strings.
        
        Returns:
            List of timeframe strings
            
        Examples:
            >>> TimeframeMapper.get_all_timeframes()
            ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1', 'MN1']
        """
        return list(cls._TIMEFRAME_TO_MT5.keys())
    
    @classmethod
    def get_timeframe_minutes(cls, timeframe: str) -> Optional[int]:
        """
        Get the duration of a timeframe in minutes.
        
        Args:
            timeframe: Timeframe string
            
        Returns:
            Duration in minutes or None if invalid
            
        Examples:
            >>> TimeframeMapper.get_timeframe_minutes('M5')
            5
            >>> TimeframeMapper.get_timeframe_minutes('H1')
            60
            >>> TimeframeMapper.get_timeframe_minutes('H4')
            240
        """
        timeframe_minutes = {
            'M1': 1,
            'M5': 5,
            'M15': 15,
            'M30': 30,
            'H1': 60,
            'H4': 240,
            'D1': 1440,
            'W1': 10080,
            'MN1': 43200,  # Approximate (30 days)
        }
        return timeframe_minutes.get(timeframe.upper())

