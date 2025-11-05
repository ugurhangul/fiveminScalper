"""
Backtest runner script.
Run backtests on historical data from MT5.
"""
import sys
from datetime import datetime, timedelta
from src.core.mt5_connector import MT5Connector
from src.backtest.backtest_engine import BacktestEngine
from src.backtest.performance_analyzer import PerformanceAnalyzer
from src.config.config import config
from src.utils.logger import init_logger, get_logger


def main():
    """Main backtest runner"""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║         FiveMinScalper - Backtesting Module               ║
    ║         Test Your Strategy on Historical Data             ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize logger
    init_logger()
    logger = get_logger()
    
    # Connect to MT5
    logger.info("Connecting to MT5...")
    connector = MT5Connector(config.mt5)
    
    if not connector.connect():
        logger.error("Failed to connect to MT5")
        return
    
    logger.info("Connected to MT5 successfully")
    
    # ========================================
    # BACKTEST CONFIGURATION
    # ========================================
    
    # Symbols to test (you can modify this list)
    symbols = [
        'EURUSD',
        'GBPUSD',
        'USDJPY',
        # Add more symbols as needed
    ]
    
    # Date range for backtest
    # Example: Test last 3 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    # Or specify exact dates:
    # start_date = datetime(2024, 1, 1)
    # end_date = datetime(2024, 12, 31)
    
    # Initial balance
    initial_balance = 10000.0
    
    # ========================================
    # RUN BACKTEST
    # ========================================
    
    logger.info("Initializing backtest engine...")
    engine = BacktestEngine(connector, initial_balance=initial_balance)
    
    logger.info("Running backtest...")
    results = engine.run_backtest(symbols, start_date, end_date)
    
    # ========================================
    # ANALYZE RESULTS
    # ========================================
    
    logger.info("Analyzing results...")
    analyzer = PerformanceAnalyzer()
    metrics = analyzer.analyze(results)
    
    # Print report
    analyzer.print_report(metrics)
    
    # ========================================
    # SAVE DETAILED RESULTS (Optional)
    # ========================================
    
    # Save trade log to CSV
    if results.get('closed_positions'):
        import pandas as pd
        
        trades_data = []
        for pos in results['closed_positions']:
            trades_data.append({
                'Ticket': pos.ticket,
                'Symbol': pos.symbol,
                'Type': pos.position_type.value,
                'Volume': pos.volume,
                'Open Time': pos.open_time,
                'Open Price': pos.open_price,
                'Close Time': pos.close_time,
                'Close Price': pos.close_price,
                'SL': pos.stop_loss,
                'TP': pos.take_profit,
                'Profit': pos.profit,
                'Close Reason': pos.close_reason,
                'Comment': pos.comment
            })
        
        df = pd.DataFrame(trades_data)
        filename = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        logger.info(f"Trade log saved to: {filename}")
    
    # Disconnect
    connector.disconnect()
    logger.info("Backtest completed!")


if __name__ == "__main__":
    main()

