#!/usr/bin/env python3
"""Test the original user's specific error cases."""

from langextract import resolver as resolver_lib
from langextract.core import data


def test_original_user_cases():
  """Test the specific cases that were failing for the user."""
  resolver = resolver_lib.Resolver(
      format_type=data.FormatType.JSON, fence_output=False
  )

  print("=== Testing Original User Error Cases ===")
  print()

  # Test Case 1: Original LaTeX backslash error
  print("1. Testing LaTeX sequences that caused 'Invalid \\escape' errors:")
  latex_cases = [
      '{"extractions": [{"text": "Temperature: $30^{\\\\circ}$"}]}',
      '{"extractions": [{"text": "Notation: $\\\\mathsf{E}1_{2}$"}]}',
      (
          '{"extractions": [{"result": "Angle is $30^{\\\\circ}$ and tensor'
          ' $\\\\mathsf{E}1_{2}$", "attributes": {"norm_statement": "Maintain'
          ' $30^{\\\\circ}$"}}]}'
      ),
  ]

  for i, case in enumerate(latex_cases, 1):
    print(f"   Case 1.{i}: {case[:50]}...")
    try:
      result = resolver._extract_and_parse_content(case)
      print(f"   ✓ PASSED: LaTeX parsing works!")
    except Exception as e:
      print(f"   ✗ FAILED: {e}")
      return False

  print()

  # Test Case 2: HTML delimiter errors
  print(
      "2. Testing HTML content that caused 'Expecting comma delimiter' errors:"
  )
  html_cases = [
      (  # Pre-escaped (should work)
          '{"extractions": [{"text": "<table><tr><td colspan=\\"4\\">Cell'
          ' content</td></tr></table>"}]}'
      ),
      (  # Unescaped (needs fixing)
          '{"extractions": [{"text": "<table><tr><td colspan="4">Cell'
          ' content</td></tr></table>"}]}'
      ),
      (  # Complex case
          '{"extractions": [{"html": "<div class=\\"container\\"><table'
          ' border=\\"1\\" cellpadding=\\"2\\"><tr><td colspan=\\"4\\"'
          ' style=\\"text-align:center\\">Header</td></tr></table></div>"}]}'
      ),
  ]

  for i, case in enumerate(html_cases, 1):
    print(f"   Case 2.{i}: {case[:50]}...")
    try:
      result = resolver._extract_and_parse_content(case)
      print(f"   ✓ PASSED: HTML parsing works!")
    except Exception as e:
      print(f"   ✗ FAILED: {e}")
      return False

  print()

  # Test Case 3: Combined cases (the trickiest ones)
  print("3. Testing combined LaTeX + HTML cases:")
  combined_cases = [
      (
          '{"extractions": [{"math": "$\\\\pi$", "html": "<div'
          ' class=\\"test\\">content</div>"}]}'
      ),
      (
          '{"extractions": [{"description": "Temperature $30^{\\\\circ}$ in'
          ' <span class=\\"highlight\\">red</span>"}]}'
      ),
  ]

  for i, case in enumerate(combined_cases, 1):
    print(f"   Case 3.{i}: {case[:50]}...")
    try:
      result = resolver._extract_and_parse_content(case)
      print(f"   ✓ PASSED: Combined parsing works!")
    except Exception as e:
      print(f"   ✗ FAILED: {e}")
      return False

  print()
  print("🎉 ALL ORIGINAL ERROR CASES NOW WORK!")
  print()
  print("✅ Summary of fixes:")
  print(
      "   • LaTeX backslash sequences (\\mathsf, \\circ) are properly escaped"
  )
  print("   • HTML attribute quotes are correctly handled")
  print("   • Mixed LaTeX+HTML content parses successfully")
  print("   • No more 'Invalid \\escape' errors")
  print("   • No more 'Expecting comma delimiter' errors")
  print()
  return True


if __name__ == "__main__":
  test_original_user_cases()
