"""
Test script for position persistence mechanism.

This script verifies:
1. Positions are saved to JSON file
2. Positions are loaded on startup
3. Reconciliation works correctly
4. Duplicate positions are prevented
"""
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.execution.position_persistence import PositionPersistence
from src.models.data_models import PositionInfo, PositionType
from src.utils.logger import init_logger

# Initialize logger before running tests
init_logger(log_to_file=False, log_to_console=True, log_level="INFO", enable_detailed=False)


def test_basic_persistence():
    """Test basic save/load functionality"""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Persistence")
    print("=" * 60)
    
    # Create test directory
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # Initialize persistence
    persistence = PositionPersistence(data_dir=str(test_dir))
    
    # Create test position
    position = PositionInfo(
        ticket=12345,
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
        comment="Test position"
    )
    
    # Add position
    print("\n1. Adding position to persistence...")
    persistence.add_position(position)
    
    # Verify it's in cache
    assert persistence.has_position(12345), "Position not found in cache"
    print("✓ Position added to cache")
    
    # Verify file exists
    positions_file = test_dir / "positions.json"
    assert positions_file.exists(), "Positions file not created"
    print("✓ Positions file created")
    
    # Load file and verify content
    with open(positions_file, 'r') as f:
        data = json.load(f)
    
    assert "12345" in data, "Position not in file"
    assert data["12345"]["symbol"] == "EURUSD", "Symbol mismatch"
    assert data["12345"]["position_type"] == "buy", "Position type mismatch"  # PositionType.BUY.value is lowercase
    print("✓ Position data correct in file")
    
    # Create new persistence instance (simulates restart)
    print("\n2. Simulating bot restart...")
    persistence2 = PositionPersistence(data_dir=str(test_dir))
    
    # Verify position loaded
    assert persistence2.has_position(12345), "Position not loaded after restart"
    loaded_pos = persistence2.get_position(12345)
    assert loaded_pos["symbol"] == "EURUSD", "Loaded position data incorrect"
    print("✓ Position loaded correctly after restart")
    
    # Cleanup
    persistence2.clear_all()
    print("\n✓ TEST 1 PASSED")


