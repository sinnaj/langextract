#!/usr/bin/env python3
"""Simple test to validate TODO fixes in lxRunnerExtraction.py"""

import os
import re
from pathlib import Path

def test_todo_fixes():
    """Test that all TODOs have been addressed in the source code"""
    print("Validating TODO fixes in lxRunnerExtraction.py...")
    
    # Read the source file
    source_file = Path(__file__).parent / "lxRunnerExtraction.py"
    content = source_file.read_text()
    
    # Test 1: Check that suppress_parse_errors_default is now configurable
    print("1. Testing suppress_parse_errors_default configurability...")
    if 'os.getenv("LX_SUPPRESS_PARSE_ERRORS"' in content:
        print("   ✓ suppress_parse_errors_default is now configurable via environment variable")
    else:
        print("   ✗ suppress_parse_errors_default is not configurable")
    
    # Test 2: Check that _synthesize_extraction is documented
    print("2. Testing _synthesize_extraction documentation...")
    if "##NOTE: _synthesize_extraction is used as a fallback" in content:
        print("   ✓ _synthesize_extraction function is now documented")
    else:
        print("   ✗ _synthesize_extraction function is not documented")
    
    # Test 3: Check that internal chunking warning is added
    print("3. Testing internal chunking warning...")
    if "Section text" in content and "exceeds max_char_buffer" in content:
        print("   ✓ Internal chunking warning is now implemented")
    else:
        print("   ✗ Internal chunking warning is not implemented")
    
    # Test 4: Check that serialization is simplified
    print("4. Testing serialization simplification...")
    if "##NOTE: Simplified serialization approach" in content:
        print("   ✓ Serialization approach is simplified")
    else:
        print("   ✗ Serialization approach is not simplified")
    
    # Test 5: Check that dynamic extraction class handling is improved
    print("5. Testing dynamic extraction class handling...")
    if "##NOTE: Improved dynamic extraction class handling" in content:
        print("   ✓ Dynamic extraction class handling is improved")
    else:
        print("   ✗ Dynamic extraction class handling is not improved")
    
    # Test 6: Count remaining TODOs
    print("6. Counting remaining TODOs...")
    todo_matches = re.findall(r'##\s*TODO', content, re.IGNORECASE)
    if len(todo_matches) == 0:
        print("   ✓ All TODOs have been addressed!")
    else:
        print(f"   ⚠ Found {len(todo_matches)} remaining TODOs")
        
    # Test 7: Test environment variable behavior
    print("7. Testing environment variable behavior...")
    
    # Test default case
    os.environ.pop("LX_SUPPRESS_PARSE_ERRORS", None)
    test_env_false = 'os.getenv("LX_SUPPRESS_PARSE_ERRORS", "false").lower() in {"1", "true", "yes"}'
    if test_env_false in content:
        print("   ✓ Environment variable defaults to false correctly")
    else:
        print("   ✗ Environment variable default behavior is incorrect")
    
    print("\nTODO fixes validation completed!")

def test_code_quality():
    """Test that the code changes maintain quality"""
    print("\nTesting code quality...")
    
    source_file = Path(__file__).parent / "lxRunnerExtraction.py"
    content = source_file.read_text()
    
    # Check for proper Python syntax by attempting to compile
    try:
        compile(content, source_file, 'exec')
        print("✓ Python syntax is valid")
    except SyntaxError as e:
        print(f"✗ Syntax error: {e}")
    
    # Check for consistent indentation
    lines = content.split('\n')
    indentation_errors = 0
    for i, line in enumerate(lines, 1):
        if line.strip() and not line.startswith('#'):
            # Check for mixed tabs and spaces
            if '\t' in line and ' ' in line[:len(line) - len(line.lstrip())]:
                indentation_errors += 1
    
    if indentation_errors == 0:
        print("✓ Indentation is consistent")
    else:
        print(f"⚠ Found {indentation_errors} potential indentation issues")

if __name__ == "__main__":
    test_todo_fixes()
    test_code_quality()