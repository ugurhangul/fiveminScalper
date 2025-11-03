"""
Test CHFNOK spread calculation
"""

def calculate_spread_percent(ask: float, bid: float) -> float:
    """Calculate spread as percentage of mid price"""
    spread_price = ask - bid
    mid_price = (ask + bid) / 2
    spread_percent = (spread_price / mid_price) * 100
    return spread_percent

# CHFNOK data
print("=" * 60)
print("CHFNOK Test")
print("=" * 60)

chfnok_mid = 12.47441
chfnok_point = 0.00001  # 5 decimal places for forex
chfnok_spread_points = 11771

# Calculate what the spread in price would be
chfnok_spread_price = chfnok_spread_points * chfnok_point
chfnok_ask = chfnok_mid + (chfnok_spread_price / 2)
chfnok_bid = chfnok_mid - (chfnok_spread_price / 2)

print(f"Mid Price: {chfnok_mid:.5f}")
print(f"Point: {chfnok_point:.5f}")
print(f"Spread Points: {chfnok_spread_points:.1f}")
print(f"Spread Price: {chfnok_spread_price:.5f}")
print(f"Ask: {chfnok_ask:.5f}")
print(f"Bid: {chfnok_bid:.5f}")

chfnok_spread_percent = calculate_spread_percent(chfnok_ask, chfnok_bid)
print(f"\nSpread %: {chfnok_spread_percent:.3f}%")

# Check against different category limits
print("\nCategory Limits:")
print(f"  Major Forex (0.05%): {'REJECTED' if chfnok_spread_percent > 0.05 else 'ACCEPTED'}")
print(f"  Minor Forex (0.2%): {'REJECTED' if chfnok_spread_percent > 0.2 else 'ACCEPTED'}")
print(f"  Exotic Forex (0.5%): {'REJECTED' if chfnok_spread_percent > 0.5 else 'ACCEPTED'}")

print(f"\nCHFNOK contains 'NOK' so it's detected as Exotic Forex")
print(f"With 0.5% limit: {'REJECTED ✓' if chfnok_spread_percent > 0.5 else 'ACCEPTED ✗'}")

