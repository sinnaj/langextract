"""DSL parser for applies_if predicates using Lark.

This module implements a safe parser for the DSL used in applies_if predicates
of Norm objects. It supports:
- Boolean operators: AND, OR, NOT, parentheses
- Comparisons: ==, !=, >, >=, <, <=
- Membership: IN with lists
- Literals: strings, integers, floats, booleans
- Identifiers: dotted notation (A.B.C)
"""

from dataclasses import dataclass
from typing import Any, List, Optional, Union

from lark import Lark, Transformer, Tree, Token


# Lark grammar for the DSL
DSL_GRAMMAR = r"""
    ?start: expr

    ?expr: or_expr

    ?or_expr: and_expr
        | or_expr "OR" and_expr -> or_op

    ?and_expr: not_expr
        | and_expr "AND" not_expr -> and_op

    ?not_expr: "NOT" not_expr -> not_op
        | comparison

    ?comparison: identifier "==" value -> eq
        | identifier "!=" value -> ne
        | identifier ">" value -> gt
        | identifier ">=" value -> ge
        | identifier "<" value -> lt
        | identifier "<=" value -> le
        | identifier "IN" "[" literal_list "]" -> in_op
        | identifier "IN" "(" literal_list ")" -> in_op
        | "HAS" "(" identifier ")" -> has_op
        | identifier "." func_name "(" string ")" -> geo_func
        | "(" expr ")"
        | "TRUE" -> true_literal
        | "FALSE" -> false_literal
    
    ?value: literal
        | identifier

    literal_list: literal ("," literal)*

    ?literal: string
        | number
        | boolean

    ?number: SIGNED_NUMBER -> num

    ?string: STRING_LITERAL -> str

    ?boolean: "TRUE" -> true_lit
        | "FALSE" -> false_lit

    identifier: IDENTIFIER ("." IDENTIFIER)*
    
    func_name: IDENTIFIER

    IDENTIFIER: /[A-Z][A-Z0-9_]*/
    STRING_LITERAL: /'[^']*'/ | /"[^"]*"/

    %import common.SIGNED_NUMBER
    %import common.WS
    %ignore WS
"""


# AST Node classes
@dataclass
class ASTNode:
    """Base class for AST nodes."""
    pass


@dataclass
class Identifier(ASTNode):
    """Dotted identifier like AREA.USAGE."""
    name: str

    def __str__(self):
        return self.name


@dataclass
class Literal(ASTNode):
    """Literal value (string, number, or boolean)."""
    value: Union[str, int, float, bool]

    def __str__(self):
        if isinstance(self.value, str):
            return f"'{self.value}'"
        return str(self.value)


@dataclass
class BinaryOp(ASTNode):
    """Binary operation (AND, OR, comparison)."""
    op: str
    left: ASTNode
    right: ASTNode

    def __str__(self):
        return f"({self.left} {self.op} {self.right})"


@dataclass
class UnaryOp(ASTNode):
    """Unary operation (NOT)."""
    op: str
    operand: ASTNode

    def __str__(self):
        return f"({self.op} {self.operand})"


@dataclass
class InOp(ASTNode):
    """Membership test (IN)."""
    identifier: Identifier
    values: List[Literal]

    def __str__(self):
        vals = ", ".join(str(v) for v in self.values)
        return f"{self.identifier} IN [{vals}]"


@dataclass
class HasOp(ASTNode):
    """Existence test (HAS)."""
    identifier: Identifier

    def __str__(self):
        return f"HAS({self.identifier})"


@dataclass
class GeoFunc(ASTNode):
    """Geographic scoping function (WITHIN, OVERLAPS, ADJACENT_TO)."""
    identifier: Identifier
    func_name: str
    arg: str

    def __str__(self):
        return f"{self.identifier}.{self.func_name}('{self.arg}')"


