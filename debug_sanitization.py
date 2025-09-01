#!/usr/bin/env python3
"""Debug the HTML quotes sanitization logic."""

def test_simple_html_escaping():
    """Test our escaping logic on problematic HTML in JSON."""
    import json
    
    # This is the problematic JSON that fails parsing
    test_cases = [
        # Simple HTML attribute
        '{"result": "<td colspan=\\"4\\">Cell</td>"}',  # Already escaped - should work
        '{"result": "<td colspan=\"4\">Cell</td>"}',    # Unescaped - breaks JSON
    ]
    
    for i, test_json in enumerate(test_cases):
        print(f"\nTest case {i+1}:")
        print(f"JSON: {repr(test_json)}")
        
        try:
            parsed = json.loads(test_json)
            print("✓ Parses successfully!")
            print(f"Result: {parsed['result']}")
        except Exception as e:
            print(f"✗ Parse failed: {e}")
            
    # Now test our sanitization approach
    print("\n" + "="*50)
    print("Testing manual sanitization:")
    
    problematic_json = '{"result": "<td colspan=\"4\">Cell</td>"}'
    print(f"Original: {repr(problematic_json)}")
    
    # Manual escaping approach: escape quotes inside HTML attributes within JSON strings
    def escape_html_quotes_in_json(s):
        """Simple approach: escape all quotes inside JSON string values."""
        import re
        
        # Pattern to match JSON string values and escape internal quotes
        def escape_internal_quotes(match):
            json_key = match.group(1)  # The key part
            json_value_content = match.group(2)  # The content between quotes
            # Escape any remaining quotes in the content
            escaped_content = json_value_content.replace('"', '\\"')
            return f'"{json_key}": "{escaped_content}"'
        
        # Pattern: "key": "value with potential unescaped quotes"
        pattern = r'"([^"]+)": "([^"]*(?:[^"\\]|\\.[^"]*)*)"'
        result = re.sub(pattern, escape_internal_quotes, s)
        return result
    
    sanitized = escape_html_quotes_in_json(problematic_json)
    print(f"Sanitized: {repr(sanitized)}")
    
    try:
        parsed = json.loads(sanitized)
        print("✓ Sanitized version parses successfully!")
        print(f"Result: {parsed['result']}")
    except Exception as e:
        print(f"✗ Sanitized version still fails: {e}")

if __name__ == "__main__":
    test_simple_html_escaping()