#!/usr/bin/env python3
"""Tests for Sandbox API endpoints."""

import json
import sys
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "ig_assessment"))

def test_ig_csv_parsing():
    """Test parsing of ig.csv into feature definitions."""
    import csv
    
    ig_csv_path = Path(__file__).parent.parent / "ig_assessment" / "tmp" / "ig.csv"
    
    if not ig_csv_path.exists():
        print("⚠️  ig.csv not found, skipping test")
        return True
    
    try:
        features = []
        with open(ig_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                feature_name = row.get('feature', '')
                numeric = row.get('numeric', 'False').strip().lower() == 'true'
                categories_or_bins = row.get('categories_or_bins', '[]').strip()
                
                # Parse categories_or_bins
                values = []
                feature_type = 'categorical'
                
                if categories_or_bins and categories_or_bins not in ['[]', '0']:
                    try:
                        import ast
                        parsed = ast.literal_eval(categories_or_bins)
                        if isinstance(parsed, list):
                            if numeric and parsed:
                                feature_type = 'bin'
                                values = [str(b) for b in parsed]
                            else:
                                feature_type = 'categorical'
                                values = parsed
                    except Exception:
                        pass
                
                if numeric and not values:
                    feature_type = 'int'
                
                features.append({
                    'name': feature_name,
                    'type': feature_type,
                    'values': values,
                    'numeric': numeric
                })
        
        print(f"✓ Parsed {len(features)} features from ig.csv")
        
        # Validate some expected features
        feature_names = {f['name'] for f in features}
        assert 'BUILDING.USAGE' in feature_names, "Expected BUILDING.USAGE feature"
        
        # Find BUILDING.USAGE and validate it's categorical with values
        building_usage = next((f for f in features if f['name'] == 'BUILDING.USAGE'), None)
        assert building_usage is not None, "BUILDING.USAGE not found"
        assert building_usage['type'] == 'categorical', f"Expected categorical, got {building_usage['type']}"
        assert len(building_usage['values']) > 0, "Expected values for BUILDING.USAGE"
        
        print(f"✓ BUILDING.USAGE has {len(building_usage['values'])} categories")
        
        return True
        
    except Exception as e:
        print(f"✗ Error parsing ig.csv: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tristate_evaluator():
    """Test tri-state evaluator with partial assignments."""
    from dsl_parser import parse_applies_if
    from evaluator import Evaluator, TristateValue
    
    try:
        # Test 1: Simple TRUE case
        ast = parse_applies_if("BUILDING.USAGE == 'EDUCATION'")
        evaluator = Evaluator({'BUILDING.USAGE': 'EDUCATION'})
        result = evaluator.evaluate(ast)
        assert result == TristateValue.TRUE, f"Expected TRUE, got {result}"
        print("✓ Tri-state evaluator: TRUE case works")
        
        # Test 2: Simple FALSE case
        evaluator = Evaluator({'BUILDING.USAGE': 'RESIDENTIAL.HOUSING'})
        result = evaluator.evaluate(ast)
        assert result == TristateValue.FALSE, f"Expected FALSE, got {result}"
        print("✓ Tri-state evaluator: FALSE case works")
        
        # Test 3: UNKNOWN case (feature not in assignment)
        evaluator = Evaluator({'OTHER_FEATURE': 'value'})
        result = evaluator.evaluate(ast)
        assert result == TristateValue.UNKNOWN, f"Expected UNKNOWN, got {result}"
        print("✓ Tri-state evaluator: UNKNOWN case works")
        
        # Test 4: IN operator
        ast = parse_applies_if("BUILDING.USAGE IN ['EDUCATION', 'COMMERCIAL']")
        evaluator = Evaluator({'BUILDING.USAGE': 'EDUCATION'})
        result = evaluator.evaluate(ast)
        assert result == TristateValue.TRUE, f"Expected TRUE for IN, got {result}"
        print("✓ Tri-state evaluator: IN operator works")
        
        # Test 5: AND operator with partial assignment
        ast = parse_applies_if("BUILDING.USAGE == 'EDUCATION' AND BUILDING.AREA.TOTAL > 1000")
        evaluator = Evaluator({'BUILDING.USAGE': 'EDUCATION'})
        result = evaluator.evaluate(ast)
        assert result == TristateValue.UNKNOWN, f"Expected UNKNOWN for partial AND, got {result}"
        print("✓ Tri-state evaluator: Partial AND returns UNKNOWN")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing tri-state evaluator: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_filtering_logic():
    """Test norm filtering logic."""
    from dsl_parser import parse_applies_if
    from evaluator import Evaluator, TristateValue
    
    try:
        # Mock norms with different applies_if conditions
        norms = [
            {
                'attributes': {
                    'id': 'norm1',
                    'applies_if': 'BUILDING.USAGE == "EDUCATION"'
                }
            },
            {
                'attributes': {
                    'id': 'norm2',
                    'applies_if': 'BUILDING.USAGE == "RESIDENTIAL.HOUSING"'
                }
            },
            {
                'attributes': {
                    'id': 'norm3',
                    'applies_if': 'TRUE'  # Always applies
                }
            },
            {
                'attributes': {
                    'id': 'norm4',
                    'applies_if': 'DOOR.TYPE == "REVOLVING"'  # Different feature
                }
            }
        ]
        
        # Filter with BUILDING.USAGE == EDUCATION
        assignment = {'BUILDING.USAGE': 'EDUCATION'}
        filtered = []
        
        for norm in norms:
            applies_if = norm['attributes']['applies_if']
            ast = parse_applies_if(applies_if)
            evaluator = Evaluator(assignment)
            result = evaluator.evaluate(ast)
            
            # Keep if TRUE or UNKNOWN, exclude if FALSE
            if result != TristateValue.FALSE:
                filtered.append(norm)
        
        # Should keep: norm1 (TRUE), norm3 (TRUE), norm4 (UNKNOWN - different feature)
        # Should exclude: norm2 (FALSE)
        assert len(filtered) == 3, f"Expected 3 norms, got {len(filtered)}"
        
        filtered_ids = {n['attributes']['id'] for n in filtered}
        assert 'norm1' in filtered_ids, "norm1 should be kept (TRUE)"
        assert 'norm2' not in filtered_ids, "norm2 should be excluded (FALSE)"
        assert 'norm3' in filtered_ids, "norm3 should be kept (TRUE)"
        assert 'norm4' in filtered_ids, "norm4 should be kept (UNKNOWN)"
        
        print("✓ Filtering logic: correctly keeps/excludes norms based on tri-state evaluation")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing filtering logic: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("SANDBOX API TESTS")
    print("=" * 60)
    
    success = True
    
    print("\n1. Testing ig.csv parsing...")
    success = test_ig_csv_parsing() and success
    
    print("\n2. Testing tri-state evaluator...")
    success = test_tristate_evaluator() and success
    
    print("\n3. Testing filtering logic...")
    success = test_filtering_logic() and success
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)
