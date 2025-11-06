"""
Trading Bot Constants Module

Centralizes all magic numbers, strings, and hard-coded values used throughout the application.
This improves maintainability and makes the codebase more readable.
"""

# ============================================================================
# MT5 ERROR CODES
# ============================================================================

class MT5ErrorCode:
    """MetaTrader 5 error codes with descriptive names"""
    
    # Trade execution errors
    RETCODE_DONE = 10009  # Request completed successfully
    RETCODE_DONE_PARTIAL = 10010  # Request partially completed
    RETCODE_ERROR = 10011  # Common error
    RETCODE_TIMEOUT = 10012  # Request timeout
    RETCODE_INVALID = 10013  # Invalid request
    RETCODE_INVALID_VOLUME = 10014  # Invalid volume
    RETCODE_INVALID_PRICE = 10015  # Invalid price
    RETCODE_INVALID_STOPS = 10016  # Invalid stops (SL/TP)
    RETCODE_TRADE_DISABLED = 10017  # Trade disabled
    RETCODE_MARKET_CLOSED = 10018  # Market closed
    RETCODE_NO_MONEY = 10019  # Insufficient funds
    RETCODE_PRICE_CHANGED = 10020  # Price changed
    RETCODE_PRICE_OFF = 10021  # No quotes
    RETCODE_INVALID_EXPIRATION = 10022  # Invalid expiration
    RETCODE_ORDER_CHANGED = 10023  # Order state changed
    RETCODE_TOO_MANY_REQUESTS = 10024  # Too many requests
    RETCODE_NO_CHANGES = 10025  # No changes in request
    RETCODE_SERVER_DISABLES_AT = 10026  # AutoTrading disabled by server
    RETCODE_CLIENT_DISABLES_AT = 10027  # AutoTrading disabled by client
    RETCODE_LOCKED = 10028  # Request locked for processing
    RETCODE_FROZEN = 10029  # Order or position frozen
    RETCODE_INVALID_FILL = 10030  # Invalid fill type
    RETCODE_CONNECTION = 10031  # No connection
    RETCODE_ONLY_REAL = 10032  # Only real accounts allowed
    RETCODE_LIMIT_ORDERS = 10033  # Limit orders reached
    RETCODE_LIMIT_VOLUME = 10034  # Volume limit reached
    RETCODE_INVALID_ORDER = 10035  # Invalid or prohibited order type
    RETCODE_POSITION_CLOSED = 10036  # Position already closed
    RETCODE_INVALID_CLOSE_VOLUME = 10038  # Invalid close volume
    RETCODE_CLOSE_ORDER_EXIST = 10039  # Close order already exists
    RETCODE_LIMIT_POSITIONS = 10040  # Position limit reached
    RETCODE_REJECT_CANCEL = 10041  # Request rejected
    RETCODE_LONG_ONLY = 10042  # Only long positions allowed
    RETCODE_SHORT_ONLY = 10043  # Only short positions allowed
    RETCODE_CLOSE_ONLY = 10044  # Only position closing allowed
    RETCODE_FIFO_CLOSE = 10045  # FIFO close rule violation
    
    # Retriable error codes (temporary issues)
    RETRIABLE_ERRORS = {
        RETCODE_TIMEOUT,
        RETCODE_PRICE_CHANGED,
        RETCODE_PRICE_OFF,
        RETCODE_TOO_MANY_REQUESTS,
        RETCODE_LOCKED,
        RETCODE_CONNECTION,
    }
    
    # Non-critical errors (don't remove symbol from active set)
    NON_CRITICAL_ERRORS = {
        RETCODE_NO_MONEY,  # Insufficient margin
        RETCODE_MARKET_CLOSED,  # Market closed
        RETCODE_TIMEOUT,  # Timeout
        RETCODE_PRICE_CHANGED,  # Price changed
        RETCODE_PRICE_OFF,  # No quotes
    }


# ============================================================================
# MT5 TIMEFRAME CONSTANTS
# ============================================================================

