# Preprocessing Module

This module provides preprocessing functionality for langextract inputs, specifically designed to handle problematic control characters that can cause parsing issues or pipeline hanging.

## Overview

The preprocessing module includes functionality to:
- Remove ASCII control characters that can cause JSON parsing issues
- Provide timeout protection to prevent hanging operations
- Create custom preprocessing pipelines
- Integrate seamlessly with langextract workflows

## Quick Start

### Basic Usage

```python
from preprocessing.sanitize_input import sanitize_for_langextract

# Simple sanitization
input_text = "Text with \x00 control characters"
clean_text = sanitize_for_langextract(input_text)
# Result: "Text with  control characters" (control char removed)
```

### Advanced Usage

```python
from preprocessing.sanitize_input import (
    preprocess_text_for_extraction,
    sanitize_control_characters,
    create_preprocessing_pipeline
)

# Advanced preprocessing with custom settings
clean_text = preprocess_text_for_extraction(
    input_text,
    enable_control_char_sanitization=True,
    enable_timeout_protection=True,
    timeout_seconds=30
)

# Custom preprocessing pipeline
def custom_sanitizer(text):
    return text.replace("unwanted_pattern", "")

pipeline = create_preprocessing_pipeline(
    sanitize_control_characters,
    custom_sanitizer
)

result = pipeline(input_text)
```

## Integration with Langextract

To integrate with your langextract workflow, simply preprocess your input before passing it to the resolver:

```python
from langextract import resolver as resolver_lib
from preprocessing.sanitize_input import sanitize_for_langextract

# Create resolver
resolver = resolver_lib.Resolver(
    format_type=data.FormatType.JSON,
    fence_output=True
)

# Preprocess input
raw_input = "```json\n{\"extractions\": [{\"text\": \"content with \x00 control chars\"}]}\n```"
clean_input = sanitize_for_langextract(raw_input)

# Process with resolver
result = resolver.resolve(clean_input)
```

## Problem Solved

This preprocessing module addresses issues where the extraction pipeline could get stuck when encountering:
- ASCII control characters (0x00-0x1F) in JSON responses from language models
- Large inputs containing control characters causing expensive parsing fallbacks
- Scenarios where `suppress_parse_errors=True` didn't work reliably

## Performance Impact

**Before preprocessing:**
```python
# Large string with control characters took 2+ seconds
result = resolver.resolve(large_input_with_control_chars)
```

**After preprocessing:**
```python
# Same input now processes quickly
clean_input = sanitize_for_langextract(large_input_with_control_chars)
result = resolver.resolve(clean_input)  # Fast processing
```

## Functions Reference

### `sanitize_for_langextract(input_text: str) -> str`
Convenience function optimized for langextract processing.

### `preprocess_text_for_extraction(input_text: str, **kwargs) -> str`
Main preprocessing function with configurable options:
- `enable_control_char_sanitization`: Remove control characters (default: True)
- `enable_timeout_protection`: Use timeout protection (default: True)  
- `timeout_seconds`: Timeout duration (default: 30)

### `sanitize_control_characters(input_text: str) -> str`
Core function to remove problematic ASCII control characters while preserving valid whitespace.

### `create_preprocessing_pipeline(*sanitizers) -> Callable`
Create custom preprocessing pipelines with multiple sanitization steps.

## Error Handling

The module provides specific exceptions:
- `InputSanitizationError`: Raised for sanitization failures
- `TimeoutError`: Raised when operations exceed timeout limits

## Testing

Run the comprehensive test suite:

```bash
python -m pytest tests/test_preprocessing_sanitization.py -v
```

The test suite covers:
- Control character removal
- Whitespace preservation  
- Performance with large inputs
- Error handling scenarios
- Integration patterns
- Custom pipeline creation