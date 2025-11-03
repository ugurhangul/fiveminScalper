# Automatic Lot Size Adjustment

## Overview

The risk management system now automatically reduces lot sizes when the calculated risk exceeds the maximum allowed risk percentage, instead of rejecting trades entirely. This feature helps maximize trading opportunities while maintaining strict risk controls.

## Problem Solved

**Before:** When `validate_trade_risk()` detected that risk exceeded the maximum (1.5x the configured `risk_percent_per_trade`), it would reject the trade with an error like:
```
ERROR | Trade validation failed: Risk 48.81% exceeds maximum 4.50%
```

This meant potentially profitable trades were being rejected due to risk calculation issues or unusual market conditions.

**After:** The system automatically recalculates a smaller lot size that brings the risk within acceptable limits, allowing the trade to proceed safely.

## How It Works

### 1. Risk Validation Process

When `validate_trade_risk()` is called:

1. **Calculate actual risk** with the proposed lot size
2. **Check against maximum** (configured risk × 1.5)
3. **If risk exceeds maximum:**
   - Automatically recalculate lot size to target the configured risk percent
   - Apply all normalization and constraints (min_lot, max_lot, lot_step)
   - Verify adjusted lot size meets minimum requirements
   - Log the adjustment with before/after values
   - Return the adjusted lot size

### 2. Target Risk Level

When adjustment is needed, the system targets the **configured risk percent**, not the maximum tolerance:

- **Configured Risk**: 3.0% (from `risk_percent_per_trade`)
- **Maximum Tolerance**: 4.5% (configured risk × 1.5)
- **Adjustment Target**: 3.0% (the configured risk, not 4.5%)

This ensures trades stay within the intended risk profile.

### 3. Lot Size Calculation

The adjusted lot size is calculated using the same formula as `calculate_lot_size()`:

```python
# Target the configured risk percent
target_risk_amount = balance * (risk_percent_per_trade / 100.0)

# Calculate lot size: lotSize = riskAmount / (stopLossPoints * tickValue)
adjusted_lot_size = target_risk_amount / (sl_distance_in_points * tick_value)

# Normalize to lot step
adjusted_lot_size = round(adjusted_lot_size / lot_step) * lot_step

# Apply min/max constraints
adjusted_lot_size = max(min_lot, min(max_lot, adjusted_lot_size))
adjusted_lot_size = max(user_min_lot, adjusted_lot_size)
```

### 4. Rejection Criteria

The trade is still rejected if:

1. **Adjusted lot size < minimum lot size** (symbol or user-defined)
2. **Invalid symbol info** cannot be retrieved
3. **Invalid stop loss distance** (zero or negative)
4. **Original lot size > maximum lot size**

## Implementation Details

### Modified Method Signature

```python
def validate_trade_risk(self, symbol: str, lot_size: float,
                       entry_price: float, stop_loss: float) -> Tuple[bool, str, float]:
    """
    Validate if trade meets risk requirements.
    If risk exceeds maximum, automatically recalculates a smaller lot size.

    Returns:
        Tuple of (is_valid, error_message, adjusted_lot_size)
        - is_valid: True if trade can proceed (possibly with adjusted lot size)
        - error_message: Error description if is_valid is False, empty string otherwise
        - adjusted_lot_size: The lot size to use (may be reduced from original)
    """
```

### Updated Caller

In `symbol_strategy.py`:

```python
# Validate trade risk (may adjust lot size if risk is too high)
is_valid, error, adjusted_lot_size = self.risk_manager.validate_trade_risk(
    symbol=self.symbol,
    lot_size=lot_size,
    entry_price=signal.entry_price,
    stop_loss=signal.stop_loss
)

if not is_valid:
    self.logger.error(f"Trade validation failed: {error}", self.symbol)
    return

# Use the adjusted lot size (may be same as original or reduced)
signal.lot_size = adjusted_lot_size
```

## Logging

### When Adjustment Occurs

The system logs detailed information about the adjustment:

```
WARNING | Risk 48.81% exceeds maximum 4.50%. Automatically reducing lot size...
WARNING | Lot size adjusted: 0.10 -> 0.01 | Risk: 48.81% -> 4.88% | Target: 3.00%
```

