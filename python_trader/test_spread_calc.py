"""
Test spread calculation to verify percentage-based limits work correctly
"""

def calculate_spread_percent(ask: float, bid: float) -> float:
    """Calculate spread as percentage of mid price"""
    spread_price = ask - bid
    mid_price = (ask + bid) / 2
    spread_percent = (spread_price / mid_price) * 100
    return spread_percent

def calculate_spread_points(ask: float, bid: float, point: float) -> float:
    """Calculate spread in points"""
    spread_price = ask - bid
    spread_points = spread_price / point
    return spread_points

# Test SEKDKK
print("=" * 60)
print("SEKDKK Test")
print("=" * 60)
# Assuming typical SEKDKK pricing
sekdkk_mid = 0.67818
sekdkk_point = 0.00001  # 5 decimal places for forex
sekdkk_spread_points = 873

# Calculate what the spread in price would be
sekdkk_spread_price = sekdkk_spread_points * sekdkk_point
sekdkk_ask = sekdkk_mid + (sekdkk_spread_price / 2)
sekdkk_bid = sekdkk_mid - (sekdkk_spread_price / 2)

print(f"Mid Price: {sekdkk_mid:.5f}")
print(f"Point: {sekdkk_point:.5f}")
print(f"Spread Points: {sekdkk_spread_points:.1f}")
print(f"Spread Price: {sekdkk_spread_price:.5f}")
print(f"Ask: {sekdkk_ask:.5f}")
print(f"Bid: {sekdkk_bid:.5f}")

sekdkk_spread_percent = calculate_spread_percent(sekdkk_ask, sekdkk_bid)
print(f"Spread %: {sekdkk_spread_percent:.3f}%")
print(f"Max for Minor Forex: 0.2%")
print(f"Result: {'REJECTED' if sekdkk_spread_percent > 0.2 else 'ACCEPTED'}")

# Test SOLUSD with different point values
print("\n" + "=" * 60)
print("SOLUSD Test (trying different point values)")
print("=" * 60)
solusd_mid = 176.0
solusd_spread_points = 8400

for point_value in [0.01, 0.001, 0.0001]:
    print(f"\n--- Point value: {point_value} ---")
    solusd_spread_price = solusd_spread_points * point_value
    solusd_ask = solusd_mid + (solusd_spread_price / 2)
    solusd_bid = solusd_mid - (solusd_spread_price / 2)

    print(f"Mid Price: {solusd_mid:.4f}")
    print(f"Spread Points: {solusd_spread_points:.1f}")
    print(f"Spread Price: {solusd_spread_price:.4f}")
    print(f"Ask: {solusd_ask:.4f}")
    print(f"Bid: {solusd_bid:.4f}")

    solusd_spread_percent = calculate_spread_percent(solusd_ask, solusd_bid)
    print(f"Spread %: {solusd_spread_percent:.3f}%")
    print(f"Max for Crypto: 0.5%")
    print(f"Result: {'REJECTED' if solusd_spread_percent > 0.5 else 'ACCEPTED'}")

# Use the most likely point value (0.0001 for 4 decimal crypto)
solusd_point = 0.0001
solusd_spread_price = solusd_spread_points * solusd_point
solusd_ask = solusd_mid + (solusd_spread_price / 2)
solusd_bid = solusd_mid - (solusd_spread_price / 2)
solusd_spread_percent = calculate_spread_percent(solusd_ask, solusd_bid)

print("\n" + "=" * 60)
print("Summary with Updated Limits")
print("=" * 60)
print(f"SEKDKK: {sekdkk_spread_percent:.3f}% - {'REJECTED' if sekdkk_spread_percent > 0.2 else 'ACCEPTED'} (limit: 0.2%)")
print(f"SOLUSD: {solusd_spread_percent:.3f}% - {'REJECTED' if solusd_spread_percent > 0.5 else 'ACCEPTED'} (limit: 0.5%)")
print("\nConclusion:")
print("- SEKDKK with 1.287% spread is REJECTED (exceeds 0.2% limit for minor forex)")
print("- SOLUSD with 0.477% spread is ACCEPTED (within 0.5% limit for crypto)")
print("- This correctly identifies SEKDKK's spread as too wide while accepting SOLUSD")

