"""
Performance analysis for backtesting results.
Calculates metrics and generates reports.
"""
import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime
from src.backtest.simulated_broker import SimulatedPosition
from src.models.data_models import PositionType
from src.utils.logger import get_logger


class PerformanceAnalyzer:
    """Analyzes backtest performance and generates reports"""
    
    def __init__(self):
        """Initialize performance analyzer"""
        self.logger = get_logger()
    
    def analyze(self, results: Dict) -> Dict:
        """
        Analyze backtest results.
        
        Args:
            results: Results dictionary from BacktestEngine
            
        Returns:
            Dictionary with performance metrics
        """
        closed_positions = results.get('closed_positions', [])
        initial_balance = results.get('initial_balance', 0)
        final_balance = results.get('final_balance', 0)
        
        if not closed_positions:
            return {
                'error': 'No trades executed',
                'total_trades': 0
            }
        
        # Calculate metrics
        metrics = {
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'net_profit': final_balance - initial_balance,
            'return_pct': ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0,
            'total_trades': len(closed_positions),
        }
        
        # Win/Loss analysis
        wins = [p for p in closed_positions if p.profit > 0]
        losses = [p for p in closed_positions if p.profit <= 0]
        
        metrics['winning_trades'] = len(wins)
        metrics['losing_trades'] = len(losses)
        metrics['win_rate'] = (len(wins) / len(closed_positions) * 100) if closed_positions else 0
        
        # Profit analysis
        if wins:
            metrics['avg_win'] = sum(p.profit for p in wins) / len(wins)
            metrics['largest_win'] = max(p.profit for p in wins)
        else:
            metrics['avg_win'] = 0
            metrics['largest_win'] = 0
        
        if losses:
            metrics['avg_loss'] = sum(p.profit for p in losses) / len(losses)
            metrics['largest_loss'] = min(p.profit for p in losses)
        else:
            metrics['avg_loss'] = 0
            metrics['largest_loss'] = 0
        
        # Profit factor
        gross_profit = sum(p.profit for p in wins) if wins else 0
        gross_loss = abs(sum(p.profit for p in losses)) if losses else 0
        metrics['gross_profit'] = gross_profit
        metrics['gross_loss'] = gross_loss
        metrics['profit_factor'] = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        # Expectancy
        metrics['expectancy'] = (metrics['avg_win'] * metrics['win_rate'] / 100 + 
                                metrics['avg_loss'] * (100 - metrics['win_rate']) / 100)
        
        # Consecutive wins/losses
        metrics['max_consecutive_wins'] = self._max_consecutive(closed_positions, True)
        metrics['max_consecutive_losses'] = self._max_consecutive(closed_positions, False)
        
        # Drawdown analysis
        equity_curve = self._calculate_equity_curve(closed_positions, initial_balance)
        metrics['max_drawdown'] = self._calculate_max_drawdown(equity_curve)
        metrics['max_drawdown_pct'] = (metrics['max_drawdown'] / initial_balance * 100) if initial_balance > 0 else 0
        
        # Strategy breakdown
        metrics['strategy_breakdown'] = self._analyze_by_strategy(closed_positions)
        
        # Symbol breakdown
        metrics['symbol_breakdown'] = self._analyze_by_symbol(closed_positions)
        
        # Time analysis
        if closed_positions:
            first_trade = min(p.open_time for p in closed_positions)
            last_trade = max(p.close_time for p in closed_positions if p.close_time)
            metrics['first_trade'] = first_trade
            metrics['last_trade'] = last_trade
            metrics['trading_days'] = (last_trade - first_trade).days if last_trade else 0
        
        return metrics
    
    def _max_consecutive(self, positions: List[SimulatedPosition], wins: bool) -> int:
        """Calculate max consecutive wins or losses"""
        max_consecutive = 0
        current_consecutive = 0
        
        for position in positions:
            is_win = position.profit > 0
            if is_win == wins:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_equity_curve(self, positions: List[SimulatedPosition], 
                               initial_balance: float) -> List[float]:
        """Calculate equity curve"""
        equity = [initial_balance]
        current_equity = initial_balance
        
        for position in sorted(positions, key=lambda p: p.close_time or datetime.now()):
            current_equity += position.profit
            equity.append(current_equity)
        
        return equity
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not equity_curve:
            return 0
        
        max_drawdown = 0
        peak = equity_curve[0]
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    def _analyze_by_strategy(self, positions: List[SimulatedPosition]) -> Dict:
        """Analyze performance by strategy type"""
        false_breakout = [p for p in positions if 'FALSE' in p.comment.upper()]
        true_breakout = [p for p in positions if 'TRUE' in p.comment.upper()]
        
        breakdown = {}
        
        if false_breakout:
            breakdown['false_breakout'] = {
                'trades': len(false_breakout),
                'wins': len([p for p in false_breakout if p.profit > 0]),
                'losses': len([p for p in false_breakout if p.profit <= 0]),
                'win_rate': len([p for p in false_breakout if p.profit > 0]) / len(false_breakout) * 100,
                'net_profit': sum(p.profit for p in false_breakout)
            }
        
        if true_breakout:
            breakdown['true_breakout'] = {
                'trades': len(true_breakout),
                'wins': len([p for p in true_breakout if p.profit > 0]),
                'losses': len([p for p in true_breakout if p.profit <= 0]),
                'win_rate': len([p for p in true_breakout if p.profit > 0]) / len(true_breakout) * 100,
                'net_profit': sum(p.profit for p in true_breakout)
            }
        
        return breakdown
    
    def _analyze_by_symbol(self, positions: List[SimulatedPosition]) -> Dict:
        """Analyze performance by symbol"""
        symbols = set(p.symbol for p in positions)
        breakdown = {}
        
        for symbol in symbols:
            symbol_positions = [p for p in positions if p.symbol == symbol]
            wins = [p for p in symbol_positions if p.profit > 0]
            
            breakdown[symbol] = {
                'trades': len(symbol_positions),
                'wins': len(wins),
                'losses': len(symbol_positions) - len(wins),
                'win_rate': len(wins) / len(symbol_positions) * 100 if symbol_positions else 0,
                'net_profit': sum(p.profit for p in symbol_positions)
            }
        
        return breakdown
    
    def print_report(self, metrics: Dict):
        """Print formatted performance report"""
        print("\n" + "=" * 80)
        print("BACKTEST PERFORMANCE REPORT")
        print("=" * 80)
        
        if 'error' in metrics:
            print(f"\nError: {metrics['error']}")
            return
        
        # Account Summary
        print("\n📊 ACCOUNT SUMMARY")
        print("-" * 80)
        print(f"Initial Balance:     ${metrics['initial_balance']:,.2f}")
        print(f"Final Balance:       ${metrics['final_balance']:,.2f}")
        print(f"Net Profit:          ${metrics['net_profit']:,.2f}")
        print(f"Return:              {metrics['return_pct']:.2f}%")
        print(f"Max Drawdown:        ${metrics['max_drawdown']:,.2f} ({metrics['max_drawdown_pct']:.2f}%)")
        
        # Trade Statistics
        print("\n📈 TRADE STATISTICS")
        print("-" * 80)
        print(f"Total Trades:        {metrics['total_trades']}")
        print(f"Winning Trades:      {metrics['winning_trades']}")
        print(f"Losing Trades:       {metrics['losing_trades']}")
        print(f"Win Rate:            {metrics['win_rate']:.2f}%")
        print(f"Profit Factor:       {metrics['profit_factor']:.2f}")
        print(f"Expectancy:          ${metrics['expectancy']:.2f}")
        
        # Win/Loss Analysis
        print("\n💰 WIN/LOSS ANALYSIS")
        print("-" * 80)
        print(f"Average Win:         ${metrics['avg_win']:.2f}")
        print(f"Average Loss:        ${metrics['avg_loss']:.2f}")
        print(f"Largest Win:         ${metrics['largest_win']:.2f}")
        print(f"Largest Loss:        ${metrics['largest_loss']:.2f}")
        print(f"Max Consecutive Wins:   {metrics['max_consecutive_wins']}")
        print(f"Max Consecutive Losses: {metrics['max_consecutive_losses']}")
        
        # Strategy Breakdown
        if 'strategy_breakdown' in metrics and metrics['strategy_breakdown']:
            print("\n🎯 STRATEGY BREAKDOWN")
            print("-" * 80)
            for strategy, stats in metrics['strategy_breakdown'].items():
                print(f"\n{strategy.upper().replace('_', ' ')}:")
                print(f"  Trades: {stats['trades']}")
                print(f"  Win Rate: {stats['win_rate']:.2f}%")
                print(f"  Net Profit: ${stats['net_profit']:.2f}")
        
        # Symbol Breakdown
        if 'symbol_breakdown' in metrics and metrics['symbol_breakdown']:
            print("\n📊 SYMBOL BREAKDOWN")
            print("-" * 80)
            for symbol, stats in sorted(metrics['symbol_breakdown'].items(), 
                                       key=lambda x: x[1]['net_profit'], reverse=True):
                print(f"\n{symbol}:")
                print(f"  Trades: {stats['trades']}")
                print(f"  Win Rate: {stats['win_rate']:.2f}%")
                print(f"  Net Profit: ${stats['net_profit']:.2f}")
        
        # Time Analysis
        if 'first_trade' in metrics:
            print("\n📅 TIME ANALYSIS")
            print("-" * 80)
            print(f"First Trade:         {metrics['first_trade']}")
            print(f"Last Trade:          {metrics['last_trade']}")
            print(f"Trading Days:        {metrics['trading_days']}")
        
        print("\n" + "=" * 80)

