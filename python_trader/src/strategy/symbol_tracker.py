"""
Symbol performance tracking and auto-disable/enable logic.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from src.models.data_models import SymbolStats
from src.config.config import SymbolAdaptationConfig
from src.utils.logger import get_logger


class SymbolTracker:
    """Tracks symbol performance and manages auto-disable/enable"""
    
    def __init__(self, symbol: str, config: SymbolAdaptationConfig):
        """
        Initialize symbol tracker.
        
        Args:
            symbol: Symbol name
            config: Symbol adaptation configuration
        """
        self.symbol = symbol
        self.config = config
        self.logger = get_logger()

        # Performance stats
        self.stats = SymbolStats()
        
        # Disable tracking
        self.is_disabled = False
        self.disabled_at: Optional[datetime] = None
    
    def on_trade_closed(self, profit: float):
        """
        Update stats when a trade is closed.
        
        Args:
            profit: Trade profit (positive or negative)
        """
        self.stats.total_trades += 1
        
        if profit > 0:
            self.stats.winning_trades += 1
            self.stats.total_profit += profit
            self.stats.consecutive_losses = 0
        else:
            self.stats.losing_trades += 1
            self.stats.total_loss += abs(profit)
            self.stats.consecutive_losses += 1
        
        # Log updated stats
        self.logger.info("=== Symbol Performance Updated ===", self.symbol)
        self.logger.info(f"Total Trades: {self.stats.total_trades}", self.symbol)
        self.logger.info(f"Win Rate: {self.stats.win_rate:.1f}%", self.symbol)
        self.logger.info(f"Net Profit: ${self.stats.net_profit:.2f}", self.symbol)
        self.logger.info(f"Consecutive Losses: {self.stats.consecutive_losses}", self.symbol)
        self.logger.separator()
        
        # Check if symbol should be disabled
        if self.config.use_symbol_adaptation and not self.is_disabled:
            self._check_disable_criteria()
    
    def _check_disable_criteria(self):
        """Check if symbol should be disabled based on performance"""
        should_disable = False
        reason = ""
        
        # Check minimum trades requirement
        if self.stats.total_trades < self.config.min_trades_for_evaluation:
            return
        
        # Check win rate
        if self.stats.win_rate < self.config.min_win_rate:
            should_disable = True
            reason = f"Win rate {self.stats.win_rate:.1f}% below minimum {self.config.min_win_rate}%"
        
        # Check total loss
        elif self.stats.total_loss > self.config.max_total_loss:
            should_disable = True
            reason = f"Total loss ${self.stats.total_loss:.2f} exceeds maximum ${self.config.max_total_loss:.2f}"
        
        # Check consecutive losses
        elif self.stats.consecutive_losses >= self.config.max_consecutive_losses:
            should_disable = True
            reason = f"Consecutive losses {self.stats.consecutive_losses} reached maximum {self.config.max_consecutive_losses}"
        
        if should_disable:
            self._disable_symbol(reason)
    
    def _disable_symbol(self, reason: str):
        """
        Disable symbol trading.
        
        Args:
            reason: Reason for disabling
        """
        self.is_disabled = True
        self.disabled_at = datetime.now(timezone.utc)
        
        self.logger.symbol_disabled(self.symbol, reason)
        self.logger.info(
            f"Symbol will be re-enabled after {self.config.cooling_period_hours} hours",
            self.symbol
        )
    
    def check_reenable(self) -> bool:
        """
        Check if symbol should be re-enabled after cooling period.
        
        Returns:
            True if symbol was re-enabled
        """
        if not self.is_disabled or self.disabled_at is None:
            return False

        # Check if cooling period has passed
        cooling_period = timedelta(hours=self.config.cooling_period_hours)
        if datetime.now(timezone.utc) - self.disabled_at >= cooling_period:
            self._reenable_symbol()
            return True
        
        return False
    
    def _reenable_symbol(self):
        """Re-enable symbol after cooling period"""
        self.is_disabled = False
        self.disabled_at = None
        
        # Reset consecutive losses
        self.stats.consecutive_losses = 0
        
        self.logger.symbol_reenabled(self.symbol)
    
    def can_trade(self) -> bool:
        """
        Check if symbol can trade.
        
        Returns:
            True if trading is allowed
        """
        # Check if re-enable is due
        if self.is_disabled:
            self.check_reenable()
        
        return not self.is_disabled
    
    def get_stats(self) -> SymbolStats:
        """Get current stats"""
        return self.stats
    
    def reset_stats(self):
        """Reset performance stats"""
        self.stats = SymbolStats()
        self.logger.info("Symbol stats reset", self.symbol)

