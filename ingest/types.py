"""Type definitions for norm ingestion pipeline."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Literal


class ValueType(str, Enum):
    """Value type enumeration matching PostgreSQL value_type enum."""

    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    NUMERIC = "NUMERIC"
    STRING = "STRING"
    ENUM = "ENUM"
    ARRAY = "ARRAY"
    JSON = "JSON"


class ComparisonOp(str, Enum):
    """Comparison operator enumeration matching PostgreSQL cmp_op enum."""

    EQ = "EQ"
    NEQ = "NEQ"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"


@dataclass
class Atomic:
    """Atomic predicate in a boolean expression.
    
    Represents a single comparison like: BUILDING.TYPE == 'RESIDENTIAL'
    
    Attributes:
        key: Canonicalized identifier (e.g., 'BUILDING.TYPE')
        op: Comparison operator
        value: Expected value (can be any type)
        value_type: Type classification for PostgreSQL storage
    """

    key: str
    op: ComparisonOp
    value: Any
    value_type: ValueType


# Type aliases for DNF representation
Conjunct = List[Atomic]  # AND-list of atomic predicates
DNF = List[Conjunct]  # OR-list of conjuncts (OR of ANDs)