class ASTBuilder(Transformer):
    """Transform Lark parse tree into AST."""

    def identifier(self, items):
        """Build identifier from tokens."""
        return Identifier(".".join(str(item) for item in items))

    def func_name(self, items):
        """Extract function name."""
        return str(items[0])

    def str(self, items):
        """Parse string literal."""
        s = str(items[0])
        # Remove quotes
        return s[1:-1] if s.startswith('"') or s.startswith("'") else s

    def num(self, items):
        """Parse numeric literal."""
        val = items[0]
        try:
            return int(val)
        except ValueError:
            return float(val)

    def true_lit(self, items):
        """Parse TRUE literal."""
        return True

    def false_lit(self, items):
        """Parse FALSE literal."""
        return False

    def literal_list(self, items):
        """Build list of literals."""
        return [Literal(item) for item in items]

    def eq(self, items):
        """Build equality comparison."""
        right = items[1] if isinstance(items[1], Identifier) else Literal(items[1])
        return BinaryOp("==", items[0], right)

    def ne(self, items):
        """Build inequality comparison."""
        right = items[1] if isinstance(items[1], Identifier) else Literal(items[1])
        return BinaryOp("!=", items[0], right)

    def gt(self, items):
        """Build greater-than comparison."""
        right = items[1] if isinstance(items[1], Identifier) else Literal(items[1])
        return BinaryOp(">", items[0], right)

    def ge(self, items):
        """Build greater-or-equal comparison."""
        right = items[1] if isinstance(items[1], Identifier) else Literal(items[1])
        return BinaryOp(">=", items[0], right)

    def lt(self, items):
        """Build less-than comparison."""
        right = items[1] if isinstance(items[1], Identifier) else Literal(items[1])
        return BinaryOp("<", items[0], right)

    def le(self, items):
        """Build less-or-equal comparison."""
        right = items[1] if isinstance(items[1], Identifier) else Literal(items[1])
        return BinaryOp("<=", items[0], right)

    def in_op(self, items):
        """Build IN operation."""
        return InOp(items[0], items[1])

    def has_op(self, items):
        """Build HAS operation."""
        return HasOp(items[0])

    def geo_func(self, items):
        """Build geographic function call."""
        return GeoFunc(items[0], items[1], items[2])

    def or_op(self, items):
        """Build OR operation."""
        return BinaryOp("OR", items[0], items[1])

    def and_op(self, items):
        """Build AND operation."""
        return BinaryOp("AND", items[0], items[1])

    def not_op(self, items):
        """Build NOT operation."""
        return UnaryOp("NOT", items[0])

    def true_literal(self, items):
        """Build TRUE literal."""
        return Literal(True)

    def false_literal(self, items):
        """Build FALSE literal."""
        return Literal(False)


class DSLParser:
    """Parser for applies_if DSL predicates."""

    def __init__(self):
        """Initialize parser."""
        self.parser = Lark(DSL_GRAMMAR, start='start', parser='lalr')
        self.transformer = ASTBuilder()

    def parse(self, text: str) -> Optional[ASTNode]:
        """Parse a DSL expression into an AST.

        Args:
            text: DSL expression string

        Returns:
            Root AST node, or None if parsing fails
        """
        if not text or text.strip() in ("", "TRUE", "FALSE"):
            # Handle trivial cases
            if text.strip() == "TRUE":
                return Literal(True)
            elif text.strip() == "FALSE":
                return Literal(False)
            return None

        try:
            tree = self.parser.parse(text)
            ast = self.transformer.transform(tree)
            return ast
        except Exception as e:
            # Return None for unparseable expressions
            # Caller should handle this gracefully
            return None


def parse_applies_if(applies_if: str) -> Optional[ASTNode]:
    """Parse an applies_if predicate string.

    Args:
        applies_if: The applies_if predicate string

    Returns:
        AST node representing the expression, or None if unparseable
    """
    parser = DSLParser()
    return parser.parse(applies_if)
