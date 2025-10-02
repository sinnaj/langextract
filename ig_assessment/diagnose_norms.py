#!/usr/bin/env python3
"""Diagnostic tool to analyze norm data quality issues.

This script checks for:
1. Duplicate norm IDs
2. Distribution of applies_if expressions
3. Expected vs actual dismissal rates
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Any


def analyze_norms(norms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze norm data quality.
    
    Args:
        norms: List of norm dictionaries
        
    Returns:
        Dictionary with analysis results
    """
    # Extract IDs
    ids = [n.get('attributes', {}).get('id') for n in norms]
    id_counts = Counter(ids)
    duplicates = {id_: count for id_, count in id_counts.items() if count > 1}
    
    # Analyze applies_if
    applies_if_true = [n for n in norms 
                       if n.get('attributes', {}).get('applies_if') == 'TRUE']
    applies_if_complex = [n for n in norms 
                          if n.get('attributes', {}).get('applies_if') not in ['TRUE', '', None]]
    
    # Group norms by ID to show duplicates
    norms_by_id = defaultdict(list)
    for norm in norms:
        norm_id = norm.get('attributes', {}).get('id')
        norms_by_id[norm_id].append(norm)
    
    return {
        'total_norms': len(norms),
        'unique_ids': len(set(ids)),
        'duplicate_ids': duplicates,
        'norms_by_id': dict(norms_by_id),
        'always_applicable': len(applies_if_true),
        'conditionally_applicable': len(applies_if_complex),
        'max_dismissible_rate': len(applies_if_complex) / len(norms) if norms else 0.0,
    }


def print_report(analysis: Dict[str, Any]) -> None:
    """Print formatted analysis report."""
    print("=" * 80)
    print("NORM DATA QUALITY DIAGNOSTIC REPORT")
    print("=" * 80)
    
    print(f"\n📊 OVERALL STATISTICS")
    print(f"   Total norms: {analysis['total_norms']}")
    print(f"   Unique IDs: {analysis['unique_ids']}")
    
    # Duplicate IDs
    duplicates = analysis['duplicate_ids']
    if duplicates:
        print(f"\n⚠️  DUPLICATE IDs FOUND: {len(duplicates)} IDs")
        print(f"   Total duplicate occurrences: {sum(duplicates.values())}")
        print(f"   Average duplicates per ID: {sum(duplicates.values()) / len(duplicates):.1f}")
        print(f"\n   Top duplicate IDs:")
        for id_, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"      {id_}: {count} occurrences")
            
        # Show examples of one duplicate
        print(f"\n   Example: Different norms with same ID '{list(duplicates.keys())[0]}':")
        example_id = list(duplicates.keys())[0]
        for i, norm in enumerate(analysis['norms_by_id'][example_id][:3]):
            attrs = norm.get('attributes', {})
            stmt = attrs.get('norm_statement', 'N/A')
            print(f"      {i+1}. {stmt[:70]}...")
    else:
        print(f"\n✓ No duplicate IDs found")
    
    # Applies_if analysis
    print(f"\n📋 APPLIES_IF DISTRIBUTION")
    print(f"   Always applicable (applies_if='TRUE'): {analysis['always_applicable']} "
          f"({analysis['always_applicable']/analysis['total_norms']*100:.1f}%)")
    print(f"   Conditionally applicable: {analysis['conditionally_applicable']} "
          f"({analysis['conditionally_applicable']/analysis['total_norms']*100:.1f}%)")
    
    # Dismissal expectations
    print(f"\n🎯 DISMISSAL RATE EXPECTATIONS")
    print(f"   Maximum possible dismissal rate: {analysis['max_dismissible_rate']:.2%}")
    print(f"   Reason: {analysis['always_applicable']} norms always apply (can't be dismissed)")
    print(f"   Only {analysis['conditionally_applicable']} norms can be dismissed by features")
    
    print("\n💡 RECOMMENDATIONS")
    if duplicates:
        print("   1. Fix duplicate norm IDs in the extraction pipeline")
        print("      - Each norm should have a unique ID")
        print("      - Consider using norm_statement hash or UUID for IDs")
    if analysis['always_applicable'] > analysis['total_norms'] * 0.3:
        print("   2. High percentage of unconditional norms (applies_if='TRUE')")
        print("      - These norms limit the effectiveness of feature-based filtering")
        print("      - Consider adding more specific applies_if conditions")
    
    print("=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python diagnose_norms.py <path_to_extraction_results.json>")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    # Load data
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract norms
    extractions = data.get('extractions', [])
    norms = [e for e in extractions if e.get('extraction_class') == 'NORM']
    
    if not norms:
        print("No NORM extractions found!")
        sys.exit(1)
    
    # Analyze and report
    analysis = analyze_norms(norms)
    print_report(analysis)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Diagnostic tool to analyze norm data quality issues.

