from typing import Any, Dict


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