class MT5Timeframe:
    """MT5 timeframe string to constant mapping"""
    
    # Timeframe mappings
    TIMEFRAME_MAP = {
        'M1': 1,      # 1 minute
        'M5': 5,      # 5 minutes
        'M15': 15,    # 15 minutes
        'M30': 30,    # 30 minutes
        'H1': 16385,  # 1 hour (0x4001)
        'H4': 16388,  # 4 hours (0x4004)
        'D1': 16408,  # 1 day (0x4018)
        'W1': 32769,  # 1 week (0x8001)
        'MN1': 49153, # 1 month (0xC001)
    }
    
    # Reverse mapping (constant to string)
    TIMEFRAME_REVERSE_MAP = {v: k for k, v in TIMEFRAME_MAP.items()}
    
    # Common timeframes
    M1 = 1
    M5 = 5
    M15 = 15
    M30 = 30
    H1 = 16385
    H4 = 16388
    D1 = 16408
    W1 = 32769
    MN1 = 49153


# ============================================================================
# MT5 FILLING MODE CONSTANTS
# ============================================================================

class MT5FillingMode:
    """MT5 order filling mode flags"""
    
    # Filling mode bit flags
    SYMBOL_FILLING_FOK = 1  # Fill or Kill (bit 0)
    SYMBOL_FILLING_IOC = 2  # Immediate or Cancel (bit 1)
    SYMBOL_FILLING_RETURN = 4  # Return (bit 2)
    
    # Preference order for filling modes
    PREFERENCE_ORDER = ['FOK', 'IOC', 'RETURN']


# ============================================================================
# TRADING DEFAULTS
# ============================================================================

class TradingDefaults:
    """Default values for trading operations"""

    # Order execution
    PRICE_DEVIATION_POINTS = 10  # Price deviation in points for order execution
    ORDER_RETRY_ATTEMPTS = 3  # Number of retry attempts for failed orders
    ORDER_RETRY_DELAY_MS = 100  # Delay between retries in milliseconds

    # Position management
    DEFAULT_MAGIC_NUMBER = 123456  # Default magic number for orders
    DEFAULT_TRADE_COMMENT = "5MinScalper"  # Default trade comment

    # Cooldown settings
    AUTOTRADING_COOLDOWN_MINUTES = 5  # Cooldown period when AutoTrading disabled
    COOLDOWN_LOG_INTERVAL_SECONDS = 60  # Log cooldown status every N seconds

    # Monitoring intervals
    POSITION_MONITOR_INTERVAL_SECONDS = 5  # Position monitoring check interval
    STATISTICS_LOG_INTERVAL_SECONDS = 300  # Log statistics every 5 minutes
    STATISTICS_LOG_INTERVAL_SECONDS_SHORT = 10  # Short interval for position statistics

    # Symbol management
    SYMBOL_INFO_CACHE_TTL_SECONDS = 60  # Symbol info cache time-to-live

    # Breakeven settings
    DEFAULT_BREAKEVEN_TRIGGER_RR = 1.0  # R:R ratio to trigger breakeven
    BREAKEVEN_OFFSET_POINTS = 1  # Offset from entry price in points

    # Trailing stop settings
    DEFAULT_TRAILING_TRIGGER_RR = 1.0  # R:R ratio to trigger trailing stop
    DEFAULT_TRAILING_DISTANCE_POINTS = 50.0  # Default trailing distance
    DEFAULT_ATR_PERIOD = 14  # Default ATR calculation period
    DEFAULT_ATR_MULTIPLIER = 2.0  # Default ATR multiplier for trailing

    # Thread management
    THREAD_JOIN_TIMEOUT_SECONDS = 5  # Timeout for thread join operations
    
    # Volume settings
    DEFAULT_VOLUME_AVERAGE_PERIOD = 20  # Default period for volume average
    
    # Divergence settings
    DEFAULT_RSI_PERIOD = 14
    DEFAULT_MACD_FAST = 12
    DEFAULT_MACD_SLOW = 26
    DEFAULT_MACD_SIGNAL = 9
    DEFAULT_DIVERGENCE_LOOKBACK = 20


# ============================================================================
# RISK MANAGEMENT CONSTANTS
# ============================================================================

