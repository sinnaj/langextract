from typing import Any, Dict


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