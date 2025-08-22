from typing import Any, Dict


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