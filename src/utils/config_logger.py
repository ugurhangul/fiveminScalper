"""
Configuration logging utility.
Centralizes configuration display logic.
"""
from typing import List
from src.config.config import Config
from src.utils.logger import Logger


class ConfigLogger:
    """Utility class for logging configuration details"""

    @staticmethod
    def log_configuration(logger: Logger, config: Config):
        """
        Log current configuration in a formatted way.

        Args:
            logger: Logger instance
            config: Configuration object
        """
        logger.info("=" * 60)
        logger.info("CONFIGURATION")
        logger.info("=" * 60)
        
        # Symbols
        ConfigLogger._log_symbols(logger, config)
        
        # Trading parameters
        ConfigLogger._log_trading_parameters(logger, config)
        
        # Risk management
        ConfigLogger._log_risk_management(logger, config)
        
        # Position management
        ConfigLogger._log_position_management(logger, config)
        
        # Strategy settings
        ConfigLogger._log_strategy_settings(logger, config)
        
        # Advanced features
        ConfigLogger._log_advanced_features(logger, config)
        
        logger.info("=" * 60)

    @staticmethod
    def _log_symbols(logger: Logger, config: Config):
        """Log symbol configuration"""
        logger.info(f"Symbols: {', '.join(config.symbols)}")
        logger.info(f"Total Symbols: {len(config.symbols)}")

    @staticmethod
    def _log_trading_parameters(logger: Logger, config: Config):
        """Log trading parameters"""
        logger.info("-" * 60)
        logger.info("Trading Parameters:")
        logger.info(f"  Magic Number: {config.advanced.magic_number}")
        logger.info(f"  Trade Comment: {config.advanced.trade_comment}")

    @staticmethod
    def _log_risk_management(logger: Logger, config: Config):
        """Log risk management settings"""
        logger.info("-" * 60)
        logger.info("Risk Management:")
        logger.info(f"  Risk Per Trade: {config.risk.risk_percent_per_trade}%")
        logger.info(f"  Max Risk Per Trade: {config.risk.max_risk_percent_per_trade}%")
        logger.info(f"  Risk/Reward Ratio: 1:{config.strategy.risk_reward_ratio}")
        
        if hasattr(config.risk, 'min_lot_size') and config.risk.min_lot_size > 0:
            logger.info(f"  Min Lot Size: {config.risk.min_lot_size}")
        if hasattr(config.risk, 'max_lot_size') and config.risk.max_lot_size > 0:
            logger.info(f"  Max Lot Size: {config.risk.max_lot_size}")

    @staticmethod
    def _log_position_management(logger: Logger, config: Config):
        """Log position management settings"""
        logger.info("-" * 60)
        logger.info("Position Management:")
        
        # Breakeven
        logger.info(f"  Use Breakeven: {config.advanced.use_breakeven}")
        if config.advanced.use_breakeven:
            logger.info(f"    Breakeven Trigger: {config.advanced.breakeven_trigger_rr} R:R")
        
        # Trailing stop
        logger.info(f"  Use Trailing Stop: {config.trailing_stop.use_trailing_stop}")
        if config.trailing_stop.use_trailing_stop:
            logger.info(f"    Trailing Trigger: {config.trailing_stop.trailing_stop_trigger_rr} R:R")
            
            if config.trailing_stop.use_atr_trailing:
                logger.info(f"    Trailing Type: ATR-based")
                logger.info(f"    ATR Period: {config.trailing_stop.atr_period}")
                logger.info(f"    ATR Multiplier: {config.trailing_stop.atr_multiplier}")
                logger.info(f"    ATR Timeframe: {config.trailing_stop.atr_timeframe}")
            else:
                logger.info(f"    Trailing Type: Fixed distance")
                logger.info(f"    Trailing Distance: {config.trailing_stop.trailing_stop_distance} points")

    @staticmethod
    def _log_strategy_settings(logger: Logger, config: Config):
        """Log strategy settings"""
        logger.info("-" * 60)
        logger.info("Strategy Settings:")
        logger.info(f"  Use Only 00:00 UTC Candle: {config.advanced.use_only_00_utc_candle}")
        
        # Multi-range configuration
        if hasattr(config, 'range_config') and config.range_config.ranges:
            logger.info(f"  Multi-Range Mode: Enabled ({len(config.range_config.ranges)} ranges)")
            for range_cfg in config.range_config.ranges:
                logger.info(f"    {range_cfg.range_id}: {range_cfg.range_timeframe}/{range_cfg.breakout_timeframe}")
        
        # Volume confirmation
        if hasattr(config, 'volume_confirmation') and config.volume_confirmation.use_volume_confirmation:
            logger.info(f"  Volume Confirmation: Enabled")
            logger.info(f"    Volume Multiplier: {config.volume_confirmation.volume_multiplier}")
        
        # Divergence confirmation
        if hasattr(config, 'divergence') and config.divergence.use_divergence_confirmation:
            logger.info(f"  Divergence Confirmation: Enabled")
            logger.info(f"    RSI Period: {config.divergence.rsi_period}")

    @staticmethod
    def _log_advanced_features(logger: Logger, config: Config):
        """Log advanced features"""
        logger.info("-" * 60)
        logger.info("Advanced Features:")
        logger.info(f"  Adaptive Filters: {config.adaptive_filters.use_adaptive_filters}")
        logger.info(f"  Symbol Adaptation: {config.symbol_adaptation.use_symbol_adaptation}")
        
        if hasattr(config, 'symbol_performance') and config.symbol_performance.use_symbol_performance_tracking:
            logger.info(f"  Symbol Performance Tracking: Enabled")
            logger.info(f"    Max Drawdown: {config.symbol_performance.max_drawdown_percent}%")
            logger.info(f"    Auto Disable: {config.symbol_performance.auto_disable_on_drawdown}")

    @staticmethod
    def log_startup_banner(logger: Logger):
        """Log startup banner"""
        logger.header("FiveMinScalper - Python Multi-Symbol Trading Bot")
        logger.info("Initializing trading system...")

    @staticmethod
    def log_initialization_complete(logger: Logger, symbol_count: int):
        """
        Log initialization completion message.

        Args:
            logger: Logger instance
            symbol_count: Number of symbols initialized
        """
        logger.separator()
        logger.info(f"✓ Trading system initialized successfully")
        logger.info(f"✓ {symbol_count} symbol(s) ready for trading")
        logger.separator()

