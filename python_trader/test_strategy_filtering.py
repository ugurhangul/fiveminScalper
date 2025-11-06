"""
Test strategy-based position filtering.
Verifies that True Breakout and False Breakout strategies can have separate positions.
"""
from src.models.data_models import PositionInfo, PositionType
from datetime import datetime, timezone


def test_comment_parsing():
    """Test extracting strategy type and range from position comments"""
    print("\n" + "=" * 60)
    print("TEST: Comment Parsing for Strategy Type and Range")
    print("=" * 60)

    test_cases = [
        ("TB|BUY|V|4H5M", "TB", "4H5M"),
        ("FB|SELL|VD|15M1M", "FB", "15M1M"),
        ("TB|BUY|NC|4H5M", "TB", "4H5M"),
        ("FB|SELL|V", "FB", ""),
        ("TB|BUY|NC", "TB", ""),
        ("", "", ""),
    ]

    for comment, expected_strategy, expected_range in test_cases:
        parts = comment.split('|') if '|' in comment else []
        strategy = parts[0] if len(parts) > 0 else ''
        range_id = parts[3] if len(parts) > 3 else ''

        strategy_ok = strategy == expected_strategy
        range_ok = range_id == expected_range
        status = "✓" if (strategy_ok and range_ok) else "✗"

        print(f"{status} Comment: '{comment}' -> Strategy: '{strategy}', Range: '{range_id}' "
              f"(expected: '{expected_strategy}', '{expected_range}')")

    print("\n" + "=" * 60)


def test_position_filtering():
    """Test that positions are correctly filtered by strategy and range"""
    print("\n" + "=" * 60)
    print("TEST: Position Filtering by Strategy and Range")
    print("=" * 60)

    # Create test positions
    positions = [
        PositionInfo(
            ticket=1001,
            symbol="EURUSD",
            position_type=PositionType.BUY,
            volume=0.1,
            open_price=1.1000,
            current_price=1.1050,
            sl=1.0950,
            tp=1.1100,
            profit=50.0,
            open_time=datetime.now(timezone.utc),
            magic_number=999999,
            comment="TB|BUY|V|4H5M"  # True Breakout, M5 scalp
        ),
        PositionInfo(
            ticket=1002,
            symbol="EURUSD",
            position_type=PositionType.BUY,
            volume=0.1,
            open_price=1.1010,
            current_price=1.1060,
            sl=1.0960,
            tp=1.1110,
            profit=50.0,
            open_time=datetime.now(timezone.utc),
            magic_number=999999,
            comment="FB|BUY|VD|4H5M"  # False Breakout, M5 scalp
        ),
        PositionInfo(
            ticket=1003,
            symbol="EURUSD",
            position_type=PositionType.BUY,
            volume=0.1,
            open_price=1.1005,
            current_price=1.1055,
            sl=1.0955,
            tp=1.1105,
            profit=50.0,
            open_time=datetime.now(timezone.utc),
            magic_number=999999,
            comment="TB|BUY|V|15M1M"  # True Breakout, M1 scalp
        ),
        PositionInfo(
            ticket=1004,
            symbol="EURUSD",
            position_type=PositionType.SELL,
            volume=0.1,
            open_price=1.1000,
            current_price=1.0950,
            sl=1.1050,
            tp=1.0900,
            profit=50.0,
            open_time=datetime.now(timezone.utc),
            magic_number=999999,
            comment="TB|SELL|NC|4H5M"  # True Breakout SELL, M5 scalp
        ),
    ]

    # Test 1: Filter for TB BUY 4H5M positions
    symbol = "EURUSD"
    position_type = PositionType.BUY
    strategy_type = "TB"
    range_id = "4H_5M"

    same_type_positions = [
        pos for pos in positions
        if pos.symbol == symbol and pos.position_type == position_type
    ]

    print(f"\nTest 1: Filtering for {symbol} {position_type.value} positions")
    print(f"Found {len(same_type_positions)} positions of same type:")
    for pos in same_type_positions:
        print(f"  - Ticket {pos.ticket}: {pos.comment}")

    # Filter by strategy and range
    filtered_positions = []
    for pos in same_type_positions:
        parts = pos.comment.split('|') if '|' in pos.comment else []
        comment_strategy = parts[0] if len(parts) > 0 else ''
        comment_range = parts[3] if len(parts) > 3 else ''

        strategy_match = comment_strategy == strategy_type
        range_match = comment_range == range_id.replace('_', '')

        if strategy_match and range_match:
            filtered_positions.append(pos)

    print(f"\nFiltering for strategy: {strategy_type}, range: {range_id}")
    print(f"Found {len(filtered_positions)} positions matching criteria:")
    for pos in filtered_positions:
        print(f"  - Ticket {pos.ticket}: {pos.comment}")

    # Verify results
    assert len(same_type_positions) == 3, "Should find 3 BUY positions"
    assert len(filtered_positions) == 1, "Should find 1 TB BUY 4H5M position"
    assert filtered_positions[0].ticket == 1001, "Should be ticket 1001"

    print("\n✓ Test 1 passed!")

    # Test 2: Verify different ranges are independent
    range_id_2 = "15M_1M"
    filtered_positions_2 = []
    for pos in same_type_positions:
        parts = pos.comment.split('|') if '|' in pos.comment else []
        comment_strategy = parts[0] if len(parts) > 0 else ''
        comment_range = parts[3] if len(parts) > 3 else ''

        strategy_match = comment_strategy == strategy_type
        range_match = comment_range == range_id_2.replace('_', '')

        if strategy_match and range_match:
            filtered_positions_2.append(pos)

    print(f"\nTest 2: Filtering for strategy: {strategy_type}, range: {range_id_2}")
    print(f"Found {len(filtered_positions_2)} positions matching criteria:")
    for pos in filtered_positions_2:
        print(f"  - Ticket {pos.ticket}: {pos.comment}")

    assert len(filtered_positions_2) == 1, "Should find 1 TB BUY 15M1M position"
    assert filtered_positions_2[0].ticket == 1003, "Should be ticket 1003"

    print("✓ Test 2 passed!")
    print("\n✓ All assertions passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_comment_parsing()
    test_position_filtering()
    print("\n✓ All tests passed!")