class RiskManagement:
    """Risk management constants"""
    
    # Default risk parameters
    DEFAULT_RISK_PERCENT = 1.0  # Default risk per trade as percentage of balance
    DEFAULT_MAX_POSITIONS = 10  # Default maximum concurrent positions
    DEFAULT_RISK_REWARD_RATIO = 2.0  # Default risk:reward ratio
    
    # Lot size constraints
    MIN_LOT_SIZE_KEYWORD = "MIN"  # Keyword to use symbol's minimum lot size
    
    # Spread limits (as percentage of price)
    DEFAULT_MAX_SPREAD_PERCENT = 0.1  # Default maximum spread percentage
    
    # Adaptive filter settings
    DEFAULT_ADAPTIVE_LOSS_TRIGGER = 3  # Losses before enabling filters
    DEFAULT_ADAPTIVE_WIN_RECOVERY = 2  # Wins needed to disable filters
    
    # Symbol performance tracking
    DEFAULT_SYMBOL_MIN_TRADES = 10  # Minimum trades for symbol statistics
    DEFAULT_SYMBOL_MIN_WIN_RATE = 30.0  # Minimum win rate percentage
    DEFAULT_SYMBOL_MAX_LOSS = -100.0  # Maximum loss before cooling
    DEFAULT_SYMBOL_MAX_CONSECUTIVE_LOSSES = 5  # Max consecutive losses
    DEFAULT_SYMBOL_COOLING_PERIOD_DAYS = 7  # Cooling period in days


# ============================================================================
# STRATEGY CONSTANTS
# ============================================================================

class StrategyConstants:
    """Strategy-related constants"""

    # Breakout detection
    BREAKOUT_PATTERN_LOOKBACK_CANDLES = 10  # Number of candles to check for pattern

    # Volume confirmation
    DEFAULT_BREAKOUT_VOLUME_MAX = 1.0  # Max volume multiplier for false breakout
    DEFAULT_REVERSAL_VOLUME_MIN = 1.5  # Min volume multiplier for reversal
    DEFAULT_TRUE_BREAKOUT_VOLUME_MIN = 2.0  # Min volume for true breakout
    DEFAULT_CONTINUATION_VOLUME_MIN = 1.5  # Min volume for continuation

    # Timeouts
    BREAKOUT_TIMEOUT_HOURS = 24  # Hours before breakout state expires

    # Trading restrictions
    RESTRICTED_PERIOD_START_HOUR = 4  # UTC hour when trading restricted starts
    RESTRICTED_PERIOD_END_HOUR = 8  # UTC hour when trading restricted ends

    # Candle processing
    CANDLE_COUNT_4H = 2  # Number of 4H candles to retrieve
    CANDLE_COUNT_5M = 2  # Number of 5M candles to retrieve
    CANDLE_COUNT_4H_INIT = 7  # Number of 4H candles for initialization
    CANDLE_COUNT_5M_DEFAULT = 100  # Default number of 5M candles to retrieve

    # Time checks
    SECOND_4H_CANDLE_HOUR = 4  # Hour of second 4H candle (04:00 UTC)
    SECOND_4H_CANDLE_MINUTE = 0  # Minute of second 4H candle
    NEW_DAY_HOUR = 0  # Hour for new day check
    NEW_DAY_MINUTE_THRESHOLD = 5  # Minutes threshold for new day check
    FOUR_HOUR_INTERVAL = 4  # 4-hour interval for candle boundaries
    HOURS_PER_DAY = 24  # Hours in a day

    # Symbol tracking
    SYMBOL_HISTORY_DAYS_BACK = 30  # Days to look back for symbol history

    # History retrieval
    HISTORY_DAYS_BACK = 7  # Days to look back for trade history
    
    # Strategy types
    STRATEGY_TYPE_FALSE_BREAKOUT = "FB"  # False breakout strategy identifier
    STRATEGY_TYPE_TRUE_BREAKOUT = "TB"  # True breakout strategy identifier
    
    # Range identifiers
    RANGE_4H_5M = "4H_5M"  # 4-hour reference, 5-minute breakout
    RANGE_15M_1M = "15M_1M"  # 15-minute reference, 1-minute breakout


# ============================================================================
# FILE PATHS AND DIRECTORIES
# ============================================================================

