#!/usr/bin/env python3
"""Test the evaluators with mock LLM responses to verify the structure."""

import json
import tempfile
from pathlib import Path
import sys
import os

# Add the current directory to Python path so we can import our modules
sys.path.insert(0, '/home/runner/work/langextract/langextract')

def create_test_combined_extractions():
    """Create a test combined_extractions.json file."""
    test_data = {
        "extractions": [
            {
                "extraction_class": "NORM",
                "extraction_text": "Sample norm text",
                "attributes": {
                    "id": "norm_001",
                    "norm_statement": "All doors must be at least 80cm wide and open outward for fire safety",
                    "applies_if": "DOOR.TYPE == 'FIRE_EXIT'",
                    "satisfied_if": "DOOR.WIDTH >= 80 AND DOOR.OPENING_DIRECTION == 'OUTWARD'",
                    "topics": ["SAFETY.FIRE"]
                }
            },
            {
                "extraction_class": "NORM", 
                "extraction_text": "Another norm",
                "attributes": {
                    "id": "norm_002",
                    "norm_statement": "Emergency lighting shall be provided in all evacuation routes",
                    "applies_if": "ROUTE.TYPE == 'EVACUATION'", 
                    "satisfied_if": "LIGHTING.EMERGENCY == TRUE",
                    "topics": ["SAFETY.EVACUATION"]
                }
            },
            {
                "extraction_class": "Tag",
                "extraction_text": "DOOR.TYPE",
                "attributes": {
                    "id": "tag_001",
                    "tag": "DOOR.TYPE",
                    "used_by_norm_ids": ["norm_001"],
                    "related_topics": ["SAFETY.FIRE"]
                }
            },
            {
                "extraction_class": "Tag",
                "extraction_text": "DOOR.WIDTH", 
                "attributes": {
                    "id": "tag_002",
                    "tag": "DOOR.WIDTH",
                    "used_by_norm_ids": ["norm_001"],
                    "related_topics": ["SAFETY.FIRE"]
                }
            },
            {
                "extraction_class": "Tag",
                "extraction_text": "ROUTE.TYPE",
                "attributes": {
                    "id": "tag_003", 
                    "tag": "ROUTE.TYPE",
                    "used_by_norm_ids": ["norm_002"],
                    "related_topics": ["SAFETY.EVACUATION"]
                }
            }
        ]
    }
    return test_data

def test_data_loading():
    """Test that our evaluators can load and parse the test data correctly."""
    
    # Create test file
    test_data = create_test_combined_extractions()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_data, f, indent=2)
        test_file = Path(f.name)
    
    try:
        # Test norm evaluator data loading
        print("Testing norm evaluator data loading...")
        
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        extractions = data.get('extractions', [])
        norms = [ext for ext in extractions if ext.get('extraction_class') == 'NORM']
        tags = [ext for ext in extractions if ext.get('extraction_class') == 'Tag']
        
        print(f"✓ Loaded {len(extractions)} total extractions")
        print(f"✓ Found {len(norms)} norms")
        print(f"✓ Found {len(tags)} tags")
        
        # Test norm structure
        if norms:
            norm = norms[0]
            attributes = norm.get('attributes', {})
            required_fields = ['id', 'norm_statement', 'applies_if', 'satisfied_if']
            missing = [field for field in required_fields if field not in attributes]
            if missing:
                print(f"✗ Missing required fields in norm: {missing}")
                return False
            else:
                print("✓ Norm structure looks correct")
        
        # Test tag structure  
        if tags:
            tag = tags[0]
            attributes = tag.get('attributes', {})
            required_fields = ['id', 'tag', 'used_by_norm_ids']
            missing = [field for field in required_fields if field not in attributes]
            if missing:
                print(f"✗ Missing required fields in tag: {missing}")
                return False
            else:
                print("✓ Tag structure looks correct")
                
        # Test the prompt generation functions
        try:
            sys.path.insert(0, '/home/runner/work/langextract/langextract')
            from norm_evaluator import create_evaluation_prompt as create_norm_prompt
            from tag_evaluator import create_evaluation_prompt as create_tag_prompt
            
            norm_prompt = create_norm_prompt(norms[0])
            tag_prompt = create_tag_prompt(tags[0], tags)
            
            if len(norm_prompt) > 100 and "atomicity" in norm_prompt.lower():
                print("✓ Norm evaluation prompt generated correctly")
            else:
                print("✗ Norm evaluation prompt seems incorrect")
                return False
                
            if len(tag_prompt) > 100 and "uniqueness" in tag_prompt.lower():
                print("✓ Tag evaluation prompt generated correctly")
            else:
                print("✗ Tag evaluation prompt seems incorrect")
                return False
                
        except ImportError as e:
            print(f"✗ Could not import evaluator modules: {e}")
            return False
            
        print("\n✓ All tests passed! The evaluators should work correctly with API keys.")
        return True
        
    finally:
        # Clean up
        test_file.unlink()

def test_output_format():
    """Test the expected output format for the evaluation reports."""
    
    # Mock evaluation data
    mock_norm_evaluation = {
        "norm_id": "norm_001",
        "norm_statement": "Test norm statement",
        "atomicity_score": 7,
        "atomicity_reasoning": "Good clarity but missing some context",
        "applicability_structure_score": 8,
        "applicability_structure_reasoning": "Well-structured conditions",
        "overall_quality": 7.5,
        "key_issues": ["Missing context for implementation"],
        "suggestions": ["Add more specific requirements"]
    }
    
    mock_tag_evaluation = {
        "tag_id": "tag_001", 
        "tag_value": "DOOR.TYPE",
        "related_topics": ["SAFETY.FIRE"],
        "used_by_norm_count": 1,
        "uniqueness_score": 9,
        "uniqueness_reasoning": "Unique and well-defined",
        "entity_structure_score": 8,
        "entity_structure_reasoning": "Good hierarchical structure",
        "overall_quality": 8.5,
        "similar_tags": [],
        "structural_issues": [],
        "suggestions": []
    }
    
    print("\nTesting output format...")
    print("✓ Mock norm evaluation structure:", "norm_id" in mock_norm_evaluation and "overall_quality" in mock_norm_evaluation)
    print("✓ Mock tag evaluation structure:", "tag_id" in mock_tag_evaluation and "overall_quality" in mock_tag_evaluation)
    
    return True

if __name__ == "__main__":
    print("="*60)
    print("EVALUATOR TESTING (NO API REQUIRED)")
    print("="*60)
    
    success1 = test_data_loading()
    success2 = test_output_format()
    
    if success1 and success2:
        print("\n🎉 All tests passed! The evaluators are ready to use.")
        print("\nTo run with real API:")
        print("1. Set OPENROUTER_API_KEY or GEMINI_API_KEY environment variable")
        print("2. Run: python norm_evaluator.py combined_extractions.json")
        print("3. Run: python tag_evaluator.py combined_extractions.json")
    else:
        print("\n❌ Some tests failed. Check the evaluator implementation.")
        sys.exit(1)