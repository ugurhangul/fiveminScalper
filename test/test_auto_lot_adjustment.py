"""
Test automatic lot size adjustment when risk exceeds maximum.
This script demonstrates the new auto-adjustment feature.
"""
from src.core.mt5_connector import MT5Connector
from src.risk.risk_manager import RiskManager
from src.config.config import RiskConfig, MT5Config, config
from src.utils.logger import get_logger

def test_auto_lot_adjustment():
    """Test automatic lot size adjustment"""
    logger = get_logger()

    # Create mock risk config
    risk_config = RiskConfig()
    risk_config.risk_percent_per_trade = 3.0  # 3% risk per trade
    risk_config.max_positions = 3
    risk_config.min_lot_size = 0.01
    risk_config.max_lot_size = 100.0

    # Initialize MT5 connector with config
    connector = MT5Connector(config.mt5)
    if not connector.connect():
        logger.error("Failed to connect to MT5")
        return
    
    # Create risk manager
    risk_manager = RiskManager(connector, risk_config)
    
    # Test symbols
    test_cases = [
        {
            'symbol': 'BTCTHB',
            'entry_price': 3250000.0,
            'stop_loss': 3249900.0,
            'description': 'BTCTHB with tight SL (100 THB)'
        },
        {
            'symbol': 'EURUSD',
            'entry_price': 1.10000,
            'stop_loss': 1.09950,
            'description': 'EURUSD with 50 pip SL'
        },
        {
            'symbol': 'XAUUSD',
            'entry_price': 2650.00,
            'stop_loss': 2645.00,
            'description': 'Gold with $5 SL'
        }
    ]
    
    logger.info("=" * 80)
    logger.info("TESTING AUTOMATIC LOT SIZE ADJUSTMENT")
    logger.info("=" * 80)
    logger.info(f"Risk Config: {risk_config.risk_percent_per_trade}% per trade")
    logger.info(f"Max Risk Tolerance: {risk_config.risk_percent_per_trade * 1.5}%")
    logger.info("=" * 80)
    
    for test_case in test_cases:
        symbol = test_case['symbol']
        entry_price = test_case['entry_price']
        stop_loss = test_case['stop_loss']
        description = test_case['description']
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Test Case: {description}")
        logger.info(f"{'='*80}")
        
        # Calculate initial lot size
        lot_size = risk_manager.calculate_lot_size(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss=stop_loss
        )
        
        if lot_size <= 0:
            logger.warning(f"Skipping {symbol} - invalid lot size calculated")
            continue
        
        logger.info(f"Initial lot size calculated: {lot_size:.2f}")
        
        # Validate trade risk (this will auto-adjust if needed)
        is_valid, error, adjusted_lot_size = risk_manager.validate_trade_risk(
            symbol=symbol,
            lot_size=lot_size,
            entry_price=entry_price,
            stop_loss=stop_loss
        )
        
        if not is_valid:
            logger.error(f"Trade validation failed: {error}")
        else:
            if adjusted_lot_size != lot_size:
                logger.info(f"✓ Lot size was automatically adjusted!")
                logger.info(f"  Original: {lot_size:.2f}")
                logger.info(f"  Adjusted: {adjusted_lot_size:.2f}")
                logger.info(f"  Reduction: {((lot_size - adjusted_lot_size) / lot_size * 100):.1f}%")
            else:
                logger.info(f"✓ Lot size is within acceptable risk - no adjustment needed")
                logger.info(f"  Lot size: {lot_size:.2f}")
    
    logger.info(f"\n{'='*80}")
    logger.info("TEST COMPLETED")
    logger.info(f"{'='*80}")
    
    connector.disconnect()

if __name__ == "__main__":
    test_auto_lot_adjustment()