class FilePaths:
    """File paths and directory names"""
    
    # Data directories
    DATA_DIR = "data"  # Main data directory
    LOGS_DIR = "logs"  # Logs directory
    
    # Data files
    ACTIVE_SET_FILE = "active.set"  # Active symbols file
    DISABLED_LOG_FILE = "disable.log"  # Disabled symbols log
    POSITION_PERSISTENCE_FILE = "positions.json"  # Position persistence file
    SYMBOL_STATS_FILE = "symbol_stats.json"  # Symbol statistics file
    
    # Configuration files
    ENV_FILE = ".env"  # Environment configuration file
    ENV_EXAMPLE_FILE = ".env.example"  # Example environment file


# ============================================================================
# LOGGING CONSTANTS
# ============================================================================

class LoggingConstants:
    """Logging-related constants"""
    
    # Separators
    SEPARATOR_CHAR = "="  # Character for separator lines
    SEPARATOR_LENGTH = 60  # Length of separator lines
    
    # Log levels
    LOG_LEVEL_DEBUG = "DEBUG"
    LOG_LEVEL_INFO = "INFO"
    LOG_LEVEL_WARNING = "WARNING"
    LOG_LEVEL_ERROR = "ERROR"
    LOG_LEVEL_CRITICAL = "CRITICAL"
    
    # Log formats
    TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # Timestamp format for logs
    
    # Log file settings
    MAX_LOG_FILE_SIZE_MB = 10  # Maximum log file size in MB
    LOG_BACKUP_COUNT = 5  # Number of backup log files to keep

    # Monitor bot constants
    MONITOR_DEFAULT_TAIL_LINES = 50  # Default number of lines to tail from log
    MONITOR_RECENT_LINES = 20  # Number of recent lines to show
    MONITOR_FILE_AGE_RUNNING = 60  # Seconds - file age threshold for "running" status
    MONITOR_FILE_AGE_POSSIBLY_RUNNING = 300  # Seconds - file age threshold for "possibly running"


# ============================================================================
# ENVIRONMENT VARIABLE NAMES
# ============================================================================

