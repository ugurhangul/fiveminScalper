"""
Symbol Parameters Repository

Stores and retrieves optimized parameters for different symbol categories.

This service follows the Single Responsibility Principle (SRP) by
focusing solely on parameter storage and retrieval.
"""
from typing import Dict
from src.models.data_models import SymbolCategory, SymbolParameters


class SymbolParametersRepository:
    """
    Repository for symbol category parameters.
    
    Stores optimized parameters for each symbol category based on
    historical performance analysis and data-driven optimization.
    """
    
    # Optimized parameters for each category
    # Updated based on log analysis (2025-11-05) to eliminate "both strategies rejected" gaps
    CATEGORY_PARAMETERS: Dict[SymbolCategory, SymbolParameters] = {
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
            max_spread_percent=0.05  # Minor pairs: 0.05% (slightly wider spreads)
        ),
        SymbolCategory.EXOTIC_FOREX: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.60-0.85x, widened significantly
            breakout_volume_max=1.0,   # Was 0.6, increased significantly
            reversal_volume_min=1.4,   # Was 2.5, lowered significantly
            true_breakout_volume_min=1.4,  # Was 2.8, lowered significantly
            continuation_volume_min=1.2,   # Was 1.8, lowered
            volume_average_period=30,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=30,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.10  # Exotic pairs: 0.10% (wider spreads)
        ),
        SymbolCategory.METALS: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.55-0.80x, widened to eliminate gaps
            breakout_volume_max=0.90,  # Was 0.75, increased
            reversal_volume_min=1.5,   # Was 2.0, lowered
            true_breakout_volume_min=1.5,  # Was 2.5, lowered significantly
            continuation_volume_min=1.3,   # Was 1.7, lowered
            volume_average_period=20,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=20,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.05  # Metals: 0.05% (tight spreads for gold/silver)
        ),
        SymbolCategory.INDICES: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.60-0.85x, widened to eliminate gaps
            breakout_volume_max=0.95,  # Was 0.7, increased significantly
            reversal_volume_min=1.5,   # Was 2.2, lowered
            true_breakout_volume_min=1.5,  # Was 2.5, lowered significantly
            continuation_volume_min=1.3,   # Was 1.8, lowered
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.08  # Indices: 0.08% (moderate spreads)
        ),
        SymbolCategory.CRYPTO: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.65-0.90x, widened significantly
            breakout_volume_max=1.0,   # Was 0.6, increased significantly
            reversal_volume_min=1.4,   # Was 3.0, lowered significantly
            true_breakout_volume_min=1.4,  # Was 3.5, lowered significantly
            continuation_volume_min=1.2,   # Was 2.0, lowered
            volume_average_period=30,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=30,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.15  # Crypto: 0.15% (very wide spreads)
        ),
        SymbolCategory.COMMODITIES: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.60-0.85x, widened to eliminate gaps
            breakout_volume_max=0.95,  # Was 0.7, increased significantly
            reversal_volume_min=1.5,   # Was 2.3, lowered
            true_breakout_volume_min=1.5,  # Was 2.6, lowered significantly
            continuation_volume_min=1.3,   # Was 1.8, lowered
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.08  # Commodities: 0.08% (moderate spreads)
        ),
        SymbolCategory.STOCKS: SymbolParameters(
            enable_false_breakout_strategy=True,
            enable_true_breakout_strategy=True,
            # Data-driven: Avg gap 0.60-0.85x, widened to eliminate gaps
            breakout_volume_max=0.95,  # Was 0.7, increased significantly
            reversal_volume_min=1.5,   # Was 2.2, lowered
            true_breakout_volume_min=1.5,  # Was 2.5, lowered significantly
            continuation_volume_min=1.3,   # Was 1.8, lowered
            volume_average_period=25,
            rsi_period=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            divergence_lookback=25,
            adaptive_loss_trigger=1,
            adaptive_win_recovery=3,
            max_spread_percent=0.10  # Stocks: 0.10% (wider spreads)
        )
    }
    
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

