"""Tri-state evaluator for DSL expressions with Kleene logic.

This module implements a three-valued logic evaluator (TRUE, FALSE, UNKNOWN)
for partial feature assignments. It uses Kleene logic for propagation:
- TRUE AND UNKNOWN → UNKNOWN; FALSE AND X → FALSE
- TRUE OR X → TRUE; FALSE OR UNKNOWN → UNKNOWN
- NOT UNKNOWN → UNKNOWN
"""

from enum import Enum
from typing import Any, Dict, Optional, Union

from dsl_parser import (
    ASTNode,
    BinaryOp,
    GeoFunc,
    HasOp,
    Identifier,
    InOp,
    Literal,
    UnaryOp,
)


class TristateValue(Enum):
    """Three-valued logic values."""
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

    def __bool__(self):
        """Convert to boolean for convenience (UNKNOWN raises error)."""
        if self == TristateValue.UNKNOWN:
            raise ValueError("Cannot convert UNKNOWN to boolean")
        return self == TristateValue.TRUE

    def __str__(self):
        return self.value


# Kleene logic truth tables
def tristate_and(a: TristateValue, b: TristateValue) -> TristateValue:
    """Kleene AND operation."""
    if a == TristateValue.FALSE or b == TristateValue.FALSE:
        return TristateValue.FALSE
    if a == TristateValue.UNKNOWN or b == TristateValue.UNKNOWN:
        return TristateValue.UNKNOWN
    return TristateValue.TRUE


def tristate_or(a: TristateValue, b: TristateValue) -> TristateValue:
    """Kleene OR operation."""
    if a == TristateValue.TRUE or b == TristateValue.TRUE:
        return TristateValue.TRUE
    if a == TristateValue.UNKNOWN or b == TristateValue.UNKNOWN:
        return TristateValue.UNKNOWN
    return TristateValue.FALSE


def tristate_not(a: TristateValue) -> TristateValue:
    """Kleene NOT operation."""
    if a == TristateValue.UNKNOWN:
        return TristateValue.UNKNOWN
    return TristateValue.TRUE if a == TristateValue.FALSE else TristateValue.FALSE


