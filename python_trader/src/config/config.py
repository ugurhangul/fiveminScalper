"""
Configuration management for the trading system.
Ported from FMS_Config.mqh
"""
import os
from typing import List, Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from src.models.data_models import SymbolCategory, SymbolParameters


# Load environment variables
load_dotenv()


@dataclass
class StrategyConfig:
    """Strategy settings"""
    entry_offset_percent: float = 0.01
    stop_loss_offset_percent: float = 0.02  # Deprecated: use stop_loss_offset_points instead
    stop_loss_offset_points: int = 100  # Stop loss offset in points (recommended)
    use_point_based_sl: bool = True  # Use point-based SL calculation instead of percentage
    risk_reward_ratio: float = 2.0


@dataclass
class RiskConfig:
    """Risk management settings"""
    risk_percent_per_trade: float = 1.0
    max_lot_size: float = 10.0
    min_lot_size: float = 0.01
    max_positions: int = 10


@dataclass
class TrailingStopConfig:
    """Trailing stop settings"""
    use_trailing_stop: bool = False
    trailing_stop_trigger_rr: float = 1.5
    trailing_stop_distance: float = 50.0


@dataclass
class TradingHoursConfig:
    """Trading hours filter settings"""
    use_trading_hours: bool = False
    start_hour: int = 0
    end_hour: int = 23


@dataclass
class AdvancedConfig:
    """Advanced settings"""
    use_breakeven: bool = True
    breakeven_trigger_rr: float = 1.0
    use_only_00_utc_candle: bool = True
    magic_number: int = 123456
    trade_comment: str = "5MinScalper"


@dataclass
class LoggingConfig:
    """Logging settings"""
    enable_detailed_logging: bool = True
    log_to_file: bool = True
    log_to_console: bool = True
    log_level: str = "INFO"
    log_active_trades_every_5min: bool = True


@dataclass
class AdaptiveFilterConfig:
    """Adaptive filter system settings

    NOTE: With dual strategy system (false + true breakout), volume confirmation
    is CRITICAL for strategy selection and should always remain enabled.
    Adaptive filters are disabled by default.
    """
    use_adaptive_filters: bool = False  # Disabled - confirmations required for dual strategy
    adaptive_loss_trigger: int = 3
    adaptive_win_recovery: int = 2
    start_with_filters_enabled: bool = True  # Always start with filters enabled


@dataclass
class SymbolAdaptationConfig:
    """Symbol-level adaptation settings"""
    use_symbol_adaptation: bool = True
    symbol_min_trades: int = 10
    symbol_min_win_rate: float = 30.0
    symbol_max_loss: float = -100.0
    symbol_max_consecutive_losses: int = 5
    symbol_cooling_period_days: int = 7


@dataclass
class VolumeConfig:
    """Volume confirmation settings"""
    breakout_volume_max_multiplier: float = 1.0
    reversal_volume_min_multiplier: float = 1.5
    volume_average_period: int = 20


@dataclass
class DivergenceConfig:
    """Divergence confirmation settings"""
    require_both_indicators: bool = False
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    divergence_lookback: int = 20


@dataclass
class MT5Config:
    """MetaTrader 5 connection settings"""
    login: int
    password: str
    server: str
    timeout: int = 60000
    portable: bool = False


