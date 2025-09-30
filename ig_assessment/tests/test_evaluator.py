"""Tests for tri-state evaluator."""

import pytest
from dsl_parser import parse_applies_if
from evaluator import (
    TristateValue,
    evaluate_with_assignment,
    tristate_and,
    tristate_or,
    tristate_not,
)


def test_tristate_and_truth_table():
    """Test Kleene AND truth table."""
    # TRUE AND TRUE = TRUE
    assert tristate_and(TristateValue.TRUE, TristateValue.TRUE) == TristateValue.TRUE
    
    # TRUE AND FALSE = FALSE
    assert tristate_and(TristateValue.TRUE, TristateValue.FALSE) == TristateValue.FALSE
    
    # TRUE AND UNKNOWN = UNKNOWN
    assert tristate_and(TristateValue.TRUE, TristateValue.UNKNOWN) == TristateValue.UNKNOWN
    
    # FALSE AND anything = FALSE
    assert tristate_and(TristateValue.FALSE, TristateValue.TRUE) == TristateValue.FALSE
    assert tristate_and(TristateValue.FALSE, TristateValue.FALSE) == TristateValue.FALSE
    assert tristate_and(TristateValue.FALSE, TristateValue.UNKNOWN) == TristateValue.FALSE


def test_tristate_or_truth_table():
    """Test Kleene OR truth table."""
    # TRUE OR anything = TRUE
    assert tristate_or(TristateValue.TRUE, TristateValue.TRUE) == TristateValue.TRUE
    assert tristate_or(TristateValue.TRUE, TristateValue.FALSE) == TristateValue.TRUE
    assert tristate_or(TristateValue.TRUE, TristateValue.UNKNOWN) == TristateValue.TRUE
    
    # FALSE OR FALSE = FALSE
    assert tristate_or(TristateValue.FALSE, TristateValue.FALSE) == TristateValue.FALSE
    
    # FALSE OR UNKNOWN = UNKNOWN
    assert tristate_or(TristateValue.FALSE, TristateValue.UNKNOWN) == TristateValue.UNKNOWN


def test_tristate_not_truth_table():
    """Test Kleene NOT truth table."""
    assert tristate_not(TristateValue.TRUE) == TristateValue.FALSE
    assert tristate_not(TristateValue.FALSE) == TristateValue.TRUE
    assert tristate_not(TristateValue.UNKNOWN) == TristateValue.UNKNOWN


def test_evaluate_simple_equality_true():
    """Test evaluating simple equality that is true."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING'")
    assignment = {"AREA.USAGE": "PARKING"}
    result = evaluate_with_assignment(ast, assignment)
    assert result == TristateValue.TRUE


def test_evaluate_simple_equality_false():
    """Test evaluating simple equality that is false."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING'")
    assignment = {"AREA.USAGE": "RESIDENTIAL"}
    result = evaluate_with_assignment(ast, assignment)
    assert result == TristateValue.FALSE


def test_evaluate_simple_equality_unknown():
    """Test evaluating simple equality with unknown value."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING'")
    assignment = {}  # AREA.USAGE not assigned
    result = evaluate_with_assignment(ast, assignment)
    assert result == TristateValue.UNKNOWN


def test_evaluate_numeric_comparison():
    """Test evaluating numeric comparison."""
    ast = parse_applies_if("AREA.SIZE > 100")
    
    # Greater than - true
    assignment = {"AREA.SIZE": 150}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # Greater than - false
    assignment = {"AREA.SIZE": 50}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE
    
    # Unknown
    assignment = {}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.UNKNOWN


def test_evaluate_and_with_unknown():
    """Test AND with unknown propagation."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING' AND AREA.SIZE > 100")
    
    # Both true
    assignment = {"AREA.USAGE": "PARKING", "AREA.SIZE": 150}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # One false
    assignment = {"AREA.USAGE": "PARKING", "AREA.SIZE": 50}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE
    
    # One unknown - should be unknown
    assignment = {"AREA.USAGE": "PARKING"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.UNKNOWN
    
    # First false, second unknown - should be false
    assignment = {"AREA.USAGE": "RESIDENTIAL"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE


def test_evaluate_or_with_unknown():
    """Test OR with unknown propagation."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING' OR AREA.USAGE == 'STORAGE'")
    
    # First true
    assignment = {"AREA.USAGE": "PARKING"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # Both false
    assignment = {"AREA.USAGE": "RESIDENTIAL"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE
    
    # Unknown - should be unknown
    assignment = {}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.UNKNOWN


def test_evaluate_not():
    """Test NOT operation."""
    ast = parse_applies_if("NOT AREA.USAGE == 'PARKING'")
    
    # True becomes false
    assignment = {"AREA.USAGE": "PARKING"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE
    
    # False becomes true
    assignment = {"AREA.USAGE": "RESIDENTIAL"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # Unknown remains unknown
    assignment = {}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.UNKNOWN


def test_evaluate_in_operation():
    """Test IN operation."""
    ast = parse_applies_if("AREA.USAGE IN ['LODGING','COMMERCIAL','EDUCATION']")
    
    # In list
    assignment = {"AREA.USAGE": "COMMERCIAL"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # Not in list
    assignment = {"AREA.USAGE": "PARKING"}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE
    
    # Unknown
    assignment = {}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.UNKNOWN


def test_evaluate_has_operation():
    """Test HAS operation."""
    ast = parse_applies_if("HAS(FIRE.EXTINGUISHER)")
    
    # Has (truthy value)
    assignment = {"FIRE.EXTINGUISHER": True}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # Doesn't have (False)
    assignment = {"FIRE.EXTINGUISHER": False}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE
    
    # Unknown
    assignment = {}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.UNKNOWN


def test_evaluate_complex_expression():
    """Test complex nested expression."""
    ast = parse_applies_if(
        "(AREA.USAGE == 'PARKING' AND AREA.SIZE > 100) OR "
        "(AREA.USAGE == 'STORAGE' AND AREA.FIRE.LOAD >= 3000000)"
    )
    
    # First clause true
    assignment = {"AREA.USAGE": "PARKING", "AREA.SIZE": 150}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # Second clause true
    assignment = {"AREA.USAGE": "STORAGE", "AREA.FIRE.LOAD": 5000000}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.TRUE
    
    # Both false
    assignment = {"AREA.USAGE": "RESIDENTIAL", "AREA.SIZE": 50, "AREA.FIRE.LOAD": 1000}
    assert evaluate_with_assignment(ast, assignment) == TristateValue.FALSE
    
    # Partial - one clause false, other unknown
    assignment = {"AREA.USAGE": "PARKING", "AREA.SIZE": 50}
    result = evaluate_with_assignment(ast, assignment)
    # First clause: PARKING AND SIZE<=100 -> TRUE AND FALSE = FALSE
    # Second clause: PARKING!=STORAGE -> FALSE (first condition fails, so FALSE AND UNKNOWN = FALSE)
    # FALSE OR FALSE = FALSE
    assert result == TristateValue.FALSE


def test_evaluate_true_literal():
    """Test TRUE literal."""
    ast = parse_applies_if("TRUE")
    result = evaluate_with_assignment(ast, {})
    assert result == TristateValue.TRUE


def test_evaluate_false_literal():
    """Test FALSE literal."""
    ast = parse_applies_if("FALSE")
    result = evaluate_with_assignment(ast, {})
    assert result == TristateValue.FALSE
