"""
Price and Volume Normalization Utilities

Provides utility functions for normalizing prices and volumes according to
symbol specifications. Eliminates code duplication across OrderManager and RiskManager.
"""
from typing import Optional, Dict, Any
from src.utils.logger import get_logger


class PriceNormalizer:
    """Utility class for normalizing prices to symbol specifications"""
    
    def __init__(self, connector):
        """
        Initialize price normalizer.
        
        Args:
            connector: MT5Connector instance for accessing symbol information
        """
        self.connector = connector
        self.logger = get_logger()
    
    def normalize_price(self, symbol: str, price: float) -> float:
        """
        Normalize price to symbol's digits.
        
        Args:
            symbol: Symbol name
            price: Price to normalize
            
        Returns:
            Normalized price rounded to symbol's digit precision
            
        Examples:
            >>> normalizer.normalize_price('EURUSD', 1.123456)
            1.12346  # Rounded to 5 digits for EURUSD
        """
        info = self.connector.get_symbol_info(symbol)
        if info is None:
            self.logger.warning(f"Could not get symbol info for {symbol}, returning unnormalized price")
            return price
        
        digits = info['digits']
        return round(price, digits)
    
    def normalize_price_to_tick(self, symbol: str, price: float) -> float:
        """
        Normalize price to symbol's tick size.
        
        Args:
            symbol: Symbol name
            price: Price to normalize
            
        Returns:
            Normalized price rounded to nearest tick
            
        Examples:
            >>> normalizer.normalize_price_to_tick('EURUSD', 1.12345)
            1.12345  # Rounded to nearest tick
        """
        info = self.connector.get_symbol_info(symbol)
        if info is None:
            self.logger.warning(f"Could not get symbol info for {symbol}, returning unnormalized price")
            return price
        
        tick_size = info.get('trade_tick_size', info['point'])
        if tick_size <= 0:
            return self.normalize_price(symbol, price)
        
        # Round to nearest tick
        normalized = round(price / tick_size) * tick_size
        
        # Also apply digit rounding
        digits = info['digits']
        return round(normalized, digits)
    
    def calculate_price_distance_in_points(self, symbol: str, price1: float, price2: float) -> float:
        """
        Calculate distance between two prices in points.
        
        Args:
            symbol: Symbol name
            price1: First price
            price2: Second price
            
        Returns:
            Distance in points (always positive)
            
        Examples:
            >>> normalizer.calculate_price_distance_in_points('EURUSD', 1.1000, 1.1050)
            500.0  # 50 pips = 500 points for 5-digit broker
        """
        info = self.connector.get_symbol_info(symbol)
        if info is None:
            self.logger.warning(f"Could not get symbol info for {symbol}")
            return 0.0
        
        point = info['point']
        if point <= 0:
            return 0.0
        
        return abs(price1 - price2) / point


class VolumeNormalizer:
    """Utility class for normalizing volumes (lot sizes) to symbol specifications"""
    
    def __init__(self, connector):
        """
        Initialize volume normalizer.
        
        Args:
            connector: MT5Connector instance for accessing symbol information
        """
        self.connector = connector
        self.logger = get_logger()
    
    def normalize_volume(self, symbol: str, volume: float) -> float:
        """
        Normalize volume to symbol's lot step and clamp to min/max.
        
        Args:
            symbol: Symbol name
            volume: Volume to normalize
            
        Returns:
            Normalized volume rounded to lot step and clamped to symbol's min/max
            
        Examples:
            >>> normalizer.normalize_volume('EURUSD', 0.123)
            0.12  # Rounded to 0.01 lot step
        """
        info = self.connector.get_symbol_info(symbol)
        if info is None:
            self.logger.warning(f"Could not get symbol info for {symbol}, returning unnormalized volume")
            return volume
        
        min_lot = info['min_lot']
        max_lot = info['max_lot']
        lot_step = info['lot_step']
        
        # Round to lot step
        if lot_step > 0:
            volume = round(volume / lot_step) * lot_step
        
        # Clamp to min/max
        volume = max(min_lot, min(max_lot, volume))
        
        return volume
    
    def get_volume_limits(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get volume limits for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Dictionary with 'min_lot', 'max_lot', 'lot_step' or None if error
            
        Examples:
            >>> normalizer.get_volume_limits('EURUSD')
            {'min_lot': 0.01, 'max_lot': 100.0, 'lot_step': 0.01}
        """
        info = self.connector.get_symbol_info(symbol)
        if info is None:
            return None
        
        return {
            'min_lot': info['min_lot'],
            'max_lot': info['max_lot'],
            'lot_step': info['lot_step']
        }
    
    def is_valid_volume(self, symbol: str, volume: float) -> bool:
        """
        Check if volume is valid for symbol.
        
        Args:
            symbol: Symbol name
            volume: Volume to check
            
        Returns:
            True if volume is within limits and matches lot step, False otherwise
        """
        limits = self.get_volume_limits(symbol)
        if limits is None:
            return False
        
        # Check min/max
        if volume < limits['min_lot'] or volume > limits['max_lot']:
            return False
        
        # Check lot step alignment
        lot_step = limits['lot_step']
        if lot_step > 0:
            remainder = abs(volume - round(volume / lot_step) * lot_step)
            if remainder > lot_step * 0.01:  # Allow small floating point errors
                return False
        
        return True


class CurrencyConverter:
    """Utility class for currency conversion operations"""
    
    def __init__(self, connector):
        """
        Initialize currency converter.
        
        Args:
            connector: MT5Connector instance for accessing currency rates
        """
        self.connector = connector
        self.logger = get_logger()
    
    def convert(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Convert amount from one currency to another.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (e.g., 'EUR')
            
        Returns:
            Converted amount or None if conversion rate not available
            
        Examples:
            >>> converter.convert(100.0, 'USD', 'EUR')
            92.5  # If EURUSD = 1.08
        """
        if from_currency == to_currency:
            return amount
        
        rate = self.connector.get_currency_conversion_rate(from_currency, to_currency)
        if rate is None:
            self.logger.warning(
                f"Could not get conversion rate from {from_currency} to {to_currency}"
            )
            return None
        
        return amount * rate
    
    def get_conversion_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Get conversion rate between two currencies.
        
        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            
        Returns:
            Conversion rate or None if not available
            
        Examples:
            >>> converter.get_conversion_rate('USD', 'EUR')
            0.925  # If EURUSD = 1.08
        """
        return self.connector.get_currency_conversion_rate(from_currency, to_currency)
    
    def convert_with_logging(self, amount: float, from_currency: str, to_currency: str,
                            symbol: str = "") -> Optional[float]:
        """
        Convert amount with detailed logging.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            symbol: Symbol name for logging context (optional)
            
        Returns:
            Converted amount or None if conversion failed
        """
        if from_currency == to_currency:
            return amount
        
        rate = self.get_conversion_rate(from_currency, to_currency)
        if rate is None:
            self.logger.error(
                f"Failed to get conversion rate from {from_currency} to {to_currency}. "
                f"Calculation may be incorrect!",
                symbol if symbol else None
            )
            return None
        
        converted = amount * rate
        
        self.logger.info(
            f"Currency conversion: {from_currency} -> {to_currency}, "
            f"Rate={rate:.5f}, Amount: {amount:.5f} -> {converted:.5f}",
            symbol if symbol else None
        )
        
        return converted