class Evaluator:
    """Evaluator for DSL expressions with partial assignments."""

    def __init__(self, assignment: Optional[Dict[str, Any]] = None):
        """Initialize evaluator with a feature assignment.

        Args:
            assignment: Dictionary mapping feature names to values.
                       If a feature is not in the dict, it's considered UNKNOWN.
        """
        self.assignment = assignment or {}

    def evaluate(self, node: Optional[ASTNode]) -> TristateValue:
        """Evaluate an AST node with the current assignment.

        Args:
            node: AST node to evaluate

        Returns:
            TristateValue (TRUE, FALSE, or UNKNOWN)
        """
        if node is None:
            return TristateValue.UNKNOWN

        if isinstance(node, Literal):
            # Literal boolean value
            if isinstance(node.value, bool):
                return TristateValue.TRUE if node.value else TristateValue.FALSE
            # Non-boolean literals shouldn't appear at top level
            return TristateValue.UNKNOWN

        elif isinstance(node, BinaryOp):
            if node.op == "AND":
                left = self.evaluate(node.left)
                right = self.evaluate(node.right)
                return tristate_and(left, right)
            elif node.op == "OR":
                left = self.evaluate(node.left)
                right = self.evaluate(node.right)
                return tristate_or(left, right)
            else:
                # Comparison operations
                return self._evaluate_comparison(node)

        elif isinstance(node, UnaryOp):
            if node.op == "NOT":
                operand = self.evaluate(node.operand)
                return tristate_not(operand)

        elif isinstance(node, InOp):
            return self._evaluate_in(node)

        elif isinstance(node, HasOp):
            return self._evaluate_has(node)

        elif isinstance(node, GeoFunc):
            # Geographic functions - treat as feature comparisons
            return self._evaluate_geo_func(node)

        return TristateValue.UNKNOWN

    def _evaluate_comparison(self, node: BinaryOp) -> TristateValue:
        """Evaluate a comparison operation."""
        # Get the identifier name
        if not isinstance(node.left, Identifier):
            return TristateValue.UNKNOWN

        feature_name = node.left.name
        
        # Check if right side is also an identifier (identifier-to-identifier comparison)
        if isinstance(node.right, Identifier):
            right_feature_name = node.right.name
            
            # Check if both features are assigned
            if feature_name not in self.assignment or right_feature_name not in self.assignment:
                return TristateValue.UNKNOWN
            
            left_value = self.assignment[feature_name]
            right_value = self.assignment[right_feature_name]
            
            # Perform comparison
            try:
                if node.op == "==":
                    result = left_value == right_value
                elif node.op == "!=":
                    result = left_value != right_value
                elif node.op == ">":
                    result = left_value > right_value
                elif node.op == ">=":
                    result = left_value >= right_value
                elif node.op == "<":
                    result = left_value < right_value
                elif node.op == "<=":
                    result = left_value <= right_value
                else:
                    return TristateValue.UNKNOWN

                return TristateValue.TRUE if result else TristateValue.FALSE
            except (TypeError, ValueError):
                return TristateValue.FALSE
        
        # Right side is a literal
        literal_value = node.right.value if isinstance(node.right, Literal) else None

        # Check if feature is assigned
        if feature_name not in self.assignment:
            return TristateValue.UNKNOWN

        actual_value = self.assignment[feature_name]

        # Perform comparison
        try:
            if node.op == "==":
                result = actual_value == literal_value
            elif node.op == "!=":
                result = actual_value != literal_value
            elif node.op == ">":
                result = actual_value > literal_value
            elif node.op == ">=":
                result = actual_value >= literal_value
            elif node.op == "<":
                result = actual_value < literal_value
            elif node.op == "<=":
                result = actual_value <= literal_value
            else:
                return TristateValue.UNKNOWN

            return TristateValue.TRUE if result else TristateValue.FALSE
        except (TypeError, ValueError):
            # Comparison failed (type mismatch, etc.)
            return TristateValue.FALSE

    def _evaluate_in(self, node: InOp) -> TristateValue:
        """Evaluate IN operation."""
        feature_name = node.identifier.name

        if feature_name not in self.assignment:
            return TristateValue.UNKNOWN

        actual_value = self.assignment[feature_name]
        literal_values = [lit.value for lit in node.values]

        # Check membership
        result = actual_value in literal_values
        return TristateValue.TRUE if result else TristateValue.FALSE

    def _evaluate_has(self, node: HasOp) -> TristateValue:
        """Evaluate HAS operation (existence test)."""
        feature_name = node.identifier.name

        if feature_name not in self.assignment:
            return TristateValue.UNKNOWN

        # If feature is assigned, it exists
        # Check if the value is truthy (not None, not False, not empty)
        actual_value = self.assignment[feature_name]
        if actual_value is None or actual_value is False:
            return TristateValue.FALSE
        return TristateValue.TRUE

    def _evaluate_geo_func(self, node: GeoFunc) -> TristateValue:
        """Evaluate geographic function like WITHIN, OVERLAPS, ADJACENT_TO."""
        # Treat as a special feature comparison
        # We construct a pseudo-feature name from the function
        feature_name = f"{node.identifier.name}.{node.func_name}"

        if feature_name not in self.assignment:
            return TristateValue.UNKNOWN

        # Check if the assigned value matches the argument
        actual_value = self.assignment[feature_name]
        result = actual_value == node.arg
        return TristateValue.TRUE if result else TristateValue.FALSE


def evaluate_with_assignment(
    ast: Optional[ASTNode],
    assignment: Dict[str, Any]
) -> TristateValue:
    """Evaluate an AST with a feature assignment.

    Args:
        ast: Root AST node
        assignment: Dictionary mapping feature names to values

    Returns:
        TristateValue (TRUE, FALSE, or UNKNOWN)
    """
    evaluator = Evaluator(assignment)
    return evaluator.evaluate(ast)


def is_fully_determined(
    ast: Optional[ASTNode],
    assignment: Dict[str, Any]
) -> bool:
    """Check if an AST evaluates to TRUE or FALSE (not UNKNOWN).

    Args:
        ast: Root AST node
        assignment: Dictionary mapping feature names to values

    Returns:
        True if the result is determined (TRUE or FALSE), False if UNKNOWN
    """
    result = evaluate_with_assignment(ast, assignment)
    return result != TristateValue.UNKNOWN
