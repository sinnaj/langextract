"""Tests for parser and DNF conversion."""

import pytest

from ingest.parser import (
    canonicalize_identifier,
    expr_to_dnf,
    infer_value_type,
    map_operator,
)
from ingest.types import ComparisonOp, ValueType


def test_canonicalize_identifier():
    """Test identifier canonicalization."""
    assert canonicalize_identifier("building.type") == "BUILDING.TYPE"
    assert canonicalize_identifier("AREA.USAGE") == "AREA.USAGE"
    assert canonicalize_identifier(" area . usage ") == "AREA.USAGE"


def test_infer_value_type():
    """Test value type inference."""
    assert infer_value_type(True) == ValueType.BOOLEAN
    assert infer_value_type(False) == ValueType.BOOLEAN
    assert infer_value_type(42) == ValueType.INTEGER
    assert infer_value_type(3.14) == ValueType.NUMERIC
    assert infer_value_type("hello") == ValueType.STRING
    assert infer_value_type([1, 2, 3]) == ValueType.ARRAY
    assert infer_value_type({"key": "value"}) == ValueType.JSON


def test_map_operator():
    """Test operator mapping."""
    assert map_operator("==") == ComparisonOp.EQ
    assert map_operator("!=") == ComparisonOp.NEQ
    assert map_operator(">") == ComparisonOp.GT
    assert map_operator(">=") == ComparisonOp.GTE
    assert map_operator("<") == ComparisonOp.LT
    assert map_operator("<=") == ComparisonOp.LTE
    assert map_operator("IN") == ComparisonOp.IN


def test_expr_to_dnf_simple():
    """Test parsing simple expressions."""
    dnf = expr_to_dnf("A == TRUE")
    assert len(dnf) == 1
    assert len(dnf[0]) == 1
    assert dnf[0][0].key == "A"
    assert dnf[0][0].op == ComparisonOp.EQ
    assert dnf[0][0].value is True


def test_expr_to_dnf_and():
    """Test parsing AND expressions."""
    dnf = expr_to_dnf("A == TRUE AND B == 1")
    assert len(dnf) == 1
    assert len(dnf[0]) == 2
    assert dnf[0][0].key == "A"
    assert dnf[0][1].key == "B"


def test_expr_to_dnf_or():
    """Test parsing OR expressions."""
    dnf = expr_to_dnf("A == TRUE OR B == 1")
    assert len(dnf) == 2
    assert len(dnf[0]) == 1
    assert len(dnf[1]) == 1
    assert dnf[0][0].key == "A"
    assert dnf[1][0].key == "B"


def test_expr_to_dnf_distribution():
    """Test distribution: (A AND (B OR C)) -> (A AND B) OR (A AND C)."""
    dnf = expr_to_dnf("A == TRUE AND (B == 1 OR C == 2)")
    assert len(dnf) == 2
    # First disjunct: A AND B
    assert len(dnf[0]) == 2
    assert dnf[0][0].key == "A"
    assert dnf[0][1].key == "B"
    # Second disjunct: A AND C
    assert len(dnf[1]) == 2
    assert dnf[1][0].key == "A"
    assert dnf[1][1].key == "C"


def test_expr_to_dnf_complex_distribution():
    """Test complex distribution: (A OR B) AND (C OR D)."""
    dnf = expr_to_dnf("(A == TRUE OR B == TRUE) AND (C == 1 OR D == 2)")
    assert len(dnf) == 4
    # Should produce: [A,C], [A,D], [B,C], [B,D]
    
    # Extract keys from each conjunct
    conjunct_keys = [sorted([a.key for a in conj]) for conj in dnf]
    
    # Check all combinations are present
    assert ["A", "C"] in conjunct_keys
    assert ["A", "D"] in conjunct_keys
    assert ["B", "C"] in conjunct_keys
    assert ["B", "D"] in conjunct_keys


def test_expr_to_dnf_with_extra_parens():
    """Test (A AND (B OR C)) AND D -> [[A,B,D], [A,C,D]]."""
    dnf = expr_to_dnf("(A == TRUE AND (B == 1 OR C == 2)) AND D == 3")
    assert len(dnf) == 2
    
    # First disjunct: A, B, D
    assert len(dnf[0]) == 3
    keys0 = sorted([a.key for a in dnf[0]])
    assert keys0 == ["A", "B", "D"]
    
    # Second disjunct: A, C, D
    assert len(dnf[1]) == 3
    keys1 = sorted([a.key for a in dnf[1]])
    assert keys1 == ["A", "C", "D"]


