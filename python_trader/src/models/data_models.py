"""
Data models for the trading system.
Ported from MQL5 structures in FMS_Config.mqh and FMS_GlobalVars.mqh
"""
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Optional, List, Dict


class SymbolCategory(Enum):
    """Symbol category enumeration"""
    MAJOR_FOREX = "major_forex"
    MINOR_FOREX = "minor_forex"
    EXOTIC_FOREX = "exotic_forex"
    METALS = "metals"
    INDICES = "indices"
    CRYPTO = "crypto"
    COMMODITIES = "commodities"
    UNKNOWN = "unknown"


class PositionType(Enum):
    """Position type enumeration"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class SymbolParameters:
    """Symbol-specific parameter set"""
    # Strategy selection
    enable_false_breakout_strategy: bool = True  # Trade reversals (weak breakouts)
    enable_true_breakout_strategy: bool = True   # Trade continuations (strong breakouts)

    # Confirmation flags
    # CRITICAL: Volume confirmation MUST be enabled for dual strategy system
    # It determines which strategy to use: LOW volume = false breakout, HIGH volume = true breakout
    volume_confirmation_enabled: bool = True
    divergence_confirmation_enabled: bool = True  # Used for false breakout strategy only

    # False breakout volume parameters
    breakout_volume_max: float = 1.0  # Max volume for weak breakout (false breakout)
    reversal_volume_min: float = 1.5  # Min volume for strong reversal (false breakout)
    volume_average_period: int = 20

    # True breakout volume parameters
    true_breakout_volume_min: float = 2.0  # Min volume for strong breakout (true breakout)
    continuation_volume_min: float = 1.5   # Min volume for continuation confirmation (true breakout)

    # Divergence parameters
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    divergence_lookback: int = 20

    # Adaptive trigger parameters
    adaptive_loss_trigger: int = 3
    adaptive_win_recovery: int = 2

    # Breakout timeout (in number of 5M candles)
    # Prevents trading on stale breakouts that have lost momentum
    # Default: 24 candles = 2 hours
    breakout_timeout_candles: int = 24

    # Spread limit (as percentage of price, e.g., 0.1 = 0.1%)
    max_spread_percent: float = 0.1


@dataclass
class SymbolStats:
    """Symbol-level performance statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    is_enabled: bool = True
    disabled_time: Optional[datetime] = None
    disable_reason: str = ""

    # Drawdown tracking
    peak_equity: float = 0.0  # Highest equity reached
    current_drawdown: float = 0.0  # Current drawdown from peak
    max_drawdown: float = 0.0  # Maximum drawdown ever reached

    # Weekly reset tracking
    week_start_time: Optional[datetime] = None  # When current week started

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100.0

    @property
    def net_profit(self) -> float:
        """Calculate net profit/loss"""
        return self.total_profit - self.total_loss

    @property
    def current_drawdown_percent(self) -> float:
        """Calculate current drawdown as percentage of peak equity"""
        if self.peak_equity == 0:
            return 0.0
        return (self.current_drawdown / self.peak_equity) * 100.0

    @property
    def max_drawdown_percent(self) -> float:
        """Calculate maximum drawdown as percentage of peak equity"""
        if self.peak_equity == 0:
            return 0.0
        return (self.max_drawdown / self.peak_equity) * 100.0


@dataclass
class PositionInfo:
    """Position information structure"""
    ticket: int
    symbol: str
    position_type: PositionType
    volume: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float
    open_time: datetime
    magic_number: int
    comment: str = ""
    
    @property
    def risk(self) -> float:
        """Calculate risk (distance from entry to SL)"""
        return abs(self.open_price - self.sl)
    
    @property
    def current_pnl(self) -> float:
        """Calculate current P&L in price terms"""
        if self.position_type == PositionType.BUY:
            return self.current_price - self.open_price
        else:
            return self.open_price - self.current_price
    
    @property
    def current_rr(self) -> float:
        """Calculate current risk/reward ratio"""
        if self.risk == 0:
            return 0.0
        return self.current_pnl / self.risk


@dataclass
class CandleData:
    """OHLCV candle data"""
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low


