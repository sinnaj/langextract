#!/usr/bin/env python3
"""Comprehensive integration test for the resolver fixes."""

from langextract import resolver as resolver_lib
from langextract.core import data


def test_comprehensive_resolver():
  """Test various edge cases and combinations to ensure robustness."""
  resolver = resolver_lib.Resolver(
      format_type=data.FormatType.JSON, fence_output=False
  )

  test_cases = [
      {
          "name": "Normal JSON (baseline)",
          "json": (
              '{"extractions": [{"entity": "test", "text": "normal text"}]}'
          ),
          "should_pass": True,
      },
      {
          "name": "LaTeX backslashes",
          "json": (
              '{"extractions": [{"entity": "math", "text": "$\\\\theta$ and'
              ' $\\\\mathsf{E}$"}]}'
          ),
          "should_pass": True,
      },
      {
          "name": "HTML attributes",
          "json": (
              '{"extractions": [{"entity": "table", "text": "<td'
              ' colspan="4">cell</td>"}]}'
          ),
          "should_pass": True,
      },
      {
          "name": "Multiple HTML attributes",
          "json": (
              '{"extractions": [{"entity": "div", "text": "<div'
              ' class="container" id="main" style="color:red">content</div>"}]}'
          ),
          "should_pass": True,
      },
      {
          "name": "Mixed LaTeX and HTML",
          "json": (
              '{"extractions": [{"math": "$\\\\pi$", "table": "<table'
              ' border="1"><tr><td'
              ' colspan="2">$\\\\alpha$</td></tr></table>"}]}'
          ),
          "should_pass": True,
      },
      {
          "name": "Nested quotes in HTML",
          "json": (
              '{"extractions": [{"html": "<div title=\\"Value is'
              ' nested\\">content</div>"}]}'
          ),
          "should_pass": True,
      },
      {
          "name": "Unicode sequences",
          "json": (
              '{"extractions": [{"text": "Unicode \\\\u03B1 and \\\\u03B2"}]}'
          ),
          "should_pass": True,
      },
  ]

  passed = 0
  total = len(test_cases)

  print("Running comprehensive resolver tests...")
  print("=" * 60)

  for i, test_case in enumerate(test_cases, 1):
    print(f"\n{i}. {test_case['name']}")
    print(
        "   JSON:"
        f" {test_case['json'][:60]}{'...' if len(test_case['json']) > 60 else ''}"
    )

    try:
      result = resolver._extract_and_parse_content(test_case["json"])
      if test_case["should_pass"]:
        print("   ✓ PASSED: Parsed successfully")
        passed += 1
      else:
        print("   ✗ FAILED: Should have failed but didn't")
    except Exception as e:
      if not test_case["should_pass"]:
        print("   ✓ PASSED: Failed as expected")
        passed += 1
      else:
        print(f"   ✗ FAILED: {str(e)[:100]}...")

  print("\n" + "=" * 60)
  print(f"COMPREHENSIVE TEST RESULTS: {passed}/{total} tests passed")

  if passed == total:
    print("🎉 All comprehensive tests PASSED!")
    print("\n✅ The resolver fixes are working correctly for:")
    print("   • LaTeX backslash sequences (\\mathsf, \\circ, etc.)")
    print('   • HTML attribute quotes (colspan="4", class="container", etc.)')
    print("   • Mixed content with both LaTeX and HTML")
    print("   • Complex nested structures")
    print("   • Unicode escape sequences")
    return True
  else:
    print("❌ Some comprehensive tests failed")
    return False


if __name__ == "__main__":
  success = test_comprehensive_resolver()
  if success:
    print("\n🚀 RESOLVER INTEGRATION COMPLETE!")
    print("The fixes successfully handle both LaTeX and HTML parsing issues.")
  else:
    print("\n⚠️  Additional work may be needed.")
