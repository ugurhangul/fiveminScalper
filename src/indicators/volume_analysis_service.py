"""
Volume Analysis Service

Provides volume analysis and comparison utilities to eliminate duplication
in volume checking logic across TechnicalIndicators and strategy engines.
"""
import pandas as pd
from typing import Optional, TYPE_CHECKING
from enum import Enum
from src.constants import DEFAULT_VOLUME_PERIOD, MIN_DATA_POINTS_VOLUME

if TYPE_CHECKING:
    from src.utils.logger import TradingLogger


class VolumeCondition(Enum):
    """Volume condition types for different trading scenarios."""
    LOW = "LOW"      # Want low volume (weak breakout for false breakout strategy)
    HIGH = "HIGH"    # Want high volume (strong confirmation)


class VolumeCheckType(Enum):
    """Types of volume checks for different trading scenarios."""
    BREAKOUT_LOW = "Breakout Volume Check (Want LOW Volume)"
    REVERSAL_HIGH = "Reversal Volume Check (Want HIGH Volume)"
    TRUE_BREAKOUT_HIGH = "TRUE Breakout Volume Check (Want HIGH Volume)"
    CONTINUATION_HIGH = "Continuation Volume Check (Want HIGH Volume)"


class VolumeAnalysisService:
    """
    Service for volume analysis and comparison.
    
    This class provides methods to:
    - Calculate average volume over a period
    - Compare volume against thresholds
    - Check volume conditions for different trading scenarios
    - Provide consistent logging for volume analysis
    """
    
    def __init__(self, logger: 'TradingLogger'):
        """
        Initialize volume analysis service.

        Args:
            logger: Logger instance for logging volume analysis
        """
        self.logger = logger
    
    def calculate_average_volume(
        self,
        volumes: pd.Series,
        period: int = DEFAULT_VOLUME_PERIOD
    ) -> float:
        """
        Calculate average volume over a period.
        
        Args:
            volumes: Series of volume data
            period: Period for average (default from constants)
            
        Returns:
            Average volume, or 0.0 if insufficient data
        """
        if len(volumes) < period:
            self.logger.warning(
                f"Not enough data for volume average: {len(volumes)} < {period}"
            )
            return 0.0
        
        avg_volume = volumes.tail(period).mean()
        return float(avg_volume)
    
    def calculate_volume_ratio(
        self,
        current_volume: int,
        average_volume: float
    ) -> Optional[float]:
        """
        Calculate volume ratio (current / average).
        
        Args:
            current_volume: Current candle volume
            average_volume: Average volume
            
        Returns:
            Volume ratio, or None if average is invalid
        """
        if average_volume <= 0:
            return None
        
        return current_volume / average_volume
    
    def is_volume_low(
        self,
        current_volume: int,
        average_volume: float,
        max_threshold: float,
        symbol: str,
        check_type: VolumeCheckType = VolumeCheckType.BREAKOUT_LOW
    ) -> bool:
        """
        Check if volume is LOW (below or equal to threshold).
        
        Used for false breakout strategy where we want weak breakouts.
        
        Args:
            current_volume: Current candle volume
            average_volume: Average volume
            max_threshold: Maximum threshold multiplier (e.g., 1.5)
            symbol: Symbol name for logging
            check_type: Type of volume check for logging
            
        Returns:
            True if volume is low (ratio <= threshold), False otherwise
        """
        if average_volume <= 0:
            self.logger.warning("Average volume is zero or negative", symbol)
            return False
        
        volume_ratio = current_volume / average_volume
        is_low = volume_ratio <= max_threshold
        
        # Log volume analysis
        self._log_volume_check(
            check_type=check_type,
            current_volume=current_volume,
            average_volume=average_volume,
            volume_ratio=volume_ratio,
            threshold=max_threshold,
            result=is_low,
            condition=VolumeCondition.LOW,
            symbol=symbol
        )
        
        return is_low
    
    def is_volume_high(
        self,
        current_volume: int,
        average_volume: float,
        min_threshold: float,
        symbol: str,
        check_type: VolumeCheckType = VolumeCheckType.REVERSAL_HIGH
    ) -> bool:
        """
        Check if volume is HIGH (above or equal to threshold).
        
        Used for confirmations where we want strong volume.
        
        Args:
            current_volume: Current candle volume
            average_volume: Average volume
            min_threshold: Minimum threshold multiplier (e.g., 1.5)
            symbol: Symbol name for logging
            check_type: Type of volume check for logging
            
        Returns:
            True if volume is high (ratio >= threshold), False otherwise
        """
        if average_volume <= 0:
            self.logger.warning("Average volume is zero or negative", symbol)
            return False
        
        volume_ratio = current_volume / average_volume
        is_high = volume_ratio >= min_threshold
        
        # Log volume analysis
        self._log_volume_check(
            check_type=check_type,
            current_volume=current_volume,
            average_volume=average_volume,
            volume_ratio=volume_ratio,
            threshold=min_threshold,
            result=is_high,
            condition=VolumeCondition.HIGH,
            symbol=symbol
        )
        
        return is_high
    
    def _log_volume_check(
        self,
        check_type: VolumeCheckType,
        current_volume: int,
        average_volume: float,
        volume_ratio: float,
        threshold: float,
        result: bool,
        condition: VolumeCondition,
        symbol: str
    ):
        """
        Log volume check with consistent formatting.
        
        Args:
            check_type: Type of volume check
            current_volume: Current candle volume
            average_volume: Average volume
            volume_ratio: Calculated volume ratio
            threshold: Threshold used for comparison
            result: Result of the check (True/False)
            condition: Expected condition (LOW/HIGH)
            symbol: Symbol name for logging
        """
        # Log header
        self.logger.info(f"=== {check_type.value} ===", symbol)
        
        # Log volume data
        volume_label = self._get_volume_label(check_type)
        self.logger.info(f"{volume_label}: {current_volume}", symbol)
        self.logger.info(f"Average Volume: {average_volume:.0f}", symbol)
        self.logger.info(f"Volume Ratio: {volume_ratio:.2f}x", symbol)
        
        # Log threshold
        threshold_label = "Max Threshold" if condition == VolumeCondition.LOW else "Min Threshold"
        self.logger.info(f"{threshold_label}: {threshold:.2f}x", symbol)
        
        # Log result
        condition_label = "LOW" if condition == VolumeCondition.LOW else "HIGH"
        self.logger.info(f"Volume is {condition_label}: {'YES' if result else 'NO'}", symbol)
        
        # Log interpretation
        self._log_interpretation(check_type, result, symbol)
    
    def _get_volume_label(self, check_type: VolumeCheckType) -> str:
        """Get appropriate volume label for check type."""
        if check_type == VolumeCheckType.BREAKOUT_LOW:
            return "Breakout Volume"
        elif check_type == VolumeCheckType.REVERSAL_HIGH:
            return "Reversal Volume"
        elif check_type == VolumeCheckType.TRUE_BREAKOUT_HIGH:
            return "Breakout Volume"
        elif check_type == VolumeCheckType.CONTINUATION_HIGH:
            return "Continuation Volume"
        return "Volume"
    
    def _log_interpretation(self, check_type: VolumeCheckType, result: bool, symbol: str):
        """Log interpretation of volume check result."""
        interpretations = {
            VolumeCheckType.BREAKOUT_LOW: {
                True: [
                    ">>> VOLUME IS LOW - Weak breakout, likely to reverse <<<",
                    ">>> Good candidate for false breakout - proceeding <<<"
                ],
                False: [
                    ">>> VOLUME TOO HIGH - Strong breakout, likely to continue <<<",
                    ">>> Not ideal for false breakout strategy - skipping <<<"
                ]
            },
            VolumeCheckType.REVERSAL_HIGH: {
                True: [
                    ">>> VOLUME IS HIGH - Strong reversal confirmation <<<",
                    ">>> Excellent false breakout signal - proceeding <<<"
                ],
                False: [
                    ">>> VOLUME TOO LOW - Weak reversal, lacks conviction <<<",
                    ">>> May not be a strong false breakout - skipping <<<"
                ]
            },
            VolumeCheckType.TRUE_BREAKOUT_HIGH: {
                True: [
                    ">>> VOLUME IS HIGH - Strong breakout, likely to continue <<<",
                    ">>> Good candidate for true breakout - proceeding <<<"
                ],
                False: [
                    ">>> VOLUME TOO LOW - Weak breakout, may fail <<<",
                    ">>> Not ideal for true breakout strategy - skipping <<<"
                ]
            },
            VolumeCheckType.CONTINUATION_HIGH: {
                True: [
                    ">>> VOLUME IS HIGH - Strong continuation confirmation <<<",
                    ">>> Excellent true breakout signal - proceeding <<<"
                ],
                False: [
                    ">>> VOLUME TOO LOW - Weak continuation, lacks momentum <<<",
                    ">>> May not be a strong true breakout - skipping <<<"
                ]
            }
        }
        
        messages = interpretations.get(check_type, {}).get(result, [])
        for message in messages:
            self.logger.info(message, symbol)
    
    def has_sufficient_data(self, volumes: pd.Series, period: int = DEFAULT_VOLUME_PERIOD) -> bool:
        """
        Check if there's sufficient volume data for analysis.
        
        Args:
            volumes: Series of volume data
            period: Required period
            
        Returns:
            True if sufficient data available, False otherwise
        """
        return len(volumes) >= MIN_DATA_POINTS_VOLUME or len(volumes) >= period + 1

