#!/usr/bin/env python3
"""
Example script demonstrating the preprocessing module for control character handling.

This script shows how to use the preprocessing module to handle problematic
control characters that can cause the langextract pipeline to hang.
"""

import sys
import time
from pathlib import Path

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from preprocessing.sanitize_input import (
    sanitize_for_langextract,
    preprocess_text_for_extraction,
    sanitize_control_characters,
    create_preprocessing_pipeline
)


def demonstrate_basic_sanitization():
    """Demonstrate basic control character sanitization."""
    print("=== Basic Control Character Sanitization ===")
    
    # Example problematic input with control characters
    problematic_input = """```json
{
  "extractions": [{
    "extraction_class": "Test",
    "extraction_text": "Content with null byte: \x00 and other control chars \x01\x02"
  }]
}
```"""
    
    print("Original input (with control characters):")
    print(repr(problematic_input[:100]) + "...")
    
    # Sanitize the input
    clean_input = sanitize_for_langextract(problematic_input)
    
    print("\nSanitized input:")
    print(repr(clean_input[:100]) + "...")
    
    print(f"\nControl characters removed: {len(problematic_input) - len(clean_input)}")
    print()


def demonstrate_performance_improvement():
    """Demonstrate performance improvement with large inputs."""
    print("=== Performance Improvement Demo ===")
    
    # Create a large input with control characters
    large_content = "A" * 5000 + "\x00" + "B" * 5000 + "\x01\x02\x03"
    large_input = f"""```json
{{
  "extractions": [{{
    "extraction_class": "LargeTest",
    "extraction_text": "{large_content}"
  }}]
}}
```"""
    
    print(f"Testing with large input ({len(large_input)} characters)")
    
    # Time the sanitization
    start_time = time.time()
    clean_input = sanitize_for_langextract(large_input)
    elapsed = time.time() - start_time
    
    print(f"Sanitization completed in {elapsed:.4f} seconds")
    print(f"Characters removed: {len(large_input) - len(clean_input)}")
    print()


def demonstrate_custom_pipeline():
    """Demonstrate creating a custom preprocessing pipeline."""
    print("=== Custom Preprocessing Pipeline ===")
    
    def add_prefix(text):
        """Add a prefix to the text."""
        return f"[PREPROCESSED] {text}"
    
    def normalize_whitespace(text):
        """Normalize multiple whitespaces to single spaces."""
        import re
        return re.sub(r'\s+', ' ', text)
    
    # Create a custom pipeline
    custom_pipeline = create_preprocessing_pipeline(
        sanitize_control_characters,
        normalize_whitespace,
        add_prefix
    )
    
    test_input = "Text  with\t\tmultiple\x00\x01spaces and\ncontrol chars"
    print("Original:", repr(test_input))
    
    result = custom_pipeline(test_input)
    print("Processed:", repr(result))
    print()


def demonstrate_advanced_options():
    """Demonstrate advanced preprocessing options."""
    print("=== Advanced Preprocessing Options ===")
    
    test_input = "Text with \x00 control character"
    
    # Different preprocessing configurations
    configs = [
        {
            "name": "Default (all enabled)",
            "kwargs": {}
        },
        {
            "name": "No timeout protection",
            "kwargs": {"enable_timeout_protection": False}
        },
        {
            "name": "No control char sanitization",
            "kwargs": {"enable_control_char_sanitization": False}
        },
        {
            "name": "Custom timeout",
            "kwargs": {"timeout_seconds": 10}
        }
    ]
    
    for config in configs:
        result = preprocess_text_for_extraction(test_input, **config["kwargs"])
        print(f"{config['name']}: {repr(result)}")
    
    print()


def demonstrate_error_handling():
    """Demonstrate error handling scenarios."""
    print("=== Error Handling Demo ===")
    
    from preprocessing.sanitize_input import InputSanitizationError
    
    # Test invalid input types
    invalid_inputs = [123, None, ["list"], {"dict": "value"}]
    
    for invalid_input in invalid_inputs:
        try:
            sanitize_for_langextract(invalid_input)
            print(f"Unexpected success with {type(invalid_input)}")
        except InputSanitizationError as e:
            print(f"Correctly caught error for {type(invalid_input)}: {e}")
    
    print()


def demonstrate_real_world_scenario():
    """Demonstrate a real-world scenario with typical LLM output."""
    print("=== Real-World Scenario ===")
    
    # Simulate problematic LLM output with control characters
    llm_output = """```json
{
  "extractions": [
    {
      "extraction_class": "person_name",
      "extraction_text": "John\x00 Doe"
    },
    {
      "extraction_class": "company_name", 
      "extraction_text": "Tech\x01Corp\x02Inc"
    },
    {
      "extraction_class": "location",
      "extraction_text": "San Francisco\x1F, CA"
    }
  ]
}
```"""
    
    print("Simulated LLM output with control characters:")
    print("Before preprocessing:")
    print("- Contains null bytes and other control characters")
    print("- Could cause JSON parsing to hang or fail")
    
    # Apply preprocessing
    clean_output = sanitize_for_langextract(llm_output)
    
    print("\nAfter preprocessing:")
    print("- Control characters removed")
    print("- Safe for JSON parsing")
    print("- Ready for langextract processing")
    
    # Show specific improvements
    print(f"\nLength change: {len(llm_output)} → {len(clean_output)}")
    print("Content preview:")
    print(clean_output)


def main():
    """Run all demonstration examples."""
    print("Langextract Preprocessing Module Demo")
    print("=" * 50)
    print()
    
    demonstrate_basic_sanitization()
    demonstrate_performance_improvement()
    demonstrate_custom_pipeline()
    demonstrate_advanced_options()
    demonstrate_error_handling()
    demonstrate_real_world_scenario()
    
    print("Demo completed successfully!")
    print("\nTo integrate with langextract:")
    print("1. Import: from preprocessing.sanitize_input import sanitize_for_langextract")
    print("2. Preprocess: clean_input = sanitize_for_langextract(raw_input)")
    print("3. Process: result = resolver.resolve(clean_input)")


if __name__ == "__main__":
    main()