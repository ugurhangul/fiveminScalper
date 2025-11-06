#!/usr/bin/env python3
"""
Bot Monitoring Script
Shows real-time status of the trading bot including:
- Active symbols being monitored
- Recent log entries
- Any errors or warnings
- Trading activity
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path


def get_latest_log_file():
    """Get the most recent log file"""
    log_dir = Path(__file__).parent / "logs"
    if not log_dir.exists():
        return None
    
    log_files = list(log_dir.glob("trading_*.log"))
    if not log_files:
        return None
    
    return max(log_files, key=lambda f: f.stat().st_mtime)


def tail_log(log_file, lines=50):
    """Read last N lines from log file"""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            return f.readlines()[-lines:]
    except Exception as e:
        return [f"Error reading log: {e}"]


def count_log_entries(log_file, keyword):
    """Count occurrences of a keyword in log file"""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            return sum(1 for line in f if keyword in line)
    except Exception:
        return 0


def analyze_log(log_file):
    """Analyze log file for key metrics"""
    if not log_file or not log_file.exists():
        return None
    
    # Count different types of entries
    total_lines = 0
    errors = 0
    warnings = 0
    initialized_symbols = 0
    worker_threads = 0
    signal_checks = 0
    trades_opened = 0
    trades_closed = 0
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                total_lines += 1
                if 'ERROR' in line:
                    errors += 1
                if 'WARNING' in line:
                    warnings += 1
                if '✓' in line and 'initialized' in line:
                    initialized_symbols += 1
                if 'Worker thread started' in line:
                    worker_threads += 1
                if 'Checking for signals' in line:
                    signal_checks += 1
                if 'Opening' in line and ('BUY' in line or 'SELL' in line):
                    trades_opened += 1
                if 'Closed position' in line:
                    trades_closed += 1
    except Exception as e:
        return {'error': str(e)}
    
    return {
        'total_lines': total_lines,
        'errors': errors,
        'warnings': warnings,
        'initialized_symbols': initialized_symbols,
        'worker_threads': worker_threads,
        'signal_checks': signal_checks,
        'trades_opened': trades_opened,
        'trades_closed': trades_closed
    }


def display_status():
    """Display bot status"""
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("=" * 80)
    print("FiveMinScalper - Bot Monitor")
    print("=" * 80)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print()
    
    # Get latest log file
    log_file = get_latest_log_file()
    
    if not log_file:
        print("❌ No log files found!")
        print("The bot may not be running.")
        return
    
    print(f"📄 Log File: {log_file.name}")
    print(f"📅 Last Modified: {datetime.fromtimestamp(log_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Analyze log
    stats = analyze_log(log_file)
    
    if stats and 'error' not in stats:
        print("=" * 80)
        print("📊 BOT STATUS")
        print("=" * 80)
        
        # Check if bot is running
        file_age = time.time() - log_file.stat().st_mtime
        if file_age < 60:
            print("✅ Status: RUNNING (log updated within last minute)")
        elif file_age < 300:
            print("⚠️  Status: POSSIBLY RUNNING (log updated within last 5 minutes)")
        else:
            print("❌ Status: NOT RUNNING (log not updated recently)")
        
        print()
        print(f"✓ Initialized Symbols: {stats['initialized_symbols']}")
        print(f"🧵 Worker Threads: {stats['worker_threads']}")
        print(f"🔍 Signal Checks: {stats['signal_checks']}")
        print(f"📈 Trades Opened: {stats['trades_opened']}")
        print(f"📉 Trades Closed: {stats['trades_closed']}")
        print()
        print(f"⚠️  Warnings: {stats['warnings']}")
        print(f"❌ Errors: {stats['errors']}")
        print()
    
    # Show recent log entries
    print("=" * 80)
    print("📋 RECENT LOG ENTRIES (Last 20 lines)")
    print("=" * 80)
    
    recent_lines = tail_log(log_file, 20)
    for line in recent_lines:
        line = line.strip()
        if 'ERROR' in line:
            print(f"❌ {line}")
        elif 'WARNING' in line:
            print(f"⚠️  {line}")
        elif 'BUY' in line or 'SELL' in line:
            print(f"📊 {line}")
        else:
            print(f"   {line}")
    
    print()
    print("=" * 80)
    print("Press Ctrl+C to exit")
    print("=" * 80)


def main():
    """Main monitoring loop"""
    try:
        while True:
            display_status()
            time.sleep(5)  # Update every 5 seconds
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


if __name__ == "__main__":
    main()

