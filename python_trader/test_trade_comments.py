#!/usr/bin/env python3
"""
Test trade comment generation for multi-range mode.
"""
from datetime import datetime, timezone
from src.models.data_models import TradeSignal, PositionType
from src.execution.order_manager import OrderManager
from src.config.config import config

def test_trade_comment_generation():
    """Test that trade comments include range information"""
    print("\n" + "=" * 70)
    print("TRADE COMMENT GENERATION TEST")
    print("=" * 70 + "\n")
    
    # Create order manager instance (minimal setup for testing)
    # We only need the _generate_trade_comment method, so we can use a mock connector
    class MockConnector:
        pass

    order_manager = OrderManager(
        connector=MockConnector(),
        magic_number=123456,
        trade_comment="Test"
    )
    
    # Test cases
    test_cases = [
        {
            "name": "False Breakout BUY - 4H_5M range - Volume + Divergence",
            "signal": TradeSignal(
                symbol="EURUSD",
                signal_type=PositionType.BUY,
                entry_price=1.1000,
                stop_loss=1.0950,
                take_profit=1.1100,
                lot_size=0.1,
                timestamp=datetime.now(timezone.utc),
                range_id="4H_5M",
                is_true_breakout=False,
                volume_confirmed=True,
                divergence_confirmed=True
            ),
            "expected": "FB|BUY|VD|4H5M"
        },
        {
            "name": "True Breakout SELL - 15M_1M range - Volume only",
            "signal": TradeSignal(
                symbol="GBPUSD",
                signal_type=PositionType.SELL,
                entry_price=1.2500,
                stop_loss=1.2550,
                take_profit=1.2400,
                lot_size=0.1,
                timestamp=datetime.now(timezone.utc),
                range_id="15M_1M",
                is_true_breakout=True,
                volume_confirmed=True,
                divergence_confirmed=False
            ),
            "expected": "TB|SELL|V|15M1M"
        },
        {
            "name": "False Breakout SELL - 4H_5M range - No confirmations",
            "signal": TradeSignal(
                symbol="USDJPY",
                signal_type=PositionType.SELL,
                entry_price=150.00,
                stop_loss=150.50,
                take_profit=149.00,
                lot_size=0.1,
                timestamp=datetime.now(timezone.utc),
                range_id="4H_5M",
                is_true_breakout=False,
                volume_confirmed=False,
                divergence_confirmed=False
            ),
            "expected": "FB|SELL|NC|4H5M"
        },
        {
            "name": "True Breakout BUY - Default range (single-range mode)",
            "signal": TradeSignal(
                symbol="AUDUSD",
                signal_type=PositionType.BUY,
                entry_price=0.6500,
                stop_loss=0.6450,
                take_profit=0.6600,
                lot_size=0.1,
                timestamp=datetime.now(timezone.utc),
                range_id="default",
                is_true_breakout=True,
                volume_confirmed=True,
                divergence_confirmed=False
            ),
            "expected": "TB|BUY|V"
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"Test: {test_case['name']}")
        print("-" * 70)
        
        # Generate comment
        comment = order_manager._generate_trade_comment(test_case['signal'])
        expected = test_case['expected']
        
        # Check result
        if comment == expected:
            result = "✓ PASS"
        else:
            result = "✗ FAIL"
            all_passed = False
        
        print(f"  Generated: {comment}")
        print(f"  Expected:  {expected}")
        print(f"  Result:    {result}")
        print()
    
    print("=" * 70)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    test_trade_comment_generation()

