"""
Parameter extraction module for LangExtract.

This module handles the extraction and processing of parameters from NORM entities
in the LangExtract post-processing pipeline.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


def parse_parameter(expr: str) -> Optional[Tuple[str, str, Any, Optional[str]]]:
    """
    Parse a parameter expression string into its components.
    
    Args:
        expr: Parameter expression string (e.g., "ROAD.WIDTH >= 3.5 m")
        
    Returns:
        Tuple of (path, operator, value, unit) or None if parsing fails
        
    Examples:
        >>> parse_parameter("ROAD.WIDTH >= 3.5 m")
        ("ROAD.WIDTH", ">=", 3.5, "m")
        
        >>> parse_parameter("BUILDING.TYPE == RESIDENTIAL")
        ("BUILDING.TYPE", "==", "RESIDENTIAL", None)
    """
    if not isinstance(expr, str):
        return None
        
    # Match parameter pattern: PATH OPERATOR VALUE [UNIT]
    m = re.match(r"^\s*([A-Z0-9_.]+)\s*(==|>=|<=|>|<)\s*(.+?)\s*$", expr)
    if not m:
        return None
        
    path, op, val_str = m.group(1), m.group(2), m.group(3)
    
    # Try numeric value with optional decimal comma/dot, keep unit remainder
    m2 = re.match(r"^\s*([0-9]+(?:[\.,][0-9]+)?)\s*(.*)$", val_str)
    if m2:
        num = m2.group(1).replace(',', '.')
        try:
            val: Any = float(num) if ('.' in num) else int(num)
        except Exception:
            try:
                val = float(num)
            except Exception:
                val = num
        unit = m2.group(2).strip() or None
        return (path, op, val, unit)
    
    # Non-numeric value (enum/string)
    return (path, op, val_str.strip(), None)


def extract_parameters_from_norms(
    norms_to_process: List[Dict[str, Any]], 
    param_counter_start: int = 1
) -> List[Dict[str, Any]]:
    """
    Extract parameters from NORM entities and create Parameter extraction items.
    
    Args:
        norms_to_process: List of norm attribute dictionaries
        param_counter_start: Starting counter for parameter IDs
        
    Returns:
        List of Parameter extraction dictionaries
    """
    param_list: List[Dict[str, Any]] = []
    param_counter = param_counter_start

    def _next_pid() -> str:
        nonlocal param_counter
        pid = f"P::{param_counter:06d}"
        param_counter += 1
        return pid

    # Process norms for parameters
    for norm_data in norms_to_process:
        if not isinstance(norm_data, dict):
            continue
            
        norm_id = norm_data.get("id")
        if not norm_id:
            continue

        # Extracted parameters - ensure it's a list
        extracted_parameters = norm_data.get("extracted_parameters")
        if extracted_parameters is None:
            extracted_parameters = []
        elif not isinstance(extracted_parameters, list):
            extracted_parameters = []
            
        for expr in extracted_parameters:
            parsed = parse_parameter(expr)
            if not parsed:
                continue
                
            path, op, val, unit = parsed
            param_list.append({
                "extraction_class": "Parameter",
                "extraction_text": expr,
                "attributes": {
                    "id": _next_pid(),
                    "applies_for_tag": path,
                    "operator": op,
                    "value": val,
                    "unit": unit,
                    "norm_ids": [norm_id],
                },
            })

    return param_list
