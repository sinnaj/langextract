"""
Input sanitization preprocessing module for langextract.

This module provides functionality to sanitize text inputs before they are processed
by the extraction pipeline, specifically to handle control characters that can cause
parsing issues or pipeline hanging.
"""

import logging
import re
import signal
import time
from typing import Callable, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


class InputSanitizationError(Exception):
    """Exception raised when input sanitization fails."""
    pass


class TimeoutError(Exception):
    """Exception raised when an operation times out."""
    pass


def sanitize_control_characters(input_text: str) -> str:
    """
    Remove problematic ASCII control characters from input text.
    
    This function removes ASCII control characters (0x00-0x1F) that can cause
    JSON parsing issues, except for valid whitespace characters (TAB, LF, CR).
    
    Args:
        input_text: The input string to sanitize
        
    Returns:
        Sanitized string with control characters removed
        
    Raises:
        InputSanitizationError: If input is not a string
    """
    if not isinstance(input_text, str):
        raise InputSanitizationError(f"Input must be a string, got {type(input_text)}")
    
    if not input_text:
        return input_text
    
    # Remove ASCII control characters except TAB (0x09), LF (0x0A), CR (0x0D)
    # These control characters can cause JSON parsing to hang or fail
    original_length = len(input_text)
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', input_text)
    
    # Log if characters were removed
    if len(sanitized) != original_length:
        removed_count = original_length - len(sanitized)
        logger.info(f"Sanitization removed {removed_count} control characters from input")
        logger.debug(f"Original length: {original_length}, sanitized length: {len(sanitized)}")
    
    return sanitized


def sanitize_with_timeout(
    input_text: str,
    timeout_seconds: int = 30,
    sanitizer_func: Callable[[str], str] = sanitize_control_characters
) -> str:
    """
    Sanitize input text with a timeout to prevent hanging operations.
    
    Args:
        input_text: The input string to sanitize
        timeout_seconds: Maximum time to wait before timing out (default: 30)
        sanitizer_func: The sanitization function to use (default: sanitize_control_characters)
        
    Returns:
        Sanitized string
        
    Raises:
        TimeoutError: If the sanitization takes longer than timeout_seconds
        InputSanitizationError: If sanitization fails
    """
    class TimeoutException(Exception):
        pass
    
    def timeout_handler(signum, frame):
        raise TimeoutException("Sanitization operation timed out")
    
    # Set up the timeout
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        result = sanitizer_func(input_text)
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
        return result
    except TimeoutException:
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
        raise TimeoutError(f"Sanitization timed out after {timeout_seconds} seconds")
    except Exception as e:
        signal.alarm(0)  # Cancel the alarm  
        signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
        if isinstance(e, InputSanitizationError):
            raise
        raise InputSanitizationError(f"Sanitization failed: {e}") from e


def preprocess_text_for_extraction(
    input_text: str,
    enable_control_char_sanitization: bool = True,
    enable_timeout_protection: bool = True,
    timeout_seconds: int = 30
) -> str:
    """
    Comprehensive preprocessing of text before extraction.
    
    This is the main entry point for preprocessing text inputs before they
    are passed to the langextract pipeline.
    
    Args:
        input_text: The input text to preprocess
        enable_control_char_sanitization: Whether to remove control characters (default: True)
        enable_timeout_protection: Whether to use timeout protection (default: True)
        timeout_seconds: Timeout for sanitization operations (default: 30)
        
    Returns:
        Preprocessed text ready for extraction
        
    Raises:
        InputSanitizationError: If preprocessing fails
        TimeoutError: If preprocessing times out
    """
    if not isinstance(input_text, str):
        raise InputSanitizationError(f"Input must be a string, got {type(input_text)}")
    
    if not input_text:
        return input_text
    
    preprocessed_text = input_text
    
    # Apply control character sanitization if enabled
    if enable_control_char_sanitization:
        if enable_timeout_protection:
            preprocessed_text = sanitize_with_timeout(
                preprocessed_text, 
                timeout_seconds=timeout_seconds
            )
        else:
            preprocessed_text = sanitize_control_characters(preprocessed_text)
    
    logger.debug(f"Preprocessing complete. Original length: {len(input_text)}, "
                f"preprocessed length: {len(preprocessed_text)}")
    
    return preprocessed_text


def create_preprocessing_pipeline(*sanitizers: Callable[[str], str]) -> Callable[[str], str]:
    """
    Create a custom preprocessing pipeline with multiple sanitization steps.
    
    Args:
        *sanitizers: Sanitization functions to apply in sequence
        
    Returns:
        A function that applies all sanitizers in sequence
    """
    def pipeline(input_text: str) -> str:
        result = input_text
        for sanitizer in sanitizers:
            result = sanitizer(result)
        return result
    
    return pipeline


# Convenience function for backward compatibility and easy integration
def sanitize_for_langextract(input_text: str) -> str:
    """
    Convenience function to sanitize input for langextract processing.
    
    This is a simple wrapper around preprocess_text_for_extraction with
    default settings optimized for langextract.
    
    Args:
        input_text: The input text to sanitize
        
    Returns:
        Sanitized text ready for langextract processing
    """
    return preprocess_text_for_extraction(input_text)