@dataclass
class RangeConfig:
    """
    Configuration for a single range-based breakout strategy.

    Defines:
    - Reference candle: The candle that establishes the high/low range
    - Breakout candle: The smaller timeframe candle used to detect breakouts

    Examples:
    - Range 1: 4H candle at 04:00 UTC, 5M breakout detection, M5 ATR
    - Range 2: 15M candle at 04:30 UTC, 1M breakout detection, M1 ATR
    """
    # Unique identifier for this range configuration
    range_id: str

    # Reference candle configuration (establishes the range)
    reference_timeframe: str  # e.g., "H4", "M15"

    # Breakout detection candle configuration
    breakout_timeframe: str  # e.g., "M5", "M1"

    # Optional fields with defaults
    reference_time: Optional[time] = None  # Specific time to use (e.g., 04:00 for 4H, 04:30 for 15M)
    use_specific_time: bool = True  # Whether to use only specific reference candle times

    # ATR configuration for this range
    atr_timeframe: Optional[str] = None  # ATR timeframe (e.g., "M5", "M1") - defaults to breakout_timeframe if None

    def __str__(self) -> str:
        """String representation for logging"""
        if self.use_specific_time and self.reference_time:
            return f"{self.range_id} ({self.reference_timeframe}@{self.reference_time.strftime('%H:%M')} -> {self.breakout_timeframe})"
        return f"{self.range_id} ({self.reference_timeframe} -> {self.breakout_timeframe})"


@dataclass
class UnifiedBreakoutState:
    """
    Unified breakout state tracking.

    Stage 1: Unified breakout detection
    Stage 2: Strategy classification (both strategies can evaluate simultaneously)
    """
    # === STAGE 1: UNIFIED BREAKOUT DETECTION ===
    # Breakout above 4H high
    breakout_above_detected: bool = False
    breakout_above_volume: int = 0
    breakout_above_time: Optional[datetime] = None

    # Breakout below 4H low
    breakout_below_detected: bool = False
    breakout_below_volume: int = 0
    breakout_below_time: Optional[datetime] = None

    # === STAGE 2: STRATEGY CLASSIFICATION ===
    # FALSE BREAKOUT - Reversal from BELOW (BUY signal)
    false_buy_qualified: bool = False  # Low volume breakout below
    false_buy_reversal_detected: bool = False  # Reversed back above
    false_buy_reversal_confirmed: bool = False  # Next candle confirmed reversal direction
    false_buy_reversal_volume: int = 0
    false_buy_volume_ok: bool = False  # Breakout volume was low (tracked, not required)
    false_buy_reversal_volume_ok: bool = False  # Reversal volume was high (tracked, not required)
    false_buy_divergence_ok: bool = False  # Divergence present (tracked, not required)
    false_buy_rejected: bool = False  # Strategy explicitly rejected this setup

    # FALSE BREAKOUT - Reversal from ABOVE (SELL signal)
    false_sell_qualified: bool = False  # Low volume breakout above
    false_sell_reversal_detected: bool = False  # Reversed back below
    false_sell_reversal_confirmed: bool = False  # Next candle confirmed reversal direction
    false_sell_reversal_volume: int = 0
    false_sell_volume_ok: bool = False  # Breakout volume was low (tracked, not required)
    false_sell_reversal_volume_ok: bool = False  # Reversal volume was high (tracked, not required)
    false_sell_divergence_ok: bool = False  # Divergence present (tracked, not required)
    false_sell_rejected: bool = False  # Strategy explicitly rejected this setup

    # TRUE BREAKOUT - Continuation ABOVE (BUY signal)
    true_buy_qualified: bool = False  # High volume breakout above
    true_buy_retest_detected: bool = False  # Price retested breakout level (pulled back to 4H high)
    true_buy_continuation_detected: bool = False  # Continued above after retest
    true_buy_continuation_volume: int = 0
    true_buy_volume_ok: bool = False  # Breakout volume was high (tracked, not required)
    true_buy_retest_ok: bool = False  # Retest occurred (tracked, not required)
    true_buy_continuation_volume_ok: bool = False  # Continuation volume was high (tracked, not required)
    true_buy_rejected: bool = False  # Strategy explicitly rejected this setup

    # TRUE BREAKOUT - Continuation BELOW (SELL signal)
    true_sell_qualified: bool = False  # High volume breakout below
    true_sell_retest_detected: bool = False  # Price retested breakout level (pulled back to 4H low)
    true_sell_continuation_detected: bool = False  # Continued below after retest
    true_sell_continuation_volume: int = 0
    true_sell_volume_ok: bool = False  # Breakout volume was high (tracked, not required)
    true_sell_retest_ok: bool = False  # Retest occurred (tracked, not required)
    true_sell_continuation_volume_ok: bool = False  # Continuation volume was high (tracked, not required)
    true_sell_rejected: bool = False  # Strategy explicitly rejected this setup

    def has_active_breakout(self) -> bool:
        """Check if there's an active breakout being tracked"""
        return self.breakout_above_detected or self.breakout_below_detected

    def both_strategies_rejected(self) -> bool:
        """Check if both strategies have rejected the current setup"""
        if self.breakout_above_detected:
            # For breakout above: check TRUE BUY and FALSE SELL
            return self.true_buy_rejected and self.false_sell_rejected
        elif self.breakout_below_detected:
            # For breakout below: check TRUE SELL and FALSE BUY
            return self.true_sell_rejected and self.false_buy_rejected
        return False

    def reset_breakout_above(self):
        """Reset breakout above 4H high"""
        self.breakout_above_detected = False
        self.breakout_above_volume = 0
        self.breakout_above_time = None
        # Reset associated strategies
        self.true_buy_qualified = False
        self.true_buy_retest_detected = False
        self.true_buy_continuation_detected = False
        self.true_buy_continuation_volume = 0
        self.true_buy_volume_ok = False
        self.true_buy_retest_ok = False
        self.true_buy_continuation_volume_ok = False
        self.true_buy_rejected = False
        self.false_sell_qualified = False
        self.false_sell_reversal_detected = False
        self.false_sell_reversal_volume = 0
        self.false_sell_volume_ok = False
        self.false_sell_reversal_volume_ok = False
        self.false_sell_divergence_ok = False
        self.false_sell_rejected = False

    def reset_breakout_below(self):
        """Reset breakout below 4H low"""
        self.breakout_below_detected = False
        self.breakout_below_volume = 0
        self.breakout_below_time = None
        # Reset associated strategies
        self.true_sell_qualified = False
        self.true_sell_retest_detected = False
        self.true_sell_continuation_detected = False
        self.true_sell_continuation_volume = 0
        self.true_sell_volume_ok = False
        self.true_sell_retest_ok = False
        self.true_sell_continuation_volume_ok = False
        self.true_sell_rejected = False
        self.false_buy_qualified = False
        self.false_buy_reversal_detected = False
        self.false_buy_reversal_volume = 0
        self.false_buy_volume_ok = False
        self.false_buy_reversal_volume_ok = False
        self.false_buy_divergence_ok = False
        self.false_buy_rejected = False

    def reset_all(self):
        """Reset all tracking"""
        self.reset_breakout_above()
        self.reset_breakout_below()


