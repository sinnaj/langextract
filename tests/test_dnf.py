"""Tests for DNF conversion and optimization."""

import pytest

from ingest.dnf import (
    deduplicate_atomics,
    dnf_to_string,
    is_contradiction,
    optimize_dnf,
)
from ingest.types import Atomic, ComparisonOp, DNF, ValueType


def test_deduplicate_atomics():
    """Test deduplication of atomic predicates."""
    atomics = [
        Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
        Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
        Atomic(key="B", op=ComparisonOp.EQ, value=1, value_type=ValueType.INTEGER),
    ]
    
    result = deduplicate_atomics(atomics)
    assert len(result) == 2
    assert result[0].key == "A"
    assert result[1].key == "B"


def test_is_contradiction_simple():
    """Test detection of simple contradictions."""
    # A == TRUE and A == FALSE
    conjunct = [
        Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
        Atomic(key="A", op=ComparisonOp.EQ, value=False, value_type=ValueType.BOOLEAN),
    ]
    
    assert is_contradiction(conjunct)


def test_is_contradiction_different_values():
    """Test detection of contradictions with different values."""
    # A == 1 and A == 2
    conjunct = [
        Atomic(key="A", op=ComparisonOp.EQ, value=1, value_type=ValueType.INTEGER),
        Atomic(key="A", op=ComparisonOp.EQ, value=2, value_type=ValueType.INTEGER),
    ]
    
    assert is_contradiction(conjunct)


def test_is_not_contradiction():
    """Test that non-contradictory conjuncts are accepted."""
    # A == TRUE and B == FALSE (different keys)
    conjunct = [
        Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
        Atomic(key="B", op=ComparisonOp.EQ, value=False, value_type=ValueType.BOOLEAN),
    ]
    
    assert not is_contradiction(conjunct)


def test_is_not_contradiction_same_value():
    """Test that duplicate constraints don't count as contradictions."""
    # A == TRUE and A == TRUE (redundant but not contradictory)
    conjunct = [
        Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
        Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
    ]
    
    assert not is_contradiction(conjunct)


def test_optimize_dnf_removes_contradictions():
    """Test that optimize_dnf removes contradictory conjuncts."""
    dnf: DNF = [
        # Valid conjunct
        [
            Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
            Atomic(key="B", op=ComparisonOp.EQ, value=1, value_type=ValueType.INTEGER),
        ],
        # Contradictory conjunct
        [
            Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
            Atomic(key="A", op=ComparisonOp.EQ, value=False, value_type=ValueType.BOOLEAN),
        ],
    ]
    
    result = optimize_dnf(dnf)
    assert len(result) == 1
    assert len(result[0]) == 2


def test_optimize_dnf_deduplicates():
    """Test that optimize_dnf removes duplicate atomics."""
    dnf: DNF = [
        [
            Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
            Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
            Atomic(key="B", op=ComparisonOp.EQ, value=1, value_type=ValueType.INTEGER),
        ],
    ]
    
    result = optimize_dnf(dnf)
    assert len(result) == 1
    assert len(result[0]) == 2


def test_dnf_to_string_simple():
    """Test DNF string conversion for simple cases."""
    dnf: DNF = [
        [
            Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
        ],
    ]
    
    result = dnf_to_string(dnf)
    assert "A == True" in result


def test_dnf_to_string_complex():
    """Test DNF string conversion for complex expressions."""
    dnf: DNF = [
        [
            Atomic(key="A", op=ComparisonOp.EQ, value=True, value_type=ValueType.BOOLEAN),
            Atomic(key="B", op=ComparisonOp.EQ, value=1, value_type=ValueType.INTEGER),
        ],
        [
            Atomic(key="C", op=ComparisonOp.GT, value=5, value_type=ValueType.INTEGER),
        ],
    ]
    
    result = dnf_to_string(dnf)
    assert "||" in result  # OR operator
    assert "&&" in result  # AND operator


def test_dnf_to_string_empty():
    """Test DNF string conversion for empty DNF."""
    dnf: DNF = []
    result = dnf_to_string(dnf)
    assert result == "FALSE"


def test_dnf_to_string_true():
    """Test DNF string conversion for always-true DNF."""
    dnf: DNF = [[]]
    result = dnf_to_string(dnf)
    assert result == "TRUE"
