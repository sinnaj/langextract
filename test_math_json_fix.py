#!/usr/bin/env python3
"""
Test script to verify that mathematical expressions with % and other symbols 
are properly handled in JSON sanitization
"""

import json
import sys
from pathlib import Path

# Add the current directory to Python path so we can import langextract
sys.path.insert(0, str(Path(__file__).parent))

from langextract.resolver import Resolver
from langextract import data


def test_mathematical_expressions():
    """Test that mathematical expressions like $80\%$ are properly sanitized"""
    
    # Create a resolver instance
    resolver = Resolver(format_type=data.FormatType.JSON, fence_output=False)
    
    # Test case 1: The specific problematic case from the error
    problematic_json = '''
    {
      "extractions": [
        {
          "extraction_class": "NORM",
          "extraction_text": "La anchura de calculo de un elemento debe ser al menos igual al $80\\%$ de la anchura de calculo de otro elemento",
          "attributes": {
            "norm_id": "N::000001",
            "text": "width calculation requirement with percentage"
          }
        }
      ]
    }
    '''
    
    print("Testing mathematical expression with \\% (problematic case)...")
    try:
        result = resolver._extract_and_parse_content(problematic_json)
        print("✓ Successfully parsed JSON with mathematical expression $80\\%$")
        print(f"Parsed content has {len(result.get('extractions', []))} extractions")
    except Exception as e:
        print(f"✗ Failed to parse: {e}")
        return False
    
    # Test case 2: Other mathematical symbols
    math_symbols_json = '''
    {
      "extractions": [
        {
          "extraction_class": "NORM", 
          "extraction_text": "Mathematical expressions: $\\mathsf{A} + B\\$ and \\{x: x > 0\\} and \\& operator",
          "attributes": {
            "norm_id": "N::000002",
            "text": "various math symbols"
          }
        }
      ]
    }
    '''
    
    print("\nTesting other mathematical symbols...")
    try:
        result = resolver._extract_and_parse_content(math_symbols_json)
        print("✓ Successfully parsed JSON with various mathematical symbols")
        print(f"Parsed content has {len(result.get('extractions', []))} extractions")
    except Exception as e:
        print(f"✗ Failed to parse: {e}")
        return False
    
    # Test case 3: Mixed content with both HTML and mathematical expressions
    mixed_content_json = '''
    {
      "extractions": [
        {
          "extraction_class": "NORM",
          "extraction_text": "<td colspan=\\"4\\">Table cell with $90\\%$ width requirement</td>",
          "attributes": {
            "norm_id": "N::000003", 
            "text": "HTML and math combined"
          }
        }
      ]
    }
    '''
    
    print("\nTesting mixed HTML and mathematical content...")
    try:
        result = resolver._extract_and_parse_content(mixed_content_json)
        print("✓ Successfully parsed JSON with mixed HTML and mathematical content")
        print(f"Parsed content has {len(result.get('extractions', []))} extractions")
    except Exception as e:
        print(f"✗ Failed to parse: {e}")
        return False
    
    print("\n🎉 All mathematical expression tests passed!")
    return True


def test_edge_cases():
    """Test edge cases to ensure we didn't break existing functionality"""
    
    resolver = Resolver(format_type=data.FormatType.JSON, fence_output=False)
    
    # Test normal JSON still works
    normal_json = '''
    {
      "extractions": [
        {
          "extraction_class": "NORM",
          "extraction_text": "Normal text without special characters",
          "attributes": {
            "norm_id": "N::000001"
          }
        }
      ]
    }
    '''
    
    print("Testing normal JSON...")
    try:
        result = resolver._extract_and_parse_content(normal_json)
        print("✓ Normal JSON still works correctly")
    except Exception as e:
        print(f"✗ Normal JSON failed: {e}")
        return False
    
    # Test valid escape sequences still work
    valid_escapes_json = '''
    {
      "extractions": [
        {
          "extraction_class": "NORM",
          "extraction_text": "Text with valid escapes: \\"quoted\\" and \\n newline and \\u00A0 unicode",
          "attributes": {
            "norm_id": "N::000002"
          }
        }
      ]
    }
    '''
    
    print("Testing valid JSON escape sequences...")
    try:
        result = resolver._extract_and_parse_content(valid_escapes_json)
        print("✓ Valid JSON escape sequences still work")
    except Exception as e:
        print(f"✗ Valid escapes failed: {e}")
        return False
    
    print("✓ Edge case tests passed!")
    return True


if __name__ == "__main__":
    print("🧪 Testing JSON sanitization fixes for mathematical expressions")
    print("=" * 70)
    
    success = True
    
    try:
        success &= test_mathematical_expressions()
        success &= test_edge_cases()
        
        if success:
            print("\n✅ All tests passed! The JSON sanitization fix is working correctly.")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)