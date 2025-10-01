"""Feature schema extraction from applies_if predicates.

This module traverses ASTs to:
1. Collect all feature names (identifiers)
2. Extract numeric thresholds and derive bins
3. Collect categorical values from string comparisons and IN lists
4. Build a feature schema with priors
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

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


@dataclass
class NumericFeature:
    """Numeric feature with bins."""
    name: str
    thresholds: List[float] = field(default_factory=list)
    bins: List[Tuple[Optional[float], Optional[float]]] = field(default_factory=list)
    is_numeric: bool = True

    def derive_bins(self):
        """Derive bins from thresholds.
        
        For thresholds [100, 250, 500], creates bins:
        (-inf, 100], (100, 250], (250, 500], (500, inf)
        """
        if not self.thresholds:
            # Default single bin for numeric with no thresholds
            self.bins = [(None, None)]
            return

        sorted_thresholds = sorted(set(self.thresholds))
        bins = []
        
        # First bin: (-inf, first_threshold]
        bins.append((None, sorted_thresholds[0]))
        
        # Middle bins
        for i in range(len(sorted_thresholds) - 1):
            bins.append((sorted_thresholds[i], sorted_thresholds[i + 1]))
        
        # Last bin: (last_threshold, inf)
        bins.append((sorted_thresholds[-1], None))
        
        self.bins = bins


@dataclass
class CategoricalFeature:
    """Categorical feature with possible values."""
    name: str
    categories: Set[str] = field(default_factory=set)
    is_numeric: bool = False


@dataclass
class FeatureSchema:
    """Schema of all features discovered in the norms."""
    numeric_features: Dict[str, NumericFeature] = field(default_factory=dict)
    categorical_features: Dict[str, CategoricalFeature] = field(default_factory=dict)
    all_feature_names: Set[str] = field(default_factory=set)
    priors: Dict[str, Dict[Any, float]] = field(default_factory=dict)

    def get_feature_values(self, feature_name: str) -> List[Any]:
        """Get possible values for a feature.
        
        For numeric features, returns bins.
        For categorical features, returns categories.
        """
        if feature_name in self.numeric_features:
            return self.numeric_features[feature_name].bins
        elif feature_name in self.categorical_features:
            return sorted(self.categorical_features[feature_name].categories)
        return []

    def is_numeric(self, feature_name: str) -> bool:
        """Check if a feature is numeric."""
        return feature_name in self.numeric_features

    def compute_uniform_priors(self, alpha: float = 1.0):
        """Compute uniform priors with Laplace smoothing.
        
        Args:
            alpha: Laplace smoothing parameter
        """
        for fname, nf in self.numeric_features.items():
            # Uniform over bins
            n_bins = len(nf.bins)
            if n_bins > 0:
                prior = {bin_idx: 1.0 / n_bins for bin_idx in range(n_bins)}
                self.priors[fname] = prior

        for fname, cf in self.categorical_features.items():
            # Uniform with Laplace smoothing
            n_cats = len(cf.categories)
            if n_cats > 0:
                total = n_cats + alpha * n_cats
                prior = {cat: (1.0 + alpha) / total for cat in cf.categories}
                self.priors[fname] = prior

    def load_priors_from_yaml(self, yaml_path: Path):
        """Load priors from a YAML file.
        
        Args:
            yaml_path: Path to priors.yaml file
        """
        if not yaml_path.exists():
            return

        with open(yaml_path, 'r') as f:
            priors_data = yaml.safe_load(f)

        if not priors_data:
            return

        # Validate and load priors
        for fname, prior in priors_data.items():
            if fname not in self.all_feature_names:
                continue

            # Normalize to ensure sum = 1.0
            total = sum(prior.values())
            if total > 0:
                self.priors[fname] = {k: v / total for k, v in prior.items()}


class FeatureExtractor:
    """Extract features from AST nodes."""

    def __init__(self):
        """Initialize feature extractor."""
        self.numeric_features: Dict[str, NumericFeature] = {}
        self.categorical_features: Dict[str, CategoricalFeature] = {}
        self.all_identifiers: Set[str] = set()

    def extract_from_ast(self, ast: Optional[ASTNode]):
        """Extract features from an AST.
        
        Args:
            ast: Root AST node
        """
        if ast is None:
            return

        self._visit(ast)

    def _visit(self, node: ASTNode):
        """Visit an AST node and extract features."""
        if isinstance(node, BinaryOp):
            # Check if this is a comparison with identifier
            if isinstance(node.left, Identifier):
                feature_name = node.left.name
                self.all_identifiers.add(feature_name)
                
                # Check if right side is also an identifier
                if isinstance(node.right, Identifier):
                    right_feature_name = node.right.name
                    self.all_identifiers.add(right_feature_name)
                    # Identifier-to-identifier comparison - treat both as categorical
                    # (we can't know if they're numeric without more context)
                    # For now, just mark them as identifiers
                
                # Check if right side is a literal
                elif isinstance(node.right, Literal):
                    # Check if numeric comparison
                    if node.op in (">", ">=", "<", "<=") and isinstance(node.right.value, (int, float)):
                        # Numeric feature
                        if feature_name not in self.numeric_features:
                            self.numeric_features[feature_name] = NumericFeature(feature_name)
                        self.numeric_features[feature_name].thresholds.append(float(node.right.value))

                    elif node.op in ("==", "!=") and isinstance(node.right.value, (int, float)):
                        # Could be numeric or categorical - assume numeric if number
                        if feature_name not in self.numeric_features:
                            self.numeric_features[feature_name] = NumericFeature(feature_name)
                        self.numeric_features[feature_name].thresholds.append(float(node.right.value))

                    elif isinstance(node.right.value, str):
                        # Categorical feature
                        if feature_name not in self.categorical_features:
                            self.categorical_features[feature_name] = CategoricalFeature(feature_name)
                        self.categorical_features[feature_name].categories.add(node.right.value)

            # Recursively visit children
            self._visit(node.left)
            if not isinstance(node.right, Literal):  # Don't recurse into literals
                self._visit(node.right)

        elif isinstance(node, UnaryOp):
            self._visit(node.operand)

        elif isinstance(node, InOp):
            feature_name = node.identifier.name
            self.all_identifiers.add(feature_name)

            # Categorical feature
            if feature_name not in self.categorical_features:
                self.categorical_features[feature_name] = CategoricalFeature(feature_name)

            for lit in node.values:
                if isinstance(lit.value, str):
                    self.categorical_features[feature_name].categories.add(lit.value)

        elif isinstance(node, HasOp):
            feature_name = node.identifier.name
            self.all_identifiers.add(feature_name)
            # Treat HAS as a boolean categorical feature
            if feature_name not in self.categorical_features:
                self.categorical_features[feature_name] = CategoricalFeature(feature_name)
            # Add True/False as categories
            self.categorical_features[feature_name].categories.add("EXISTS")
            self.categorical_features[feature_name].categories.add("NOT_EXISTS")

        elif isinstance(node, GeoFunc):
            # Geographic function - treat as categorical
            feature_name = f"{node.identifier.name}.{node.func_name}"
            self.all_identifiers.add(feature_name)
            if feature_name not in self.categorical_features:
                self.categorical_features[feature_name] = CategoricalFeature(feature_name)
            self.categorical_features[feature_name].categories.add(node.arg)

        elif isinstance(node, Identifier):
            # Standalone identifier (shouldn't happen in well-formed AST)
            self.all_identifiers.add(node.name)

    def build_schema(self) -> FeatureSchema:
        """Build final feature schema.
        
        Returns:
            FeatureSchema object
        """
        # Derive bins for numeric features
        for nf in self.numeric_features.values():
            nf.derive_bins()

        schema = FeatureSchema(
            numeric_features=self.numeric_features,
            categorical_features=self.categorical_features,
            all_feature_names=self.all_identifiers
        )

        # Compute uniform priors by default
        schema.compute_uniform_priors()

        return schema


def extract_features_from_norms(
    norms: List[Dict[str, Any]],
    priors_yaml: Optional[Path] = None
) -> FeatureSchema:
    """Extract feature schema from a list of norms.
    
    Args:
        norms: List of norm dictionaries with 'attributes.applies_if'
        priors_yaml: Optional path to priors YAML file
    
    Returns:
        FeatureSchema object
    """
    from dsl_parser import parse_applies_if

    extractor = FeatureExtractor()

    for norm in norms:
        applies_if = norm.get('attributes', {}).get('applies_if', '')
        if not applies_if or applies_if.strip() in ('', 'TRUE', 'FALSE'):
            continue

        ast = parse_applies_if(applies_if)
        extractor.extract_from_ast(ast)

    schema = extractor.build_schema()

    # Load custom priors if provided
    if priors_yaml:
        schema.load_priors_from_yaml(priors_yaml)

    return schema