class TradingConfig:
    """Main configuration class"""
    
    def __init__(self):
        # MT5 Configuration
        self.mt5 = MT5Config(
            login=int(os.getenv('MT5_LOGIN', '0')),
            password=os.getenv('MT5_PASSWORD', ''),
            server=os.getenv('MT5_SERVER', '')
        )

        # Symbols to trade - will be populated from Market Watch after MT5 connection
        self.symbols: List[str] = []
        
        # Strategy settings
        self.strategy = StrategyConfig(
            entry_offset_percent=float(os.getenv('ENTRY_OFFSET_PERCENT', '0.01')),
            stop_loss_offset_percent=float(os.getenv('STOP_LOSS_OFFSET_PERCENT', '0.02')),
            stop_loss_offset_points=int(os.getenv('STOP_LOSS_OFFSET_POINTS', '100')),
            use_point_based_sl=os.getenv('USE_POINT_BASED_SL', 'true').lower() == 'true',
            risk_reward_ratio=float(os.getenv('RISK_REWARD_RATIO', '2.0'))
        )
        
        # Risk management
        # Parse MIN_LOT_SIZE: if "MIN", use 0 to signal using symbol's minimum
        min_lot_str = os.getenv('MIN_LOT_SIZE', '0.01').strip().upper()
        min_lot_value = 0.0 if min_lot_str == 'MIN' else float(min_lot_str)

        # Parse MAX_LOT_SIZE: if "MIN", use 0 to signal using symbol's minimum
        max_lot_str = os.getenv('MAX_LOT_SIZE', '0.01').strip().upper()
        max_lot_value = 0.0 if max_lot_str == 'MIN' else float(max_lot_str)

        self.risk = RiskConfig(
            risk_percent_per_trade=float(os.getenv('RISK_PERCENT_PER_TRADE', '1.0')),
            max_lot_size=max_lot_value,
            min_lot_size=min_lot_value,
            max_positions=int(os.getenv('MAX_POSITIONS', '1000'))
        )
        
        # Trailing stop
        self.trailing_stop = TrailingStopConfig(
            use_trailing_stop=os.getenv('USE_TRAILING_STOP', 'false').lower() == 'true',
            trailing_stop_trigger_rr=float(os.getenv('TRAILING_STOP_TRIGGER_RR', '1.5')),
            trailing_stop_distance=float(os.getenv('TRAILING_STOP_DISTANCE', '50.0'))
        )
        
        # Trading hours
        self.trading_hours = TradingHoursConfig(
            use_trading_hours=os.getenv('USE_TRADING_HOURS', 'false').lower() == 'true',
            start_hour=int(os.getenv('START_HOUR', '0')),
            end_hour=int(os.getenv('END_HOUR', '23'))
        )
        
        # Advanced settings
        self.advanced = AdvancedConfig(
            use_breakeven=os.getenv('USE_BREAKEVEN', 'true').lower() == 'true',
            breakeven_trigger_rr=float(os.getenv('BREAKEVEN_TRIGGER_RR', '1.0')),
            use_only_00_utc_candle=os.getenv('USE_ONLY_00_UTC_CANDLE', 'true').lower() == 'true',
            magic_number=int(os.getenv('MAGIC_NUMBER', '123456')),
            trade_comment=os.getenv('TRADE_COMMENT', '5MinScalper')
        )
        
        # Logging
        self.logging = LoggingConfig(
            enable_detailed_logging=os.getenv('ENABLE_DETAILED_LOGGING', 'true').lower() == 'true',
            log_to_file=os.getenv('LOG_TO_FILE', 'true').lower() == 'true',
            log_to_console=os.getenv('LOG_TO_CONSOLE', 'true').lower() == 'true',
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_active_trades_every_5min=os.getenv('LOG_ACTIVE_TRADES_EVERY_5MIN', 'true').lower() == 'true'
        )
        
        # Adaptive filters
        # NOTE: Defaults changed for dual strategy system - confirmations must stay enabled
        self.adaptive_filters = AdaptiveFilterConfig(
            use_adaptive_filters=os.getenv('USE_ADAPTIVE_FILTERS', 'false').lower() == 'true',  # Changed default to 'false'
            adaptive_loss_trigger=int(os.getenv('ADAPTIVE_LOSS_TRIGGER', '3')),
            adaptive_win_recovery=int(os.getenv('ADAPTIVE_WIN_RECOVERY', '2')),
            start_with_filters_enabled=os.getenv('START_WITH_FILTERS_ENABLED', 'true').lower() == 'true'  # Changed default to 'true'
        )
        
        # Symbol adaptation
        self.symbol_adaptation = SymbolAdaptationConfig(
            use_symbol_adaptation=os.getenv('USE_SYMBOL_ADAPTATION', 'true').lower() == 'true',
            symbol_min_trades=int(os.getenv('SYMBOL_MIN_TRADES', '10')),
            symbol_min_win_rate=float(os.getenv('SYMBOL_MIN_WIN_RATE', '30.0')),
            symbol_max_loss=float(os.getenv('SYMBOL_MAX_LOSS', '-100.0')),
            symbol_max_consecutive_losses=int(os.getenv('SYMBOL_MAX_CONSECUTIVE_LOSSES', '3')),
            symbol_cooling_period_days=int(os.getenv('SYMBOL_COOLING_PERIOD_DAYS', '7'))
        )
        
        # Volume confirmation
        self.volume = VolumeConfig(
            breakout_volume_max_multiplier=float(os.getenv('BREAKOUT_VOLUME_MAX_MULTIPLIER', '1.0')),
            reversal_volume_min_multiplier=float(os.getenv('REVERSAL_VOLUME_MIN_MULTIPLIER', '1.5')),
            volume_average_period=int(os.getenv('VOLUME_AVERAGE_PERIOD', '20'))
        )
        
        # Divergence confirmation
        self.divergence = DivergenceConfig(
            require_both_indicators=os.getenv('REQUIRE_BOTH_INDICATORS', 'false').lower() == 'true',
            rsi_period=int(os.getenv('RSI_PERIOD', '14')),
            macd_fast=int(os.getenv('MACD_FAST', '12')),
            macd_slow=int(os.getenv('MACD_SLOW', '26')),
            macd_signal=int(os.getenv('MACD_SIGNAL', '9')),
            divergence_lookback=int(os.getenv('DIVERGENCE_LOOKBACK', '20'))
        )
        
        # Symbol-specific optimization enabled
        self.use_symbol_specific_settings: bool = os.getenv('USE_SYMBOL_SPECIFIC_SETTINGS', 'true').lower() == 'true'

    def load_symbols_from_active_set(self, file_path: str = "data/active.set") -> bool:
        """
        Load symbols from active.set file in UTF-8 encoding.

        Args:
            file_path: Path to active.set file

        Returns:
            True if symbols loaded successfully
        """
        from pathlib import Path

        active_set_path = Path(file_path)
        if not active_set_path.exists():
            return False

        try:
            with open(active_set_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # First line is count, rest are symbols
            symbols = [
                line.strip()
                for line in lines[1:]
                if line.strip()
            ]

            if not symbols:
                return False

            self.symbols = symbols
            return True

        except Exception:
            return False

    def load_symbols_from_market_watch(self, connector) -> bool:
        """
        Load symbols from MetaTrader's Market Watch list.

        Args:
            connector: MT5Connector instance (must be connected)

        Returns:
            True if symbols loaded successfully
        """
        symbols = connector.get_market_watch_symbols()
        if not symbols:
            return False

        self.symbols = symbols
        return True

    def validate(self, check_symbols: bool = True) -> bool:
        """
        Validate configuration.

        Args:
            check_symbols: Whether to validate symbols (False during initial validation)
        """
        if not self.mt5.login or not self.mt5.password or not self.mt5.server:
            raise ValueError("MT5 credentials not configured")

        if self.risk.risk_percent_per_trade <= 0 or self.risk.risk_percent_per_trade > 100:
            raise ValueError("Risk percent must be between 0 and 100")

        if self.strategy.risk_reward_ratio <= 0:
            raise ValueError("Risk/Reward ratio must be positive")

        if check_symbols and not self.symbols:
            raise ValueError("No symbols configured")

        return True


# Global configuration instance
config = TradingConfig()

