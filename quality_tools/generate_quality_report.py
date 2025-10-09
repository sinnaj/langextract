#!/usr/bin/env python3
"""Generate Quality Assessment Report for Extracted Norms.

This standalone script analyzes extracted norms across multiple quality dimensions:
- Completeness (all required fields present)
- Consistency (no contradictions, valid DSL)
- Atomicity (single obligation per norm)
- Traceability (source references present)
- Clustering potential

Usage:
    python generate_quality_report.py --input enhanced_extraction_results.json --output quality_report.txt
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def check_completeness(norm: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Check if norm has all required fields.
    
    Args:
        norm: Norm to check
    
    Returns:
        Tuple of (completeness_score, list of issues)
    """
    issues = []
    required_fields = ['id', 'applies_if', 'satisfied_if', 'obligation_type']
    
    attrs = norm.get('attributes', {})
    
    # Check required fields
    missing = []
    for field in required_fields:
        if not attrs.get(field):
            missing.append(field)
    
    if missing:
        issues.append(f"Missing required fields: {', '.join(missing)}")
    
    # Check for meaningful content
    applies_if = attrs.get('applies_if', '').strip()
    if applies_if.upper() == 'TRUE':
        issues.append("Unconditional norm (applies_if == TRUE)")
    
    # Check for statement text
    statement = (attrs.get('statement_text') or 
                attrs.get('norm_statement') or 
                norm.get('extraction_text', ''))
    if not statement or len(statement.strip()) < 10:
        issues.append("Missing or too short statement text")
    
    # Check tags
    tags = attrs.get('relevant_tags', [])
    if not tags:
        issues.append("No relevant tags")
    
    # Calculate score
    score = 1.0
    if missing:
        score -= 0.5
    if applies_if.upper() == 'TRUE':
        score -= 0.2
    if not tags:
        score -= 0.15
    if not statement or len(statement.strip()) < 10:
        score -= 0.15
    
    score = max(0.0, score)
    
    return score, issues