class EnvVars:
    """Environment variable names"""
    
    # MT5 Configuration
    MT5_LOGIN = "MT5_LOGIN"
    MT5_PASSWORD = "MT5_PASSWORD"
    MT5_SERVER = "MT5_SERVER"
    MT5_TIMEOUT = "MT5_TIMEOUT"
    MT5_PORTABLE = "MT5_PORTABLE"
    
    # Trading Configuration
    MAGIC_NUMBER = "MAGIC_NUMBER"
    TRADE_COMMENT = "TRADE_COMMENT"
    RISK_PERCENT_PER_TRADE = "RISK_PERCENT_PER_TRADE"
    MAX_LOT_SIZE = "MAX_LOT_SIZE"
    MIN_LOT_SIZE = "MIN_LOT_SIZE"
    MAX_POSITIONS = "MAX_POSITIONS"
    RISK_REWARD_RATIO = "RISK_REWARD_RATIO"
    
    # Strategy Settings
    ENTRY_OFFSET_PERCENT = "ENTRY_OFFSET_PERCENT"
    STOP_LOSS_OFFSET_PERCENT = "STOP_LOSS_OFFSET_PERCENT"
    STOP_LOSS_OFFSET_POINTS = "STOP_LOSS_OFFSET_POINTS"
    USE_POINT_BASED_SL = "USE_POINT_BASED_SL"
    
    # Advanced Settings
    USE_BREAKEVEN = "USE_BREAKEVEN"
    BREAKEVEN_TRIGGER_RR = "BREAKEVEN_TRIGGER_RR"
    USE_TRAILING_STOP = "USE_TRAILING_STOP"
    TRAILING_STOP_TRIGGER_RR = "TRAILING_STOP_TRIGGER_RR"
    TRAILING_STOP_DISTANCE = "TRAILING_STOP_DISTANCE"
    USE_ATR_TRAILING = "USE_ATR_TRAILING"
    ATR_PERIOD = "ATR_PERIOD"
    ATR_MULTIPLIER = "ATR_MULTIPLIER"
    ATR_TIMEFRAME = "ATR_TIMEFRAME"
    
    # Multi-range mode
    USE_MULTI_RANGE_MODE = "USE_MULTI_RANGE_MODE"
    MULTI_RANGE_ENABLED = "MULTI_RANGE_ENABLED"
    USE_ONLY_00_UTC_CANDLE = "USE_ONLY_00_UTC_CANDLE"
    
    # Volume confirmation
    BREAKOUT_VOLUME_MAX_MULTIPLIER = "BREAKOUT_VOLUME_MAX_MULTIPLIER"
    REVERSAL_VOLUME_MIN_MULTIPLIER = "REVERSAL_VOLUME_MIN_MULTIPLIER"
    VOLUME_AVERAGE_PERIOD = "VOLUME_AVERAGE_PERIOD"
    
    # Divergence settings
    RSI_PERIOD = "RSI_PERIOD"
    MACD_FAST = "MACD_FAST"
    MACD_SLOW = "MACD_SLOW"
    MACD_SIGNAL = "MACD_SIGNAL"
    DIVERGENCE_LOOKBACK = "DIVERGENCE_LOOKBACK"
    
    # Adaptive filters
    USE_ADAPTIVE_FILTERS = "USE_ADAPTIVE_FILTERS"
    START_WITH_FILTERS_ENABLED = "START_WITH_FILTERS_ENABLED"
    ADAPTIVE_LOSS_TRIGGER = "ADAPTIVE_LOSS_TRIGGER"
    ADAPTIVE_WIN_RECOVERY = "ADAPTIVE_WIN_RECOVERY"
    
    # Symbol adaptation
    USE_SYMBOL_ADAPTATION = "USE_SYMBOL_ADAPTATION"
    SYMBOL_MIN_TRADES = "SYMBOL_MIN_TRADES"
    SYMBOL_MIN_WIN_RATE = "SYMBOL_MIN_WIN_RATE"
    SYMBOL_MAX_LOSS = "SYMBOL_MAX_LOSS"
    SYMBOL_MAX_TOTAL_LOSS = "SYMBOL_MAX_TOTAL_LOSS"
    SYMBOL_MAX_CONSECUTIVE_LOSSES = "SYMBOL_MAX_CONSECUTIVE_LOSSES"
    SYMBOL_MAX_DRAWDOWN_PERCENT = "SYMBOL_MAX_DRAWDOWN_PERCENT"
    SYMBOL_COOLING_PERIOD_HOURS = "SYMBOL_COOLING_PERIOD_HOURS"
    SYMBOL_RESET_WEEKLY = "SYMBOL_RESET_WEEKLY"
    SYMBOL_WEEKLY_RESET_DAY = "SYMBOL_WEEKLY_RESET_DAY"
    SYMBOL_WEEKLY_RESET_HOUR = "SYMBOL_WEEKLY_RESET_HOUR"

    # Trading hours
    USE_TRADING_HOURS = "USE_TRADING_HOURS"
    START_HOUR = "START_HOUR"
    END_HOUR = "END_HOUR"

    # Logging
    ENABLE_DETAILED_LOGGING = "ENABLE_DETAILED_LOGGING"
    LOG_TO_FILE = "LOG_TO_FILE"
    LOG_TO_CONSOLE = "LOG_TO_CONSOLE"
    LOG_LEVEL = "LOG_LEVEL"
    LOG_ACTIVE_TRADES_EVERY_5MIN = "LOG_ACTIVE_TRADES_EVERY_5MIN"

    # Symbol-specific settings
    USE_SYMBOL_SPECIFIC_SETTINGS = "USE_SYMBOL_SPECIFIC_SETTINGS"

    # Divergence confirmation
    REQUIRE_BOTH_INDICATORS = "REQUIRE_BOTH_INDICATORS"
    SYMBOL_COOLING_PERIOD_DAYS = "SYMBOL_COOLING_PERIOD_DAYS"
    SYMBOL_WEEKLY_RESET_HOUR = "SYMBOL_WEEKLY_RESET_HOUR"
    
    # Logging
    ENABLE_DETAILED_LOGGING = "ENABLE_DETAILED_LOGGING"
    
    # Telegram (optional)
    TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
    TELEGRAM_CHAT_ID = "TELEGRAM_CHAT_ID"

