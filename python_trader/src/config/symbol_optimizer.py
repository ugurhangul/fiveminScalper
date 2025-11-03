"""
Symbol-specific optimization.
Ported from FMS_SymbolOptimization.mqh
"""
from typing import Dict
from src.models.data_models import SymbolCategory, SymbolParameters


class SymbolOptimizer:
    """Manages symbol-specific parameter optimization"""
    
    # Symbol category detection patterns
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
    
    # Optimized parameters for each category
    CATEGORY_PARAMETERS = {
        SymbolCategory.MAJOR_FOREX: SymbolParameters(
            breakout_volume_max=0.8,
            reversal_volume_min=1.8,
            volume_average_period=20,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=20,
            adaptive_loss_trigger=3,
            adaptive_win_recovery=2,
            max_spread_percent=0.05  # Major pairs: 0.05% (tight spreads)
        ),
        SymbolCategory.MINOR_FOREX: SymbolParameters(
            breakout_volume_max=0.7,
            reversal_volume_min=2.0,
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=2,
            adaptive_win_recovery=3,
            max_spread_percent=0.2  # Minor pairs: 0.2% (moderate spreads)
        ),
        SymbolCategory.EXOTIC_FOREX: SymbolParameters(
            breakout_volume_max=0.6,
            reversal_volume_min=2.5,
            volume_average_period=30,
            rsi_period=21,
            macd_fast=16,
            macd_slow=32,
            macd_signal=12,
            divergence_lookback=30,
            adaptive_loss_trigger=2,
            adaptive_win_recovery=4,
            max_spread_percent=0.05 
        ),
        SymbolCategory.METALS: SymbolParameters(
            breakout_volume_max=0.7,
            reversal_volume_min=2.2,
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=2,
            adaptive_win_recovery=3,
            max_spread_percent=0.1  # Metals: 0.1%
        ),
        SymbolCategory.INDICES: SymbolParameters(
            breakout_volume_max=0.8,
            reversal_volume_min=1.8,
            volume_average_period=20,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=20,
            adaptive_loss_trigger=3,
            adaptive_win_recovery=2,
            max_spread_percent=0.1  # Indices: 0.1%
        ),
        SymbolCategory.CRYPTO: SymbolParameters(
            breakout_volume_max=0.5,
            reversal_volume_min=3.0,
            volume_average_period=40,
            rsi_period=21,
            macd_fast=16,
            macd_slow=32,
            macd_signal=12,
            divergence_lookback=40,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=5,
            max_spread_percent=0.5  # Crypto: 0.5% (very wide spreads acceptable)
        ),
        SymbolCategory.COMMODITIES: SymbolParameters(
            breakout_volume_max=0.7,
            reversal_volume_min=2.0,
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=2,
            adaptive_win_recovery=3,
            max_spread_percent=0.1  # Commodities: 0.1%
        )
    }
    
    @classmethod
    def detect_category(cls, symbol: str) -> SymbolCategory:
        """
        Detect symbol category based on symbol name.
        
        Args:
            symbol: Symbol name (e.g., 'EURUSD', 'XAUUSD')
            
        Returns:
            SymbolCategory enum value
        """
        symbol_upper = symbol.upper()
        
        for category, patterns in cls.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern in symbol_upper:
                    return category
        
        return SymbolCategory.UNKNOWN
    
    @classmethod
    def get_category_name(cls, category: SymbolCategory) -> str:
        """Get human-readable category name"""
        names = {
            SymbolCategory.MAJOR_FOREX: "Major Forex",
            SymbolCategory.MINOR_FOREX: "Minor Forex",
            SymbolCategory.EXOTIC_FOREX: "Exotic Forex",
            SymbolCategory.METALS: "Precious Metals",
            SymbolCategory.INDICES: "Stock Indices",
            SymbolCategory.CRYPTO: "Cryptocurrencies",
            SymbolCategory.COMMODITIES: "Commodities",
            SymbolCategory.UNKNOWN: "Unknown"
        }
        return names.get(category, "Unknown")
    
    @classmethod
    def get_parameters(cls, category: SymbolCategory, default_params: SymbolParameters) -> SymbolParameters:
        """
        Get optimized parameters for symbol category.
        
        Args:
            category: Symbol category
            default_params: Default parameters to use if category is unknown
            
        Returns:
            SymbolParameters for the category
        """
        if category == SymbolCategory.UNKNOWN:
            return default_params
        
        return cls.CATEGORY_PARAMETERS.get(category, default_params)
    
    @classmethod
    def get_symbol_parameters(cls, symbol: str, default_params: SymbolParameters) -> tuple[SymbolCategory, SymbolParameters]:
        """
        Get category and optimized parameters for a symbol.
        
        Args:
            symbol: Symbol name
            default_params: Default parameters
            
        Returns:
            Tuple of (category, parameters)
        """
        category = cls.detect_category(symbol)
        params = cls.get_parameters(category, default_params)
        return category, params

