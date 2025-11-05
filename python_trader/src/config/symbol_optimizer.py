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
    # Updated based on log analysis (2025-11-05) to eliminate "both strategies rejected" gaps
    CATEGORY_PARAMETERS = {
        SymbolCategory.MAJOR_FOREX: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.50-0.82x, widened to capture more opportunities
            breakout_volume_max=0.85,  # Was 0.8, increased to capture 0.82x breakouts
            reversal_volume_min=1.5,   # Was 1.8, lowered for better signal generation
            true_breakout_volume_min=1.5,  # Was 2.0, lowered to reduce rejections
            continuation_volume_min=1.3,   # Was 1.5, lowered for consistency
            volume_average_period=20,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=20,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.05  # Major pairs: 0.05% (tight spreads)
        ),
        SymbolCategory.MINOR_FOREX: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.57-0.78x, widened to eliminate gaps
            breakout_volume_max=0.90,  # Was 0.7, increased significantly
            reversal_volume_min=1.5,   # Was 2.0, lowered
            true_breakout_volume_min=1.5,  # Was 2.2, lowered significantly
            continuation_volume_min=1.3,   # Was 1.6, lowered
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.2  # Minor pairs: 0.2% (moderate spreads)
        ),
        SymbolCategory.EXOTIC_FOREX: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.80-1.03x, very wide range needs aggressive widening
            breakout_volume_max=1.20,  # Was 0.6, DOUBLED to capture 1.03x breakouts
            reversal_volume_min=1.5,   # Was 2.5, lowered significantly
            true_breakout_volume_min=1.3,  # Was 2.8, lowered significantly
            continuation_volume_min=1.2,   # Was 2.0, lowered
            volume_average_period=30,
            rsi_period=21,
            macd_fast=16,
            macd_slow=32,
            macd_signal=12,
            divergence_lookback=30,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.05
        ),
        SymbolCategory.METALS: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.70-1.06x, wide range
            breakout_volume_max=1.15,  # Was 0.7, increased significantly
            reversal_volume_min=1.5,   # Was 2.2, lowered
            true_breakout_volume_min=1.4,  # Was 2.5, lowered significantly
            continuation_volume_min=1.3,   # Was 1.8, lowered
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.1  # Metals: 0.1%
        ),
        SymbolCategory.INDICES: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.32-0.69x, relatively tight
            breakout_volume_max=0.75,  # Was 0.8, slightly lowered for precision
            reversal_volume_min=1.4,   # Was 1.8, lowered
            true_breakout_volume_min=1.3,  # Was 2.0, lowered
            continuation_volume_min=1.2,   # Was 1.5, lowered
            volume_average_period=20,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=20,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.1  # Indices: 0.1%
        ),
        SymbolCategory.CRYPTO: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.51-1.12x, VERY wide range - crypto is volatile
            breakout_volume_max=1.35,  # Was 0.5, TRIPLED to capture 1.12x breakouts
            reversal_volume_min=1.5,   # Was 3.0, halved for more signals
            true_breakout_volume_min=1.3,  # Was 3.5, significantly lowered
            continuation_volume_min=1.2,   # Was 2.5, lowered
            volume_average_period=40,
            rsi_period=21,
            macd_fast=16,
            macd_slow=32,
            macd_signal=12,
            divergence_lookback=40,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.5  # Crypto: 0.5% (very wide spreads acceptable)
        ),
        SymbolCategory.COMMODITIES: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.61-0.65x, tight range
            breakout_volume_max=0.80,  # Was 0.7, increased slightly
            reversal_volume_min=1.4,   # Was 2.0, lowered
            true_breakout_volume_min=1.3,  # Was 2.2, lowered
            continuation_volume_min=1.2,   # Was 1.6, lowered
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=1,
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

