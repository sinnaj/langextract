import re
from typing import Any, Dict, Iterable, Set, List, Tuple, Optional, Callable


# Required top-level keys for rich schema validation
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


def collect_dsl_keys(obj: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    dsl_fields = ("applies_if", "satisfied_if", "exempt_if")
    pattern = re.compile(r"[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+")
    for norm in obj.get("norms", []):
        for f in dsl_fields:
            v = norm.get(f)
            if isinstance(v, str):
                for m in pattern.findall(v):
                    keys.add(m)
    for param in obj.get("parameters", []):
        fp = param.get("field_path")
        if isinstance(fp, str):
            keys.add(fp)
    return keys


# New helpers to centralize rich-schema discovery and logging
def extract_primary_rich(data: Any) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Return the primary rich object from a raw decoded JSON payload.

    Accepts either a root rich object or an object with {"extractions": [ rich, ... ]}.
    Returns a tuple of (primary_object_or_None, wrapped_flag).
    """
    if isinstance(data, dict) and isinstance(data.get("extractions"), list) and data["extractions"]:
        primary = data["extractions"][0]
        return (primary if isinstance(primary, dict) else None, True)
    if isinstance(data, dict):
        return (data, False)
    return (None, False)


def validate_rich_verbose(data: Any, print_fn: Callable[[str], None] = print) -> Tuple[Optional[Dict[str, Any]], bool, List[str]]:
    """Validate a decoded JSON payload and print diagnostics.

    - Detects primary rich object (supports wrapper format).
    - Uses is_rich_schema/validate_rich for checks.
    - Emits PASS/WARN logs similar to previous inline logic.

    Returns (primary_obj_or_None, ok, errors).
    """
    primary, _wrapped = extract_primary_rich(data)
    if primary is None:
        print_fn("[WARN] Loaded payload did not contain a recognizable rich schema object")
        return (None, False, ["NO_PRIMARY"])

    if is_rich_schema(primary):
        print_fn("[INFO] Rich schema validation: PASS")
        return (primary, True, [])

    errs = validate_rich(primary)
    print_fn(f"[WARN] Rich schema validation: FAIL with {len(errs)} issues")
    for e in errs[:25]:
        print_fn(f" - {e}")
    return (primary, False, errs)