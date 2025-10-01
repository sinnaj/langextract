"""Tests for dismissal statistics in IG computation."""

import json
import pytest
from pathlib import Path
import numpy as np

from compute_ig import (
    compute_dismissal_stats,
    generate_samples,
    evaluate_norms_on_samples,
    compute_information_gain,
)
from feature_schema import extract_features_from_norms


def test_dismissal_stats_basic():
    """Test basic dismissal statistics computation."""
    # Create a simple test case
    # 2 norms, 4 samples
    # Norm 0 applies when feature is in certain categories
    # Norm 1 always applies
    applicability = np.array([
        [True, True, False, False],  # norm 0: applies for samples 0,1
        [True, True, True, True],     # norm 1: always applies
    ])
    
    samples = [
        {'AREA.USAGE': 'PARKING'},
        {'AREA.USAGE': 'PARKING'},
        {'AREA.USAGE': 'RESIDENTIAL'},
        {'AREA.USAGE': 'RESIDENTIAL'},
    ]
    
    # Mock schema
    class MockSchema:
        def get_feature_values(self, feature):
            return ['PARKING', 'RESIDENTIAL']
        
        def is_numeric(self, feature):
            return False
    
    schema = MockSchema()
    
    max_dismissal, avg_dismissal, best_value = compute_dismissal_stats(
        applicability, samples, 'AREA.USAGE', schema
    )
    
    # RESIDENTIAL dismisses 1 out of 2 norms (50%)
    # PARKING dismisses 0 out of 2 norms (0%)
    # So max_dismissal should be 0.5
    assert max_dismissal == 0.5
    assert best_value == 'RESIDENTIAL'
    # Average dismissal: (0.5 + 0.0) / 2 = 0.25
    assert avg_dismissal == 0.25


def test_dismissal_with_project_type():
    """Test dismissal with PROJECT.TYPE example from issue."""
    test_data = {
        "pipeline_info": {
            "version": "test",
            "total_extractions": 3
        },
        "extractions": [
            {
                "extraction_class": "NORM",
                "extraction_text": "Reform projects require permits",
                "attributes": {
                    "id": "reform_permit",
                    "norm_statement": "Reform projects require permits",
                    "applies_if": "PROJECT.TYPE == 'REFORM'",
                    "satisfied_if": "HAS(PERMIT)",
                    "obligation_type": "MANDATORY"
                }
            },
            {
                "extraction_class": "NORM",
                "extraction_text": "New construction requires review",
                "attributes": {
                    "id": "new_review",
                    "norm_statement": "New construction requires review",
                    "applies_if": "PROJECT.TYPE == 'NEW_CONSTRUCTION'",
                    "satisfied_if": "HAS(REVIEW)",
                    "obligation_type": "MANDATORY"
                }
            },
            {
                "extraction_class": "NORM",
                "extraction_text": "All projects need documentation",
                "attributes": {
                    "id": "all_docs",
                    "norm_statement": "All projects need documentation",
                    "applies_if": "TRUE",
                    "satisfied_if": "HAS(DOCS)",
                    "obligation_type": "MANDATORY"
                }
            }
        ]
    }
    
    norms = [e for e in test_data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Compute IG with dismissal stats
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=2000,
        seed=42,
        costs=None
    )
    
    # PROJECT.TYPE should be in the results
    assert 'PROJECT.TYPE' in df['feature'].values
    
    # Get PROJECT.TYPE row
    pt_row = df[df['feature'] == 'PROJECT.TYPE'].iloc[0]
    
    # PROJECT.TYPE should have some dismissal rate
    # Each value dismisses 1 norm out of 3 (33.3%)
    # Both NEW_CONSTRUCTION and REFORM dismiss one norm each
    assert pt_row['max_dismissal_rate'] > 0.0
    assert pt_row['max_dismissal_rate'] <= 1.0
    
    # Check that best_dismissal_value is one of the valid values
    assert pt_row['best_dismissal_value'] in ['NEW_CONSTRUCTION', 'REFORM']


