
import re
from typing import Any, Dict, Set, Tuple, Optional




PARAM_PATTERN = re.compile(r"(?P<field>[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+)\s*(?P<op>>=|<=|==|!=|>|<)\s*(?P<val>-?\d+(?:\.\d+)?)")
UNIT_NUMBER_PATTERN = re.compile(r"(?P<val>\d+(?:\.\d+)?)\s?(?P<unit>N|m|kg|personas?|N/m2|kg/m2)\b", re.IGNORECASE)

ParamKey = Tuple[str, str, float, Optional[str]]

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

def build_existing_param_index(obj: Dict[str, Any]) -> Dict[ParamKey, Dict[str,Any]]:
    index: Dict[ParamKey, Dict[str,Any]] = {}
    for p in obj.get("parameters", []):
        try:
            key = (p.get("field_path"), p.get("operator"), float(p.get("value")), p.get("unit"))
            index[key] = p
        except Exception:
            continue
    return index


def enrich_parameters(obj: Dict[str, Any]):
    """Derive parameter objects from DSL expressions & Norm text if missing.
    Non-destructive: adds only new parameters and links them to norms.
    """
    norms = obj.get("norms", [])
    params = obj.setdefault("parameters", [])
    index = build_existing_param_index(obj)
    next_id_int = len(params) + 1
    created = 0
    for norm in norms:
        collected_ids = set(norm.get("extracted_parameters_ids") or [])
        # DSL fields
        for fld in ("applies_if", "satisfied_if", "exempt_if"):
            expr = norm.get(fld)
            if not isinstance(expr, str):
                continue
            for m in PARAM_PATTERN.finditer(expr):
                field_path = m.group("field")
                op = m.group("op")
                val = float(m.group("val"))
                unit = None  # unit not in DSL component; may capture from norm text later
                key = (field_path, op, val, unit)
                if key not in index:
                    pid = f"P::{next_id_int:04d}"
                    param_obj = {
                        "id": pid,
                        "field_path": field_path,
                        "operator": op,
                        "value": val if val % 1 else int(val),
                        "unit": unit,
                        "original_text": None,
                        "norm_ids": [norm.get("id")],
                        "confidence": 0.75,
                        "uncertainty": 0.25,
                    }
                    params.append(param_obj)
                    index[key] = param_obj
                    next_id_int += 1
                    created += 1
                else:
                    index[key].setdefault("norm_ids", [])
                    nid = norm.get("id")
                    if nid and nid not in index[key]["norm_ids"]:
                        index[key]["norm_ids"].append(nid)
                # ensure linkage in norm
                pid = index[key]["id"]
                if pid not in collected_ids:
                    collected_ids.add(pid)
        # attempt capture of numeric with unit inside Norm text
        text_snip = norm.get("statement_text") or norm.get("Norm") or ""
        for mu in UNIT_NUMBER_PATTERN.finditer(text_snip):
            val = float(mu.group("val"))
            unit_found: Optional[str] = mu.group("unit").upper() if mu.group("unit") else None
            field_path = "DOOR.OPENING.PUSH_FORCE_N" if unit_found == "N" else None
            if not field_path:
                continue
            op = "<="
            key_u = (field_path, op, val, unit_found)
            if key_u not in index:
                pid = f"P::{next_id_int:04d}"
                param_obj = {
                    "id": pid,
                    "field_path": field_path,
                    "operator": op,
                    "value": val if val % 1 else int(val),
                    "unit": unit_found,
                    "original_text": mu.group(0),
                    "norm_ids": [norm.get("id")],
                    "confidence": 0.65,
                    "uncertainty": 0.35,
                }
                params.append(param_obj)
                index[key_u] = param_obj
                next_id_int += 1
                created += 1
            else:
                nid = norm.get("id")
                if nid and nid not in index[key_u]["norm_ids"]:
                    index[key_u]["norm_ids"].append(nid)
            pid = index[key_u]["id"]
            collected_ids.add(pid)
        if collected_ids:
            norm["extracted_parameters_ids"] = sorted(collected_ids)
    if created:
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"PARAMETERS_ENRICHED:{created}")


def merge_duplicate_tags(obj: Dict[str, Any]):
    """Collapse duplicate ACTIVE tags with identical tag_path marking extras as MERGED."""
    tags = obj.get("tags", [])
    seen: Dict[str, Dict[str, Any]] = {}
    merged = 0
    for t in tags:
        if not isinstance(t, dict):
            continue
        path = t.get("tag_path")
        status = t.get("status")
        if not path or status != "ACTIVE":
            continue
        if path in seen:
            # mark duplicate as MERGED
            t["status"] = "MERGED"
            t["merge_target"] = path
            merged += 1
        else:
            seen[path] = t
    if merged:
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"DUPLICATE_TAGS_MERGED:{merged}")