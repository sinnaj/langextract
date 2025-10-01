"""Memory management utilities for enhanced extraction pipeline.

This module provides memory monitoring, garbage collection, and optimization
utilities to handle large PDF processing efficiently.
"""

import gc
import os
import sys
from typing import Optional


# Memory management constants
MAX_SECTION_SIZE_MB = 50  # Maximum size for a section before chunking
MAX_CHUNK_SIZE_CHARS = 50000  # Maximum characters per chunk to prevent OOM
MEMORY_WARNING_THRESHOLD_MB = 1000  # Warn if memory usage exceeds this
CRITICAL_MEMORY_THRESHOLD_MB = 2000  # Force cleanup if exceeded


def get_memory_usage_mb() -> float:
    """Get current memory usage in MB.
    
    Returns:
        Current memory usage in megabytes, or 0.0 if psutil unavailable
    """
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        # Fallback - no memory monitoring
        return 0.0


def check_memory_usage(operation: str = "") -> None:
    """Check and log memory usage, warn if high.
    
    Args:
        operation: Description of current operation for logging context
    """
    memory_mb = get_memory_usage_mb()
    
    if memory_mb > CRITICAL_MEMORY_THRESHOLD_MB:
        print(f"[CRITICAL] Very high memory usage during {operation}: {memory_mb:.1f} MB - forcing cleanup")
        force_garbage_collection()
    elif memory_mb > MEMORY_WARNING_THRESHOLD_MB:
        print(f"[WARNING] High memory usage during {operation}: {memory_mb:.1f} MB")
    else:
        print(f"[DEBUG] Memory usage during {operation}: {memory_mb:.1f} MB")


def force_garbage_collection() -> None:
    """Force garbage collection to free memory.
    
    Performs aggressive garbage collection to help with memory management
    during large document processing.
    """
    # Multiple GC cycles to ensure thorough cleanup
    for _ in range(3):
        gc.collect()
    print("[DEBUG] Forced garbage collection")


def estimate_content_size_mb(content: str) -> float:
    """Estimate memory size of content string in MB.
    
    Args:
        content: Text content to estimate size of
        
    Returns:
        Estimated memory size in megabytes
    """
    if not content:
        return 0.0
    # Rough estimate: UTF-8 encoding typically uses 1-4 bytes per character
    # We use 2 as a reasonable average estimate
    return len(content) * 2 / 1024 / 1024


def should_chunk_content(content: str, section_title: str = "") -> bool:
    """Determine if content should be chunked based on size.
    
    Args:
        content: Text content to check
        section_title: Section title for logging
        
    Returns:
        True if content should be chunked, False otherwise
    """
    size_mb = estimate_content_size_mb(content)
    
    if size_mb > MAX_SECTION_SIZE_MB:
        print(f"[INFO] Large section '{section_title}' ({size_mb:.1f} MB) will be chunked")
        return True
    
    return False


def monitor_memory_during_processing(func):
    """Decorator to monitor memory usage during function execution.
    
    Args:
        func: Function to monitor
        
    Returns:
        Wrapped function with memory monitoring
    """
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        
        # Check memory before
        memory_before = get_memory_usage_mb()
        print(f"[DEBUG] Starting {func_name}, memory: {memory_before:.1f} MB")
        
        try:
            result = func(*args, **kwargs)
            
            # Check memory after
            memory_after = get_memory_usage_mb()
            memory_diff = memory_after - memory_before
            
            if memory_diff > 100:  # More than 100MB increase
                print(f"[WARNING] {func_name} increased memory by {memory_diff:.1f} MB")
            else:
                print(f"[DEBUG] {func_name} memory change: {memory_diff:+.1f} MB")
                
            return result
            
        except Exception as e:
            print(f"[ERROR] {func_name} failed with memory at {get_memory_usage_mb():.1f} MB")
            raise
            
    return wrapper