This script checks for:
1. Duplicate norm IDs
2. Distribution of applies_if expressions
3. Expected vs actual dismissal rates
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Any


def analyze_norms(norms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze norm data quality.
    
    Args:
        norms: List of norm dictionaries
        
    Returns:
        Dictionary with analysis results
    """
    # Extract IDs
    ids = [n.get('attributes', {}).get('id') for n in norms]
    id_counts = Counter(ids)
    duplicates = {id_: count for id_, count in id_counts.items() if count > 1}
    
    # Analyze applies_if
    applies_if_true = [n for n in norms 
                       if n.get('attributes', {}).get('applies_if') == 'TRUE']
    applies_if_complex = [n for n in norms 
                          if n.get('attributes', {}).get('applies_if') not in ['TRUE', '', None]]
    
    # Group norms by ID to show duplicates
    norms_by_id = defaultdict(list)
    for norm in norms:
        norm_id = norm.get('attributes', {}).get('id')
        norms_by_id[norm_id].append(norm)
    
    return {
        'total_norms': len(norms),
        'unique_ids': len(set(ids)),
        'duplicate_ids': duplicates,
        'norms_by_id': dict(norms_by_id),
        'always_applicable': len(applies_if_true),
        'conditionally_applicable': len(applies_if_complex),
        'max_dismissible_rate': len(applies_if_complex) / len(norms) if norms else 0.0,
    }


def print_report(analysis: Dict[str, Any]) -> None:
    """Print formatted analysis report."""
    print("=" * 80)
    print("NORM DATA QUALITY DIAGNOSTIC REPORT")
    print("=" * 80)
    
    print(f"\n📊 OVERALL STATISTICS")
    print(f"   Total norms: {analysis['total_norms']}")
    print(f"   Unique IDs: {analysis['unique_ids']}")
    
    # Duplicate IDs
    duplicates = analysis['duplicate_ids']
    if duplicates:
        print(f"\n⚠️  DUPLICATE IDs FOUND: {len(duplicates)} IDs")
        print(f"   Total duplicate occurrences: {sum(duplicates.values())}")
        print(f"   Average duplicates per ID: {sum(duplicates.values()) / len(duplicates):.1f}")
        print(f"\n   Top duplicate IDs:")
        for id_, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"      {id_}: {count} occurrences")
            
        # Show examples of one duplicate
        print(f"\n   Example: Different norms with same ID '{list(duplicates.keys())[0]}':")
        example_id = list(duplicates.keys())[0]
        for i, norm in enumerate(analysis['norms_by_id'][example_id][:3]):
            attrs = norm.get('attributes', {})
            stmt = attrs.get('norm_statement', 'N/A')
            print(f"      {i+1}. {stmt[:70]}...")
    else:
        print(f"\n✓ No duplicate IDs found")
    
    # Applies_if analysis
    print(f"\n📋 APPLIES_IF DISTRIBUTION")
    print(f"   Always applicable (applies_if='TRUE'): {analysis['always_applicable']} "
          f"({analysis['always_applicable']/analysis['total_norms']*100:.1f}%)")
    print(f"   Conditionally applicable: {analysis['conditionally_applicable']} "
          f"({analysis['conditionally_applicable']/analysis['total_norms']*100:.1f}%)")
    
    # Dismissal expectations
    print(f"\n🎯 DISMISSAL RATE EXPECTATIONS")
    print(f"   Maximum possible dismissal rate: {analysis['max_dismissible_rate']:.2%}")
    print(f"   Reason: {analysis['always_applicable']} norms always apply (can't be dismissed)")
    print(f"   Only {analysis['conditionally_applicable']} norms can be dismissed by features")
    
    print("\n💡 RECOMMENDATIONS")
    if duplicates:
        print("   1. Fix duplicate norm IDs in the extraction pipeline")
        print("      - Each norm should have a unique ID")
        print("      - Consider using norm_statement hash or UUID for IDs")
    if analysis['always_applicable'] > analysis['total_norms'] * 0.3:
        print("   2. High percentage of unconditional norms (applies_if='TRUE')")
        print("      - These norms limit the effectiveness of feature-based filtering")
        print("      - Consider adding more specific applies_if conditions")
    
    print("=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python diagnose_norms.py <path_to_extraction_results.json>")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    # Load data
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract norms
    extractions = data.get('extractions', [])
    norms = [e for e in extractions if e.get('extraction_class') == 'NORM']
    
    if not norms:
        print("No NORM extractions found!")
        sys.exit(1)
    
    # Analyze and report
    analysis = analyze_norms(norms)
    print_report(analysis)


if __name__ == '__main__':
    main()
