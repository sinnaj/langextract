import re
from typing import Any, Dict, Optional


def ensure_tag(obj: Dict[str, Any], tag_path: str) -> Optional[str]:
    if not tag_path or not isinstance(tag_path, str):
        return None
    tags = obj.setdefault("tags", [])
    for t in tags:
        if t.get("tag_path") == tag_path:
            return t.get("id")
    # create new tag id
    new_id = f"T::{len(tags)+1:04d}"
    parent = tag_path.rsplit('.', 1)[0] if '.' in tag_path else None
    tags.append({
        "id": new_id,
        "tag_path": tag_path,
        "parent": parent,
        "definition": "AUTO-GENERATED PLACEHOLDER",
        "status": "ACTIVE",
    })
    obj.setdefault("quality", {}).setdefault("warnings", []).append(f"PLACEHOLDER_TAG_CREATED:{tag_path}")
    return new_id


def ensure_consequence_id(cons: Dict[str, Any], obj: Dict[str, Any]) -> str:
    if cons.get("id"):
        return cons["id"]
    cons_list = obj.get("consequences", [])
    new_id = f"C::{len(cons_list)+1:04d}"
    cons["id"] = new_id
    return new_id


LOCATION_CODE_FIELDS = ["ZONES", "PROVINCES", "REGIONS", "STATES", "COMMUNES", "GEO_CODES"]
SINGLE_QUOTED_LITERAL_PATTERN = re.compile(r"'([^'\\]{1,40})'")


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


def compute_extended_metrics(obj: Dict[str, Any]) -> Dict[str, float]:
    tags = obj.get("tags", [])
    questions = obj.get("questions", [])
    consequences = obj.get("consequences", [])
    norms = obj.get("norms", [])
    tag_paths = {t.get("tag_path") for t in tags if t.get("tag_path")}
    q_align = 0
    for q in questions:
        if q.get("tag_path") in tag_paths:
            q_align += 1
    question_tag_alignment_rate = q_align/len(questions) if questions else 0.0
    cons_linked = 0
    for c in consequences:
        if c.get("source_norm_ids") or c.get("activates_norm_ids"):
            cons_linked += 1
    consequence_linkage_rate = cons_linked/len(consequences) if consequences else 0.0
    # location scope population
    norms_with_codes = 0
    for n in norms:
        loc_scope = n.get("location_scope") or {}
        if any(loc_scope.get(k) for k in ("ZONES","PROVINCES","REGIONS","STATES","COMMUNES","GEO_CODES")):
            norms_with_codes += 1
    location_scope_population_rate = norms_with_codes/len(norms) if norms else 0.0
    return {
        "question_tag_alignment_rate": round(question_tag_alignment_rate,3),
        "consequence_linkage_rate": round(consequence_linkage_rate,3),
        "location_scope_population_rate": round(location_scope_population_rate,3),
    }


QUESTION_VERB_MAP = {
    "TYPE": "¿Cuál es el tipo?",
    "METHOD": "¿Cuál es el método?",
    "SYSTEM": "¿Qué sistema se utiliza?",
    "CLASS": "¿Cuál es la clase?",
    "RATING": "¿Cuál es la clasificación?",
}


def humanize_segment(seg: str) -> str:
    seg_clean = seg.replace('_',' ').lower()
    return seg_clean


def build_question_from_tag_path(tag_path: str) -> str:
    parts = tag_path.split('.') if tag_path else []
    leaf = parts[-1] if parts else ''
    if leaf in QUESTION_VERB_MAP:
        return QUESTION_VERB_MAP[leaf]
    # Generic fallback
    base = humanize_segment(leaf or 'valor')
    return f"¿Cuál es el {base}?" if not base.endswith('?') else base


def autophrase_questions(obj: Dict[str, Any]):
    qs = obj.get("questions", [])
    created = 0
    for q in qs:
        if q.get("question_text"):
            continue
        tp = q.get("tag_path") or (q.get("outputs") or [None])[0]
        if not isinstance(tp, str):
            continue
        phrased = build_question_from_tag_path(tp)
        q["question_text"] = phrased + " (auto)"
        created += 1
    if created:
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"AUTO_QUESTION_PHRASED:{created}")