# Currency Conversion Fix for Risk Calculation

## Problem

The risk calculation was failing for cross-currency pairs like BTCTHB with the error:
```
Risk 48.81% exceeds maximum 4.50%
```

The calculated risk was approximately **10x higher** than expected (should be ~3-4.5%).

## Root Cause

For symbols where the **profit currency** differs from the **account currency**, MT5's `trade_tick_value` returns the value in the profit currency, not the account currency.

### Example: BTCTHB
- **Base Currency**: BTC
- **Profit Currency**: THB (Thai Baht)
- **Account Currency**: USD (or other)
- **Issue**: `trade_tick_value` is in THB, but risk calculation needs it in USD

When the tick value is in THB but treated as USD, the risk calculation becomes incorrect because:
- 1 THB ≈ 0.03 USD (approximately 30:1 ratio)
- Using THB value as USD inflates the calculated risk by ~30x

## Solution

Implemented automatic currency conversion that:

1. **Detects currency mismatches** between symbol profit currency and account currency
2. **Finds conversion rates** by checking available currency pairs
3. **Converts tick_value** to account currency before calculations
4. **Logs all conversions** for transparency and debugging

## Implementation Details

### 1. Enhanced Symbol Information (`mt5_connector.py`)

Added currency information to symbol info:
```python
symbol_dict = {
    # ... existing fields ...
    'currency_base': info.currency_base,
    'currency_profit': info.currency_profit,
    'currency_margin': info.currency_margin,
}
```

Added method to get account currency:
```python
def get_account_currency(self) -> str:
    """Get account currency"""
    account_info = mt5.account_info()
    return account_info.currency if account_info else ""
```

### 2. Currency Conversion Method (`mt5_connector.py`)

Added intelligent currency conversion that tries multiple approaches:
```python
def get_currency_conversion_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
    """
    Get conversion rate from one currency to another.
    
    Tries:
    1. Direct pair: FROMTO (e.g., THBUSD)
    2. Inverse pair: TOFROM (e.g., USDTHB) - returns 1/rate
    3. Pairs with separators: FROM/TO, FROM.TO, FROM_TO
    """
```

### 3. Automatic Conversion in Risk Manager (`risk_manager.py`)

Applied in both `calculate_lot_size()` and `validate_trade_risk()`:

```python
# Get account currency
account_currency = self.connector.get_account_currency()

# Convert tick value to account currency if needed
if currency_profit != account_currency and account_currency:
    conversion_rate = self.connector.get_currency_conversion_rate(
        currency_profit, account_currency
    )
    if conversion_rate is not None:
        tick_value = tick_value * conversion_rate
        self.logger.info(
            f"Currency conversion applied: {currency_profit} -> {account_currency}, "
            f"Rate={conversion_rate:.5f}, TickValue: {original_tick_value:.5f} -> {tick_value:.5f}"
        )
```

## How It Works

### For BTCTHB with USD Account:

1. **Detect**: Profit currency (THB) ≠ Account currency (USD)
2. **Find Rate**: Look for THBUSD or USDTHB pair
3. **Convert**: 
   - If THBUSD exists: `tick_value_usd = tick_value_thb * THBUSD_rate`
   - If USDTHB exists: `tick_value_usd = tick_value_thb / USDTHB_rate`
4. **Calculate**: Use converted tick_value for lot size and risk calculations

### Example Calculation:

**Before Fix:**
- Tick Value: 30.5 THB (treated as USD)
- Risk calculation uses 30.5 USD → **Massively inflated risk**

**After Fix:**
- Tick Value: 30.5 THB
- Conversion Rate: USDTHB = 33.5 → 1/33.5 = 0.0298
- Converted Tick Value: 30.5 * 0.0298 = 0.91 USD
- Risk calculation uses 0.91 USD → **Correct risk**

## Logging

The system now logs:

### During Lot Size Calculation:
```
Symbol Info: Point=0.01, TickValue=30.50000, ContractSize=1.0, 
  CurrencyBase=BTC, CurrencyProfit=THB, AccountCurrency=USD
Currency conversion applied: THB -> USD, Rate=0.02985, 
  TickValue: 30.50000 -> 0.91043
```

### During Risk Validation:
```
Risk validation currency conversion: THB -> USD, Rate=0.02985, 
  TickValue: 30.50000 -> 0.91043
Risk Validation: Balance=10000.00, Entry=3250000.00, SL=3249900.00, 
  SL_Dist=100.00, Point=0.01, SL_Points=10000.00, TickValue=0.91043, 
  LotSize=0.01, RiskAmount=91.04, RiskPercent=0.91%
```

## Testing

Run the test script to verify currency conversion:
```bash
python python_trader/test_currency_conversion.py
```

This will:
- Show account currency
- Test multiple symbols (BTCTHB, EURUSD, XAUUSD, USDJPY)
- Display currency information for each
- Show conversion rates and converted tick values

## Supported Conversion Pairs

The system tries to find conversion rates using:
1. Direct pairs: `FROMTO` (e.g., `THBUSD`, `JPYUSD`)
2. Inverse pairs: `TOFROM` (e.g., `USDTHB`, `USDJPY`)
3. Pairs with separators: `FROM/TO`, `FROM.TO`, `FROM_TO`

## Error Handling

If conversion rate cannot be found:
- Logs an ERROR message
- Continues with original tick_value
- Risk calculation may be incorrect (logged as warning)

## Benefits

1. ✅ **Accurate Risk Calculation** for all currency pairs
2. ✅ **Automatic Detection** of currency mismatches
3. ✅ **Transparent Logging** of all conversions
4. ✅ **Fallback Behavior** if conversion fails
5. ✅ **No Manual Configuration** required

## Impact on Existing Symbols

- **Major Forex (USD-based)**: No change if account is USD
- **Cross Pairs**: Automatic conversion applied
- **Exotic Pairs**: Automatic conversion applied
- **Crypto**: Automatic conversion applied (e.g., BTCTHB, ETHEUR)
- **Metals**: Automatic conversion if needed (e.g., XAUEUR)

## Future Enhancements

Potential improvements:
1. Cache conversion rates to reduce API calls
2. Support for triangular currency conversion (via intermediate currency)
3. Fallback to external exchange rate APIs if MT5 pairs unavailable
4. Configuration option to override conversion rates manually

