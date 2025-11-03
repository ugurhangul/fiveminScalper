# 4H Candle Selection Change Summary

**Date:** 2025-11-03  
**Change:** Switched from using **first 4H candle** to **second 4H candle** of the UTC day

---

## Overview

The strategy has been updated to use the **second 4H candle** (04:00-08:00 UTC) instead of the first 4H candle (00:00-04:00 UTC) for all trading decisions.

---

## Changes Made

### 1. Candle Selection Logic

**Before:**
- Used first 4H candle: Opens 00:00 UTC, Closes 04:00 UTC
- Chart displays: 00:00 UTC (opening time)
- Hour check: `hour == 0` (opening time in iTime)

**After:**
- Uses second 4H candle: Opens 04:00 UTC, Closes 08:00 UTC
- Chart displays: 04:00 UTC (opening time)
- Hour check: `hour == 4` (opening time in iTime)

### 2. Trading Suspension Period

**Before:**
- Suspended: 00:00-04:00 UTC (while first candle forming)
- Trading enabled: 04:00 UTC onwards

**After:**
- Suspended: 04:00-08:00 UTC (while second candle forming)
- Trading enabled: 08:00 UTC onwards

### 3. Daily Trading Schedule

**New Schedule:**
- **00:00-04:00 UTC**: First 4H candle forming → ✅ **TRADING ALLOWED** (using previous day's second candle)
- **04:00 UTC**: First 4H candle closes, second 4H candle starts forming
- **04:00-08:00 UTC**: Second 4H candle forming → ⛔ **TRADING SUSPENDED**
- **08:00 UTC**: Second 4H candle closes → ✅ **TRADING ENABLED**
- **08:00+ UTC**: Trading continues using the second 4H candle for the rest of the day

---

## Files Modified

### MQL5 EA Files

1. **Include/FMS_Utilities.mqh**
   - `IsNew4HCandle()`: Hour check remains `4` (second candle opens at 04:00 UTC)
   - `IsInCandleFormationPeriod()`: Changed period from `0-4` to `4-8`

2. **Include/FMS_CandleProcessing.mqh**
   - `Find00UTCCandle()`: Hour check remains `4` (second candle opens at 04:00 UTC)
   - `Find00UTCCandleIndex()`: Hour check remains `4` (second candle opens at 04:00 UTC)

3. **Include/FMS_Strategy.mqh**
   - Updated log messages to reflect second candle usage and 04:00-08:00 suspension

4. **fiveminscalper.mq5**
   - Updated initialization logic to search for second candle (hour == 4)
   - Updated log messages throughout

### Python Implementation Files

1. **python_trader/src/strategy/candle_processor.py**
   - `is_new_4h_candle()`: Hour check remains `4` (second candle opens at 04:00 UTC)
   - `_initialize_4h_candle()`: Hour check remains `4` (second candle opens at 04:00 UTC)
   - `is_in_candle_formation_period()`: Changed period from `0-4` to `4-8`
   - Updated all log messages and comments

2. **python_trader/src/strategy/strategy_engine.py**
   - Updated trading suspension check log message to 04:00-08:00 UTC

---

## Testing Checklist

Before deploying to live trading, verify:

- [ ] EA correctly identifies 04:00 UTC candle on chart (second candle)
- [ ] EA suspends trading during 04:00-08:00 UTC
- [ ] EA enables trading at 08:00 UTC
- [ ] Python bot correctly identifies 04:00 UTC candle (second candle)
- [ ] Python bot suspends trading during 04:00-08:00 UTC
- [ ] Python bot enables trading at 08:00 UTC
- [ ] Both implementations use the same 4H candle throughout the day
- [ ] Midnight crossing (00:00 UTC) does NOT suspend trading
- [ ] New day's second candle (04:00 UTC on chart) triggers candle update

---

## Rationale for Change

Using the second 4H candle (04:00-08:00 UTC) instead of the first provides:

1. **More Market Activity**: The 04:00-08:00 UTC period typically has more trading volume as Asian and early European sessions overlap
2. **Better Price Discovery**: More participants lead to more reliable support/resistance levels
3. **Reduced Weekend Gap Impact**: The first candle (00:00-04:00) can be heavily influenced by weekend gaps
4. **Improved Breakout Quality**: False breakouts are more meaningful with higher volume

---

## Configuration

The behavior is controlled by the `UseOnly00UTCCandle` parameter:
- **True** (default): Uses only the second 4H candle (04:00 UTC on chart, closes at 08:00 UTC)
- **False**: Uses any 4H candle (updates every 4 hours)

**Note:** Despite the parameter name referencing "00UTC", it now controls the second candle selection. The name is kept for backward compatibility.

---

## Important Notes

1. **Chart Display = Opening Time**:
   - MT5's `iTime()` returns the **opening time** (04:00 UTC)
   - Charts **also display the opening time** (04:00 UTC)
   - The code checks for `hour == 4` which represents the second candle opening at 04:00 UTC
   - The second candle closes at 08:00 UTC (not shown on chart label)

2. **Backward Compatibility**:
   - The parameter name `UseOnly00UTCCandle` remains unchanged
   - Existing configuration files will continue to work
   - The behavior has changed from first to second candle

3. **Synchronization**:
   - Both EA and Python implementations have been updated identically
   - They will use the exact same 4H candle for trading decisions

---

## Verification Commands

To verify the changes are working correctly:

1. **Check Current 4H Candle**:
   - Look for log message: "NEW 4H CANDLE DETECTED (04:00 UTC)"
   - Verify the candle time shows hour 4 (opening time)
   - This represents the second 4H candle (opens 04:00, closes 08:00 UTC)

2. **Check Trading Suspension**:
   - Between 04:00-08:00 UTC, should see: "Trading suspended - Restricted period (04:00-08:00 UTC)"
   - After 08:00 UTC, trading should be enabled

3. **Monitor Candle Updates**:
   - New candle should only be detected once per day at 04:00 UTC (chart time)
   - No updates at 00:00, 08:00, 12:00, 16:00, or 20:00 UTC

---

**Status:** ✅ **COMPLETE**  
**Both EA and Python implementations updated and synchronized**

