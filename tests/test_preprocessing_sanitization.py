"""
Tests for the input sanitization preprocessing module.
"""

import time
import unittest
from unittest.mock import patch

from preprocessing.sanitize_input import (
    InputSanitizationError,
    TimeoutError,
    sanitize_control_characters,
    sanitize_with_timeout,
    preprocess_text_for_extraction,
    create_preprocessing_pipeline,
    sanitize_for_langextract
)


class TestControlCharacterSanitization(unittest.TestCase):
    """Test cases for control character sanitization functionality."""

    def test_sanitize_control_characters_basic(self):
        """Test basic control character removal."""
        # Test input with null byte control character
        input_text = "Text with control char: \x00 here"
        result = sanitize_control_characters(input_text)
        
        self.assertNotIn('\x00', result)
        self.assertIn('Text with control char:', result)
        self.assertIn('here', result)

    def test_sanitize_multiple_control_characters(self):
        """Test removal of multiple different control characters."""
        input_text = "Text with multiple: \x01\x02\x03\x1F chars"
        result = sanitize_control_characters(input_text)
        
        # Verify all control characters were removed
        self.assertNotIn('\x01', result)
        self.assertNotIn('\x02', result)
        self.assertNotIn('\x03', result)
        self.assertNotIn('\x1F', result)
        self.assertIn('Text with multiple:', result)
        self.assertIn('chars', result)

    def test_preserve_valid_whitespace_characters(self):
        """Test that valid whitespace characters (TAB, LF, CR) are preserved."""
        input_text = "Text with\ttab\nand\rnewlines"
        result = sanitize_control_characters(input_text)
        
        # Verify valid whitespace is preserved
        self.assertIn('\t', result)  # TAB preserved
        self.assertIn('\n', result)  # LF preserved  
        self.assertIn('\r', result)  # CR preserved

    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        result = sanitize_control_characters("")
        self.assertEqual(result, "")

    def test_string_without_control_characters(self):
        """Test that normal strings are not modified."""
        input_text = "This is a normal string with no control characters."
        result = sanitize_control_characters(input_text)
        self.assertEqual(result, input_text)

    def test_invalid_input_type(self):
        """Test that non-string input raises appropriate error."""
        with self.assertRaises(InputSanitizationError):
            sanitize_control_characters(123)
        
        with self.assertRaises(InputSanitizationError):
            sanitize_control_characters(None)

    def test_large_input_performance(self):
        """Test that large inputs are handled efficiently."""
        # Create a large string with control characters
        large_text = 'A' * 10000 + '\x00' + 'B' * 10000
        
        start_time = time.time()
        result = sanitize_control_characters(large_text)
        elapsed = time.time() - start_time
        
        # Should complete quickly (under 1 second)
        self.assertLess(elapsed, 1.0)
        self.assertNotIn('\x00', result)
        self.assertIn('A' * 10000, result)
        self.assertIn('B' * 10000, result)


class TestTimeoutSanitization(unittest.TestCase):
    """Test cases for timeout-protected sanitization."""

    def test_normal_sanitization_with_timeout(self):
        """Test that normal sanitization works with timeout protection."""
        input_text = "Text with \x00 control character"
        result = sanitize_with_timeout(input_text, timeout_seconds=5)
        
        self.assertNotIn('\x00', result)
        self.assertIn('Text with', result)
        self.assertIn('control character', result)

    def test_timeout_protection_with_fast_operation(self):
        """Test timeout protection with a fast operation."""
        input_text = "Normal text"
        result = sanitize_with_timeout(input_text, timeout_seconds=1)
        self.assertEqual(result, input_text)

    @patch('preprocessing.sanitize_input.signal.alarm')
    @patch('preprocessing.sanitize_input.signal.signal')
    def test_timeout_cleanup_on_success(self, mock_signal, mock_alarm):
        """Test that timeout cleanup happens correctly on successful operation."""
        input_text = "Test text"
        sanitize_with_timeout(input_text, timeout_seconds=5)
        
        # Should call alarm(5) to set timeout, then alarm(0) to cancel
        alarm_calls = mock_alarm.call_args_list
        self.assertGreaterEqual(len(alarm_calls), 2)
        self.assertEqual(alarm_calls[-1][0][0], 0)  # Last call should cancel alarm

    def test_custom_sanitizer_function(self):
        """Test using a custom sanitizer function with timeout."""
        def custom_sanitizer(text):
            return text.upper()
        
        input_text = "hello world"
        result = sanitize_with_timeout(input_text, sanitizer_func=custom_sanitizer)
        self.assertEqual(result, "HELLO WORLD")


