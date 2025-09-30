"""Tests for feature schema extraction."""

import pytest
from pathlib import Path
from dsl_parser import parse_applies_if
from feature_schema import (
    FeatureExtractor,
    extract_features_from_norms,
    NumericFeature,
    CategoricalFeature,
)


def test_extract_numeric_feature():
    """Test extracting numeric feature with threshold."""
    ast = parse_applies_if("AREA.SIZE > 100")
    extractor = FeatureExtractor()
    extractor.extract_from_ast(ast)
    
    assert "AREA.SIZE" in extractor.numeric_features
    assert 100.0 in extractor.numeric_features["AREA.SIZE"].thresholds


def test_extract_categorical_feature():
    """Test extracting categorical feature."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING'")
    extractor = FeatureExtractor()
    extractor.extract_from_ast(ast)
    
    assert "AREA.USAGE" in extractor.categorical_features
    assert "PARKING" in extractor.categorical_features["AREA.USAGE"].categories


def test_extract_in_operation():
    """Test extracting features from IN operation."""
    ast = parse_applies_if("AREA.USAGE IN ['LODGING','COMMERCIAL','EDUCATION']")
    extractor = FeatureExtractor()
    extractor.extract_from_ast(ast)
    
    assert "AREA.USAGE" in extractor.categorical_features
    cats = extractor.categorical_features["AREA.USAGE"].categories
    assert "LODGING" in cats
    assert "COMMERCIAL" in cats
    assert "EDUCATION" in cats


def test_extract_multiple_thresholds():
    """Test extracting multiple thresholds for same feature."""
    expr = "(AREA.SIZE > 100) OR (AREA.SIZE > 500) OR (AREA.SIZE <= 250)"
    ast = parse_applies_if(expr)
    extractor = FeatureExtractor()
    extractor.extract_from_ast(ast)
    
    assert "AREA.SIZE" in extractor.numeric_features
    thresholds = extractor.numeric_features["AREA.SIZE"].thresholds
    assert 100.0 in thresholds
    assert 500.0 in thresholds
    assert 250.0 in thresholds


def test_derive_bins():
    """Test deriving bins from thresholds."""
    nf = NumericFeature("AREA.SIZE", thresholds=[100, 250, 500])
    nf.derive_bins()
    
    assert len(nf.bins) == 4
    # (-inf, 100], (100, 250], (250, 500], (500, inf)
    assert nf.bins[0] == (None, 100)
    assert nf.bins[1] == (100, 250)
    assert nf.bins[2] == (250, 500)
    assert nf.bins[3] == (500, None)


def test_derive_bins_single_threshold():
    """Test deriving bins with single threshold."""
    nf = NumericFeature("VALUE", thresholds=[100])
    nf.derive_bins()
    
    assert len(nf.bins) == 2
    assert nf.bins[0] == (None, 100)
    assert nf.bins[1] == (100, None)


def test_derive_bins_duplicate_thresholds():
    """Test deriving bins with duplicate thresholds."""
    nf = NumericFeature("VALUE", thresholds=[100, 100, 250, 250])
    nf.derive_bins()
    
    # Should deduplicate
    assert len(nf.bins) == 3
    assert nf.bins[0] == (None, 100)
    assert nf.bins[1] == (100, 250)
    assert nf.bins[2] == (250, None)


def test_extract_from_toy_norms():
    """Test extracting features from toy norms dataset."""
    test_file = Path(__file__).parent / "data" / "enhanced_extraction_results.min.json"
    
    import json
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    norms = [e for e in data['extractions'] if e.get('extraction_class') == 'NORM']
    schema = extract_features_from_norms(norms)
    
    # Check that key features are extracted
    assert "AREA.USAGE" in schema.all_feature_names
    assert "AREA.SIZE" in schema.all_feature_names
    assert "AREA.OCCUPANCY" in schema.all_feature_names
    assert "AREA.FIRE.LOAD_TOTAL_CORRECTED" in schema.all_feature_names
    
    # Check numeric features
    assert "AREA.SIZE" in schema.numeric_features
    assert "AREA.OCCUPANCY" in schema.numeric_features
    
    # Check categorical features
    assert "AREA.USAGE" in schema.categorical_features
    
    # Check that AREA.USAGE has the expected categories
    cats = schema.categorical_features["AREA.USAGE"].categories
    assert "PARKING" in cats
    assert "RESIDENTIAL.HOUSING" in cats
    assert "STORAGE" in cats
    assert "PUBLIC.ASSEMBLY" in cats


def test_uniform_priors():
    """Test computing uniform priors."""
    norms = [
        {
            "extraction_class": "NORM",
            "attributes": {
                "applies_if": "AREA.USAGE IN ['A','B','C']"
            }
        }
    ]
    
    schema = extract_features_from_norms(norms)
    schema.compute_uniform_priors()
    
    assert "AREA.USAGE" in schema.priors
    prior = schema.priors["AREA.USAGE"]
    
    # With Laplace smoothing (alpha=1), each category gets (1 + alpha) / (n + n*alpha)
    # For 3 categories: (1 + 1) / (3 + 3*1) = 2/6 = 1/3
    assert len(prior) == 3
    for cat in ["A", "B", "C"]:
        assert abs(prior[cat] - 1/3) < 0.01


def test_extract_has_operation():
    """Test extracting HAS operation."""
    ast = parse_applies_if("HAS(FIRE.EXTINGUISHER)")
    extractor = FeatureExtractor()
    extractor.extract_from_ast(ast)
    
    assert "FIRE.EXTINGUISHER" in extractor.categorical_features
    cats = extractor.categorical_features["FIRE.EXTINGUISHER"].categories
    assert "EXISTS" in cats
    assert "NOT_EXISTS" in cats


def test_complex_extraction():
    """Test extracting from complex expression."""
    expr = """AREA.USAGE != BUILDING.USAGE AND (
        (AREA.USAGE == 'RESIDENTIAL.HOUSING') OR
        (AREA.USAGE IN ['LODGING','ADMINISTRATIVE','COMMERCIAL','EDUCATION'] AND AREA.SIZE > 500) OR
        (AREA.USAGE == 'PUBLIC.ASSEMBLY' AND AREA.OCCUPANCY > 500) OR
        (AREA.USAGE == 'PARKING' AND AREA.SIZE > 100) OR
        (AREA.USAGE == 'STORAGE' AND AREA.FIRE.LOAD_TOTAL_CORRECTED >= 3000000)
    )"""
    
    ast = parse_applies_if(expr)
    extractor = FeatureExtractor()
    extractor.extract_from_ast(ast)
    
    # Check features extracted
    assert "AREA.USAGE" in extractor.all_identifiers
    assert "BUILDING.USAGE" in extractor.all_identifiers
    assert "AREA.SIZE" in extractor.all_identifiers
    assert "AREA.OCCUPANCY" in extractor.all_identifiers
    assert "AREA.FIRE.LOAD_TOTAL_CORRECTED" in extractor.all_identifiers
    
    # Check categories
    cats = extractor.categorical_features["AREA.USAGE"].categories
    assert "RESIDENTIAL.HOUSING" in cats
    assert "LODGING" in cats
    assert "PARKING" in cats
    assert "STORAGE" in cats
    
    # Check thresholds
    assert 100 in extractor.numeric_features["AREA.SIZE"].thresholds
    assert 500 in extractor.numeric_features["AREA.SIZE"].thresholds
    assert 500 in extractor.numeric_features["AREA.OCCUPANCY"].thresholds
    assert 3000000 in extractor.numeric_features["AREA.FIRE.LOAD_TOTAL_CORRECTED"].thresholds
