#!/usr/bin/env python3
"""Generate Isolation Report for Extracted Norms.

This standalone script analyzes extracted norms and identifies isolated norms that
cannot be meaningfully clustered with others. It accepts enhanced_extraction_results.json
as input and generates a comprehensive isolation report.

Usage:
    python generate_isolation_report.py --input enhanced_extraction_results.json --output isolation_report.txt
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def extract_features_from_applies_if(applies_if: str) -> Set[str]:
    """Extract feature names from applies_if expression.
    
    Args:
        applies_if: DSL expression (e.g., "AREA.USAGE == 'PARKING' AND AREA.SIZE > 100")
    
    Returns:
        Set of feature names (e.g., {'AREA.USAGE', 'AREA.SIZE'})
    """
    if not applies_if or applies_if.strip().upper() == 'TRUE':
        return set()
    
    features = set()
    # Simple pattern matching for UPPERCASE.DOTTED.NAMES
    import re
    pattern = r'\b([A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9_]*)+)\b'
    matches = re.findall(pattern, applies_if)
    features.update(matches)
    
    return features


def compute_feature_isolation_score(norm: Dict[str, Any], all_norms: List[Dict[str, Any]]) -> float:
    """Compute how isolated a norm is based on its features.
    
    Args:
        norm: Norm to evaluate
        all_norms: All norms in the dataset
    
    Returns:
        Isolation score from 0.0 (not isolated) to 1.0 (completely isolated)
    """
    norm_features = extract_features_from_applies_if(
        norm.get('attributes', {}).get('applies_if', '')
    )
    
    if not norm_features:
        return 1.0  # No features = completely isolated
    
    # Count how many other norms share at least one feature
    sharing_norms = 0
    for other_norm in all_norms:
        if other_norm.get('attributes', {}).get('id') == norm.get('attributes', {}).get('id'):
            continue
        
        other_features = extract_features_from_applies_if(
            other_norm.get('attributes', {}).get('applies_if', '')
        )
        
        if norm_features & other_features:  # Intersection
            sharing_norms += 1
    
    # Isolation score: inverse of sharing ratio
    sharing_ratio = sharing_norms / max(len(all_norms) - 1, 1)
    isolation_score = 1.0 - sharing_ratio
    
    return isolation_score


def compute_tag_isolation_score(norm: Dict[str, Any]) -> float:
    """Compute isolation based on tag coverage.
    
    Args:
        norm: Norm to evaluate
    
    Returns:
        1.0 if no tags, 0.0 if has tags
    """
    tags = norm.get('attributes', {}).get('relevant_tags', [])
    return 1.0 if not tags else 0.0


def compute_composite_isolation(norm: Dict[str, Any], all_norms: List[Dict[str, Any]]) -> float:
    """Compute composite isolation score.
    
    Args:
        norm: Norm to evaluate
        all_norms: All norms in the dataset
    
    Returns:
        Composite isolation score from 0.0 to 1.0
    """
    feature_iso = compute_feature_isolation_score(norm, all_norms)
    tag_iso = compute_tag_isolation_score(norm)
    
    # Weighted combination (60% features, 40% tags)
    composite = 0.6 * feature_iso + 0.4 * tag_iso
    
    return composite


def diagnose_isolation_reason(norm: Dict[str, Any], all_norms: List[Dict[str, Any]]) -> str:
    """Diagnose why a norm is isolated.
    
    Args:
        norm: Norm to diagnose
        all_norms: All norms in the dataset
    
    Returns:
        Human-readable reason for isolation
    """
    reasons = []
    
    # Check features
    features = extract_features_from_applies_if(
        norm.get('attributes', {}).get('applies_if', '')
    )
    
    if not features:
        reasons.append("No explicit features (applies_if == TRUE or unparseable)")
    else:
        # Check if features are unique
        feature_counts = Counter()
        for other_norm in all_norms:
            other_features = extract_features_from_applies_if(
                other_norm.get('attributes', {}).get('applies_if', '')
            )
            feature_counts.update(other_features)
        
        unique_features = [f for f in features if feature_counts[f] == 1]
        if unique_features:
            reasons.append(f"Unique features: {', '.join(unique_features)}")
    
    # Check tags
    tags = norm.get('attributes', {}).get('relevant_tags', [])
    if not tags:
        reasons.append("No relevant tags")
    
    # Check if applies_if is unconditional
    applies_if = norm.get('attributes', {}).get('applies_if', '').strip()
    if applies_if.upper() == 'TRUE':
        reasons.append("Unconditional norm (applies to all)")
    
    return "; ".join(reasons) if reasons else "Unknown reason"


def generate_isolation_report(
    extraction_results: Dict[str, Any],
    threshold: float = 0.7
) -> Dict[str, Any]:
    """Generate isolation report for extraction results.
    
    Args:
        extraction_results: Loaded enhanced_extraction_results.json
        threshold: Isolation score threshold (default 0.7)
    
    Returns:
        Dictionary containing report data
    """
    # Extract norms
    norms = [
        e for e in extraction_results.get('extractions', [])
        if e.get('extraction_class') == 'NORM'
    ]
    
    if not norms:
        return {
            'total_norms': 0,
            'isolated_count': 0,
            'isolation_rate': 0.0,
            'isolated_norms': []
        }
    
    # Compute isolation scores
    isolation_data = []
    for norm in norms:
        score = compute_composite_isolation(norm, norms)
        reason = diagnose_isolation_reason(norm, norms)
        
        isolation_data.append({
            'norm_id': norm.get('attributes', {}).get('id', 'unknown'),
            'statement': norm.get('attributes', {}).get('statement_text') or 
                        norm.get('attributes', {}).get('norm_statement') or
                        norm.get('extraction_text', '')[:100],
            'isolation_score': score,
            'reason': reason,
            'applies_if': norm.get('attributes', {}).get('applies_if', ''),
            'features': list(extract_features_from_applies_if(
                norm.get('attributes', {}).get('applies_if', '')
            )),
            'tags': norm.get('attributes', {}).get('relevant_tags', [])
        })
    
    # Sort by isolation score (descending)
    isolation_data.sort(key=lambda x: x['isolation_score'], reverse=True)
    
    # Filter isolated norms
    isolated = [item for item in isolation_data if item['isolation_score'] >= threshold]
    
    # Categorize by reason
    reason_counts = Counter()
    for item in isolated:
        # Extract primary reason
        primary_reason = item['reason'].split(';')[0].strip()
        reason_counts[primary_reason] += 1
    
    # Build report
    report = {
        'total_norms': len(norms),
        'isolated_count': len(isolated),
        'isolation_rate': len(isolated) / len(norms) if norms else 0.0,
        'average_isolation_score': sum(d['isolation_score'] for d in isolation_data) / len(isolation_data),
        'threshold': threshold,
        'reason_breakdown': dict(reason_counts),
        'isolated_norms': isolated,
        'all_scores': isolation_data
    }
    
    return report


def format_report_text(report: Dict[str, Any]) -> str:
    """Format report as human-readable text.
    
    Args:
        report: Report data from generate_isolation_report
    
    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("ISOLATION ANALYSIS REPORT")
    lines.append("=" * 70)
    lines.append("")
    
    lines.append("SUMMARY STATISTICS")
    lines.append("-" * 70)
    lines.append(f"Total Norms:           {report['total_norms']}")
    lines.append(f"Isolated Norms:        {report['isolated_count']} ({report['isolation_rate']*100:.1f}%)")
    lines.append(f"Average Isolation:     {report['average_isolation_score']:.2f}")
    lines.append(f"Threshold Used:        {report['threshold']:.2f}")
    lines.append("")
    
    if report['reason_breakdown']:
        lines.append("ISOLATION BREAKDOWN BY REASON")
        lines.append("-" * 70)
        for reason, count in sorted(report['reason_breakdown'].items(), 
                                    key=lambda x: x[1], reverse=True):
            percentage = (count / report['isolated_count']) * 100
            lines.append(f"  {count:3d} ({percentage:5.1f}%) - {reason}")
        lines.append("")
    
    if report['isolated_norms']:
        lines.append(f"TOP {min(20, len(report['isolated_norms']))} MOST ISOLATED NORMS")
        lines.append("-" * 70)
        
        for i, item in enumerate(report['isolated_norms'][:20], 1):
            lines.append(f"\n{i}. [{item['isolation_score']:.2f}] {item['norm_id']}")
            lines.append(f"   Statement: {item['statement'][:80]}{'...' if len(item['statement']) > 80 else ''}")
            lines.append(f"   Reason: {item['reason']}")
            if item['features']:
                lines.append(f"   Features: {', '.join(item['features'])}")
            else:
                lines.append(f"   Features: None")
            if item['tags']:
                lines.append(f"   Tags: {', '.join(item['tags'][:3])}{'...' if len(item['tags']) > 3 else ''}")
            else:
                lines.append(f"   Tags: None")
        
        lines.append("")
    
    lines.append("RECOMMENDATIONS")
    lines.append("-" * 70)
    
    if report['isolation_rate'] > 0.15:
        lines.append("⚠️  HIGH ISOLATION RATE (>15%)")
        lines.append("   - Review extraction prompts to ensure better tag coverage")
        lines.append("   - Consider semantic clustering for isolated norms")
        lines.append("   - Investigate unique feature combinations")
    elif report['isolation_rate'] > 0.10:
        lines.append("⚠️  MODERATE ISOLATION RATE (10-15%)")
        lines.append("   - Acceptable but could be improved")
        lines.append("   - Review top isolated norms for patterns")
    else:
        lines.append("✓  LOW ISOLATION RATE (<10%)")
        lines.append("   - Good clustering potential")
        lines.append("   - Review isolated norms for manual categorization")
    
    lines.append("")
    
    # Feature analysis
    if report['all_scores']:
        all_features = set()
        for item in report['all_scores']:
            all_features.update(item['features'])
        
        lines.append(f"FEATURE COVERAGE")
        lines.append("-" * 70)
        lines.append(f"Total unique features found: {len(all_features)}")
        
        norms_with_features = sum(1 for item in report['all_scores'] if item['features'])
        feature_coverage = norms_with_features / len(report['all_scores']) * 100
        lines.append(f"Norms with features: {norms_with_features}/{len(report['all_scores'])} ({feature_coverage:.1f}%)")
        
        norms_with_tags = sum(1 for item in report['all_scores'] if item['tags'])
        tag_coverage = norms_with_tags / len(report['all_scores']) * 100
        lines.append(f"Norms with tags: {norms_with_tags}/{len(report['all_scores'])} ({tag_coverage:.1f}%)")
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate isolation report for extracted norms',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report with default threshold (0.7)
  python generate_isolation_report.py --input enhanced_extraction_results.json --output report.txt
  
  # Use custom threshold
  python generate_isolation_report.py --input data.json --output report.txt --threshold 0.6
  
  # Output JSON format
  python generate_isolation_report.py --input data.json --output report.json --format json
        """
    )
    
    parser.add_argument(
        '--input',
        required=True,
        type=Path,
        help='Path to enhanced_extraction_results.json'
    )
    
    parser.add_argument(
        '--output',
        required=True,
        type=Path,
        help='Path to output report file'
    )
    
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.7,
        help='Isolation score threshold (0.0-1.0, default: 0.7)'
    )
    
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    if not 0.0 <= args.threshold <= 1.0:
        print(f"Error: Threshold must be between 0.0 and 1.0", file=sys.stderr)
        sys.exit(1)
    
    # Load data
    print(f"Loading data from {args.input}...")
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            extraction_results = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Generate report
    print(f"Analyzing norms with threshold {args.threshold}...")
    report = generate_isolation_report(extraction_results, threshold=args.threshold)
    
    # Output report
    print(f"Writing report to {args.output}...")
    try:
        if args.format == 'json':
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        else:
            text_report = format_report_text(report)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(text_report)
        
        print(f"\n✓ Report generated successfully!")
        print(f"  Total norms: {report['total_norms']}")
        print(f"  Isolated: {report['isolated_count']} ({report['isolation_rate']*100:.1f}%)")
        
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