@dataclass
class MultiRangeBreakoutState:
    """
    Multi-range breakout state tracking.

    Manages independent breakout detection and strategy classification for multiple
    range configurations simultaneously (e.g., 4H/5M and 15M/1M).

    Each range configuration has its own UnifiedBreakoutState instance.
    """
    # Dictionary mapping range_id to UnifiedBreakoutState
    range_states: Dict[str, UnifiedBreakoutState] = field(default_factory=dict)

    def get_or_create_state(self, range_id: str) -> UnifiedBreakoutState:
        """Get or create state for a specific range configuration"""
        if range_id not in self.range_states:
            self.range_states[range_id] = UnifiedBreakoutState()
        return self.range_states[range_id]

    def get_state(self, range_id: str) -> Optional[UnifiedBreakoutState]:
        """Get state for a specific range configuration (returns None if not exists)"""
        return self.range_states.get(range_id)

    def has_active_breakout(self, range_id: Optional[str] = None) -> bool:
        """
        Check if there's an active breakout.

        Args:
            range_id: Specific range to check, or None to check all ranges

        Returns:
            True if any range has an active breakout
        """
        if range_id:
            state = self.get_state(range_id)
            return state.has_active_breakout() if state else False

        # Check all ranges
        return any(state.has_active_breakout() for state in self.range_states.values())

    def reset_range(self, range_id: str):
        """Reset state for a specific range configuration"""
        if range_id in self.range_states:
            self.range_states[range_id].reset_all()

    def reset_all(self):
        """Reset all range states"""
        for state in self.range_states.values():
            state.reset_all()


