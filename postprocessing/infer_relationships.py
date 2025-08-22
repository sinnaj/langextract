from postprocessing.ensure_consequence_id import ensure_consequence_id
from testExtraction_3_norms_min_copy import LOCATION_CODE_FIELDS, SINGLE_QUOTED_LITERAL_PATTERN, ensure_tag


import re
from typing import Any, Dict, List


def infer_relationships(obj: Dict[str, Any]):
    id_index = {item.get("id"): item for k in ("norms","tags","locations","questions","consequences","parameters") for item in obj.get(k, []) if isinstance(item, dict)}
    tag_by_path = {t.get("tag_path"): t for t in obj.get("tags", []) if isinstance(t, dict)}
    # 1. Questions -> ensure tag existence & outputs tags
    for q in obj.get("questions", []):
        tp = q.get("tag_path")
        if tp and tp not in tag_by_path:
            ensure_tag(obj, tp)
        for out in q.get("outputs", []) or []:
            if isinstance(out, str) and out not in tag_by_path:
                ensure_tag(obj, out)
    # Refresh tag index after possible additions
    tag_by_path = {t.get("tag_path"): t for t in obj.get("tags", []) if isinstance(t, dict)}
    # 2. Consequence ↔ Norm linking via ANNEX code in Norm DSL and consequence reference_code
    annex_map: Dict[str, List[Dict[str, Any]]] = {}
    for cons in obj.get("consequences", []):
        code = cons.get("reference_code")
        if code:
            annex_map.setdefault(code, []).append(cons)
    for norm in obj.get("norms", []):
        for fld in ("satisfied_if","applies_if","exempt_if"):
            expr = norm.get(fld)
            if not isinstance(expr, str):
                continue
            # pattern ANNEX.<CODE>.SUBMITTED
            for m in re.finditer(r"ANNEX\.([A-Z0-9_]+)\.SUBMITTED", expr):
                code = f"Anexo {m.group(1)}" if not m.group(1).startswith("Anexo") else m.group(1)
                if code in annex_map:
                    for cons in annex_map[code]:
                        # link norm -> consequence
                        cid = cons.get("id") or ensure_consequence_id(cons, obj)
                        norm.setdefault("consequence_ids", [])
                        if cid not in norm["consequence_ids"]:
                            norm["consequence_ids"].append(cid)
                        # link consequence -> norm
                        cons.setdefault("source_norm_ids", [])
                        nid = norm.get("id")
                        if nid and nid not in cons["source_norm_ids"]:
                            cons["source_norm_ids"].append(nid)
    # 3. Location codes propagation from DSL literals
    location_codes = {loc.get("code"): loc for loc in obj.get("locations", []) if isinstance(loc, dict)}
    for norm in obj.get("norms", []):
        collected = []
        for fld in ("applies_if","satisfied_if","exempt_if"):
            expr = norm.get(fld)
            if not isinstance(expr, str):
                continue
            for lit in SINGLE_QUOTED_LITERAL_PATTERN.findall(expr):
                if lit in location_codes:
                    collected.append(lit)
        if collected:
            scope = norm.setdefault("location_scope", {})
            scope.setdefault("COUNTRY", "ES")
            for arr_name in LOCATION_CODE_FIELDS:
                scope.setdefault(arr_name, [])
            # naive classification: treat codes with pattern letter+digits+dot as ZONES
            for code in sorted(set(collected)):
                if code not in scope["ZONES"]:
                    scope["ZONES"].append(code)