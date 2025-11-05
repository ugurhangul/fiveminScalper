"""
Symbol performance persistence mechanism.

This module provides:
1. JSON-based symbol stats storage with atomic writes
2. Thread-safe file access
3. Automatic backup of corrupted files
4. Per-symbol performance tracking across restarts
"""
import json
import os
import threading
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

from src.models.data_models import SymbolStats
from src.utils.logger import get_logger


class SymbolPerformancePersistence:
    """Manages symbol performance persistence across restarts"""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize symbol performance persistence.
        
        Args:
            data_dir: Directory to store symbol_stats.json file
        """
        self.logger = get_logger()
        
        # Create data directory if it doesn't exist
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Stats file path
        self.stats_file = self.data_dir / "symbol_stats.json"
        
        # Thread lock for file access
        self.lock = threading.Lock()
        
        # In-memory cache of symbol stats
        self.stats_cache: Dict[str, Dict] = {}
        
        # Load existing stats on initialization
        self._load_stats()
    
    def _load_stats(self):
        """Load symbol stats from JSON file"""
        with self.lock:
            try:
                if self.stats_file.exists():
                    with open(self.stats_file, 'r') as f:
                        self.stats_cache = json.load(f)
                    
                    self.logger.info(f"Loaded stats for {len(self.stats_cache)} symbols from persistence file")
                else:
                    self.stats_cache = {}
                    self.logger.info("No existing symbol stats file found, starting fresh")
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Corrupted symbol stats file: {e}")
                self.logger.warning("Starting with empty stats cache")
                self.stats_cache = {}
                # Backup corrupted file
                if self.stats_file.exists():
                    backup_path = self.stats_file.with_suffix('.json.corrupted')
                    self.stats_file.rename(backup_path)
                    self.logger.info(f"Corrupted file backed up to: {backup_path}")
                    
            except Exception as e:
                self.logger.error(f"Error loading symbol stats: {e}")
                self.stats_cache = {}
    
    def _save_stats(self):
        """
        Save symbol stats to JSON file with atomic write.
        
        NOTE: This method does NOT acquire the lock - it must be called
        from a method that already holds the lock.
        """
        try:
            # Write to temporary file first (atomic write)
            temp_file = self.stats_file.with_suffix('.json.tmp')
            
            with open(temp_file, 'w') as f:
                json.dump(self.stats_cache, f, indent=2, default=str)
            
            # Atomic rename (replaces old file)
            temp_file.replace(self.stats_file)
            
            self.logger.debug(f"Saved stats for {len(self.stats_cache)} symbols to persistence file")
            
        except Exception as e:
            self.logger.error(f"Error saving symbol stats: {e}")
    
    def save_symbol_stats(self, symbol: str, stats: SymbolStats):
        """
        Save stats for a symbol.
        
        Args:
            symbol: Symbol name
            stats: SymbolStats object
        """
        with self.lock:
            stats_data = {
                'total_trades': stats.total_trades,
                'winning_trades': stats.winning_trades,
                'losing_trades': stats.losing_trades,
                'total_profit': stats.total_profit,
                'total_loss': stats.total_loss,
                'consecutive_losses': stats.consecutive_losses,
                'consecutive_wins': stats.consecutive_wins,
                'is_enabled': stats.is_enabled,
                'disabled_time': stats.disabled_time.isoformat() if stats.disabled_time else None,
                'disable_reason': stats.disable_reason,
                'peak_equity': stats.peak_equity,
                'current_drawdown': stats.current_drawdown,
                'max_drawdown': stats.max_drawdown,
                'week_start_time': stats.week_start_time.isoformat() if stats.week_start_time else None
            }
            
            self.stats_cache[symbol] = stats_data
            self._save_stats()
            
            self.logger.debug(f"Saved stats for {symbol}")
    
    def load_symbol_stats(self, symbol: str) -> Optional[SymbolStats]:
        """
        Load stats for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            SymbolStats object or None if not found
        """
        with self.lock:
            if symbol not in self.stats_cache:
                return None
            
            data = self.stats_cache[symbol]
            
            # Parse datetime fields
            disabled_time = None
            if data.get('disabled_time'):
                try:
                    disabled_time = datetime.fromisoformat(data['disabled_time'])
                except (ValueError, TypeError):
                    pass
            
            week_start_time = None
            if data.get('week_start_time'):
                try:
                    week_start_time = datetime.fromisoformat(data['week_start_time'])
                except (ValueError, TypeError):
                    pass
            
            stats = SymbolStats(
                total_trades=data.get('total_trades', 0),
                winning_trades=data.get('winning_trades', 0),
                losing_trades=data.get('losing_trades', 0),
                total_profit=data.get('total_profit', 0.0),
                total_loss=data.get('total_loss', 0.0),
                consecutive_losses=data.get('consecutive_losses', 0),
                consecutive_wins=data.get('consecutive_wins', 0),
                is_enabled=data.get('is_enabled', True),
                disabled_time=disabled_time,
                disable_reason=data.get('disable_reason', ''),
                peak_equity=data.get('peak_equity', 0.0),
                current_drawdown=data.get('current_drawdown', 0.0),
                max_drawdown=data.get('max_drawdown', 0.0),
                week_start_time=week_start_time
            )
            
            self.logger.debug(f"Loaded stats for {symbol}")
            return stats
    
    def delete_symbol_stats(self, symbol: str):
        """
        Delete stats for a symbol.
        
        Args:
            symbol: Symbol name
        """
        with self.lock:
            if symbol in self.stats_cache:
                del self.stats_cache[symbol]
                self._save_stats()
                self.logger.info(f"Deleted stats for {symbol}")
    
    def get_all_symbols(self) -> list[str]:
        """
        Get list of all symbols with saved stats.
        
        Returns:
            List of symbol names
        """
        with self.lock:
            return list(self.stats_cache.keys())
    
    def clear_all_stats(self):
        """Clear all symbol stats"""
        with self.lock:
            self.stats_cache = {}
            self._save_stats()
            self.logger.info("Cleared all symbol stats")

