"""Tests for DSL parser."""

import pytest
from dsl_parser import (
    parse_applies_if,
    Identifier,
    Literal,
    BinaryOp,
    UnaryOp,
    InOp,
    HasOp,
)


def test_parse_simple_equality():
    """Test parsing simple equality."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING'")
    assert isinstance(ast, BinaryOp)
    assert ast.op == "=="
    assert isinstance(ast.left, Identifier)
    assert ast.left.name == "AREA.USAGE"
    assert isinstance(ast.right, Literal)
    assert ast.right.value == "PARKING"


def test_parse_numeric_comparison():
    """Test parsing numeric comparison."""
    ast = parse_applies_if("AREA.SIZE > 100")
    assert isinstance(ast, BinaryOp)
    assert ast.op == ">"
    assert ast.left.name == "AREA.SIZE"
    assert ast.right.value == 100


def test_parse_and_operation():
    """Test parsing AND operation."""
    ast = parse_applies_if("AREA.USAGE == 'PARKING' AND AREA.SIZE > 100")
    assert isinstance(ast, BinaryOp)
    assert ast.op == "AND"


def test_parse_or_operation():
    """Test parsing OR operation."""
    ast = parse_applies_if("AREA.USAGE == 'RESIDENTIAL' OR AREA.USAGE == 'COMMERCIAL'")
    assert isinstance(ast, BinaryOp)
    assert ast.op == "OR"


def test_parse_not_operation():
    """Test parsing NOT operation."""
    ast = parse_applies_if("NOT AREA.USAGE == 'PARKING'")
    assert isinstance(ast, UnaryOp)
    assert ast.op == "NOT"


def test_parse_in_operation():
    """Test parsing IN operation."""
    ast = parse_applies_if("AREA.USAGE IN ['LODGING','COMMERCIAL','EDUCATION']")
    assert isinstance(ast, InOp)
    assert ast.identifier.name == "AREA.USAGE"
    assert len(ast.values) == 3
    assert ast.values[0].value == "LODGING"


def test_parse_has_operation():
    """Test parsing HAS operation."""
    ast = parse_applies_if("HAS(FIRE.EXTINGUISHER)")
    assert isinstance(ast, HasOp)
    assert ast.identifier.name == "FIRE.EXTINGUISHER"


def test_parse_nested_parentheses():
    """Test parsing nested parentheses."""
    ast = parse_applies_if("(AREA.USAGE == 'PARKING' AND AREA.SIZE > 100) OR (AREA.USAGE == 'STORAGE')")
    assert isinstance(ast, BinaryOp)
    assert ast.op == "OR"


def test_parse_complex_expression():
    """Test parsing complex expression from problem statement."""
    expr = """AREA.USAGE != BUILDING.USAGE AND (
        (AREA.USAGE == 'RESIDENTIAL.HOUSING') OR
        (AREA.USAGE IN ['LODGING','ADMINISTRATIVE','COMMERCIAL','EDUCATION'] AND AREA.SIZE > 500) OR
        (AREA.USAGE == 'PUBLIC.ASSEMBLY' AND AREA.OCCUPANCY > 500) OR
        (AREA.USAGE == 'PARKING' AND AREA.SIZE > 100) OR
        (AREA.USAGE == 'STORAGE' AND AREA.FIRE.LOAD_TOTAL_CORRECTED >= 3000000)
    )"""
    ast = parse_applies_if(expr)
    assert ast is not None
    assert isinstance(ast, BinaryOp)


def test_parse_true_literal():
    """Test parsing TRUE literal."""
    ast = parse_applies_if("TRUE")
    assert isinstance(ast, Literal)
    assert ast.value is True


def test_parse_false_literal():
    """Test parsing FALSE literal."""
    ast = parse_applies_if("FALSE")
    assert isinstance(ast, Literal)
    assert ast.value is False


def test_parse_all_comparison_operators():
    """Test all comparison operators."""
    operators = ["==", "!=", ">", ">=", "<", "<="]
    for op in operators:
        ast = parse_applies_if(f"VALUE {op} 100")
        assert isinstance(ast, BinaryOp)
        assert ast.op == op


def test_parse_empty_string():
    """Test parsing empty string."""
    ast = parse_applies_if("")
    assert ast is None


def test_parse_invalid_expression():
    """Test parsing invalid expression."""
    ast = parse_applies_if("INVALID SYNTAX @@")
    assert ast is None
