"""
Analyze volume patterns from logs to determine optimal thresholds for each symbol.
"""
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import statistics

def parse_log_file(log_path: Path) -> Dict[str, List[float]]:
    """
    Parse a log file and extract volume ratios for breakouts.
    
    Returns:
        Dict with keys: 'breakout_ratios', 'rejected_true', 'rejected_false', 'both_rejected'
    """
    data = {
        'breakout_ratios': [],
        'rejected_true': [],
        'rejected_false': [],
        'both_rejected': [],
        'true_qualified': [],
        'false_qualified': []
    }
    
    current_ratio = None
    
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Extract volume ratio
            if 'Volume Ratio:' in line:
                match = re.search(r'Volume Ratio: ([\d.]+)x', line)
                if match:
                    current_ratio = float(match.group(1))
                    data['breakout_ratios'].append(current_ratio)
            
            # Track rejections
            if current_ratio is not None:
                if 'TRUE SELL REJECTED' in line or 'TRUE BUY REJECTED' in line:
                    data['rejected_true'].append(current_ratio)
                elif 'FALSE SELL REJECTED' in line or 'FALSE BUY REJECTED' in line:
                    data['rejected_false'].append(current_ratio)
                elif 'BOTH STRATEGIES REJECTED' in line:
                    data['both_rejected'].append(current_ratio)
                elif 'TRUE SELL QUALIFIED' in line or 'TRUE BUY QUALIFIED' in line:
                    data['true_qualified'].append(current_ratio)
                elif 'FALSE SELL QUALIFIED' in line or 'FALSE BUY QUALIFIED' in line:
                    data['false_qualified'].append(current_ratio)
    
    return data

def analyze_symbol(symbol: str, data: Dict[str, List[float]]) -> Dict:
    """Analyze volume patterns for a symbol and recommend thresholds."""
    if not data['breakout_ratios']:
        return None
    
    ratios = data['breakout_ratios']
    both_rejected = data['both_rejected']
    
    analysis = {
        'symbol': symbol,
        'total_breakouts': len(ratios),
        'both_rejected_count': len(both_rejected),
        'both_rejected_pct': (len(both_rejected) / len(ratios) * 100) if ratios else 0,
        'min_ratio': min(ratios),
        'max_ratio': max(ratios),
        'avg_ratio': statistics.mean(ratios),
        'median_ratio': statistics.median(ratios),
    }
    
    # Calculate percentiles
    if ratios:
        sorted_ratios = sorted(ratios)
        analysis['p25'] = sorted_ratios[len(sorted_ratios) // 4]
        analysis['p75'] = sorted_ratios[3 * len(sorted_ratios) // 4]
    
    # Analyze both_rejected ratios to find the gap
    if both_rejected:
        analysis['both_rejected_min'] = min(both_rejected)
        analysis['both_rejected_max'] = max(both_rejected)
        analysis['both_rejected_avg'] = statistics.mean(both_rejected)
    
    # Recommend thresholds
    if both_rejected:
        # Find the gap where both strategies reject
        gap_center = statistics.mean(both_rejected)
        
        # Recommend FALSE BREAKOUT max to be slightly above gap center
        analysis['recommended_false_max'] = round(gap_center * 1.2, 2)
        
        # Recommend TRUE BREAKOUT min to be slightly below gap center
        analysis['recommended_true_min'] = round(gap_center * 0.8, 2)
    else:
        # No rejections - use percentiles
        analysis['recommended_false_max'] = round(analysis['p25'], 2)
        analysis['recommended_true_min'] = round(analysis['p75'], 2)
    
    return analysis

def main():
    log_dir = Path('python_trader/logs/2025-11-05')
    
    results = []
    
    # Analyze each symbol
    for log_file in sorted(log_dir.glob('*.log')):
        if log_file.name == 'main.log':
            continue
        
        symbol = log_file.stem
        data = parse_log_file(log_file)
        
        analysis = analyze_symbol(symbol, data)
        if analysis:
            results.append(analysis)
    
    # Sort by both_rejected_pct descending
    results.sort(key=lambda x: x['both_rejected_pct'], reverse=True)
    
    # Print summary
    print("=" * 120)
    print(f"{'Symbol':<12} {'Breakouts':<10} {'Both Rej':<10} {'Rej %':<8} {'Avg Ratio':<10} {'Gap Range':<20} {'Rec FALSE Max':<15} {'Rec TRUE Min':<15}")
    print("=" * 120)
    
    for r in results:
        gap_range = f"{r.get('both_rejected_min', 0):.2f}-{r.get('both_rejected_max', 0):.2f}" if 'both_rejected_min' in r else "N/A"
        print(f"{r['symbol']:<12} {r['total_breakouts']:<10} {r['both_rejected_count']:<10} {r['both_rejected_pct']:<8.1f} {r['avg_ratio']:<10.2f} {gap_range:<20} {r['recommended_false_max']:<15.2f} {r['recommended_true_min']:<15.2f}")
    
    print("=" * 120)
    print(f"\nTotal symbols analyzed: {len(results)}")
    print(f"Symbols with both-rejected breakouts: {sum(1 for r in results if r['both_rejected_count'] > 0)}")
    
    # Generate configuration recommendations
    print("\n" + "=" * 120)
    print("CONFIGURATION RECOMMENDATIONS")
    print("=" * 120)
    
    # Group by category (you'll need to map symbols to categories)
    print("\nSymbols needing threshold adjustments (>10% both-rejected):")
    for r in results:
        if r['both_rejected_pct'] > 10:
            print(f"\n{r['symbol']}:")
            print(f"  Current issue: {r['both_rejected_pct']:.1f}% of breakouts rejected by both strategies")
            print(f"  Gap range: {r.get('both_rejected_min', 0):.2f}x - {r.get('both_rejected_max', 0):.2f}x")
            print(f"  Recommended FALSE BREAKOUT max: {r['recommended_false_max']:.2f}x")
            print(f"  Recommended TRUE BREAKOUT min: {r['recommended_true_min']:.2f}x")

if __name__ == '__main__':
    main()