def check_dsl_syntax(applies_if: str) -> Tuple[bool, str]:
    """Check if DSL expression is syntactically valid.
    
    Args:
        applies_if: DSL expression to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not applies_if or applies_if.strip().upper() == 'TRUE':
        return True, ""
    
    # Basic syntax checks
    issues = []
    
    # Check for balanced parentheses
    if applies_if.count('(') != applies_if.count(')'):
        issues.append("Unbalanced parentheses")
    
    # Check for balanced brackets
    if applies_if.count('[') != applies_if.count(']'):
        issues.append("Unbalanced brackets")
    
    # Check for balanced quotes
    single_quotes = applies_if.count("'")
    if single_quotes % 2 != 0:
        issues.append("Unbalanced single quotes")
    
    double_quotes = applies_if.count('"')
    if double_quotes % 2 != 0:
        issues.append("Unbalanced double quotes")
    
    # Check for valid operators
    invalid_patterns = [
        r'={3,}',  # More than 2 equals
        r'[<>]{3,}',  # More than 2 comparison operators
        r'&&',  # C-style AND (should be AND)
        r'\|\|',  # C-style OR (should be OR)
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, applies_if):
            issues.append(f"Invalid operator pattern: {pattern}")
    
    if issues:
        return False, "; ".join(issues)
    
    return True, ""


def check_consistency(norms: List[Dict[str, Any]]) -> List[str]:
    """Check for consistency issues across norms.
    
    Args:
        norms: List of norms to check
    
    Returns:
        List of consistency issues
    """
    issues = []
    
    # Check DSL syntax for all norms
    invalid_dsl_count = 0
    for norm in norms:
        applies_if = norm.get('attributes', {}).get('applies_if', '')
        valid, error = check_dsl_syntax(applies_if)
        if not valid:
            norm_id = norm.get('attributes', {}).get('id', 'unknown')
            issues.append(f"Norm {norm_id}: Invalid DSL - {error}")
            invalid_dsl_count += 1
    
    # Check for duplicate IDs
    id_counts = Counter()
    for norm in norms:
        norm_id = norm.get('attributes', {}).get('id')
        if norm_id:
            id_counts[norm_id] += 1
    
    duplicates = [norm_id for norm_id, count in id_counts.items() if count > 1]
    if duplicates:
        issues.append(f"Duplicate norm IDs: {', '.join(duplicates[:5])}" + 
                     (f" and {len(duplicates)-5} more" if len(duplicates) > 5 else ""))
    
    # Check obligation type consistency
    valid_obligation_types = {
        'MANDATORY', 'PROHIBITION', 'PERMISSION', 'CONDITIONAL', 
        'OPTIONAL', 'RECOMMENDATION'
    }
    
    invalid_types = []
    for norm in norms:
        obligation_type = norm.get('attributes', {}).get('obligation_type', '').upper()
        if obligation_type and obligation_type not in valid_obligation_types:
            invalid_types.append(obligation_type)
    
    if invalid_types:
        unique_invalid = set(invalid_types)
        issues.append(f"Invalid obligation types: {', '.join(unique_invalid)}")
    
    return issues


def check_atomicity(norm: Dict[str, Any]) -> List[str]:
    """Check if norm represents a single atomic obligation.
    
    Args:
        norm: Norm to check
    
    Returns:
        List of atomicity issues
    """
    issues = []
    
    applies_if = norm.get('attributes', {}).get('applies_if', '')
    
    # Check for OR with different thresholds (potential split needed)
    if ' OR ' in applies_if.upper():
        # Simple heuristic: if OR appears with different numeric values
        numbers = re.findall(r'\d+\.?\d*', applies_if)
        if len(set(numbers)) > 1:
            issues.append("OR clause with different thresholds (may need splitting)")
    
    # Check statement for multiple obligations
    statement = (norm.get('attributes', {}).get('statement_text') or 
                norm.get('attributes', {}).get('norm_statement') or 
                norm.get('extraction_text', ''))
    
    multi_obligation_indicators = [
        'and also', 'additionally', 'furthermore', 'as well as',
        'moreover', 'in addition', 'likewise'
    ]
    
    statement_lower = statement.lower()
    found_indicators = [ind for ind in multi_obligation_indicators if ind in statement_lower]
    
    if found_indicators:
        issues.append(f"Multiple obligation indicators: {', '.join(found_indicators)}")
    
    # Check for multiple sentences
    sentences = statement.split('.')
    if len([s for s in sentences if len(s.strip()) > 10]) > 2:
        issues.append("Multiple sentences (may contain multiple obligations)")
    
    return issues


def check_traceability(norm: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Check if norm has proper source traceability.
    
    Args:
        norm: Norm to check
    
    Returns:
        Tuple of (traceability_score, list of issues)
    """
    issues = []
    score = 1.0
    
    source = norm.get('attributes', {}).get('source', {})
    
    # Check for page reference
    page = source.get('page')
    if not page or page == -1:
        issues.append("Missing page reference")
        score -= 0.4
    
    # Check for character span
    char_start = source.get('span_char_start')
    char_end = source.get('span_char_end')
    if char_start is None or char_end is None:
        issues.append("Missing character span")
        score -= 0.3
    elif char_start >= char_end:
        issues.append("Invalid character span (start >= end)")
        score -= 0.3
    
    # Check for document ID
    doc_id = source.get('doc_id')
    if not doc_id:
        issues.append("Missing document ID")
        score -= 0.3
    
    score = max(0.0, score)
    
    return score, issues


