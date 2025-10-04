"""Parser for applies_if expressions with DNF conversion.

This module converts boolean expressions to Disjunctive Normal Form (DNF).
It leverages the existing DSL parser from ig_assessment and adds DNF conversion.
"""

import sys
from pathlib import Path
from typing import Any, List, Optional

# Add ig_assessment to path to import dsl_parser
ig_assessment_path = Path(__file__).parent.parent / "ig_assessment"
if str(ig_assessment_path) not in sys.path:
    sys.path.insert(0, str(ig_assessment_path))

from dsl_parser import (
    ASTNode,
    BinaryOp,
    Identifier,
    InOp,
    Literal,
    UnaryOp,
    parse_applies_if,
)

from .types import Atomic, ComparisonOp, Conjunct, DNF, ValueType


def infer_value_type(value: Any) -> ValueType:
    """Infer the value type from a Python value.
    
    Args:
        value: The value to classify
        
    Returns:
        ValueType enum matching the value's type
    """
    if isinstance(value, bool):
        return ValueType.BOOLEAN
    elif isinstance(value, int):
        return ValueType.INTEGER
    elif isinstance(value, float):
        return ValueType.NUMERIC
    elif isinstance(value, str):
        return ValueType.STRING
    elif isinstance(value, list):
        return ValueType.ARRAY
    elif isinstance(value, dict):
        return ValueType.JSON
    else:
        return ValueType.STRING  # Default fallback


def canonicalize_identifier(identifier: str) -> str:
    """Canonicalize identifier to UPPER.DOT.CASE format.
    
    Args:
        identifier: Raw identifier string
        
    Returns:
        Canonicalized identifier in uppercase with dots
    """
    # Remove extra whitespace and convert to uppercase
    canonical = identifier.strip().upper()
    # Ensure consistent dot notation (no spaces around dots)
    canonical = ".".join(part.strip() for part in canonical.split("."))
    return canonical


def map_operator(op_str: str) -> ComparisonOp:
    """Map DSL operator string to ComparisonOp enum.
    
    Args:
        op_str: Operator string from AST (e.g., '==', '!=', '>')
        
    Returns:
        ComparisonOp enum value
    """
    mapping = {
        "==": ComparisonOp.EQ,
        "!=": ComparisonOp.NEQ,
        ">": ComparisonOp.GT,
        ">=": ComparisonOp.GTE,
        "<": ComparisonOp.LT,
        "<=": ComparisonOp.LTE,
        "IN": ComparisonOp.IN,
        "NOT_IN": ComparisonOp.NOT_IN,
    }
    return mapping.get(op_str, ComparisonOp.EQ)


def ast_to_atomic(node: ASTNode) -> Optional[Atomic]:
    """Convert a comparison AST node to an Atomic predicate.
    
    Args:
        node: AST node representing a comparison
        
    Returns:
        Atomic predicate or None if not a simple comparison
    """
    if isinstance(node, BinaryOp) and node.op in ["==", "!=", ">", ">=", "<", "<="]:
        # Standard comparison
        if isinstance(node.left, Identifier):
            key = canonicalize_identifier(node.left.name)
            # Get value from right side
            if isinstance(node.right, Literal):
                value = node.right.value
            elif isinstance(node.right, Identifier):
                # Identifier on right side - treat as string
                value = node.right.name
            else:
                return None
            
            op = map_operator(node.op)
            value_type = infer_value_type(value)
            return Atomic(key=key, op=op, value=value, value_type=value_type)
    
    elif isinstance(node, InOp):
        # IN operation
        key = canonicalize_identifier(node.identifier.name)
        # Extract values from list of Literals
        values = [lit.value for lit in node.values]
        op = ComparisonOp.IN
        value_type = ValueType.ARRAY
        return Atomic(key=key, op=op, value=values, value_type=value_type)
    
    return None


