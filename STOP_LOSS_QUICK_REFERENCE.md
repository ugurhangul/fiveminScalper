# Stop Loss Configuration - Quick Reference

## TL;DR

**Use point-based stop loss for consistent risk across all symbols:**

```bash
USE_POINT_BASED_SL=true
STOP_LOSS_OFFSET_POINTS=100  # 10 pips for most symbols
```

## Why Point-Based?

| Method | EURUSD (1.10) | XAUUSD (2000) | USDJPY (150) | Consistency |
|--------|---------------|---------------|--------------|-------------|
| **2% Percentage** | 220 pips | 4000 pips | 300 pips | ❌ Inconsistent |
| **100 Points** | 10 pips | 10 pips | 10 pips | ✅ Consistent |

## Quick Settings Guide

### Tight Stops (Scalping)
```bash
STOP_LOSS_OFFSET_POINTS=50   # 5 pips
```
- **Risk**: Lower per trade
- **Win Rate**: May decrease (more stop-outs)
- **Best For**: High-frequency trading, tight ranges

### Moderate Stops (Recommended)
```bash
STOP_LOSS_OFFSET_POINTS=100  # 10 pips
```
- **Risk**: Balanced
- **Win Rate**: Balanced
- **Best For**: Most trading styles

### Wide Stops (Swing Trading)
```bash
STOP_LOSS_OFFSET_POINTS=200  # 20 pips
```
- **Risk**: Higher per trade
- **Win Rate**: May increase (fewer stop-outs)
- **Best For**: Volatile markets, swing trading

### Very Wide Stops (Position Trading)
```bash
STOP_LOSS_OFFSET_POINTS=500  # 50 pips
```
- **Risk**: Much higher per trade
- **Win Rate**: Higher (rare stop-outs)
- **Best For**: Long-term positions, high volatility

## Point-to-Pip Conversion

For most symbols, **10 points = 1 pip**:

| Points | Pips | Use Case |
|--------|------|----------|
| 50 | 5 | Very tight, scalping |
| 100 | 10 | Recommended default |
| 150 | 15 | Moderate |
| 200 | 20 | Wide |
| 300 | 30 | Very wide |
| 500 | 50 | Extremely wide |

## Symbol-Specific Examples

### Forex Pairs (5-digit quotes)
```
EURUSD, GBPUSD, AUDUSD, etc.
Point = 0.00001
100 points = 0.001 = 10 pips
```

### JPY Pairs (3-digit quotes)
```
USDJPY, EURJPY, GBPJPY, etc.
Point = 0.001
100 points = 0.1 = 10 pips
```

### Gold/Metals
```
XAUUSD (Gold)
Point = 0.01
100 points = 1.0 = 10 pips (in gold terms)
```

### Indices
```
US30, SPX500, NAS100, etc.
Point varies by broker
100 points = broker-specific
```

## Configuration File (.env)

### Recommended Setup
```bash
# Stop Loss - Point-Based (RECOMMENDED)
USE_POINT_BASED_SL=true
STOP_LOSS_OFFSET_POINTS=100

# Risk Management
RISK_PERCENT_PER_TRADE=1.0
RISK_REWARD_RATIO=2.0
```

### Legacy Setup (Not Recommended)
```bash
# Stop Loss - Percentage-Based (LEGACY)
USE_POINT_BASED_SL=false
STOP_LOSS_OFFSET_PERCENT=0.02

# Risk Management
RISK_PERCENT_PER_TRADE=1.0
RISK_REWARD_RATIO=2.0
```

## How to Change Settings

1. **Edit `.env` file** in `python_trader/` directory
2. **Update the values**:
   ```bash
   USE_POINT_BASED_SL=true
   STOP_LOSS_OFFSET_POINTS=100
   ```
3. **Restart the trading bot**
4. **Monitor the logs** to verify new SL distances

## Verifying Your Settings

Check the logs for messages like:
```
SL offset (point-based): 100 points = 0.00100
Entry: 1.10500
Stop Loss: 1.10400
Risk: 0.00100
```

## Common Questions

### Q: What if I want the same risk as my old 2% setting?

**A:** Calculate the pip distance and convert to points:
```
Old: 2% of 1.10 = 0.022 = 220 pips = 2200 points
New: STOP_LOSS_OFFSET_POINTS=2200
```

### Q: Can I use different settings for different symbols?

**A:** Currently, the same setting applies to all symbols. The point-based approach automatically adjusts for each symbol's price scale.

### Q: What happens if I set it too tight?

**A:** You'll get more stop-outs and lower win rate. Start with 100 points and adjust based on results.

### Q: What happens if I set it too wide?

**A:** You'll risk more per trade and may have smaller position sizes. Your win rate may improve but individual losses will be larger.

### Q: How do I know what's right for me?

**A:** 
1. Start with 100 points (10 pips)
2. Run on demo for 1-2 weeks
3. Analyze win rate and risk/reward
4. Adjust up or down by 50 points
5. Repeat until satisfied

## Risk Calculator

Use this formula to estimate your risk per trade:

```
Risk per Trade = Account Balance × Risk% × (SL Points / Entry Price Points)

Example:
- Balance: $10,000
- Risk%: 1%
- SL Points: 100
- Entry: 1.10000 (110000 points)

Risk = $10,000 × 1% × (100 / 110000) = $0.91 per pip
```

## Best Practices

1. ✅ **Start Conservative**: Use 100 points (10 pips) initially
2. ✅ **Test on Demo**: Verify settings before going live
3. ✅ **Monitor Results**: Track win rate and average risk
4. ✅ **Adjust Gradually**: Change by 50 points at a time
5. ✅ **Consider Volatility**: Wider stops for volatile markets
6. ❌ **Don't Set Too Tight**: < 50 points may cause excessive stop-outs
7. ❌ **Don't Set Too Wide**: > 500 points may risk too much per trade

## Troubleshooting

### Issue: Stop losses are too tight, getting stopped out frequently
**Solution**: Increase `STOP_LOSS_OFFSET_POINTS` by 50-100

### Issue: Stop losses are too wide, risking too much
**Solution**: Decrease `STOP_LOSS_OFFSET_POINTS` by 50-100

### Issue: Different symbols have very different SL distances
**Solution**: Verify `USE_POINT_BASED_SL=true` is set correctly

### Issue: Settings not taking effect
**Solution**: 
1. Check `.env` file is in `python_trader/` directory
2. Restart the trading bot
3. Check logs for "SL offset (point-based)" messages

## Support

For more details, see:
- `STOP_LOSS_NORMALIZATION_SOLUTION.md` - Full technical documentation
- `.env.example` - Complete configuration example
- Logs in `python_trader/logs/` - Verify your settings are working