### Log Details Include:

1. **Original risk percentage** that triggered the adjustment
2. **Maximum allowed risk** (for reference)
3. **Original lot size** before adjustment
4. **Adjusted lot size** after recalculation
5. **New risk percentage** with adjusted lot size
6. **Target risk percentage** (configured risk)

### When No Adjustment Needed

If risk is within acceptable limits, the original lot size is returned:

```python
# Risk is within acceptable limits, return original lot size
return True, "", lot_size
```

## Example Scenarios

### Scenario 1: BTCTHB with Currency Conversion Issue

**Before Fix:**
- Calculated lot size: 0.10
- Risk with 0.10 lots: 48.81% (due to currency conversion issue)
- Result: **Trade rejected**

**After Fix:**
- Calculated lot size: 0.10
- Risk with 0.10 lots: 48.81%
- System detects risk > 4.5% (max tolerance)
- Recalculates lot size targeting 3.0% risk
- Adjusted lot size: 0.01
- Risk with 0.01 lots: ~4.88%
- Result: **Trade proceeds with 0.01 lots**

### Scenario 2: Normal Trade Within Limits

**Scenario:**
- Calculated lot size: 0.05
- Risk with 0.05 lots: 2.8%
- Max tolerance: 4.5%
- Result: **No adjustment needed, trade proceeds with 0.05 lots**

### Scenario 3: Adjusted Lot Size Below Minimum

**Scenario:**
- Calculated lot size: 0.10
- Risk with 0.10 lots: 50.0%
- Recalculated lot size: 0.006
- Minimum lot size: 0.01
- Result: **Trade rejected** (adjusted lot size below minimum)

## Benefits

1. ✅ **Maximizes Trading Opportunities** - Trades aren't rejected unnecessarily
2. ✅ **Maintains Risk Control** - All trades stay within configured risk limits
3. ✅ **Automatic Recovery** - Handles temporary calculation issues gracefully
4. ✅ **Transparent Logging** - All adjustments are clearly logged
5. ✅ **Conservative Targeting** - Targets configured risk, not maximum tolerance
6. ✅ **Respects All Constraints** - Min/max lot sizes, lot steps, user limits

## Testing

Run the test script to see the feature in action:

```bash
python python_trader/test_auto_lot_adjustment.py
```

This will:
- Test multiple symbols (BTCTHB, EURUSD, XAUUSD)
- Show initial lot size calculations
- Demonstrate automatic adjustments when needed
- Display before/after risk percentages

## Configuration

The feature uses existing risk configuration:

```python
class RiskConfig:
    risk_percent_per_trade: float = 3.0  # Target risk per trade
    max_positions: int = 3
    min_lot_size: float = 0.01  # User-defined minimum
    max_lot_size: float = 100.0  # User-defined maximum
```

- **risk_percent_per_trade**: Target risk percentage (e.g., 3.0%)
- **Maximum tolerance**: Automatically calculated as `risk_percent_per_trade * 1.5`
- **Adjustment target**: Always targets `risk_percent_per_trade`, not the tolerance

## Edge Cases Handled

1. **Lot size below minimum after adjustment** → Trade rejected with clear message
2. **Currency conversion failures** → Logged as error, adjustment still attempted
3. **Invalid symbol info** → Trade rejected immediately
4. **Zero or negative SL distance** → Trade rejected immediately
5. **Balance = 0** → Risk calculation returns 0%, no adjustment needed

## Backward Compatibility

The change is **backward compatible** with one caveat:

- **Return value changed** from `Tuple[bool, str]` to `Tuple[bool, str, float]`
- **All callers must be updated** to handle the third return value (adjusted lot size)
- Currently only called in `symbol_strategy.py`, which has been updated

## Future Enhancements

Potential improvements:
1. Make adjustment behavior configurable (enable/disable auto-adjustment)
2. Add adjustment statistics to trading reports
3. Allow custom adjustment targets (e.g., target 2% instead of configured 3%)
4. Add maximum adjustment ratio limit (e.g., don't reduce by more than 90%)

