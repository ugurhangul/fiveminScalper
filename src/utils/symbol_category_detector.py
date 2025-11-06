"""
Symbol Category Detector Utility

Centralizes symbol categorization logic using both MT5 native categories
and pattern-based fallback detection.
"""
from typing import Optional
from src.models.data_models import SymbolCategory


class SymbolCategoryDetector:
    """Utility class for detecting symbol categories"""
    
    # MT5 native category to SymbolCategory mapping
    # This is the PRIMARY categorization method when MT5 data is available
    MT5_CATEGORY_MAPPING = {
        'Majors': SymbolCategory.MAJOR_FOREX,
        'Minors': SymbolCategory.MINOR_FOREX,
        'Exotic': SymbolCategory.EXOTIC_FOREX,
        'Metals': SymbolCategory.METALS,
        'Indices': SymbolCategory.INDICES,
        'Crypto': SymbolCategory.CRYPTO,
        'Energies': SymbolCategory.COMMODITIES,
        'Stocks': SymbolCategory.STOCKS,
        # Note: 'Other', 'Heartbeat' are not mapped and will fall through to pattern matching
    }
    
    # Symbol category detection patterns (FALLBACK method when MT5 category is unavailable)
    CATEGORY_PATTERNS = {
        SymbolCategory.MAJOR_FOREX: [
            'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF',
            'AUDUSD', 'USDCAD', 'NZDUSD'
        ],
        SymbolCategory.MINOR_FOREX: [
            'EURGBP', 'EURJPY', 'GBPJPY', 'EURCHF',
            'EURAUD', 'EURCAD', 'GBPCHF', 'GBPAUD',
            'AUDNZD', 'AUDCAD', 'AUDJPY', 'CADJPY',
            'CHFJPY', 'NZDJPY', 'EURNZD', 'GBPCAD',
            'GBPNZD', 'NZDCAD', 'NZDCHF'
        ],
        SymbolCategory.EXOTIC_FOREX: [
            'TRY', 'ZAR', 'MXN', 'BRL', 'RUB', 'HKD',
            'SGD', 'THB', 'NOK', 'SEK', 'DKK', 'PLN',
            'CZK', 'HUF', 'ILS', 'CNH'
        ],
        SymbolCategory.METALS: [
            'XAUUSD', 'GOLD', 'XAGUSD', 'SILVER', 'XAU', 'XAG',
            'XALUSD', 'XCUUSD', 'XPBUSD', 'XPDUSD', 'XPTUSD', 'XZNUSD'
        ],
        SymbolCategory.INDICES: [
            'SPX', 'SP500', 'US500', 'NAS100', 'NASDAQ', 'USTEC', 'US30', 'DOW',
            'DAX', 'DE30', 'GER', 'FTSE', 'UK100', 'CAC', 'FR40', 'FRA',
            'NIKKEI', 'JP225', 'JPN', 'ASX', 'AUS', 'HK50', 'DXY'
        ],
        SymbolCategory.CRYPTO: [
            'BTC', 'ETH', 'XRP', 'LTC', 'BCH', 'ADA',
            'DOT', 'LINK', 'DOGE', 'CRYPTO', 'BNB', 'SOL',
            'UNI', 'FIL', 'BAT', 'XTZ'
        ],
        SymbolCategory.COMMODITIES: [
            'WTI', 'BRENT', 'OIL', 'USOIL', 'UKOIL', 'NGAS', 'GAS', 'XNG'
        ]
    }
    
    # Human-readable category names
    CATEGORY_NAMES = {
        SymbolCategory.MAJOR_FOREX: "Major Forex",
        SymbolCategory.MINOR_FOREX: "Minor Forex",
        SymbolCategory.EXOTIC_FOREX: "Exotic Forex",
        SymbolCategory.METALS: "Precious Metals",
        SymbolCategory.INDICES: "Stock Indices",
        SymbolCategory.CRYPTO: "Cryptocurrencies",
        SymbolCategory.COMMODITIES: "Commodities",
        SymbolCategory.STOCKS: "Stocks",
        SymbolCategory.UNKNOWN: "Unknown"
    }
    
    @classmethod
    def detect(cls, symbol: str, mt5_category: Optional[str] = None) -> SymbolCategory:
        """
        Detect symbol category, preferring MT5 native category if available.
        
        This method uses a hybrid approach:
        1. PRIMARY: Use MT5 native category from symbol_info().category if provided
        2. FALLBACK: Use pattern matching on symbol name if MT5 category is unavailable
        
        Args:
            symbol: Symbol name (e.g., 'EURUSD', 'XAUUSD')
            mt5_category: Optional MT5 native category string (e.g., 'Majors', 'Crypto', 'Exotic')
                         from mt5.symbol_info(symbol).category
        
        Returns:
            SymbolCategory enum value
        """
        # PRIMARY: Try MT5 native category first if provided
        if mt5_category:
            mapped_category = cls.MT5_CATEGORY_MAPPING.get(mt5_category)
            if mapped_category:
                return mapped_category
        
        # FALLBACK: Use pattern matching on symbol name
        symbol_upper = symbol.upper()
        
        for category, patterns in cls.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in symbol_upper:
                    return category
        
        return SymbolCategory.UNKNOWN
    
    @classmethod
    def get_category_name(cls, category: SymbolCategory) -> str:
        """
        Get human-readable category name.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            Human-readable category name
        """
        return cls.CATEGORY_NAMES.get(category, "Unknown")
    
    @classmethod
    def is_forex(cls, category: SymbolCategory) -> bool:
        """
        Check if category is any type of forex.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            True if major, minor, or exotic forex
        """
        return category in (
            SymbolCategory.MAJOR_FOREX,
            SymbolCategory.MINOR_FOREX,
            SymbolCategory.EXOTIC_FOREX
        )
    
    @classmethod
    def is_major_forex(cls, category: SymbolCategory) -> bool:
        """
        Check if category is major forex.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            True if major forex
        """
        return category == SymbolCategory.MAJOR_FOREX
    
    @classmethod
    def is_crypto(cls, category: SymbolCategory) -> bool:
        """
        Check if category is cryptocurrency.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            True if cryptocurrency
        """
        return category == SymbolCategory.CRYPTO
    
    @classmethod
    def is_metal(cls, category: SymbolCategory) -> bool:
        """
        Check if category is precious metal.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            True if precious metal
        """
        return category == SymbolCategory.METALS
    
    @classmethod
    def is_index(cls, category: SymbolCategory) -> bool:
        """
        Check if category is stock index.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            True if stock index
        """
        return category == SymbolCategory.INDICES
    
    @classmethod
    def is_commodity(cls, category: SymbolCategory) -> bool:
        """
        Check if category is commodity.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            True if commodity
        """
        return category == SymbolCategory.COMMODITIES
    
    @classmethod
    def is_stock(cls, category: SymbolCategory) -> bool:
        """
        Check if category is stock.
        
        Args:
            category: SymbolCategory enum value
            
        Returns:
            True if stock
        """
        return category == SymbolCategory.STOCKS

