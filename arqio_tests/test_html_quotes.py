#!/usr/bin/env python3
"""Test script for HTML quotes in JSON parsing."""

from langextract import resolver as resolver_lib
from langextract.core import data

def test_html_quotes_parsing():
    """Test parsing JSON that contains HTML with attribute quotes."""
    resolver = resolver_lib.Resolver(
        format_type=data.FormatType.JSON,
        fence_output=False
    )
    
    # Test case 1: Simple HTML with quoted attributes
    json_with_html = '''
    {
      "extractions": [{
        "result": "<table><tr><td colspan=\"4\">Cell content</td></tr></table>",
        "status": "success"
      }]
    }
    '''
    
    print("Testing HTML quotes in JSON...")
    try:
        result = resolver._extract_and_parse_content(json_with_html)
        print("✓ Parsing succeeded!")
        print(f"Parsed result: {result}")
    except Exception as e:
        print(f"✗ Parsing failed: {e}")
        return False
    
    # Test case 2: More complex HTML with multiple quoted attributes
    complex_html_json = '''
    {
      "extractions": [{
        "entity": "table_data", 
        "text": "<div class=\"container\"><table border=\"1\" cellpadding=\"2\"><tr><td colspan=\"4\" style=\"text-align:center\">Header</td></tr><tr><td>A</td><td>B</td><td>C</td><td>D</td></tr></table></div>",
        "attributes": {"type": "structured_data"}
      }]
    }
    '''
    
    print("\nTesting complex HTML with multiple quotes...")
    try:
        result = resolver._extract_and_parse_content(complex_html_json)
        print("✓ Complex parsing succeeded!")
        print(f"Parsed result keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}")
    except Exception as e:
        print(f"✗ Complex parsing failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_html_quotes_parsing()
    if success:
        print("\n🎉 All HTML quote parsing tests passed!")
    else:
        print("\n❌ Some tests failed.")