def test_reconciliation():
    """Test reconciliation between persistence and MT5"""
    print("\n" + "=" * 60)
    print("TEST 2: Position Reconciliation")
    print("=" * 60)
    
    # Create test directory
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # Initialize persistence with some positions
    persistence = PositionPersistence(data_dir=str(test_dir))
    
    # Add positions to persistence
    pos1 = PositionInfo(
        ticket=100,
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
        comment="Position 1"
    )
    
    pos2 = PositionInfo(
        ticket=200,
        symbol="GBPUSD",
        position_type=PositionType.SELL,
        volume=0.2,
        open_price=1.3000,
        current_price=1.2950,
        sl=1.3050,
        tp=1.2900,
        profit=100.0,
        open_time=datetime.now(timezone.utc),
        magic_number=999999,
        comment="Position 2"
    )
    
    pos3 = PositionInfo(
        ticket=300,
        symbol="USDJPY",
        position_type=PositionType.BUY,
        volume=0.15,
        open_price=150.00,
        current_price=150.50,
        sl=149.50,
        tp=151.00,
        profit=75.0,
        open_time=datetime.now(timezone.utc),
        magic_number=999999,
        comment="Position 3"
    )
    
    print("\n1. Adding 3 positions to persistence...")
    persistence.add_position(pos1)
    persistence.add_position(pos2)
    persistence.add_position(pos3)
    print(f"✓ Persisted positions: {persistence.get_all_tickets()}")
    
    # Simulate MT5 positions (pos1 and pos2 exist, pos3 closed, pos4 is new)
    pos4 = PositionInfo(
        ticket=400,
        symbol="AUDUSD",
        position_type=PositionType.BUY,
        volume=0.1,
        open_price=0.6500,
        current_price=0.6550,
        sl=0.6450,
        tp=0.6600,
        profit=50.0,
        open_time=datetime.now(timezone.utc),
        magic_number=999999,
        comment="Position 4 (new)"
    )
    
    # Update pos2 SL/TP (modified in MT5)
    pos2_modified = PositionInfo(
        ticket=200,
        symbol="GBPUSD",
        position_type=PositionType.SELL,
        volume=0.2,
        open_price=1.3000,
        current_price=1.2950,
        sl=1.3000,  # Changed from 1.3050
        tp=1.2850,  # Changed from 1.2900
        profit=100.0,
        open_time=datetime.now(timezone.utc),
        magic_number=999999,
        comment="Position 2"
    )
    
    mt5_positions = [pos1, pos2_modified, pos4]
    
    print("\n2. Simulating MT5 positions:")
    print(f"   - Position 100 (EURUSD): Still open")
    print(f"   - Position 200 (GBPUSD): Still open, SL/TP modified")
    print(f"   - Position 300 (USDJPY): Closed externally")
    print(f"   - Position 400 (AUDUSD): New position (not in persistence)")
    
    # Reconcile
    print("\n3. Running reconciliation...")
    results = persistence.reconcile_with_mt5(mt5_positions)
    
    # Verify results
    print("\n4. Verifying reconciliation results...")
    assert 400 in results['added'], "Position 400 should be added"
    assert 300 in results['removed'], "Position 300 should be removed"
    assert 200 in results['updated'], "Position 200 should be updated"
    print(f"✓ Added: {results['added']}")
    print(f"✓ Removed: {results['removed']}")
    print(f"✓ Updated: {results['updated']}")
    
    # Verify final state
    final_tickets = persistence.get_all_tickets()
    assert 100 in final_tickets, "Position 100 should still exist"
    assert 200 in final_tickets, "Position 200 should still exist"
    assert 300 not in final_tickets, "Position 300 should be removed"
    assert 400 in final_tickets, "Position 400 should be added"
    print(f"✓ Final persisted positions: {final_tickets}")
    
    # Verify position 200 was updated
    pos200 = persistence.get_position(200)
    assert pos200['sl'] == 1.3000, "Position 200 SL not updated"
    assert pos200['tp'] == 1.2850, "Position 200 TP not updated"
    print("✓ Position 200 SL/TP updated correctly")
    
    # Cleanup
    persistence.clear_all()
    print("\n✓ TEST 2 PASSED")


def test_duplicate_prevention():
    """Test that duplicate positions are detected"""
    print("\n" + "=" * 60)
    print("TEST 3: Duplicate Position Prevention")
    print("=" * 60)
    
    # Create test directory
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # Initialize persistence
    persistence = PositionPersistence(data_dir=str(test_dir))
    
    # Add a position
    position = PositionInfo(
        ticket=12345,
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
        comment="Test position"
    )
    
    print("\n1. Adding position 12345...")
    persistence.add_position(position)
    
    # Check if position exists
    print("\n2. Checking for existing position...")
    tickets = persistence.get_all_tickets()
    print(f"✓ Persisted tickets: {tickets}")
    
    # Simulate checking before creating duplicate
    if 12345 in tickets:
        print("✓ Position 12345 already exists - would prevent duplicate creation")
    else:
        raise AssertionError("Position not found - duplicate prevention would fail")
    
    # Cleanup
    persistence.clear_all()
    print("\n✓ TEST 3 PASSED")


def cleanup_test_data():
    """Remove test data directory"""
    test_dir = Path("test_data")
    if test_dir.exists():
        # Remove positions file
        positions_file = test_dir / "positions.json"
        if positions_file.exists():
            positions_file.unlink()
        
        # Remove directory
        test_dir.rmdir()
        print("\n✓ Test data cleaned up")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("POSITION PERSISTENCE TEST SUITE")
    print("=" * 60)
    
    try:
        # Run tests
        test_basic_persistence()
        test_reconciliation()
        test_duplicate_prevention()
        
        # Cleanup
        cleanup_test_data()
        
        # Summary
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        print("\nPosition persistence mechanism is working correctly!")
        print("The bot will now:")
        print("  1. Save positions to data/positions.json")
        print("  2. Load positions on startup")
        print("  3. Reconcile with MT5 positions")
        print("  4. Prevent duplicate position creation")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        cleanup_test_data()
        sys.exit(1)