def push_not_down(node: ASTNode) -> ASTNode:
    """Push NOT operations down to atomic predicates using De Morgan's laws.
    
    Args:
        node: AST node to transform
        
    Returns:
        Transformed AST with NOTs pushed down
    """
    if isinstance(node, UnaryOp) and node.op == "NOT":
        operand = node.operand
        
        # NOT NOT X -> X
        if isinstance(operand, UnaryOp) and operand.op == "NOT":
            return push_not_down(operand.operand)
        
        # NOT (A AND B) -> (NOT A) OR (NOT B)
        elif isinstance(operand, BinaryOp) and operand.op == "AND":
            left = push_not_down(UnaryOp("NOT", operand.left))
            right = push_not_down(UnaryOp("NOT", operand.right))
            return BinaryOp("OR", left, right)
        
        # NOT (A OR B) -> (NOT A) AND (NOT B)
        elif isinstance(operand, BinaryOp) and operand.op == "OR":
            left = push_not_down(UnaryOp("NOT", operand.left))
            right = push_not_down(UnaryOp("NOT", operand.right))
            return BinaryOp("AND", left, right)
        
        # NOT (A == B) -> A != B (and vice versa)
        elif isinstance(operand, BinaryOp) and operand.op in ["==", "!="]:
            new_op = "!=" if operand.op == "==" else "=="
            return BinaryOp(new_op, operand.left, operand.right)
        
        # NOT (A > B) -> A <= B, etc.
        elif isinstance(operand, BinaryOp):
            op_negation = {
                ">": "<=",
                ">=": "<",
                "<": ">=",
                "<=": ">",
            }
            if operand.op in op_negation:
                return BinaryOp(op_negation[operand.op], operand.left, operand.right)
        
        # Keep NOT for atomic predicates that can't be negated
        return node
    
    elif isinstance(node, BinaryOp):
        left = push_not_down(node.left)
        right = push_not_down(node.right)
        return BinaryOp(node.op, left, right)
    
    else:
        return node


def to_dnf_recursive(node: ASTNode) -> DNF:
    """Convert AST to DNF representation recursively.
    
    Args:
        node: AST node to convert
        
    Returns:
        DNF representation (list of conjuncts, each a list of atomics)
    """
    # Handle literals
    if isinstance(node, Literal):
        if node.value is True:
            # TRUE -> empty DNF (always satisfied)
            return [[]]
        elif node.value is False:
            # FALSE -> no disjuncts (never satisfied)
            return []
        else:
            # Non-boolean literal shouldn't appear at top level
            return [[]]
    
    # Handle comparisons (atomic predicates)
    atomic = ast_to_atomic(node)
    if atomic:
        # Single atomic -> DNF with one conjunct containing one atomic
        return [[atomic]]
    
    # Handle binary operations
    if isinstance(node, BinaryOp):
        if node.op == "AND":
            # A AND B -> combine all pairs of conjuncts
            left_dnf = to_dnf_recursive(node.left)
            right_dnf = to_dnf_recursive(node.right)
            result = []
            for left_conj in left_dnf:
                for right_conj in right_dnf:
                    # Merge conjuncts
                    combined = left_conj + right_conj
                    result.append(combined)
            return result
        
        elif node.op == "OR":
            # A OR B -> concatenate DNFs
            left_dnf = to_dnf_recursive(node.left)
            right_dnf = to_dnf_recursive(node.right)
            return left_dnf + right_dnf
    
    # Fallback for unsupported node types
    return [[]]


def ast_to_dnf(ast: Optional[ASTNode]) -> DNF:
    """Convert AST to DNF after pushing NOTs down.
    
    Args:
        ast: Root AST node
        
    Returns:
        DNF representation
    """
    if ast is None:
        return []
    
    # First push NOTs down to leaves
    normalized_ast = push_not_down(ast)
    
    # Then convert to DNF
    return to_dnf_recursive(normalized_ast)


def expr_to_dnf(expr: str) -> DNF:
    """Parse expression string and convert to DNF.
    
    This is the main entry point for converting boolean expressions.
    
    Args:
        expr: Boolean expression string (e.g., "A == TRUE AND (B OR C)")
        
    Returns:
        DNF representation
        
    Example:
        >>> expr_to_dnf("A == TRUE AND (B == 1 OR C == 2)")
        [
            [Atomic(key='A', op='EQ', value=True, ...), 
             Atomic(key='B', op='EQ', value=1, ...)],
            [Atomic(key='A', op='EQ', value=True, ...), 
             Atomic(key='C', op='EQ', value=2, ...)]
        ]
    """
    if not expr or expr.strip().upper() in ["TRUE", "FALSE"]:
        # Handle trivial cases
        if expr.strip().upper() == "TRUE":
            return [[]]  # Always true
        else:
            return []  # Always false
    
    ast = parse_applies_if(expr)
    if ast is None:
        # Failed to parse - return empty DNF
        return []
    
    return ast_to_dnf(ast)
