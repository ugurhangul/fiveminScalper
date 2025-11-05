"""
Data models for the trading system.
Ported from MQL5 structures in FMS_Config.mqh and FMS_GlobalVars.mqh
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


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
class BreakoutState:
    """Tracks breakout and reversal state for a symbol"""
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
class FourHourCandle:
    """4-Hour candle tracking"""
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

