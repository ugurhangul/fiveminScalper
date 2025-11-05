"""
Backtesting engine for the trading bot.
Processes historical data and simulates trading.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from src.backtest.historical_data_loader import HistoricalDataLoader
from src.backtest.simulated_broker import SimulatedBroker
from src.strategy.candle_processor import CandleProcessor
from src.strategy.strategy_engine import StrategyEngine
from src.indicators.technical_indicators import TechnicalIndicators
from src.risk.risk_manager import RiskManager
from src.models.data_models import SymbolParameters, CandleData
from src.config.config import config
from src.config.symbol_optimizer import SymbolOptimizer
from src.utils.logger import get_logger


class BacktestEngine:
    """Main backtesting engine"""
    
    def __init__(self, connector, initial_balance: float = 10000.0):
        """
        Initialize backtest engine.
        
        Args:
            connector: MT5Connector instance (must be connected)
            initial_balance: Starting account balance
        """
        self.connector = connector
        self.logger = get_logger()
        
        # Components
        self.data_loader = HistoricalDataLoader(connector)
        self.broker = SimulatedBroker(initial_balance=initial_balance)
        self.indicators = TechnicalIndicators()
        
        # Symbol strategies
        self.candle_processors: Dict[str, CandleProcessor] = {}
        self.strategy_engines: Dict[str, StrategyEngine] = {}
        self.symbol_params: Dict[str, SymbolParameters] = {}
        
        # Risk manager (will be initialized per symbol)
        self.risk_managers: Dict[str, RiskManager] = {}
    
    def run_backtest(self, symbols: List[str], start_date: datetime, 
                    end_date: datetime) -> Dict:
        """
        Run backtest for multiple symbols.
        
        Args:
            symbols: List of symbols to test
            start_date: Start date for backtest
            end_date: End date for backtest
            
        Returns:
            Dictionary with backtest results
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING BACKTEST")
        self.logger.info("=" * 80)
        self.logger.info(f"Symbols: {', '.join(symbols)}")
        self.logger.info(f"Period: {start_date} to {end_date}")
        self.logger.info(f"Initial Balance: ${self.broker.initial_balance:,.2f}")
        self.logger.info("=" * 80)
        
        # Load historical data for all symbols
        self.logger.info("Loading historical data...")
        data_5m = self.data_loader.load_multiple_symbols(symbols, 'M5', start_date, end_date)
        data_4h = self.data_loader.load_multiple_symbols(symbols, 'H4', start_date, end_date)
        
        if not data_5m or not data_4h:
            self.logger.error("Failed to load historical data")
            return {}
        
        # Initialize strategies for each symbol
        self._initialize_strategies(symbols)
        
        # Get all unique timestamps from 5M data
        all_timestamps = set()
        for df in data_5m.values():
            all_timestamps.update(df['time'].tolist())
        
        timestamps = sorted(all_timestamps)
        self.logger.info(f"Processing {len(timestamps)} time periods...")
        
        # Process each timestamp
        for i, current_time in enumerate(timestamps):
            # Progress update every 1000 candles
            if i % 1000 == 0:
                progress = (i / len(timestamps)) * 100
                self.logger.info(f"Progress: {progress:.1f}% ({i}/{len(timestamps)})")
            
            # Process each symbol at this timestamp
            for symbol in symbols:
                self._process_symbol_at_time(
                    symbol, current_time, data_5m[symbol], data_4h[symbol]
                )
        
        # Close all remaining positions at end of backtest
        self._close_all_positions(end_date)
        
        self.logger.info("=" * 80)
        self.logger.info("BACKTEST COMPLETED")
        self.logger.info("=" * 80)
        
        # Return results
        return self._get_results()
    
    def _initialize_strategies(self, symbols: List[str]):
        """Initialize strategy components for each symbol"""
        for symbol in symbols:
            # Get symbol info
            symbol_info = self.connector.get_symbol_info(symbol)
            if not symbol_info:
                self.logger.warning(f"Could not get symbol info for {symbol}")
                continue
            
            # Set symbol info in broker
            self.broker.set_symbol_info(symbol, symbol_info)
            
            # Get symbol parameters
            symbol_params = SymbolOptimizer.get_symbol_parameters(symbol)
            self.symbol_params[symbol] = symbol_params
            
            # Create candle processor
            self.candle_processors[symbol] = CandleProcessor(
                symbol=symbol,
                connector=self.connector,
                use_only_00_utc=config.advanced.use_only_00_utc_candle
            )
            
            # Create strategy engine
            self.strategy_engines[symbol] = StrategyEngine(
                symbol=symbol,
                candle_processor=self.candle_processors[symbol],
                indicators=self.indicators,
                connector=self.connector,
                symbol_params=symbol_params,
                strategy_config=config.strategy
            )
            
            # Create risk manager
            self.risk_managers[symbol] = RiskManager(
                connector=self.connector,
                risk_config=config.risk
            )
    
    def _process_symbol_at_time(self, symbol: str, current_time: datetime,
                               df_5m: pd.DataFrame, df_4h: pd.DataFrame):
        """Process a symbol at a specific time"""
        # Get candles up to current time
        candles_5m = self.data_loader.get_candles_up_to_time(df_5m, current_time, count=100)
        candles_4h = self.data_loader.get_candles_up_to_time(df_4h, current_time, count=10)
        
        if candles_5m is None or len(candles_5m) < 2:
            return
        if candles_4h is None or len(candles_4h) < 2:
            return
        
        # Get current candle
        current_candle = candles_5m.iloc[-1]
        
        # Update positions with current prices
        bid_price = current_candle['close']
        ask_price = current_candle['close'] + (self.broker.spread_points * 
                                               self.broker.symbol_info_cache[symbol]['point'])
        self.broker.update_positions(symbol, current_time, bid_price, ask_price)
        
        # Check for new 5M candle (compare with previous timestamp)
        if len(candles_5m) >= 2:
            prev_candle = candles_5m.iloc[-2]
            if current_candle['time'] != prev_candle['time']:
                # New candle - check for signals
                self._check_for_signal(symbol, current_time, candles_5m, candles_4h)
    
    def _check_for_signal(self, symbol: str, current_time: datetime,
                         candles_5m: pd.DataFrame, candles_4h: pd.DataFrame):
        """Check for trade signals"""
        if symbol not in self.strategy_engines:
            return
        
        strategy = self.strategy_engines[symbol]
        candle_processor = self.candle_processors[symbol]
        
        # Update candle processor with latest data
        # (In backtest mode, we manually feed the data)
        latest_5m = candles_5m.iloc[-1]
        latest_4h = candles_4h.iloc[-1]
        
        # Check if new 4H candle
        if len(candles_4h) >= 2:
            prev_4h = candles_4h.iloc[-2]
            if latest_4h['time'] != prev_4h['time']:
                # New 4H candle - update processor
                candle_processor._update_4h_candle(latest_4h)
        
        # Check for signal
        signal = strategy.check_for_signal()
        
        if signal:
            self._execute_signal(symbol, signal, current_time, latest_5m['close'])
    
    def _execute_signal(self, symbol: str, signal, current_time: datetime, current_price: float):
        """Execute a trade signal"""
        # Calculate lot size
        risk_manager = self.risk_managers.get(symbol)
        if not risk_manager:
            return
        
        lot_size = risk_manager.calculate_lot_size(
            symbol=symbol,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            balance=self.broker.get_balance()
        )
        
        if lot_size <= 0:
            return
        
        # Validate risk
        is_valid, message, adjusted_lot = risk_manager.validate_risk(
            symbol=symbol,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            lot_size=lot_size
        )
        
        if not is_valid:
            self.logger.warning(f"Risk validation failed for {symbol}: {message}")
            return
        
        if adjusted_lot > 0:
            lot_size = adjusted_lot
        
        # Execute order
        ticket = self.broker.execute_order(signal, lot_size, current_time, current_price)
        
        if ticket:
            self.logger.info(f"Signal executed: {signal.signal_type.value.upper()} {symbol}")
    
    def _close_all_positions(self, close_time: datetime):
        """Close all remaining positions"""
        for position in list(self.broker.positions.values()):
            self.broker._close_position(position, close_time, "Backtest End")
    
    def _get_results(self) -> Dict:
        """Get backtest results"""
        closed_positions = self.broker.get_closed_positions()
        
        return {
            'initial_balance': self.broker.initial_balance,
            'final_balance': self.broker.get_balance(),
            'total_trades': len(closed_positions),
            'closed_positions': closed_positions,
            'broker': self.broker
        }

