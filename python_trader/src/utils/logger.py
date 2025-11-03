"""
Logging system for the trading bot.
Provides comprehensive logging similar to the MQL5 EA.
"""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict
import colorlog
from logging.handlers import TimedRotatingFileHandler


class UTCFormatter(logging.Formatter):
    """Custom formatter that uses UTC time for all log messages"""

    def formatTime(self, record, datefmt=None):
        """Override formatTime to use UTC"""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.isoformat(timespec='seconds')
        return s


class SymbolFileHandler(logging.FileHandler):
    """File handler for symbol-specific logs"""

    def __init__(self, symbol: str, log_dir: Path):
        """
        Initialize symbol-specific file handler.

        Args:
            symbol: Trading symbol name
            log_dir: Base log directory
        """
        self.symbol = symbol
        self.log_dir = log_dir

        # Create date-based directory structure: logs/YYYY-MM-DD/
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir = log_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)

        # Create symbol-specific log file: logs/YYYY-MM-DD/SYMBOL.log
        log_file = date_dir / f"{symbol}.log"

        super().__init__(log_file, encoding='utf-8')


class TradingLogger:
    """Custom logger for trading operations"""

    def __init__(self, name: str = "TradingBot", log_to_file: bool = True,
                 log_to_console: bool = True, log_level: str = "INFO",
                 enable_detailed: bool = True):
        """
        Initialize the trading logger.

        Args:
            name: Logger name
            log_to_file: Enable file logging
            log_to_console: Enable console logging
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_detailed: Enable detailed logging
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.handlers.clear()  # Clear existing handlers

        self.enable_detailed = enable_detailed
        self.log_dir = Path("logs")
        self.symbol_handlers: Dict[str, logging.FileHandler] = {}

        # Create logs directory if it doesn't exist
        if log_to_file:
            self.log_dir.mkdir(exist_ok=True)

            # Create date-based directory structure: logs/YYYY-MM-DD/
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            date_dir = self.log_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)

            # Create master log file: logs/YYYY-MM-DD/main.log
            master_log_file = date_dir / "main.log"

            file_handler = logging.FileHandler(master_log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)

            # Use UTC formatter for file logs
            file_formatter = UTCFormatter(
                '%(asctime)s UTC | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        # Create console handler with colors (still using UTC)
        if log_to_console:
            console_handler = colorlog.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level.upper()))

            # Create custom colored formatter with UTC
            class UTCColoredFormatter(colorlog.ColoredFormatter):
                def formatTime(self, record, datefmt=None):
                    dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
                    if datefmt:
                        s = dt.strftime(datefmt)
                    else:
                        s = dt.isoformat(timespec='seconds')
                    return s

            console_formatter = UTCColoredFormatter(
                '%(log_color)s%(asctime)s UTC | %(levelname)-8s | %(message)s',
                datefmt='%H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'white',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

    def _get_symbol_handler(self, symbol: str) -> Optional[logging.FileHandler]:
        """
        Get or create a file handler for a specific symbol.

        Args:
            symbol: Trading symbol name

        Returns:
            File handler for the symbol, or None if file logging is disabled
        """
        # Check if handler already exists
        if symbol in self.symbol_handlers:
            return self.symbol_handlers[symbol]

        # Create new handler for this symbol
        try:
            # Create date-based directory structure: logs/YYYY-MM-DD/
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            date_dir = self.log_dir / date_str
            date_dir.mkdir(parents=True, exist_ok=True)

            # Create symbol-specific log file: logs/YYYY-MM-DD/SYMBOL.log
            log_file = date_dir / f"{symbol}.log"

            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setLevel(logging.DEBUG)

            # Use UTC formatter
            formatter = UTCFormatter(
                '%(asctime)s UTC | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)

            # Store handler
            self.symbol_handlers[symbol] = handler

            return handler
        except Exception as e:
            self.logger.error(f"Failed to create log handler for {symbol}: {e}")
            return None

    def _log_to_symbol_file(self, level: int, message: str, symbol: str):
        """
        Log a message to a symbol-specific file.

        Args:
            level: Logging level
            message: Log message
            symbol: Trading symbol
        """
        handler = self._get_symbol_handler(symbol)
        if handler:
            # Create a log record
            record = self.logger.makeRecord(
                self.logger.name,
                level,
                "(symbol_log)",
                0,
                message,
                (),
                None
            )
            handler.emit(record)

    def info(self, message: str, symbol: Optional[str] = None):
        """Log info message"""
        if symbol:
            # Log to symbol-specific file
            self._log_to_symbol_file(logging.INFO, message, symbol)
            # Add symbol prefix for master log
            message = f"[{symbol}] {message}"
        self.logger.info(message)

    def debug(self, message: str, symbol: Optional[str] = None):
        """Log debug message (only if detailed logging enabled)"""
        if self.enable_detailed:
            if symbol:
                # Log to symbol-specific file
                self._log_to_symbol_file(logging.DEBUG, message, symbol)
                # Add symbol prefix for master log
                message = f"[{symbol}] {message}"
            self.logger.debug(message)

    def warning(self, message: str, symbol: Optional[str] = None):
        """Log warning message"""
        if symbol:
            # Log to symbol-specific file
            self._log_to_symbol_file(logging.WARNING, message, symbol)
            # Add symbol prefix for master log
            message = f"[{symbol}] {message}"
        self.logger.warning(message)

    def error(self, message: str, symbol: Optional[str] = None):
        """Log error message"""
        if symbol:
            # Log to symbol-specific file
            self._log_to_symbol_file(logging.ERROR, message, symbol)
            # Add symbol prefix for master log
            message = f"[{symbol}] {message}"
        self.logger.error(message)

    def critical(self, message: str, symbol: Optional[str] = None):
        """Log critical message"""
        if symbol:
            # Log to symbol-specific file
            self._log_to_symbol_file(logging.CRITICAL, message, symbol)
            # Add symbol prefix for master log
            message = f"[{symbol}] {message}"
        self.logger.critical(message)
    
    def separator(self, char: str = "=", length: int = 60):
        """Log a separator line"""
        self.logger.info(char * length)
    
    def header(self, title: str, width: int = 60):
        """Log a formatted header"""
        self.separator("=", width)
        padding = (width - len(title) - 2) // 2
        self.logger.info(f"{'=' * padding} {title} {'=' * padding}")
        self.separator("=", width)
    
    def box(self, title: str, lines: list[str], width: int = 60):
        """Log a formatted box with title and content"""
        self.logger.info("╔" + "═" * (width - 2) + "╗")
        
        # Title
        title_padding = width - len(title) - 4
        self.logger.info(f"║  {title}{' ' * title_padding}║")
        
        self.logger.info("╚" + "═" * (width - 2) + "╝")
        
        # Content
        for line in lines:
            self.logger.info(line)
    
    def trade_signal(self, signal_type: str, symbol: str, entry: float, 
                    sl: float, tp: float, lot_size: float):
        """Log a trade signal"""
        self.header(f"{signal_type} SIGNAL - {symbol}")
        self.info(f"Entry Price: {entry:.5f}")
        self.info(f"Stop Loss: {sl:.5f}")
        self.info(f"Take Profit: {tp:.5f}")
        self.info(f"Lot Size: {lot_size:.2f}")
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk if risk > 0 else 0
        self.info(f"Risk: {risk:.5f} | Reward: {reward:.5f} | R:R: {rr:.2f}")
        self.separator()
    
    def position_opened(self, ticket: int, symbol: str, position_type: str,
                       volume: float, price: float, sl: float, tp: float):
        """Log position opened"""
        self.header(f"POSITION OPENED - {symbol}")
        self.info(f"Ticket: {ticket}")
        self.info(f"Type: {position_type}")
        self.info(f"Volume: {volume:.2f}")
        self.info(f"Price: {price:.5f}")
        self.info(f"SL: {sl:.5f} | TP: {tp:.5f}")
        self.separator()
    
    def position_closed(self, ticket: int, symbol: str, profit: float,
                       is_win: bool, rr_achieved: float):
        """Log position closed"""
        result = "WIN" if is_win else "LOSS"
        self.header(f"POSITION CLOSED - {result}")
        self.info(f"Ticket: {ticket} | Symbol: {symbol}")
        self.info(f"Profit: ${profit:.2f}")
        self.info(f"R:R Achieved: {rr_achieved:.2f}")
        self.separator()
    
    def symbol_disabled(self, symbol: str, reason: str, stats: dict):
        """Log symbol disabled"""
        lines = [
            f"Reason: {reason}",
            "",
            "Statistics:",
            f"  Total Trades: {stats.get('total_trades', 0)}",
            f"  Wins: {stats.get('wins', 0)} ({stats.get('win_rate', 0):.1f}%)",
            f"  Losses: {stats.get('losses', 0)}",
            f"  Net P&L: ${stats.get('net_pnl', 0):.2f}",
            f"  Consecutive Losses: {stats.get('consecutive_losses', 0)}",
            "",
            f"Cooling Period: {stats.get('cooling_days', 0)} days",
            f"Re-enable Date: {stats.get('reenable_date', 'N/A')}"
        ]
        self.box(f"SYMBOL DISABLED: {symbol}", lines)
    
    def symbol_reenabled(self, symbol: str, old_stats: dict):
        """Log symbol re-enabled"""
        lines = [
            "Reason: Cooling period expired",
            "",
            "Previous Performance:",
            f"  Total Trades: {old_stats.get('total_trades', 0)}",
            f"  Net P&L: ${old_stats.get('net_pnl', 0):.2f}",
            f"  Disable Reason: {old_stats.get('disable_reason', 'N/A')}",
            "",
            "Statistics: RESET",
            "Status: Ready to trade"
        ]
        self.box(f"SYMBOL RE-ENABLED: {symbol}", lines)


# Global logger instance
_logger: Optional[TradingLogger] = None


def get_logger() -> TradingLogger:
    """Get the global logger instance"""
    global _logger
    if _logger is None:
        from src.config.config import config
        _logger = TradingLogger(
            log_to_file=config.logging.log_to_file,
            log_to_console=config.logging.log_to_console,
            log_level=config.logging.log_level,
            enable_detailed=config.logging.enable_detailed_logging
        )
    return _logger


def init_logger(log_to_file: bool = True, log_to_console: bool = True,
                log_level: str = "INFO", enable_detailed: bool = True) -> TradingLogger:
    """Initialize the global logger"""
    global _logger
    _logger = TradingLogger(
        log_to_file=log_to_file,
        log_to_console=log_to_console,
        log_level=log_level,
        enable_detailed=enable_detailed
    )
    return _logger

