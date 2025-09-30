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
        bin_idx = sampled_value
        if bin_idx < len(nf.bins):
            bin_low, bin_high = nf.bins[bin_idx]
            # Return a representative value
            if bin_low is None and bin_high is not None:
                # (-inf, high]
                return bin_high - 1.0
            elif bin_low is not None and bin_high is None:
                # (low, inf)
                return bin_low + 1.0
            elif bin_low is not None and bin_high is not None:
                # (low, high]
                return (bin_low + bin_high) / 2.0
            else:
                # (-inf, inf)
                return 0.0
    
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
    samples: List[Dict[str, Any]]
) -> np.ndarray:
    """Evaluate all norms on all samples.
    
    Args:
        norms: List of norm dictionaries
        samples: List of feature assignments
    
    Returns:
        Boolean numpy array of shape (n_norms, n_samples)
    """
    n_norms = len(norms)
    n_samples = len(samples)
    applicability = np.zeros((n_norms, n_samples), dtype=bool)

    # Parse all norms first
    norm_asts = []
    for norm in norms:
        applies_if = norm.get('attributes', {}).get('applies_if', '')
        ast = parse_applies_if(applies_if)
        norm_asts.append(ast)

    # Evaluate each norm on each sample
    for i, ast in enumerate(norm_asts):
        if ast is None:
            continue
        
        for j, assignment in enumerate(samples):
            result = evaluate_with_assignment(ast, assignment)
            if result == TristateValue.TRUE:
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
            
            # Check if val is in the bin
            in_bin = True
            if bin_low is not None and val <= bin_low:
                in_bin = False
            if bin_high is not None and val > bin_high:
                in_bin = False
            
            if in_bin:
                mask[j] = True
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


def compute_information_gain(
    norms: List[Dict[str, Any]],
    schema: FeatureSchema,
    n_samples: int,
    seed: int,
    costs: Optional[Dict[str, float]] = None,
    include_features: Optional[List[str]] = None,
    exclude_features: Optional[List[str]] = None
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
    
    Returns:
        DataFrame with IG results
    """
    # Generate samples
    print(f"Generating {n_samples} samples...")
    samples = generate_samples(schema, n_samples, seed)

    # Evaluate norms on samples
    print(f"Evaluating {len(norms)} norms on samples...")
    applicability = evaluate_norms_on_samples(norms, samples)

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
            'categories_or_bins': values_str
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
    with open(args.input, 'r') as f:
        data = json.load(f)

    # Extract norms
    extractions = data.get('extractions', [])
    norms = [e for e in extractions if e.get('extraction_class') == 'NORM']
    
    if not norms:
        print("No NORM extractions found!")
        sys.exit(1)

    print(f"Found {len(norms)} norms")

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
        exclude_features=args.exclude
    )

    # Save CSV
    print(f"Saving results to {args.output}...")
    df.to_csv(args.output, index=False)

    # Print table
    print("\nTop 20 features by IG per cost:")
    table_data = df.head(20)[['feature', 'IG', 'cost', 'IG_per_cost', 'num_values', 'numeric']].values
    headers = ['Feature', 'IG', 'Cost', 'IG/Cost', '#Values', 'Numeric?']
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
