import json
from typing import Any, Dict, List, Set


def aggregate_extractions(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple chunk extraction objects into a single unified object.

    Strategy:
      1. Concatenate arrays preserving chunk order.
      2. Re-index IDs sequentially per entity type (N/T/L/Q/C/P) to avoid collisions.
      3. Remap all reference fields to new IDs.
      4. Merge metadata: doc_id must match across chunks else fallback MULTI_CHUNK; page_range union; topics union.
      5. window_config: input_chars = sum of chunk window_config.input_chars (fallback length of INPUT_TEXT), extracted_norm_count updated, max_norms_per_5k_tokens = max across chunks.
      6. truncated / has_more true if any chunk true.
      7. quality.errors & warnings union (deduplicated, order preserved by first appearance).
    """
    if not chunks:
        return {}
    if len(chunks) == 1:
        return chunks[0]
    # Base skeleton from first chunk (shallow copy of scalar sections)
    merged: Dict[str, Any] = {k: chunks[0].get(k) for k in chunks[0].keys() if k not in {"norms","tags","locations","questions","consequences","parameters","quality","window_config","document_metadata"}}
    # Collect arrays
    merged["norms"] = [n for idx,c in enumerate(chunks) for n in c.get("norms", [])]
    merged["tags"] = [t for c in chunks for t in c.get("tags", [])]
    merged["locations"] = [l for c in chunks for l in c.get("locations", [])]
    merged["questions"] = [q for c in chunks for q in c.get("questions", [])]
    merged["consequences"] = [cns for c in chunks for cns in c.get("consequences", [])]
    merged["parameters"] = [p for c in chunks for p in c.get("parameters", [])]

    # Metadata merge
    doc_ids = {c.get("document_metadata", {}).get("doc_id") for c in chunks if c.get("document_metadata")}
    first_md = chunks[0].get("document_metadata", {})
    md: Dict[str, Any] = dict(first_md)
    if len(doc_ids) > 1:
        md["doc_id"] = "MULTI_CHUNK"
    # Page range
    starts = [c.get("document_metadata", {}).get("page_range", {}).get("start") for c in chunks if c.get("document_metadata", {}).get("page_range")]
    ends = [c.get("document_metadata", {}).get("page_range", {}).get("end") for c in chunks if c.get("document_metadata", {}).get("page_range")]
    if starts and ends:
        md.setdefault("page_range", {})
        md["page_range"]["start"] = min(s for s in starts if isinstance(s, int)) if any(isinstance(s,int) for s in starts) else -1
        md["page_range"]["end"] = max(e for e in ends if isinstance(e, int)) if any(isinstance(e,int) for e in ends) else -1
    # Topics union
    topics_union: List[str] = []
    seen_topics = set()
    for c in chunks:
        for t in c.get("document_metadata", {}).get("topics", []) or []:
            if t not in seen_topics:
                seen_topics.add(t)
                topics_union.append(t)
    if topics_union:
        md["topics"] = topics_union
    merged["document_metadata"] = md

    # window_config merge
    wc_total_chars = 0
    max_norms_setting = 0
    for c in chunks:
        cw = c.get("window_config", {}) or {}
        wc_total_chars += int(cw.get("input_chars") or 0)
        max_norms_setting = max(max_norms_setting, int(cw.get("max_norms_per_5k_tokens") or 0))
    merged_wc = {
        "input_chars": wc_total_chars or len(INPUT_TEXT),
        "max_norms_per_5k_tokens": max_norms_setting or MAX_NORMS_PER_5K,
        "extracted_norm_count": len(merged["norms"]),
    }
    merged["window_config"] = merged_wc

    # truncated / has_more
    merged["truncated"] = any(c.get("truncated") for c in chunks)
    merged["has_more"] = any(c.get("has_more") for c in chunks)

    # Quality combine
    def combine_quality(chunks):
        def norm_item(x: Any) -> str:
            if isinstance(x, (str, int, float)):
                return str(x)
            try:
                return json.dumps(x, sort_keys=True, ensure_ascii=False)
            except Exception:
                return repr(x)
        err_order: List[Any] = []
        warn_order: List[Any] = []
        err_seen: Set[str] = set(); warn_seen: Set[str] = set()
        for c in chunks:
            q = c.get("quality", {}) or {}
            for e in q.get("errors", []) or []:
                key = norm_item(e)
                if key not in err_seen:
                    err_seen.add(key); err_order.append(e)
            for w in q.get("warnings", []) or []:
                key = norm_item(w)
                if key not in warn_seen:
                    warn_seen.add(key); warn_order.append(w)
        return {"errors": err_order, "warnings": warn_order}
    merged_quality = combine_quality(chunks)
    merged_quality.setdefault("errors", [])
    merged_quality.setdefault("warnings", [])
    merged_quality["errors"].append(f"AGGREGATED_CHUNKS:{len(chunks)}")
    merged["quality"] = merged_quality

    # Re-index IDs
    id_prefixes = [
        ("norms", "N"),
        ("tags", "T"),
        ("locations", "L"),
        ("questions", "Q"),
        ("consequences", "C"),
        ("parameters", "P"),
    ]
    mapping: Dict[str, str] = {}
    for collection, prefix in id_prefixes:
        new_list = []
        counter = 1
        for obj in merged.get(collection, []):
            if not isinstance(obj, dict):
                continue
            old_id = obj.get("id")
            new_id = f"{prefix}::{counter:04d}"
            mapping[old_id] = new_id
            obj["id"] = new_id
            counter += 1
            new_list.append(obj)
        merged[collection] = new_list

    # Patch references with new IDs
    for n in merged.get("norms", []):
        for fld in ("extracted_parameters_ids", "consequence_ids"):
            ids = n.get(fld) or []
            n[fld] = [mapping.get(i, i) for i in ids]
    for t in merged.get("tags", []):
        for fld in ("introduced_by_norm_ids", "refined_by_norm_ids"):
            ids = t.get(fld) or []
            if ids:
                t[fld] = [mapping.get(i, i) for i in ids]
    for q in merged.get("questions", []):
        ids = q.get("trigger_norm_ids") or []
        if ids:
            q["trigger_norm_ids"] = [mapping.get(i, i) for i in ids]
    for cns in merged.get("consequences", []):
        for fld in ("activates_norm_ids", "activates_question_ids", "source_norm_ids"):
            ids = cns.get(fld) or []
            if ids:
                cns[fld] = [mapping.get(i, i) for i in ids]
    for p in merged.get("parameters", []):
        ids = p.get("norm_ids") or []
        if ids:
            p["norm_ids"] = [mapping.get(i, i) for i in ids]

    return merged