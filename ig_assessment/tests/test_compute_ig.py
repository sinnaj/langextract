"""Tests for Information Gain computation."""

import json
import pytest
from pathlib import Path
import numpy as np

from compute_ig import (
    binary_entropy,
    generate_samples,
    evaluate_norms_on_samples,
    compute_base_entropy,
    compute_information_gain,
)
from feature_schema import extract_features_from_norms


def test_binary_entropy():
    """Test binary entropy function."""
    # h(0) = 0
    assert binary_entropy(0.0) == 0.0
    
    # h(1) = 0
    assert binary_entropy(1.0) == 0.0
    
    # h(0.5) = 1 (maximum entropy)
    assert abs(binary_entropy(0.5) - 1.0) < 0.0001
    
    # h(0.25) ≈ 0.811
    assert abs(binary_entropy(0.25) - 0.811) < 0.01


def test_generate_samples():
    """Test sample generation."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    samples = generate_samples(schema, n_samples=100, seed=42)
    
    assert len(samples) == 100
    assert all(isinstance(s, dict) for s in samples)
    
    # Check that samples contain feature assignments
    for sample in samples:
        assert "AREA.USAGE" in sample
        assert "AREA.SIZE" in sample


def test_evaluate_norms_on_samples():
    """Test evaluating norms on samples."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    samples = generate_samples(schema, n_samples=100, seed=42)
    applicability = evaluate_norms_on_samples(norms, samples)
    
    assert applicability.shape == (len(norms), 100)
    assert applicability.dtype == bool


def test_compute_base_entropy():
    """Test base entropy computation."""
    # Create a simple applicability matrix
    # 2 norms, 4 samples
    applicability = np.array([
        [True, True, False, False],  # norm 1: p=0.5
        [True, False, False, False],  # norm 2: p=0.25
    ])
    
    entropy = compute_base_entropy(applicability)
    
    # h(0.5) + h(0.25) ≈ 1.0 + 0.811 ≈ 1.811
    assert abs(entropy - 1.811) < 0.01


def test_ig_computation_on_toy_data():
    """Test IG computation on toy data."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Compute IG with small sample size for speed
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=1000,
        seed=42,
        costs=None
    )
    
    assert len(df) > 0
    assert "feature" in df.columns
    assert "IG" in df.columns
    assert "IG_per_cost" in df.columns
    
    # Check that IG values are non-negative
    assert (df["IG"] >= 0).all()
    
    # AREA.USAGE should have high IG since most norms depend on it
    area_usage_ig = df[df["feature"] == "AREA.USAGE"]["IG"].iloc[0]
    
    # TRUE literal norm should have zero IG contribution
    # Overall, AREA.USAGE should be one of the top features
    top_features = df.head(5)["feature"].tolist()
    assert "AREA.USAGE" in top_features


def test_ig_ranking():
    """Test that IG rankings make sense.
    
    With the toy data:
    - AREA.USAGE gates 5 out of 6 norms (parking, residential, storage, assembly, commercial)
    - AREA.SIZE gates 2 norms (parking if >100, commercial if >500)
    - AREA.OCCUPANCY gates 1 norm (assembly if >500)
    - AREA.FIRE.LOAD_TOTAL_CORRECTED gates 1 norm (storage if >=3000000)
    
    Expected: AREA.USAGE should have the highest IG.
    """
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Use larger sample size for more stable results
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=5000,
        seed=42,
        costs=None
    )
    
    # Sort by IG descending
    df = df.sort_values('IG', ascending=False)
    
    # AREA.USAGE should be at or near the top
    top_feature = df.iloc[0]["feature"]
    
    # Either AREA.USAGE is first, or it's in top 3
    top_3 = df.head(3)["feature"].tolist()
    assert "AREA.USAGE" in top_3
    
    print(f"Top feature by IG: {top_feature}")
    print("\nTop 5 features:")
    print(df.head(5)[["feature", "IG", "IG_per_cost"]])


def test_costs_integration():
    """Test that costs are properly integrated."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Define different costs for features
    costs = {
        "AREA.USAGE": 0.1,  # cheap
        "AREA.SIZE": 0.5,   # medium
        "AREA.OCCUPANCY": 1.0,  # expensive
    }
    
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=1000,
        seed=42,
        costs=costs
    )
    
    # Check that costs are applied
    assert df[df["feature"] == "AREA.USAGE"]["cost"].iloc[0] == 0.1
    assert df[df["feature"] == "AREA.SIZE"]["cost"].iloc[0] == 0.5
    
    # Check that IG_per_cost is computed correctly
    for _, row in df.iterrows():
        expected_ig_per_cost = row["IG"] / row["cost"]
        assert abs(row["IG_per_cost"] - expected_ig_per_cost) < 0.0001


def test_feature_filtering():
    """Test include/exclude feature filtering."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Include only specific features
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=500,
        seed=42,
        costs=None,
        include_features=["AREA.USAGE", "AREA.SIZE"]
    )
    
    assert len(df) == 2
    assert set(df["feature"]) == {"AREA.USAGE", "AREA.SIZE"}
    
    # Exclude specific features
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=500,
        seed=42,
        costs=None,
        exclude_features=["AREA.OCCUPANCY"]
    )
    
    assert "AREA.OCCUPANCY" not in df["feature"].tolist()
