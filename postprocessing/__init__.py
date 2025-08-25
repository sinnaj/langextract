"""Utilities for postprocessing extracted entities/relations.

This package auto-discovers and exposes all non-private submodules in this folder, so you can:

	from langextract.postprocessing import enrich_outputdata
	from langextract.postprocessing import output_schema_validation

and similar. It also populates __all__ for wildcard imports.
"""

from __future__ import annotations

import importlib as _importlib
import pkgutil as _pkgutil

__all__: list[str] = []

# Eagerly import all non-private submodules in this package so that
# `from langextract.postprocessing import *` works as expected.
for _finder, _modname, _ispkg in _pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
	if _modname.startswith("_"):
		continue
	try:
		_module = _importlib.import_module(f"{__name__}.{_modname}")
		globals()[_modname] = _module
		__all__.append(_modname)
	except Exception:
		# If a submodule has import-time issues, skip exposing it
		# to avoid breaking package import entirely.
		continue

# """Utilities for postprocessing extracted entities/relations.

# This package exposes its submodules for convenient imports like:

#     from langextract.postprocessing import merge_duplicate_tags

# """

# from . import compute_extended_metrics
# from . import enrich_parameters
# from . import ensure_consequence_id
# from . import infer_relationships
# from . import merge_duplicate_tags

# __all__ = [
#     "compute_extended_metrics",
#     "enrich_parameters",
#     "ensure_consequence_id",
#     "infer_relationships",
#     "merge_duplicate_tags",
# ]