def test_expr_to_dnf_in_operator():
    """Test IN operator parsing."""
    dnf = expr_to_dnf("A IN ['x', 'y', 'z']")
    assert len(dnf) == 1
    assert len(dnf[0]) == 1
    assert dnf[0][0].key == "A"
    assert dnf[0][0].op == ComparisonOp.IN
    assert dnf[0][0].value == ["x", "y", "z"]


def test_expr_to_dnf_numeric_comparison():
    """Test numeric comparison operators."""
    dnf = expr_to_dnf("X > 100")
    assert len(dnf) == 1
    assert dnf[0][0].key == "X"
    assert dnf[0][0].op == ComparisonOp.GT
    assert dnf[0][0].value == 100
    
    dnf = expr_to_dnf("Y <= 50")
    assert len(dnf) == 1
    assert dnf[0][0].key == "Y"
    assert dnf[0][0].op == ComparisonOp.LTE
    assert dnf[0][0].value == 50


def test_expr_to_dnf_string_values():
    """Test parsing with string values."""
    dnf = expr_to_dnf("TYPE == 'RESIDENTIAL'")
    assert len(dnf) == 1
    assert dnf[0][0].key == "TYPE"
    assert dnf[0][0].value == "RESIDENTIAL"
    assert dnf[0][0].value_type == ValueType.STRING


def test_expr_to_dnf_not_operator():
    """Test NOT operator pushdown."""
    # NOT (A == TRUE) -> A != TRUE or A == FALSE (simplified)
    dnf = expr_to_dnf("NOT (A == TRUE)")
    assert len(dnf) == 1
    assert len(dnf[0]) == 1
    assert dnf[0][0].key == "A"
    # Should be converted to NEQ
    assert dnf[0][0].op == ComparisonOp.NEQ


def test_expr_to_dnf_de_morgan():
    """Test De Morgan's law: NOT (A AND B) -> (NOT A) OR (NOT B)."""
    dnf = expr_to_dnf("NOT (A == TRUE AND B == TRUE)")
    # Should produce (A != TRUE) OR (B != TRUE)
    assert len(dnf) == 2


def test_expr_to_dnf_trivial_true():
    """Test trivial TRUE expression."""
    dnf = expr_to_dnf("TRUE")
    assert dnf == [[]]  # Empty conjunct = always true


def test_expr_to_dnf_trivial_false():
    """Test trivial FALSE expression."""
    dnf = expr_to_dnf("FALSE")
    assert dnf == []  # No disjuncts = always false


def test_expr_to_dnf_real_world_example():
    """Test real-world example from problem statement."""
    expr = "BUILDING.PROTECTION_LEVEL.IS_PROTECTED == TRUE AND DB.APPLICATION.IS_INCOMPATIBLE_WITH_PROTECTION_LEVEL == TRUE"
    dnf = expr_to_dnf(expr)
    
    assert len(dnf) == 1
    assert len(dnf[0]) == 2
    
    keys = [a.key for a in dnf[0]]
    assert "BUILDING.PROTECTION_LEVEL.IS_PROTECTED" in keys
    assert "DB.APPLICATION.IS_INCOMPATIBLE_WITH_PROTECTION_LEVEL" in keys


def test_expr_to_dnf_complex_real_world():
    """Test complex real-world expression."""
    expr = "A != B AND ((C == 'X') OR (D IN ['Y', 'Z'] AND E > 500))"
    dnf = expr_to_dnf(expr)
    
    # Should produce 2 disjuncts:
    # 1. A != B AND C == 'X'
    # 2. A != B AND D IN ['Y','Z'] AND E > 500
    assert len(dnf) == 2
    
    # First disjunct should have A, C
    # Second disjunct should have A, D, E
    keys0 = sorted([a.key for a in dnf[0]])
    keys1 = sorted([a.key for a in dnf[1]])
    
    if "C" in keys0:
        assert set(keys0) == {"A", "C"}
        assert set(keys1) == {"A", "D", "E"}
    else:
        assert set(keys0) == {"A", "D", "E"}
        assert set(keys1) == {"A", "C"}