def test_dismissal_with_numeric_features():
    """Test dismissal statistics with numeric features."""
    test_data = {
        "pipeline_info": {
            "version": "test",
            "total_extractions": 2
        },
        "extractions": [
            {
                "extraction_class": "NORM",
                "extraction_text": "Large areas require fire alarms",
                "attributes": {
                    "id": "large_alarm",
                    "norm_statement": "Large areas require fire alarms",
                    "applies_if": "AREA.SIZE > 500",
                    "satisfied_if": "HAS(FIRE.ALARM)",
                    "obligation_type": "MANDATORY"
                }
            },
            {
                "extraction_class": "NORM",
                "extraction_text": "Small areas require extinguisher",
                "attributes": {
                    "id": "small_extinguisher",
                    "norm_statement": "Small areas require extinguisher",
                    "applies_if": "AREA.SIZE <= 100",
                    "satisfied_if": "HAS(EXTINGUISHER)",
                    "obligation_type": "MANDATORY"
                }
            }
        ]
    }
    
    norms = [e for e in test_data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Compute IG with dismissal stats
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=2000,
        seed=42,
        costs=None
    )
    
    # AREA.SIZE should be in the results
    assert 'AREA.SIZE' in df['feature'].values
    
    # Get AREA.SIZE row
    size_row = df[df['feature'] == 'AREA.SIZE'].iloc[0]
    
    # AREA.SIZE should have some dismissal rate
    assert size_row['max_dismissal_rate'] > 0.0
    assert size_row['max_dismissal_rate'] <= 1.0
    
    # best_dismissal_value should be a bin string
    assert isinstance(size_row['best_dismissal_value'], str)
    # Should contain one of: ≤, >, or parentheses
    assert any(char in size_row['best_dismissal_value'] for char in ['≤', '>', '(', ')'])


def test_dismissal_full_integration():
    """Test dismissal metrics on the toy dataset."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Compute IG with dismissal stats
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=5000,
        seed=42,
        costs=None
    )
    
    # Check that all expected columns are present
    assert 'max_dismissal_rate' in df.columns
    assert 'avg_dismissal_rate' in df.columns
    assert 'best_dismissal_value' in df.columns
    
    # Check that values are in valid range
    assert (df['max_dismissal_rate'] >= 0.0).all()
    assert (df['max_dismissal_rate'] <= 1.0).all()
    assert (df['avg_dismissal_rate'] >= 0.0).all()
    assert (df['avg_dismissal_rate'] <= 1.0).all()
    
    # Check that max >= avg for each feature
    assert (df['max_dismissal_rate'] >= df['avg_dismissal_rate']).all()
    
    # AREA.USAGE should have the highest dismissal rate
    # because different usage types dismiss different norms
    max_dismissal_row = df.sort_values('max_dismissal_rate', ascending=False).iloc[0]
    assert max_dismissal_row['feature'] == 'AREA.USAGE'
    
    # AREA.USAGE should dismiss a significant portion of norms
    area_usage_row = df[df['feature'] == 'AREA.USAGE'].iloc[0]
    assert area_usage_row['max_dismissal_rate'] > 0.5  # Should dismiss at least 50% of norms


def test_dismissal_ordering():
    """Test that dismissal statistics provide useful ordering."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Compute IG with dismissal stats
    df = compute_information_gain(
        norms=norms,
        schema=schema,
        n_samples=5000,
        seed=42,
        costs=None
    )
    
    # Sort by max_dismissal_rate
    df_by_dismissal = df.sort_values('max_dismissal_rate', ascending=False)
    
    # The top feature by dismissal should also have relatively high IG
    # (though not necessarily the highest)
    top_dismissal_feature = df_by_dismissal.iloc[0]['feature']
    top_dismissal_ig = df_by_dismissal.iloc[0]['IG']
    
    # Should be in top 50% by IG
    median_ig = df['IG'].median()
    assert top_dismissal_ig >= median_ig
    
    print(f"\nTop feature by dismissal: {top_dismissal_feature}")
    print(f"  Max dismissal rate: {df_by_dismissal.iloc[0]['max_dismissal_rate']:.4f}")
    print(f"  IG: {top_dismissal_ig:.4f}")