class TestPreprocessingPipeline(unittest.TestCase):
    """Test cases for the main preprocessing functionality."""

    def test_preprocess_text_for_extraction_default(self):
        """Test default preprocessing behavior."""
        input_text = "Text with \x00 control characters"
        result = preprocess_text_for_extraction(input_text)
        
        self.assertNotIn('\x00', result)
        self.assertIn('Text with', result)
        self.assertIn('control characters', result)

    def test_preprocess_text_disable_control_char_sanitization(self):
        """Test preprocessing with control character sanitization disabled."""
        input_text = "Text with \x00 control characters"
        result = preprocess_text_for_extraction(
            input_text, 
            enable_control_char_sanitization=False
        )
        
        # Control character should still be present
        self.assertIn('\x00', result)

    def test_preprocess_text_disable_timeout_protection(self):
        """Test preprocessing with timeout protection disabled."""
        input_text = "Text with \x00 control characters"
        result = preprocess_text_for_extraction(
            input_text,
            enable_timeout_protection=False
        )
        
        self.assertNotIn('\x00', result)

    def test_preprocess_text_custom_timeout(self):
        """Test preprocessing with custom timeout."""
        input_text = "Normal text"
        result = preprocess_text_for_extraction(
            input_text,
            timeout_seconds=10
        )
        self.assertEqual(result, input_text)

    def test_preprocess_empty_string(self):
        """Test preprocessing empty string."""
        result = preprocess_text_for_extraction("")
        self.assertEqual(result, "")

    def test_preprocess_invalid_input_type(self):
        """Test preprocessing with invalid input type."""
        with self.assertRaises(InputSanitizationError):
            preprocess_text_for_extraction(123)


class TestPipelineCreation(unittest.TestCase):
    """Test cases for custom pipeline creation."""

    def test_create_preprocessing_pipeline_single_function(self):
        """Test creating pipeline with single sanitization function."""
        def upper_sanitizer(text):
            return text.upper()
        
        pipeline = create_preprocessing_pipeline(upper_sanitizer)
        result = pipeline("hello world")
        self.assertEqual(result, "HELLO WORLD")

    def test_create_preprocessing_pipeline_multiple_functions(self):
        """Test creating pipeline with multiple sanitization functions."""
        def upper_sanitizer(text):
            return text.upper()
        
        def exclamation_sanitizer(text):
            return text + "!"
        
        pipeline = create_preprocessing_pipeline(upper_sanitizer, exclamation_sanitizer)
        result = pipeline("hello world")
        self.assertEqual(result, "HELLO WORLD!")

    def test_create_preprocessing_pipeline_with_control_char_sanitizer(self):
        """Test pipeline that includes control character sanitization."""
        def prefix_sanitizer(text):
            return "PREFIX: " + text
        
        pipeline = create_preprocessing_pipeline(
            sanitize_control_characters,
            prefix_sanitizer
        )
        
        input_text = "Text with \x00 control"
        result = pipeline(input_text)
        
        self.assertNotIn('\x00', result)
        self.assertIn('PREFIX:', result)
        self.assertIn('Text with', result)


class TestConvenienceFunctions(unittest.TestCase):
    """Test cases for convenience functions."""

    def test_sanitize_for_langextract(self):
        """Test the convenience function for langextract integration."""
        input_text = "Text with \x00 control characters"
        result = sanitize_for_langextract(input_text)
        
        self.assertNotIn('\x00', result)
        self.assertIn('Text with', result)
        self.assertIn('control characters', result)

    def test_sanitize_for_langextract_normal_text(self):
        """Test convenience function with normal text."""
        input_text = "This is normal text"
        result = sanitize_for_langextract(input_text)
        self.assertEqual(result, input_text)


class TestIntegrationScenarios(unittest.TestCase):
    """Test cases for real-world integration scenarios."""

    def test_json_like_input_with_control_characters(self):
        """Test preprocessing JSON-like input with control characters."""
        json_input = '''```json
{
  "extractions": [{
    "extraction_class": "Test",
    "extraction_text": "Text with control char: \x00 here"
  }]
}
```'''
        
        result = sanitize_for_langextract(json_input)
        
        # Should preserve JSON structure but remove control characters
        self.assertIn('extractions', result)
        self.assertIn('extraction_class', result)
        self.assertNotIn('\x00', result)
        self.assertIn('Text with control char:', result)

    def test_large_json_input_performance(self):
        """Test performance with large JSON-like inputs."""
        large_content = 'A' * 5000 + '\x00\x01\x02' + 'B' * 5000
        json_input = f'''```json
{{
  "extractions": [{{
    "extraction_class": "LargeTest",
    "extraction_text": "{large_content}"
  }}]
}}
```'''
        
        start_time = time.time()
        result = sanitize_for_langextract(json_input)
        elapsed = time.time() - start_time
        
        # Should complete quickly
        self.assertLess(elapsed, 2.0)
        self.assertNotIn('\x00', result)
        self.assertNotIn('\x01', result)
        self.assertNotIn('\x02', result)

    def test_multiple_control_characters_in_json(self):
        """Test handling multiple types of control characters in JSON."""
        json_input = '''```json
{
  "extractions": [{
    "extraction_class": "MultiTest",
    "extraction_text": "Multiple\x00chars\x01with\x1Fcontrol"
  }]
}
```'''
        
        result = sanitize_for_langextract(json_input)
        
        # All control characters should be removed
        self.assertNotIn('\x00', result)
        self.assertNotIn('\x01', result)
        self.assertNotIn('\x1F', result)
        # But content should remain
        self.assertIn('Multiple', result)
        self.assertIn('chars', result)
        self.assertIn('with', result)
        self.assertIn('control', result)


if __name__ == '__main__':
    unittest.main()