def compute_quality_metrics(extraction_results: Dict[str, Any]) -> Dict[str, Any]:
    """Compute comprehensive quality metrics.
    
    Args:
        extraction_results: Loaded enhanced_extraction_results.json
    
    Returns:
        Dictionary with quality metrics
    """
    # Extract norms
    norms = [
        e for e in extraction_results.get('extractions', [])
        if e.get('extraction_class') == 'NORM'
    ]
    
    if not norms:
        return {
            'total_norms': 0,
            'overall_score': 0.0,
            'grade': 'N/A',
            'dimensions': {}
        }
    
    metrics = {
        'total_norms': len(norms),
        'dimensions': {}
    }
    
    # 1. Completeness
    completeness_scores = []
    completeness_issues = []
    
    for norm in norms:
        score, issues = check_completeness(norm)
        completeness_scores.append(score)
        if issues:
            norm_id = norm.get('attributes', {}).get('id', 'unknown')
            completeness_issues.append(f"{norm_id}: {'; '.join(issues)}")
    
    metrics['dimensions']['completeness'] = {
        'score': sum(completeness_scores) / len(completeness_scores),
        'issues_count': len(completeness_issues),
        'top_issues': completeness_issues[:10]
    }
    
    # 2. Consistency
    consistency_issues = check_consistency(norms)
    consistency_score = max(0.0, 1.0 - (len(consistency_issues) / max(len(norms), 1)))
    
    metrics['dimensions']['consistency'] = {
        'score': consistency_score,
        'issues_count': len(consistency_issues),
        'top_issues': consistency_issues[:10]
    }
    
    # 3. Atomicity
    atomicity_scores = []
    atomicity_issues = []
    
    for norm in norms:
        issues = check_atomicity(norm)
        score = 1.0 if not issues else max(0.5, 1.0 - 0.2 * len(issues))
        atomicity_scores.append(score)
        
        if issues:
            norm_id = norm.get('attributes', {}).get('id', 'unknown')
            atomicity_issues.append(f"{norm_id}: {'; '.join(issues)}")
    
    metrics['dimensions']['atomicity'] = {
        'score': sum(atomicity_scores) / len(atomicity_scores),
        'issues_count': len(atomicity_issues),
        'top_issues': atomicity_issues[:10]
    }
    
    # 4. Traceability
    traceability_scores = []
    traceability_issues = []
    
    for norm in norms:
        score, issues = check_traceability(norm)
        traceability_scores.append(score)
        
        if issues:
            norm_id = norm.get('attributes', {}).get('id', 'unknown')
            traceability_issues.append(f"{norm_id}: {'; '.join(issues)}")
    
    metrics['dimensions']['traceability'] = {
        'score': sum(traceability_scores) / len(traceability_scores),
        'issues_count': len(traceability_issues),
        'top_issues': traceability_issues[:10]
    }
    
    # 5. Clustering potential (based on feature and tag coverage)
    norms_with_features = 0
    norms_with_tags = 0
    
    for norm in norms:
        applies_if = norm.get('attributes', {}).get('applies_if', '')
        if applies_if and applies_if.strip().upper() != 'TRUE':
            # Has some condition
            pattern = r'\b([A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9_]*)+)\b'
            if re.findall(pattern, applies_if):
                norms_with_features += 1
        
        tags = norm.get('attributes', {}).get('relevant_tags', [])
        if tags:
            norms_with_tags += 1
    
    feature_coverage = norms_with_features / len(norms)
    tag_coverage = norms_with_tags / len(norms)
    clustering_score = 0.5 * feature_coverage + 0.5 * tag_coverage
    
    metrics['dimensions']['clustering'] = {
        'score': clustering_score,
        'feature_coverage': feature_coverage,
        'tag_coverage': tag_coverage,
        'norms_with_features': norms_with_features,
        'norms_with_tags': norms_with_tags
    }
    
    # Compute overall quality score
    weights = {
        'completeness': 0.25,
        'consistency': 0.25,
        'atomicity': 0.20,
        'clustering': 0.15,
        'traceability': 0.15
    }
    
    overall_score = sum(
        metrics['dimensions'][dim]['score'] * weights[dim]
        for dim in weights
    )
    
    # Assign grade
    if overall_score >= 0.90:
        grade = 'A (Excellent)'
    elif overall_score >= 0.80:
        grade = 'B (Good)'
    elif overall_score >= 0.70:
        grade = 'C (Fair)'
    elif overall_score >= 0.60:
        grade = 'D (Poor)'
    else:
        grade = 'F (Failing)'
    
    metrics['overall_score'] = overall_score
    metrics['grade'] = grade
    
    return metrics


