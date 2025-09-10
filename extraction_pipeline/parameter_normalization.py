"""Parameter and unit normalization for the extraction pipeline.

This module provides parameter normalization with both original and SI units,
following the pipeline guide specifications.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Union
from .data_models import Parameter


# Unit conversion mappings to SI units
UNIT_CONVERSIONS = {
    # Length units
    'mm': ('m', 0.001),
    'millimeter': ('m', 0.001),
    'millimeters': ('m', 0.001),
    'cm': ('m', 0.01),
    'centimeter': ('m', 0.01),
    'centimeters': ('m', 0.01),
    'dm': ('m', 0.1),
    'decimeter': ('m', 0.1),
    'decimeters': ('m', 0.1),
    'km': ('m', 1000),
    'kilometer': ('m', 1000),
    'kilometers': ('m', 1000),
    'in': ('m', 0.0254),
    'inch': ('m', 0.0254),
    'inches': ('m', 0.0254),
    'ft': ('m', 0.3048),
    'foot': ('m', 0.3048),
    'feet': ('m', 0.3048),
    
    # Area units
    'mm²': ('m²', 0.000001),
    'mm2': ('m²', 0.000001),
    'cm²': ('m²', 0.0001),
    'cm2': ('m²', 0.0001),
    'dm²': ('m²', 0.01),
    'dm2': ('m²', 0.01),
    'km²': ('m²', 1000000),
    'km2': ('m²', 1000000),
    'ha': ('m²', 10000),
    'hectare': ('m²', 10000),
    'hectares': ('m²', 10000),
    
    # Volume units
    'mm³': ('m³', 0.000000001),
    'mm3': ('m³', 0.000000001),
    'cm³': ('m³', 0.000001),
    'cm3': ('m³', 0.000001),
    'dm³': ('m³', 0.001),
    'dm3': ('m³', 0.001),
    'l': ('m³', 0.001),
    'liter': ('m³', 0.001),
    'liters': ('m³', 0.001),
    'litre': ('m³', 0.001),
    'litres': ('m³', 0.001),
    
    # Time units
    'min': ('s', 60),
    'minute': ('s', 60),
    'minutes': ('s', 60),
    'h': ('s', 3600),
    'hour': ('s', 3600),
    'hours': ('s', 3600),
    'day': ('s', 86400),
    'days': ('s', 86400),
    
    # Temperature units (special handling needed)
    '°f': ('°C', 'fahrenheit'),
    'fahrenheit': ('°C', 'fahrenheit'),
    'f': ('°C', 'fahrenheit'),
    'k': ('°C', 'kelvin'),
    'kelvin': ('°C', 'kelvin'),
    
    # Pressure units
    'bar': ('Pa', 100000),
    'mbar': ('Pa', 100),
    'kpa': ('Pa', 1000),
    'mpa': ('Pa', 1000000),
    'psi': ('Pa', 6894.76),
    'atm': ('Pa', 101325),
    
    # Mass units
    'g': ('kg', 0.001),
    'gram': ('kg', 0.001),
    'grams': ('kg', 0.001),
    'mg': ('kg', 0.000001),
    'milligram': ('kg', 0.000001),
    'milligrams': ('kg', 0.000001),
    't': ('kg', 1000),
    'ton': ('kg', 1000),
    'tons': ('kg', 1000),
    'tonne': ('kg', 1000),
    'tonnes': ('kg', 1000),
    
    # Speed units
    'km/h': ('m/s', 0.277778),
    'kmh': ('m/s', 0.277778),
    'kph': ('m/s', 0.277778),
    'mph': ('m/s', 0.44704),
    
    # Force units
    'n': ('N', 1),  # Already SI
    'kn': ('N', 1000),
    'kilonewton': ('N', 1000),
    'kilonewtons': ('N', 1000),
    
    # Power units
    'w': ('W', 1),  # Already SI
    'kw': ('W', 1000),
    'kilowatt': ('W', 1000),
    'kilowatts': ('W', 1000),
    'mw': ('W', 1000000),
    'megawatt': ('W', 1000000),
    'megawatts': ('W', 1000000),
    'hp': ('W', 745.7),
    'horsepower': ('W', 745.7),
}


def normalize_unit(unit: str) -> Tuple[str, float]:
    """Normalize a unit to SI base unit with conversion factor.
    
    Args:
        unit: Original unit string
        
    Returns:
        Tuple of (si_unit, conversion_factor)
    """
    if not unit:
        return "", 1.0
    
    unit_clean = unit.strip().lower()
    
    # Direct lookup
    if unit_clean in UNIT_CONVERSIONS:
        si_unit, factor = UNIT_CONVERSIONS[unit_clean]
        return si_unit, factor
    
    # Handle compound units like "m/s²"
    if '/' in unit_clean:
        parts = unit_clean.split('/')
        if len(parts) == 2:
            numerator = parts[0].strip()
            denominator = parts[1].strip()
            
            num_si, num_factor = normalize_unit(numerator)
            den_si, den_factor = normalize_unit(denominator)
            
            if num_si and den_si:
                si_unit = f"{num_si}/{den_si}"
                factor = num_factor / den_factor if den_factor != 0 else 1.0
                return si_unit, factor
    
    # If no conversion found, return original
    return unit, 1.0


def convert_temperature(value: float, from_unit: str, to_unit: str = "°C") -> float:
    """Convert temperature between different scales.
    
    Args:
        value: Temperature value
        from_unit: Source unit
        to_unit: Target unit (default: °C)
        
    Returns:
        Converted temperature value
    """
    from_unit_clean = from_unit.lower().strip()
    
    # Convert to Celsius first
    if from_unit_clean in ['°f', 'fahrenheit', 'f']:
        celsius = (value - 32) * 5/9
    elif from_unit_clean in ['k', 'kelvin']:
        celsius = value - 273.15
    else:
        celsius = value  # Assume already Celsius
    
    # Convert from Celsius to target
    if to_unit.lower() in ['°f', 'fahrenheit', 'f']:
        return celsius * 9/5 + 32
    elif to_unit.lower() in ['k', 'kelvin']:
        return celsius + 273.15
    else:
        return celsius  # Return Celsius


def normalize_parameter_value(
    value: Union[str, float, int],
    unit: Optional[str] = None
) -> Tuple[Union[str, float, int], Optional[str], str]:
    """Normalize a parameter value and unit.
    
    Args:
        value: Original parameter value
        unit: Original unit
        
    Returns:
        Tuple of (normalized_value, normalized_unit, unit_system)
    """
    if unit is None:
        return value, None, "original"
    
    # Try to convert numeric values
    if isinstance(value, (int, float)):
        numeric_value = float(value)
    elif isinstance(value, str):
        # Try to parse numeric value from string
        numeric_match = re.search(r'^([+-]?\d+\.?\d*)(.*)$', value.strip())
        if numeric_match:
            try:
                numeric_value = float(numeric_match.group(1))
                # If unit was in the value string, extract it
                if not unit and numeric_match.group(2).strip():
                    unit = numeric_match.group(2).strip()
            except ValueError:
                # Non-numeric string value
                return value, unit, "original"
        else:
            # Non-numeric string value
            return value, unit, "original"
    else:
        return value, unit, "original"
    
    # Handle temperature conversion specially
    if unit and any(temp_unit in unit.lower() 
                   for temp_unit in ['°f', 'fahrenheit', 'kelvin', '°c', 'celsius']):
        if '°f' in unit.lower() or 'fahrenheit' in unit.lower():
            converted_value = convert_temperature(numeric_value, unit, "°C")
            return converted_value, "°C", "SI"
        elif 'kelvin' in unit.lower() or unit.lower() == 'k':
            converted_value = convert_temperature(numeric_value, unit, "°C")
            return converted_value, "°C", "SI"
        else:
            return numeric_value, "°C", "SI"
    
    # Standard unit conversion
    si_unit, conversion_factor = normalize_unit(unit)
    
    if si_unit != unit and conversion_factor != 1.0:
        normalized_value = numeric_value * conversion_factor
        return normalized_value, si_unit, "SI"
    
    return value, unit, "original"


def enhance_parameter_with_normalization(param_dict: Dict[str, Any]) -> Parameter:
    """Enhance parameter dictionary with normalization.
    
    Args:
        param_dict: Parameter dictionary from extraction
        
    Returns:
        Enhanced Parameter object with normalization
    """
    name = param_dict.get('name', param_dict.get('parameter', ''))
    operator = param_dict.get('operator', '==')
    original_value = param_dict.get('value', param_dict.get('original_value', ''))
    original_unit = param_dict.get('unit', param_dict.get('original_unit'))
    norm_id = param_dict.get('norm_id', param_dict.get('used_by_norm_id'))
    
    # Normalize the value and unit
    normalized_value, normalized_unit, unit_system = normalize_parameter_value(
        original_value, original_unit
    )
    
    # Create parameter with deterministic ID
    parameter = Parameter.create_with_id(
        name=name,
        operator=operator,
        value=original_value,
        unit=original_unit,
        norm_id=norm_id,
        normalized_value=normalized_value,
        normalized_unit=normalized_unit,
        unit_system=unit_system
    )
    
    return parameter


def batch_normalize_parameters(param_dicts: List[Dict[str, Any]]) -> List[Parameter]:
    """Batch normalize a list of parameter dictionaries.
    
    Args:
        param_dicts: List of parameter dictionaries
        
    Returns:
        List of enhanced Parameter objects
    """
    return [enhance_parameter_with_normalization(param_dict) for param_dict in param_dicts]


def calculate_normalization_coverage(parameters: List[Parameter]) -> float:
    """Calculate the percentage of parameters that were successfully normalized.
    
    Args:
        parameters: List of Parameter objects
        
    Returns:
        Normalization coverage percentage (0.0 to 1.0)
    """
    if not parameters:
        return 0.0
    
    normalized_count = sum(1 for p in parameters if p.unit_system == "SI")
    return normalized_count / len(parameters)


def get_normalization_report(parameters: List[Parameter]) -> Dict[str, Any]:
    """Generate a normalization report for parameters.
    
    Args:
        parameters: List of Parameter objects
        
    Returns:
        Dictionary with normalization statistics
    """
    total = len(parameters)
    if total == 0:
        return {
            'total_parameters': 0,
            'normalized_count': 0,
            'normalization_coverage': 0.0,
            'unit_systems': {},
            'failed_normalizations': []
        }
    
    normalized_count = sum(1 for p in parameters if p.unit_system == "SI")
    coverage = normalized_count / total
    
    # Count by unit system
    unit_systems = {}
    for param in parameters:
        system = param.unit_system
        unit_systems[system] = unit_systems.get(system, 0) + 1
    
    # Identify failed normalizations (parameters with no unit normalization)
    failed_normalizations = []
    for param in parameters:
        if (param.original_unit and 
            param.unit_system == "original" and 
            param.original_unit.lower() not in ['', 'none', 'n/a']):
            failed_normalizations.append({
                'param_id': param.param_id,
                'name': param.name,
                'original_unit': param.original_unit,
                'original_value': param.original_value
            })
    
    return {
        'total_parameters': total,
        'normalized_count': normalized_count,
        'normalization_coverage': coverage,
        'unit_systems': unit_systems,
        'failed_normalizations': failed_normalizations
    }