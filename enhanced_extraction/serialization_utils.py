"""Utility functions for data serialization and interval handling.

This module contains common utility functions that were previously duplicated
across enhanced_lx_runner.py and lxRunnerExtraction.py.
"""

from typing import Any, Dict, Optional


def ci_dict(ci) -> Optional[Dict[str, Any]]:
    """Convert CharInterval to JSON-serializable dict.
    
    Args:
        ci: CharInterval object with start_pos/end_pos attributes
        
    Returns:
        Dictionary with start_pos and end_pos, or None if ci is None
    """
    if not ci:
        return None
    # CharInterval has start_pos/end_pos
    return {
        "start_pos": getattr(ci, "start_pos", None),
        "end_pos": getattr(ci, "end_pos", None),
    }


def ti_dict(ti) -> Optional[Dict[str, Any]]:
    """Convert TokenInterval to JSON-serializable dict.
    
    Args:
        ti: TokenInterval object with start_index/end_index attributes
        
    Returns:
        Dictionary with start_index and end_index, or None if ti is None
    """
    if not ti:
        return None
    # TokenInterval has start_index/end_index
    return {
        "start_index": getattr(ti, "start_index", None),
        "end_index": getattr(ti, "end_index", None),
    }


def get_alignment_status_value(alignment_status) -> Optional[str]:
    """Extract alignment status value from enum or string.
    
    Args:
        alignment_status: Alignment status object (enum or string)
        
    Returns:
        String value of alignment status, or None if None
    """
    if alignment_status is None:
        return None
    # Handle enum objects with .value attribute
    if hasattr(alignment_status, "value"):
        return alignment_status.value
    # Handle string values directly
    return alignment_status


def serialize_extraction_for_json(extraction) -> Dict[str, Any]:
    """Convert LangExtract extraction object to JSON-serializable format.
    
    Args:
        extraction: LangExtract extraction object
        
    Returns:
        JSON-serializable dictionary representation
    """
    if not extraction:
        return {}
        
    # Base extraction data
    result = {
        "extraction_class": getattr(extraction, "extraction_class", None),
        "text": getattr(extraction, "text", None),
        "attributes": getattr(extraction, "attributes", {}),
        "char_interval": ci_dict(getattr(extraction, "char_interval", None)),
        "token_interval": ti_dict(getattr(extraction, "token_interval", None)),
    }
    
    # Add alignment status if available
    alignment_status = getattr(extraction, "alignment_status", None)
    if alignment_status is not None:
        result["alignment_status"] = get_alignment_status_value(alignment_status)
        
    # Add any additional attributes that might be present
    for attr in ["confidence", "source", "metadata"]:
        if hasattr(extraction, attr):
            result[attr] = getattr(extraction, attr)
            
    return result