def format_quality_report_text(metrics: Dict[str, Any]) -> str:
    """Format quality metrics as human-readable text.
    
    Args:
        metrics: Quality metrics from compute_quality_metrics
    
    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("DATA QUALITY REPORT")
    lines.append("=" * 70)
    lines.append("")
    
    lines.append(f"OVERALL QUALITY SCORE: {metrics['grade']}")
    lines.append(f"Score: {metrics['overall_score']*100:.1f}%")
    lines.append("-" * 70)
    lines.append("")
    
    lines.append("DIMENSION SCORES")
    lines.append("-" * 70)
    
    dimensions = metrics['dimensions']
    
    # Format each dimension
    dim_display = [
        ('Completeness', 'completeness'),
        ('Consistency', 'consistency'),
        ('Atomicity', 'atomicity'),
        ('Clustering', 'clustering'),
        ('Traceability', 'traceability')
    ]
    
    for display_name, dim_key in dim_display:
        dim = dimensions[dim_key]
        score = dim['score']
        issues_count = dim.get('issues_count', 0)
        
        status = '✓' if score >= 0.90 else '○' if score >= 0.70 else '✗'
        level = 'Excellent' if score >= 0.90 else 'Good' if score >= 0.80 else 'Fair' if score >= 0.70 else 'Poor'
        
        lines.append(f"{display_name:15s}: {score*100:5.1f}% {status} {level}")
        
        if issues_count > 0:
            lines.append(f"{'':15s}  {issues_count} issues detected")
    
    lines.append("")
    
    # Detailed findings
    lines.append("DETAILED FINDINGS")
    lines.append("-" * 70)
    lines.append("")
    
    for display_name, dim_key in dim_display:
        dim = dimensions[dim_key]
        score = dim['score']
        
        lines.append(f"{display_name} ({score*100:.1f}%):")
        
        if dim_key == 'clustering':
            lines.append(f"  Feature coverage: {dim['feature_coverage']*100:.1f}% " +
                        f"({dim['norms_with_features']}/{metrics['total_norms']} norms)")
            lines.append(f"  Tag coverage: {dim['tag_coverage']*100:.1f}% " +
                        f"({dim['norms_with_tags']}/{metrics['total_norms']} norms)")
        else:
            issues = dim.get('top_issues', [])
            if issues:
                lines.append(f"  Top issues (showing {len(issues)}):")
                for issue in issues:
                    # Truncate long issues
                    if len(issue) > 100:
                        issue = issue[:97] + "..."
                    lines.append(f"    - {issue}")
            else:
                lines.append("  ✓ No issues detected")
        
        lines.append("")
    
    # Recommendations
    lines.append("RECOMMENDATIONS")
    lines.append("-" * 70)
    
    completeness_score = dimensions['completeness']['score']
    consistency_score = dimensions['consistency']['score']
    atomicity_score = dimensions['atomicity']['score']
    clustering_score = dimensions['clustering']['score']
    traceability_score = dimensions['traceability']['score']
    
    if metrics['overall_score'] >= 0.90:
        lines.append("✓ Excellent overall quality!")
        lines.append("  - Data is ready for production use")
        lines.append("  - Continue monitoring for consistency")
    elif metrics['overall_score'] >= 0.80:
        lines.append("✓ Good overall quality")
        lines.append("  - Data is acceptable for use")
        lines.append("  - Address noted issues for improvement")
    else:
        lines.append("⚠️  Quality improvements needed")
        
        if completeness_score < 0.80:
            lines.append("  - Improve tag coverage and field completeness")
        if consistency_score < 0.80:
            lines.append("  - Fix DSL syntax errors and duplicates")
        if atomicity_score < 0.80:
            lines.append("  - Review norms with multiple obligations for splitting")
        if clustering_score < 0.70:
            lines.append("  - Enhance feature extraction and tag assignment")
        if traceability_score < 0.80:
            lines.append("  - Improve source references (pages, spans)")
    
    lines.append("")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate quality assessment report for extracted norms',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate text report
  python generate_quality_report.py --input enhanced_extraction_results.json --output quality_report.txt
  
  # Generate JSON report
  python generate_quality_report.py --input data.json --output quality_report.json --format json
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
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
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
    
    # Compute metrics
    print("Computing quality metrics...")
    metrics = compute_quality_metrics(extraction_results)
    
    # Output report
    print(f"Writing report to {args.output}...")
    try:
        if args.format == 'json':
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
        else:
            text_report = format_quality_report_text(metrics)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(text_report)
        
        print(f"\n✓ Quality report generated successfully!")
        print(f"  Total norms: {metrics['total_norms']}")
        print(f"  Overall score: {metrics['overall_score']*100:.1f}%")
        print(f"  Grade: {metrics['grade']}")
        
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
