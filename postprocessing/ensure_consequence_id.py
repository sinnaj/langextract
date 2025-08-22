from typing import Any, Dict


def ensure_consequence_id(cons: Dict[str, Any], obj: Dict[str, Any]) -> str:
    if cons.get("id"):
        return cons["id"]
    cons_list = obj.get("consequences", [])
    new_id = f"C::{len(cons_list)+1:04d}"
    cons["id"] = new_id
    return new_id