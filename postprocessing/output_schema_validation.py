# ---------------------------------------------------------------------------
# 3. Validation & Utility Helpers
# ---------------------------------------------------------------------------
import re
from typing import Any, Dict, Iterable, List, Set


TOP_LEVEL_REQUIRED = [
    "schema_version",
    "ontology_version",
    # (dsl_version, run_info) intentionally excluded from strict required list during transition
    "truncated",
    "has_more",
    "window_config",
    "global_disclaimer",
    "document_metadata",
    "norms",
    "tags",
    "locations",
    "questions",
    "consequences",
    "parameters",
    "quality",
]


def is_rich_schema(d: Any) -> bool:
    return isinstance(d, dict) and all(k in d for k in TOP_LEVEL_REQUIRED)


DSL_TOKEN_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)*$")


def validate_rich(obj: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    # Required keys
    for k in TOP_LEVEL_REQUIRED:
        if k not in obj:
            errors.append(f"MISSING_TOP_LEVEL:{k}")
    # Soft missing (transition)
    for soft in ("dsl_version", "run_info"):
        if soft not in obj:
            errors.append(f"WARN_SOFT_MISSING:{soft}")
    # Basic type checks
    for arr_key in ("norms", "tags", "locations", "questions", "consequences", "parameters"):
        if arr_key in obj and not isinstance(obj[arr_key], list):
            errors.append(f"NOT_LIST:{arr_key}")
    # ID uniqueness & reference integrity
    id_sets: Dict[str, Set[str]] = {k: set() for k in ("N", "T", "L", "Q", "C", "P")}
    def collect_ids(prefix: str, items: Iterable[Dict[str, Any]]):
        for it in items:
            _id = it.get("id")
            if not isinstance(_id, str) or not _id.startswith(prefix + "::"):
                errors.append(f"BAD_ID:{_id}")
                continue
            if _id in id_sets[prefix]:
                errors.append(f"DUP_ID:{_id}")
            id_sets[prefix].add(_id)

    collect_ids("N", obj.get("norms", []))
    collect_ids("T", obj.get("tags", []))
    collect_ids("L", obj.get("locations", []))
    collect_ids("Q", obj.get("questions", []))
    collect_ids("C", obj.get("consequences", []))
    collect_ids("P", obj.get("parameters", []))

    # Cross references (best effort) – only flag missing referenced IDs
    all_ids = set().union(*id_sets.values())
    for norm in obj.get("norms", []):
        for ref_list_key in ("extracted_parameters_ids", "consequence_ids"):
            for rid in norm.get(ref_list_key, []) or []:
                if rid not in all_ids:
                    errors.append(f"MISSING_REF:{rid}")
    for cons in obj.get("consequences", []):
        for ref_list_key in ("activates_norm_ids", "activates_question_ids"):
            for rid in cons.get(ref_list_key, []) or []:
                if rid not in all_ids:
                    errors.append(f"MISSING_REF:{rid}")
    # DSL heuristic (light) – ensure ; OR formatting and membership formatting
    for norm in obj.get("norms", [])[:20]:
        for fld in ("applies_if", "satisfied_if", "exempt_if"):
            val = norm.get(fld)
            if not isinstance(val, str) or val in ("TRUE", "null", "None", ""):
                continue
            # basic check: uppercase OR usage for alternatives separated by '; OR '
            if "; OR" in val and not val.count("; OR "):
                errors.append(f"ALT_FORMAT:{fld}")
    return errors


