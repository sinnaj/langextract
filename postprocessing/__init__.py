"""Utilities for postprocessing extracted entities/relations.

This package exposes its submodules for convenient imports like:

    from langextract.postprocessing import merge_duplicate_tags

"""

from . import compute_extended_metrics
from . import enrich_parameters
from . import ensure_consequence_id
from . import infer_relationships
from . import merge_duplicate_tags

__all__ = [
    "compute_extended_metrics",
    "enrich_parameters",
    "ensure_consequence_id",
    "infer_relationships",
    "merge_duplicate_tags",
]


