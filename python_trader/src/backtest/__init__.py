"""
Backtesting module for the trading bot.
"""
from src.backtest.historical_data_loader import HistoricalDataLoader
from src.backtest.simulated_broker import SimulatedBroker, SimulatedPosition
from src.backtest.backtest_engine import BacktestEngine
from src.backtest.performance_analyzer import PerformanceAnalyzer

__all__ = [
    'HistoricalDataLoader',
    'SimulatedBroker',
    'SimulatedPosition',
    'BacktestEngine',
    'PerformanceAnalyzer'
]

