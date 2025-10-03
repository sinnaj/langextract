#!/usr/bin/env python3
"""Compute Information Gain for features extracted from norm applies_if predicates.

This script implements Monte-Carlo sampling to compute the information gain (IG)
of candidate features for decision-making in building code compliance.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from tabulate import tabulate

from dsl_parser import parse_applies_if
from evaluator import TristateValue, evaluate_with_assignment
from feature_schema import extract_features_from_norms, FeatureSchema


def binary_entropy(p: float) -> float:
    """Compute binary entropy: h(p) = -p*log2(p) - (1-p)*log2(1-p).
    
    Args:
        p: Probability in [0, 1]
    
    Returns:
        Binary entropy value
    """
    if p <= 0 or p >= 1:
        return 0.0
    return -p * np.log2(p) - (1 - p) * np.log2(1 - p)


def sample_feature_value(
    feature_name: str,
    schema: FeatureSchema,
    rng: np.random.Generator
) -> Any:
    """Sample a value for a feature from its prior.
    
    Args:
        feature_name: Name of the feature
        schema: Feature schema with priors
        rng: Random number generator
    
    Returns:
        Sampled value
    """
    if feature_name not in schema.priors:
        # No prior defined - return a default
        if schema.is_numeric(feature_name):
            return 0.0
        return "UNKNOWN"

    prior = schema.priors[feature_name]
    values = list(prior.keys())
    probs = [prior[v] for v in values]

    # Normalize probabilities
    total = sum(probs)
    if total > 0:
        probs = [p / total for p in probs]
    else:
        # Uniform fallback
        probs = [1.0 / len(values)] * len(values)

    # Sample
    idx = rng.choice(len(values), p=probs)
    sampled_value = values[idx]

    # For numeric features, sampled_value is a bin index
    # We need to return a concrete value within that bin
    if schema.is_numeric(feature_name):
        nf = schema.numeric_features[feature_name]
        try:
            bin_idx = int(sampled_value)
            if bin_idx < len(nf.bins):
                bin_low, bin_high = nf.bins[bin_idx]
                # Return a representative value
                if bin_low is None and bin_high is not None:
                    return bin_high - 1.0
                elif bin_low is not None and bin_high is None:
                    return bin_low + 1.0
                elif bin_low is not None and bin_high is not None:
                    return (bin_low + bin_high) / 2.0
                else:
                    return 0.0
            else:
                # If bin_idx is out of range, just return the sampled value
                return sampled_value
        except (ValueError, TypeError):
            # If sampled_value is not an int, treat as categorical
            return sampled_value
    
    return sampled_value


def generate_samples(
    schema: FeatureSchema,
    n_samples: int,
    seed: int
) -> List[Dict[str, Any]]:
    """Generate Monte-Carlo samples of feature assignments.
    
    Args:
        schema: Feature schema with priors
        n_samples: Number of samples to generate
        seed: Random seed
    
    Returns:
        List of feature assignments (dicts)
    """
    rng = np.random.default_rng(seed)
    samples = []

    for _ in range(n_samples):
        assignment = {}
        for feature_name in schema.all_feature_names:
            assignment[feature_name] = sample_feature_value(feature_name, schema, rng)
        samples.append(assignment)

    return samples


def evaluate_norms_on_samples(
    norms: List[Dict[str, Any]],
    samples: List[Dict[str, Any]],
    sections: Optional[List[Dict[str, Any]]] = None
) -> np.ndarray:
    """Evaluate all norms on all samples.
    
    Args:
        norms: List of norm dictionaries
        samples: List of feature assignments
        sections: Optional list of section dictionaries with meta_applies_if and meta_exempt_if
    
    Returns:
        Boolean numpy array of shape (n_norms, n_samples)
    """
    n_norms = len(norms)
    n_samples = len(samples)
    applicability = np.zeros((n_norms, n_samples), dtype=bool)

    # Build section lookup map
    section_map = {}
    if sections:
        for section in sections:
            section_id = section.get('section_id')
            if section_id:
                section_map[section_id] = section

    # Parse all norms first
    norm_data = []
    for norm in norms:
        applies_if = norm.get('attributes', {}).get('applies_if', '')
        exempt_if = norm.get('attributes', {}).get('exempt_if', '')
        parent_section_id = norm.get('attributes', {}).get('parent_section_id')
        
        applies_ast = parse_applies_if(applies_if)
        exempt_ast = parse_applies_if(exempt_if) if exempt_if else None
        
        # Get section metadata if available
        section_applies_ast = None
        section_exempt_ast = None
        if parent_section_id and parent_section_id in section_map:
            section = section_map[parent_section_id]
            section_applies_if = section.get('meta_applies_if', '')
            section_exempt_if = section.get('meta_exempt_if', '')
            
            if section_applies_if:
                section_applies_ast = parse_applies_if(section_applies_if)
            if section_exempt_if:
                section_exempt_ast = parse_applies_if(section_exempt_if)
        
        norm_data.append({
            'applies_ast': applies_ast,
            'exempt_ast': exempt_ast,
            'section_applies_ast': section_applies_ast,
            'section_exempt_ast': section_exempt_ast
        })

    # Evaluate each norm on each sample
    for i, data in enumerate(norm_data):
        for j, assignment in enumerate(samples):
            # Norm applies if:
            # 1. section_applies_if is TRUE (or not present)
            # 2. norm applies_if is TRUE
            # 3. section_exempt_if is FALSE or UNKNOWN (not TRUE)
            # 4. norm exempt_if is FALSE or UNKNOWN (not TRUE)
            
            # Check section applies_if
            section_applies = True
            if data['section_applies_ast'] is not None:
                result = evaluate_with_assignment(data['section_applies_ast'], assignment)
                if result != TristateValue.TRUE:
                    section_applies = False
            
            # Check norm applies_if
            norm_applies = False
            if data['applies_ast'] is not None:
                result = evaluate_with_assignment(data['applies_ast'], assignment)
                if result == TristateValue.TRUE:
                    norm_applies = True
            
            # Check section exempt_if
            section_exempt = False
            if data['section_exempt_ast'] is not None:
                result = evaluate_with_assignment(data['section_exempt_ast'], assignment)
                if result == TristateValue.TRUE:
                    section_exempt = True
            
            # Check norm exempt_if
            norm_exempt = False
            if data['exempt_ast'] is not None:
                result = evaluate_with_assignment(data['exempt_ast'], assignment)
                if result == TristateValue.TRUE:
                    norm_exempt = True
            
            # Final applicability: applies AND not exempt
            if section_applies and norm_applies and not section_exempt and not norm_exempt:
                applicability[i, j] = True

    return applicability


def compute_base_entropy(applicability: np.ndarray) -> float:
    """Compute base entropy across all norms.
    
    Args:
        applicability: Boolean array of shape (n_norms, n_samples)
    
    Returns:
        Total entropy summed over all norms
    """
    n_norms, n_samples = applicability.shape
    total_entropy = 0.0

    for i in range(n_norms):
        p = applicability[i, :].mean()
        total_entropy += binary_entropy(p)

    return total_entropy


def compute_conditional_entropy(
    applicability: np.ndarray,
    samples: List[Dict[str, Any]],
    feature_name: str,
    feature_value: Any,
    schema: FeatureSchema
) -> Tuple[float, int]:
    """Compute conditional entropy H(norms | feature=value).
    
    Args:
        applicability: Boolean array of shape (n_norms, n_samples)
        samples: List of feature assignments
        feature_name: Feature to condition on
        feature_value: Value to condition on
        schema: Feature schema
    
    Returns:
        Tuple of (conditional_entropy, n_matching_samples)
    """
    n_norms, n_samples = applicability.shape

    # Find samples where feature == value
    mask = np.zeros(n_samples, dtype=bool)
    
    if schema.is_numeric(feature_name):
        # feature_value is a bin index
        nf = schema.numeric_features[feature_name]
        if feature_value >= len(nf.bins):
            return 0.0, 0
        
        bin_low, bin_high = nf.bins[feature_value]
        
        for j, assignment in enumerate(samples):
            val = assignment.get(feature_name, None)
            if val is None:
                continue
            
            # Check if val is in the bin (only if val is a number)
            if isinstance(val, (int, float)):
                in_bin = True
                if bin_low is not None and val <= bin_low:
                    in_bin = False
                if bin_high is not None and val > bin_high:
                    in_bin = False
                if in_bin:
                    mask[j] = True
            else:
                # If val is not numeric, skip this sample for numeric binning
                continue
    else:
        # Categorical feature
        for j, assignment in enumerate(samples):
            if assignment.get(feature_name) == feature_value:
                mask[j] = True

    n_matching = mask.sum()
    if n_matching == 0:
        return 0.0, 0

    # Compute entropy over matching samples
    conditional_entropy = 0.0
    for i in range(n_norms):
        p = applicability[i, mask].mean()
        conditional_entropy += binary_entropy(p)

    return conditional_entropy, n_matching


def compute_expected_entropy(
    applicability: np.ndarray,
    samples: List[Dict[str, Any]],
    feature_name: str,
    schema: FeatureSchema
) -> float:
    """Compute expected conditional entropy E[H | feature].
    
    Args:
        applicability: Boolean array of shape (n_norms, n_samples)
        samples: List of feature assignments
        feature_name: Feature to condition on
        schema: Feature schema
    
    Returns:
        Expected conditional entropy
    """
    feature_values = schema.get_feature_values(feature_name)
    if not feature_values:
        return 0.0

    n_samples = len(samples)
    expected_entropy = 0.0

    if schema.is_numeric(feature_name):
        # Feature values are bin indices
        for bin_idx in range(len(feature_values)):
            cond_entropy, n_matching = compute_conditional_entropy(
                applicability, samples, feature_name, bin_idx, schema
            )
            p_value = n_matching / n_samples if n_samples > 0 else 0.0
            expected_entropy += p_value * cond_entropy
    else:
        # Categorical feature
        for value in feature_values:
            cond_entropy, n_matching = compute_conditional_entropy(
                applicability, samples, feature_name, value, schema
            )
            p_value = n_matching / n_samples if n_samples > 0 else 0.0
            expected_entropy += p_value * cond_entropy

    return expected_entropy


def compute_dismissal_stats(
    norm_data: List[Dict[str, Any]],
    feature_name: str,
    schema: FeatureSchema
) -> Tuple[float, float, str]:
    """Compute dismissal statistics for a feature.
    
    This shows how many norms (out of ALL norms in the dataset) would be 
    dismissed (made inapplicable/FALSE) by selecting different values of 
    this feature, when all other features are left unspecified.
    
    This matches the behavior of the Sandbox filter where setting a single
    feature value filters out norms whose applies_if becomes definitively FALSE
    or exempt_if becomes TRUE.
    
    Args:
        norm_data: List of dicts with 'applies_ast', 'exempt_ast', 
                   'section_applies_ast', 'section_exempt_ast' keys
        feature_name: Feature to analyze
        schema: Feature schema
    
    Returns:
        Tuple of (max_dismissal_rate, avg_dismissal_rate, best_value_str)
        - max_dismissal_rate: Highest fraction of ALL norms dismissed by any value
        - avg_dismissal_rate: Average dismissal rate across all values
        - best_value_str: String representation of value with highest dismissal
    """
    n_norms = len(norm_data)
    feature_values = schema.get_feature_values(feature_name)
    
    if not feature_values:
        return 0.0, 0.0, "N/A"
    
    dismissal_rates = []
    value_strs = []
    
    if schema.is_numeric(feature_name):
        nf = schema.numeric_features[feature_name]
        # For each bin, test with a representative value from that bin
        for bin_idx in range(len(feature_values)):
            bin_low, bin_high = nf.bins[bin_idx]
            
            # Choose a representative value from this bin
            if bin_low is None:
                test_value = bin_high - 1 if bin_high is not None else 0
            elif bin_high is None:
                test_value = bin_low + 1
            else:
                test_value = (bin_low + bin_high) / 2
            
            # Create assignment with only this feature set
            assignment = {feature_name: test_value}
            
            # Count how many norms are dismissed (applies=FALSE or exempt=TRUE)
            norms_dismissed = 0
            for i, data in enumerate(norm_data):
                # Check section applies_if
                section_applies = True
                if data['section_applies_ast'] is not None:
                    result = evaluate_with_assignment(data['section_applies_ast'], assignment)
                    if result == TristateValue.FALSE:
                        section_applies = False
                
                # Check norm applies_if
                norm_applies = False
                if data['applies_ast'] is not None:
                    result = evaluate_with_assignment(data['applies_ast'], assignment)
                    if result != TristateValue.FALSE:
                        norm_applies = True
                
                # Check section exempt_if
                section_exempt = False
                if data['section_exempt_ast'] is not None:
                    result = evaluate_with_assignment(data['section_exempt_ast'], assignment)
                    if result == TristateValue.TRUE:
                        section_exempt = True
                
                # Check norm exempt_if
                norm_exempt = False
                if data['exempt_ast'] is not None:
                    result = evaluate_with_assignment(data['exempt_ast'], assignment)
                    if result == TristateValue.TRUE:
                        norm_exempt = True
                
                # Norm is dismissed if section doesn't apply, norm doesn't apply, 
                # section is exempt, or norm is exempt
                if not section_applies or not norm_applies or section_exempt or norm_exempt:
                    norms_dismissed += 1
            
            dismissal_rate = norms_dismissed / n_norms if n_norms > 0 else 0.0
            dismissal_rates.append(dismissal_rate)
            
            # Format bin string
            if bin_low is None:
                bin_str = f"≤{bin_high}"
            elif bin_high is None:
                bin_str = f">{bin_low}"
            else:
                bin_str = f"({bin_low}, {bin_high}]"
            value_strs.append(bin_str)
    else:
        # Categorical feature
        for value in feature_values:
            # Create assignment with only this feature set
            assignment = {feature_name: value}
            
            # Count how many norms are dismissed
            norms_dismissed = 0
            for i, data in enumerate(norm_data):
                # Check section applies_if
                section_applies = True
                if data['section_applies_ast'] is not None:
                    result = evaluate_with_assignment(data['section_applies_ast'], assignment)
                    if result == TristateValue.FALSE:
                        section_applies = False
                
                # Check norm applies_if
                norm_applies = False
                if data['applies_ast'] is not None:
                    result = evaluate_with_assignment(data['applies_ast'], assignment)
                    if result != TristateValue.FALSE:
                        norm_applies = True
                
                # Check section exempt_if
                section_exempt = False
                if data['section_exempt_ast'] is not None:
                    result = evaluate_with_assignment(data['section_exempt_ast'], assignment)
                    if result == TristateValue.TRUE:
                        section_exempt = True
                
                # Check norm exempt_if
                norm_exempt = False
                if data['exempt_ast'] is not None:
                    result = evaluate_with_assignment(data['exempt_ast'], assignment)
                    if result == TristateValue.TRUE:
                        norm_exempt = True
                
                # Norm is dismissed if section doesn't apply, norm doesn't apply,
                # section is exempt, or norm is exempt
                if not section_applies or not norm_applies or section_exempt or norm_exempt:
                    norms_dismissed += 1
            
            dismissal_rate = norms_dismissed / n_norms if n_norms > 0 else 0.0
            dismissal_rates.append(dismissal_rate)
            value_strs.append(str(value))
    
    if not dismissal_rates:
        return 0.0, 0.0, "N/A"
    
    max_dismissal_rate = max(dismissal_rates)
    avg_dismissal_rate = sum(dismissal_rates) / len(dismissal_rates)
    
    # Find value with max dismissal
    max_idx = dismissal_rates.index(max_dismissal_rate)
    best_value_str = value_strs[max_idx]
    
    return max_dismissal_rate, avg_dismissal_rate, best_value_str


def compute_information_gain(
    norms: List[Dict[str, Any]],
    schema: FeatureSchema,
    n_samples: int,
    seed: int,
    costs: Optional[Dict[str, float]] = None,
    include_features: Optional[List[str]] = None,
    exclude_features: Optional[List[str]] = None,
    sections: Optional[List[Dict[str, Any]]] = None
) -> pd.DataFrame:
    """Compute information gain for all features.
    
    Args:
        norms: List of norm dictionaries
        schema: Feature schema
        n_samples: Number of Monte-Carlo samples
        seed: Random seed
        costs: Optional dict mapping feature -> cost
        include_features: Optional list of features to include
        exclude_features: Optional list of features to exclude
        sections: Optional list of section dictionaries with meta_applies_if and meta_exempt_if
    
    Returns:
        DataFrame with IG results including dismissal statistics
    """
    # Generate samples
    print(f"Generating {n_samples} samples...")
    samples = generate_samples(schema, n_samples, seed)

    # Evaluate norms on samples
    print(f"Evaluating {len(norms)} norms on samples...")
    applicability = evaluate_norms_on_samples(norms, samples, sections)

    # Build section lookup map and parse norms for dismissal stats
    print("Parsing norms for dismissal statistics...")
    section_map = {}
    if sections:
        for section in sections:
            section_id = section.get('section_id')
            if section_id:
                section_map[section_id] = section

    norm_data = []
    for norm in norms:
        applies_if = norm.get('attributes', {}).get('applies_if', '')
        exempt_if = norm.get('attributes', {}).get('exempt_if', '')
        parent_section_id = norm.get('attributes', {}).get('parent_section_id')
        
        applies_ast = parse_applies_if(applies_if)
        exempt_ast = parse_applies_if(exempt_if) if exempt_if else None
        
        # Get section metadata if available
        section_applies_ast = None
        section_exempt_ast = None
        if parent_section_id and parent_section_id in section_map:
            section = section_map[parent_section_id]
            section_applies_if = section.get('meta_applies_if', '')
            section_exempt_if = section.get('meta_exempt_if', '')
            
            if section_applies_if:
                section_applies_ast = parse_applies_if(section_applies_if)
            if section_exempt_if:
                section_exempt_ast = parse_applies_if(section_exempt_if)
        
        norm_data.append({
            'applies_ast': applies_ast,
            'exempt_ast': exempt_ast,
            'section_applies_ast': section_applies_ast,
            'section_exempt_ast': section_exempt_ast
        })

    # Compute base entropy
    base_entropy = compute_base_entropy(applicability)
    print(f"Base entropy: {base_entropy:.4f}")

    # Filter features
    candidate_features = list(schema.all_feature_names)
    if include_features:
        candidate_features = [f for f in candidate_features if f in include_features]
    if exclude_features:
        candidate_features = [f for f in candidate_features if f not in exclude_features]

    # Compute IG for each feature
    results = []
    for i, feature in enumerate(candidate_features):
        print(f"Computing IG for {feature} ({i+1}/{len(candidate_features)})...")
        
        expected_entropy = compute_expected_entropy(
            applicability, samples, feature, schema
        )
        ig = base_entropy - expected_entropy

        # Get cost
        cost = costs.get(feature, 0.25) if costs else 0.25
        ig_per_cost = ig / cost if cost > 0 else 0.0

        # Compute dismissal statistics
        max_dismissal, avg_dismissal, best_value = compute_dismissal_stats(
            norm_data, feature, schema
        )

        # Get feature values
        feature_values = schema.get_feature_values(feature)
        num_values = len(feature_values)
        is_numeric = schema.is_numeric(feature)

        # Format values
        if is_numeric:
            nf = schema.numeric_features[feature]
            values_str = str(nf.bins)
        else:
            values_str = str(sorted(feature_values))

        results.append({
            'feature': feature,
            'base_entropy': base_entropy,
            'expected_entropy': expected_entropy,
            'IG': ig,
            'cost': cost,
            'IG_per_cost': ig_per_cost,
            'num_values': num_values,
            'numeric': is_numeric,
            'categories_or_bins': values_str,
            'max_dismissal_rate': max_dismissal,
            'avg_dismissal_rate': avg_dismissal,
            'best_dismissal_value': best_value
        })

    # Create DataFrame
    df = pd.DataFrame(results)
    df = df.sort_values('IG_per_cost', ascending=False)
    
    return df


def load_costs(costs_path: Optional[Path]) -> Dict[str, float]:
    """Load costs from YAML file.
    
    Args:
        costs_path: Path to costs.yaml
    
    Returns:
        Dictionary mapping feature -> cost
    """
    if not costs_path or not costs_path.exists():
        return {}

    with open(costs_path, 'r') as f:
        costs = yaml.safe_load(f)

    return costs if costs else {}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Compute Information Gain for features in norm applies_if predicates'
    )
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help='Path to enhanced_extraction_results.json'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Path to output CSV file'
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=20000,
        help='Number of Monte-Carlo samples (default: 20000)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=7,
        help='Random seed (default: 7)'
    )
    parser.add_argument(
        '--costs',
        type=Path,
        help='Path to costs.yaml (optional)'
    )
    parser.add_argument(
        '--priors',
        type=Path,
        help='Path to priors.yaml (optional)'
    )
    parser.add_argument(
        '--report',
        type=Path,
        help='Path to JSON report file (optional)'
    )
    parser.add_argument(
        '--include',
        nargs='+',
        help='List of features to include (optional)'
    )
    parser.add_argument(
        '--exclude',
        nargs='+',
        help='List of features to exclude (optional)'
    )

    args = parser.parse_args()

    # Load input JSON
    print(f"Loading {args.input}...")
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract norms
    extractions = data.get('extractions', [])
    norms = [e for e in extractions if e.get('extraction_class') == 'NORM']
    
    if not norms:
        print("No NORM extractions found!")
        sys.exit(1)

    print(f"Found {len(norms)} norms")

    # Extract sections (for meta_applies_if and meta_exempt_if)
    sections = data.get('sections', [])
    print(f"Found {len(sections)} sections")
    
    # Count sections with metadata
    sections_with_metadata = sum(
        1 for s in sections 
        if s.get('meta_applies_if') or s.get('meta_exempt_if')
    )
    if sections_with_metadata > 0:
        print(f"  - {sections_with_metadata} sections have metadata (meta_applies_if/meta_exempt_if)")
    
    # Count norms with exempt_if
    norms_with_exempt = sum(
        1 for n in norms
        if n.get('attributes', {}).get('exempt_if')
    )
    if norms_with_exempt > 0:
        print(f"  - {norms_with_exempt} norms have exempt_if conditions")

    # Extract feature schema
    print("Extracting feature schema...")
    schema = extract_features_from_norms(norms, args.priors)
    print(f"Found {len(schema.all_feature_names)} features:")
    print(f"  - {len(schema.numeric_features)} numeric")
    print(f"  - {len(schema.categorical_features)} categorical")

    # Load costs
    costs = load_costs(args.costs)

    # Compute IG
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=args.samples,
        seed=args.seed,
        costs=costs,
        include_features=args.include,
        exclude_features=args.exclude,
        sections=sections
    )

    # Save CSV
    print(f"Saving results to {args.output}...")
    df.to_csv(args.output, index=False)

    # Print table
    print("\nTop 20 features by IG per cost:")
    table_data = df.head(20)[['feature', 'IG', 'cost', 'IG_per_cost', 'num_values', 'numeric']].values
    headers = ['Feature', 'IG', 'Cost', 'IG/Cost', '#Values', 'Numeric?']
    print(tabulate(table_data, headers=headers, floatfmt='.4f'))
    
    # Print dismissal statistics
    print("\nTop 20 features by maximum dismissal rate:")
    df_by_dismissal = df.sort_values('max_dismissal_rate', ascending=False)
    table_data = df_by_dismissal.head(20)[['feature', 'max_dismissal_rate', 'avg_dismissal_rate', 'best_dismissal_value']].values
    headers = ['Feature', 'Max Dismissal', 'Avg Dismissal', 'Best Value']
    print(tabulate(table_data, headers=headers, floatfmt='.4f'))

    # Save report if requested
    if args.report:
        print(f"Saving report to {args.report}...")
        report = {
            'input_file': str(args.input),
            'n_norms': len(norms),
            'n_features': len(schema.all_feature_names),
            'n_numeric': len(schema.numeric_features),
            'n_categorical': len(schema.categorical_features),
            'n_samples': args.samples,
            'seed': args.seed,
            'base_entropy': float(df['base_entropy'].iloc[0]) if len(df) > 0 else 0.0,
            'top_20_by_ig': df.head(20)[['feature', 'IG', 'IG_per_cost']].to_dict('records'),
            'top_20_by_ig_per_cost': df.sort_values('IG_per_cost', ascending=False).head(20)[
                ['feature', 'IG', 'IG_per_cost']
            ].to_dict('records'),
            'feature_schema': {
                'numeric_features': {
                    name: {
                        'thresholds': nf.thresholds,
                        'bins': [[b[0], b[1]] for b in nf.bins]
                    }
                    for name, nf in schema.numeric_features.items()
                },
                'categorical_features': {
                    name: {
                        'categories': sorted(cf.categories)
                    }
                    for name, cf in schema.categorical_features.items()
                }
            }
        }

        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)

    print("Done!")


if __name__ == '__main__':
    main()
