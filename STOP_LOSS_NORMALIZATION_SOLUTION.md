# Stop Loss Offset Normalization Solution

## Problem Statement

The original stop loss calculation used a **percentage-based approach** that didn't account for different symbol price scales, creating inconsistent risk levels across different asset classes.

### Example of the Problem

With `stop_loss_offset_percent = 2.0%`:

| Symbol | Price | 2% Offset | Pips | Issue |
|--------|-------|-----------|------|-------|
| EURUSD | 1.10 | 0.022 | 220 | ✓ Reasonable |
| GBPUSD | 1.25 | 0.025 | 250 | ✓ Reasonable |
| XAUUSD | 2000 | 40.0 | 4000 | ✗ Too large! |
| USDJPY | 150 | 3.0 | 300 | ✗ Too large! |
| EURJPY | 165 | 3.3 | 330 | ✗ Too large! |

**The core issue:** Applying the same percentage to vastly different price scales creates wildly different stop loss distances in terms of actual market movement (pips).

## Solution: Point-Based Stop Loss Calculation

The solution implements a **point-based offset** that normalizes stop loss distances across all symbols by using each symbol's `point` value from MT5.

### How It Works

1. **Point Value**: MT5 provides a `point` value for each symbol that represents the minimum price change
   - For 5-digit forex pairs (EURUSD): 1 point = 0.00001 (0.1 pip)
   - For 3-digit JPY pairs (USDJPY): 1 point = 0.001 (0.1 pip)
   - For gold (XAUUSD): 1 point = 0.01 (1 cent)

2. **Offset Calculation**: 
   ```python
   sl_offset = stop_loss_offset_points * symbol_point_value
   ```

3. **Consistent Risk**: Using the same number of points across all symbols ensures consistent risk

### Example with Point-Based Calculation

With `stop_loss_offset_points = 100`:

| Symbol | Point Value | 100 Points | Equivalent Pips | Result |
|--------|-------------|------------|-----------------|--------|
| EURUSD | 0.00001 | 0.001 | 10 pips | ✓ Consistent |
| GBPUSD | 0.00001 | 0.001 | 10 pips | ✓ Consistent |
| XAUUSD | 0.01 | 1.0 | 10 pips | ✓ Consistent |
| USDJPY | 0.001 | 0.1 | 10 pips | ✓ Consistent |
| EURJPY | 0.001 | 0.1 | 10 pips | ✓ Consistent |

**Result:** All symbols now have a consistent 10-pip stop loss offset, regardless of their price scale!

## Implementation Details

### Configuration Changes

Added three new parameters to `StrategyConfig`:

```python
@dataclass
class StrategyConfig:
    stop_loss_offset_points: int = 100  # Stop loss offset in points (recommended)
    use_point_based_sl: bool = True     # Use point-based SL calculation
    stop_loss_offset_percent: float = 0.02  # Deprecated: legacy fallback
```

### Environment Variables

```bash
# Recommended: Point-based SL
USE_POINT_BASED_SL=true
STOP_LOSS_OFFSET_POINTS=100

# Legacy: Percentage-based SL (not recommended)
USE_POINT_BASED_SL=false
STOP_LOSS_OFFSET_PERCENT=0.02
```

### Code Changes

1. **StrategyEngine Constructor**: Added `connector` parameter to access symbol information
   ```python
   def __init__(self, ..., connector=None):
       self.connector = connector
   ```

2. **New Helper Method**: `_calculate_sl_offset()` handles both point-based and percentage-based calculations
   ```python
   def _calculate_sl_offset(self, reference_price: float) -> float:
       if self.strategy_config.use_point_based_sl and self.connector is not None:
           symbol_info = self.connector.get_symbol_info(self.symbol)
           point = symbol_info['point']
           return self.strategy_config.stop_loss_offset_points * point
       else:
           # Fallback to percentage-based
           return reference_price * (self.strategy_config.stop_loss_offset_percent / 100.0)
   ```

3. **Updated Signal Generation**: Both `_generate_buy_signal()` and `_generate_sell_signal()` now use the new method
   ```python
   # Old (percentage-based)
   sl_offset = lowest_low * (self.strategy_config.stop_loss_offset_percent / 100.0)
   
   # New (point-based or percentage-based)
   sl_offset = self._calculate_sl_offset(lowest_low)
   ```

## Recommended Settings

### Conservative (Tighter Stops)
```bash
STOP_LOSS_OFFSET_POINTS=50   # 5 pips
```

### Moderate (Recommended)
```bash
STOP_LOSS_OFFSET_POINTS=100  # 10 pips
```

### Aggressive (Wider Stops)
```bash
STOP_LOSS_OFFSET_POINTS=200  # 20 pips
```

## Benefits

1. **Consistent Risk**: Same pip distance across all symbols
2. **Symbol-Agnostic**: Works correctly for forex, metals, indices, crypto
3. **Predictable**: Easy to understand and calculate expected risk
4. **MT5 Native**: Uses MT5's built-in point values for accuracy
5. **Backward Compatible**: Falls back to percentage-based if needed

## Migration Guide

### For Existing Users

1. **Update Configuration**:
   ```bash
   # Add to your .env file
   USE_POINT_BASED_SL=true
   STOP_LOSS_OFFSET_POINTS=100
   ```

2. **Test First**: Start with a demo account to verify the new stop loss distances

3. **Adjust Points**: Fine-tune `STOP_LOSS_OFFSET_POINTS` based on your risk tolerance
   - Current 2% on EURUSD ≈ 220 pips → Use `STOP_LOSS_OFFSET_POINTS=2200`
   - Recommended tighter stops → Use `STOP_LOSS_OFFSET_POINTS=100` (10 pips)

### For New Users

Simply use the recommended settings in `.env.example`:
```bash
USE_POINT_BASED_SL=true
STOP_LOSS_OFFSET_POINTS=100
```

## Technical Notes

### Point vs Pip
- **Point**: Minimum price change (MT5 definition)
  - 5-digit quotes: 1 pip = 10 points
  - 3-digit quotes: 1 pip = 10 points
- **Pip**: Standard unit of price movement
  - Most forex: 0.0001
  - JPY pairs: 0.01

### Symbol Point Values (Examples)
```
EURUSD: point = 0.00001 (5 digits)
GBPUSD: point = 0.00001 (5 digits)
USDJPY: point = 0.001   (3 digits)
XAUUSD: point = 0.01    (2 digits)
BTCUSD: point = 0.01    (2 digits)
```

### Calculation Formula
```
SL Distance (price) = offset_points × symbol_point_value

Example for EURUSD:
100 points × 0.00001 = 0.001 = 10 pips

Example for XAUUSD:
100 points × 0.01 = 1.0 = 10 pips (in gold terms)
```

## Testing

To verify the implementation:

1. **Check Logs**: Look for debug messages showing SL offset calculation
   ```
   SL offset (point-based): 100 points = 0.00100
   ```

2. **Compare Symbols**: Verify that different symbols have proportional SL distances
   - EURUSD: ~10 pips
   - USDJPY: ~10 pips
   - XAUUSD: ~$1.00 (equivalent to 10 pips)

3. **Validate Risk**: Ensure lot sizes are calculated correctly based on the new SL distances

## Conclusion

The point-based stop loss calculation provides a robust, symbol-agnostic solution that ensures consistent risk management across all asset classes. This is the recommended approach for all users going forward.