@dataclass
class BreakoutState:
    """
    DEPRECATED: Legacy breakout state tracking.
    Kept for backward compatibility during migration.
    Use UnifiedBreakoutState instead.
    """
    # FALSE BREAKOUT - BUY signal tracking (reversal strategy)
    buy_breakout_confirmed: bool = False
    buy_reversal_confirmed: bool = False
    buy_breakout_candle_time: Optional[datetime] = None
    buy_breakout_volume: int = 0
    buy_reversal_volume: int = 0
    buy_breakout_volume_ok: bool = False
    buy_reversal_volume_ok: bool = False
    buy_divergence_ok: bool = False

    # FALSE BREAKOUT - SELL signal tracking (reversal strategy)
    sell_breakout_confirmed: bool = False
    sell_reversal_confirmed: bool = False
    sell_breakout_candle_time: Optional[datetime] = None
    sell_breakout_volume: int = 0
    sell_reversal_volume: int = 0
    sell_breakout_volume_ok: bool = False
    sell_reversal_volume_ok: bool = False
    sell_divergence_ok: bool = False

    # TRUE BREAKOUT - BUY signal tracking (continuation strategy)
    true_buy_breakout_confirmed: bool = False
    true_buy_continuation_confirmed: bool = False
    true_buy_breakout_candle_time: Optional[datetime] = None
    true_buy_breakout_volume: int = 0
    true_buy_continuation_volume: int = 0
    true_buy_breakout_volume_ok: bool = False
    true_buy_continuation_volume_ok: bool = False

    # TRUE BREAKOUT - SELL signal tracking (continuation strategy)
    true_sell_breakout_confirmed: bool = False
    true_sell_continuation_confirmed: bool = False
    true_sell_breakout_candle_time: Optional[datetime] = None
    true_sell_breakout_volume: int = 0
    true_sell_continuation_volume: int = 0
    true_sell_breakout_volume_ok: bool = False
    true_sell_continuation_volume_ok: bool = False

    def reset_buy(self):
        """Reset FALSE BREAKOUT BUY signal tracking"""
        self.buy_breakout_confirmed = False
        self.buy_reversal_confirmed = False
        self.buy_breakout_candle_time = None
        self.buy_breakout_volume = 0
        self.buy_reversal_volume = 0
        self.buy_breakout_volume_ok = False
        self.buy_reversal_volume_ok = False
        self.buy_divergence_ok = False

    def reset_sell(self):
        """Reset FALSE BREAKOUT SELL signal tracking"""
        self.sell_breakout_confirmed = False
        self.sell_reversal_confirmed = False
        self.sell_breakout_candle_time = None
        self.sell_breakout_volume = 0
        self.sell_reversal_volume = 0
        self.sell_breakout_volume_ok = False
        self.sell_reversal_volume_ok = False
        self.sell_divergence_ok = False

    def reset_true_buy(self):
        """Reset TRUE BREAKOUT BUY signal tracking"""
        self.true_buy_breakout_confirmed = False
        self.true_buy_continuation_confirmed = False
        self.true_buy_breakout_candle_time = None
        self.true_buy_breakout_volume = 0
        self.true_buy_continuation_volume = 0
        self.true_buy_breakout_volume_ok = False
        self.true_buy_continuation_volume_ok = False

    def reset_true_sell(self):
        """Reset TRUE BREAKOUT SELL signal tracking"""
        self.true_sell_breakout_confirmed = False
        self.true_sell_continuation_confirmed = False
        self.true_sell_breakout_candle_time = None
        self.true_sell_breakout_volume = 0
        self.true_sell_continuation_volume = 0
        self.true_sell_breakout_volume_ok = False
        self.true_sell_continuation_volume_ok = False

    def reset_all(self):
        """Reset all tracking"""
        self.reset_buy()
        self.reset_sell()
        self.reset_true_buy()
        self.reset_true_sell()


@dataclass
class ReferenceCandle:
    """
    Generic reference candle for range-based breakout detection.
    Can represent any timeframe (4H, 15M, etc.)
    """
    time: datetime
    high: float
    low: float
    open: float
    close: float
    timeframe: str  # e.g., "H4", "M15"
    is_processed: bool = False

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open


@dataclass
class FourHourCandle:
    """
    4-Hour candle tracking.
    DEPRECATED: Use ReferenceCandle instead for new code.
    Kept for backward compatibility.
    """
    time: datetime
    high: float
    low: float
    open: float
    close: float
    is_processed: bool = False

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open


@dataclass
class AdaptiveFilterState:
    """Adaptive filter system state"""
    is_active: bool = False
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    volume_confirmation_active: bool = False
    divergence_confirmation_active: bool = False
    original_volume_confirmation: bool = False
    original_divergence_confirmation: bool = False
    last_closed_ticket: int = 0


@dataclass
class TradeSignal:
    """Trade signal information"""
    symbol: str
    signal_type: PositionType
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    timestamp: datetime
    range_id: str = "default"  # Identifier for which range configuration triggered this signal
    reason: str = ""
    max_spread_percent: float = 0.1  # Maximum allowed spread as percentage of price (e.g., 0.1 = 0.1%)

    # Strategy type
    is_true_breakout: bool = False  # True = true breakout (continuation), False = false breakout (reversal)

    # Confirmation tracking (for allowing second position)
    volume_confirmed: bool = False  # Both breakout and reversal/continuation volume confirmed
    divergence_confirmed: bool = False  # Divergence confirmed at breakout (false breakout only)

    @property
    def risk(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward(self) -> float:
        return abs(self.take_profit - self.entry_price)

    @property
    def risk_reward_ratio(self) -> float:
        if self.risk == 0:
            return 0.0
        return self.reward / self.risk

    @property
    def all_confirmations_met(self) -> bool:
        """Check if all confirmations were met for this signal"""
        if self.is_true_breakout:
            # True breakout only requires volume confirmation
            return self.volume_confirmed
        else:
            # False breakout requires both volume and divergence
            return self.volume_confirmed and self.divergence_confirmed

