"""
Test currency conversion for tick value.
This script tests the automatic currency conversion functionality.
"""
import MetaTrader5 as mt5
from src.core.mt5_connector import MT5Connector
from src.config.config import MT5Config
from src.utils.logger import get_logger

def test_currency_conversion():
    """Test currency conversion for various symbols"""
    logger = get_logger()
    
    # Initialize MT5
    if not mt5.initialize():
        logger.error("Failed to initialize MT5")
        return
    
    # Get account info
    account_info = mt5.account_info()
    if account_info:
        logger.info(f"Account Currency: {account_info.currency}")
        logger.info(f"Balance: {account_info.balance:.2f}")
    
    # Test symbols with different currency configurations
    test_symbols = [
        'BTCTHB',   # BTC/THB - likely needs conversion
        'EURUSD',   # EUR/USD - may not need conversion if account is USD
        'XAUUSD',   # Gold/USD
        'USDJPY',   # USD/JPY
    ]
    
    for symbol in test_symbols:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {symbol}")
        logger.info(f"{'='*60}")
        
        # Get symbol info
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.warning(f"Symbol {symbol} not available")
            continue
        
        logger.info(f"Base Currency: {info.currency_base}")
        logger.info(f"Profit Currency: {info.currency_profit}")
        logger.info(f"Margin Currency: {info.currency_margin}")
        logger.info(f"Tick Value: {info.trade_tick_value:.5f}")
        logger.info(f"Contract Size: {info.trade_contract_size}")
        logger.info(f"Point: {info.point}")
        
        # Test conversion
        if account_info and info.currency_profit != account_info.currency:
            logger.info(f"\nCurrency mismatch detected: {info.currency_profit} != {account_info.currency}")
            
            # Try to find conversion rate
            from_curr = info.currency_profit
            to_curr = account_info.currency
            
            # Try direct pair
            direct_pair = f"{from_curr}{to_curr}"
            tick = mt5.symbol_info_tick(direct_pair)
            if tick:
                logger.info(f"Direct pair {direct_pair} found: Rate = {tick.bid:.5f}")
                converted_tick_value = info.trade_tick_value * tick.bid
                logger.info(f"Converted Tick Value: {info.trade_tick_value:.5f} * {tick.bid:.5f} = {converted_tick_value:.5f}")
            else:
                # Try inverse pair
                inverse_pair = f"{to_curr}{from_curr}"
                tick = mt5.symbol_info_tick(inverse_pair)
                if tick:
                    rate = 1.0 / tick.ask if tick.ask > 0 else 0
                    logger.info(f"Inverse pair {inverse_pair} found: Rate = {rate:.5f} (1/{tick.ask:.5f})")
                    converted_tick_value = info.trade_tick_value * rate
                    logger.info(f"Converted Tick Value: {info.trade_tick_value:.5f} * {rate:.5f} = {converted_tick_value:.5f}")
                else:
                    logger.warning(f"No conversion pair found for {from_curr} to {to_curr}")
        else:
            logger.info(f"No conversion needed - currencies match")
    
    mt5.shutdown()
    logger.info("\nTest completed")

if __name__ == "__main__":
    test_currency_conversion()

