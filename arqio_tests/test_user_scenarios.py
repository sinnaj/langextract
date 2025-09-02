#!/usr/bin/env python3
"""Test the actual user scenarios that were failing."""

from langextract import resolver as resolver_lib
from langextract.core import data

def test_user_scenarios():
    """Test the specific scenarios the user reported."""
    resolver = resolver_lib.Resolver(
        format_type=data.FormatType.JSON,
        fence_output=False
    )
    
    print("Testing user scenarios:")
    
    # Test case 1: LaTeX-style sequences from the user's original report
    latex_json = '''
    {
      "extractions": [{
        "entity": "measurement", 
        "text": "Temperature: $30^{\\circ}$ and notation: $\\mathsf{E}1_{2}$",
        "attributes": {"type": "mathematical"}
      }]
    }
    '''
    
    print("\n1. LaTeX sequences test:")
    try:
        result = resolver._extract_and_parse_content(latex_json)
        print("✓ LaTeX parsing succeeded!")
        print(f"Parsed LaTeX content: {result['extractions'][0]['text']}")
        success_latex = True
    except Exception as e:
        print(f"✗ LaTeX parsing failed: {e}")
        success_latex = False
    
    # Test case 2: HTML table content from the user's latest error
    html_json = '''
    {
      "extractions": [{
        "entity": "table_content",
        "text": "<table><tr><td colspan=\"4\" style=\"text-align:center\">Header Cell</td></tr><tr><td>A</td><td>B</td><td>C</td><td>D</td></tr></table>",
        "attributes": {"type": "structured_data"}
      }]
    }
    '''
    
    print("\n2. HTML table test:")
    try:
        result = resolver._extract_and_parse_content(html_json)
        print("✓ HTML table parsing succeeded!")
        print(f"Parsed HTML content: {result['extractions'][0]['text'][:100]}...")
        success_html = True
    except Exception as e:
        print(f"✗ HTML table parsing failed: {e}")
        success_html = False
    
    # Test case 3: Combined LaTeX and HTML 
    combined_json = '''
    {
      "extractions": [
        {
          "entity": "math_formula",
          "text": "The angle $\\theta = 30^{\\circ}$ in equation $\\mathsf{E} = mc^2$"
        },
        {
          "entity": "table_data", 
          "text": "<table border=\"1\"><tr><td colspan=\"2\">Results</td></tr><tr><td>Value</td><td>$\\pi \\approx 3.14$</td></tr></table>"
        }
      ]
    }
    '''
    
    print("\n3. Combined LaTeX + HTML test:")
    try:
        result = resolver._extract_and_parse_content(combined_json)
        print("✓ Combined parsing succeeded!")
        print(f"LaTeX part: {result['extractions'][0]['text']}")
        print(f"HTML part: {result['extractions'][1]['text'][:80]}...")
        success_combined = True
    except Exception as e:
        print(f"✗ Combined parsing failed: {e}")
        success_combined = False
    
    # Summary
    total_tests = 3
    passed_tests = sum([success_latex, success_html, success_combined])
    
    print(f"\n" + "="*60)
    print(f"TEST SUMMARY: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All user scenario tests PASSED!")
        return True
    else:
        print("❌ Some tests failed - more work needed.")
        return False

if __name__ == "__main__":
    test_user_scenarios()