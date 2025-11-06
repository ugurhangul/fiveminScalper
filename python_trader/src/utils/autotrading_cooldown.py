"""
AutoTrading Cooldown Manager.
Manages cooldown period when server disables AutoTrading (error 10026).
"""
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from src.utils.logger import get_logger


class AutoTradingCooldown:
    """
    Manages cooldown period when AutoTrading is disabled by server.
    
    When error 10026 is detected, all trading operations (opening new positions
    and modifying existing positions) are paused for a cooldown period.
    """
    
    def __init__(self, cooldown_minutes: int = 5):
        """
        Initialize cooldown manager.
        
        Args:
            cooldown_minutes: Duration of cooldown period in minutes (default: 5)
        """
        self.cooldown_minutes = cooldown_minutes
        self.cooldown_until: Optional[datetime] = None
        self.lock = threading.Lock()
        self.logger = get_logger()
        self.last_log_time: Optional[datetime] = None
        self.log_interval_seconds = 60  # Log status every 60 seconds
    
    def activate_cooldown(self, reason: str = "AutoTrading disabled by server"):
        """
        Activate cooldown period.
        
        Args:
            reason: Reason for activating cooldown
        """
        with self.lock:
            now = datetime.now(timezone.utc)
            self.cooldown_until = now + timedelta(minutes=self.cooldown_minutes)
            self.last_log_time = now
            
            self.logger.warning(
                f"🚫 TRADING COOLDOWN ACTIVATED: {reason}"
            )
            self.logger.warning(
                f"⏸️  All trading operations paused for {self.cooldown_minutes} minutes"
            )
            self.logger.warning(
                f"⏰ Cooldown will end at: {self.cooldown_until.strftime('%H:%M:%S')} UTC"
            )
    
    def is_in_cooldown(self) -> bool:
        """
        Check if currently in cooldown period.
        
        Returns:
            True if in cooldown, False otherwise
        """
        with self.lock:
            if self.cooldown_until is None:
                return False
            
            now = datetime.now(timezone.utc)
            
            # Check if cooldown has expired
            if now >= self.cooldown_until:
                # Cooldown expired - log and clear
                self.logger.info(
                    f"✅ TRADING COOLDOWN ENDED - Resuming normal operations"
                )
                self.cooldown_until = None
                self.last_log_time = None
                return False
            
            # Still in cooldown - log periodic updates
            self._log_cooldown_status(now)
            return True
    
    def _log_cooldown_status(self, now: datetime):
        """
        Log cooldown status if enough time has passed since last log.
        
        Args:
            now: Current time
        """
        # Only log if we haven't logged recently
        if self.last_log_time is None or \
           (now - self.last_log_time).total_seconds() >= self.log_interval_seconds:
            
            remaining = self.cooldown_until - now
            remaining_minutes = int(remaining.total_seconds() / 60)
            remaining_seconds = int(remaining.total_seconds() % 60)
            
            self.logger.info(
                f"⏸️  Trading cooldown active - {remaining_minutes}m {remaining_seconds}s remaining"
            )
            self.last_log_time = now
    
    def get_remaining_time(self) -> Optional[timedelta]:
        """
        Get remaining cooldown time.
        
        Returns:
            Remaining time as timedelta, or None if not in cooldown
        """
        with self.lock:
            if self.cooldown_until is None:
                return None
            
            now = datetime.now(timezone.utc)
            if now >= self.cooldown_until:
                return None
            
            return self.cooldown_until - now
    
    def reset_cooldown(self):
        """
        Manually reset/clear cooldown period.
        Useful for testing or manual intervention.
        """
        with self.lock:
            if self.cooldown_until is not None:
                self.logger.info("Cooldown manually reset")
                self.cooldown_until = None
                self.last_log_time = None

