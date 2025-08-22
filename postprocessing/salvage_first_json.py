# --- Salvage logic: extract first balanced JSON object if wrapper text present ---
import json
from typing import Any, Dict


def salvage_first_json(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to locate the first balanced JSON object within an arbitrary wrapper string.

    Strategy:
      1. Find first '{'.
      2. Incrementally scan, tracking nesting depth; when depth returns to 0, slice candidate.
      3. Attempt json.loads on slice; if fails, progressively extend forward searching for next '}' occurrences.
      4. If object loads and has 'extractions' key (rich schema root) OR is an object whose key 'extractions' appears nested at top-level, return it.
    This intentionally refuses arrays at root to maintain strict contract. Returns None if no valid object found.
    """
    if not isinstance(text, str):
        return None
    # Prefer explicit pattern start for our root
    pattern_indices = []
    root_pat = '{"extractions"'
    idx = 0
    while True:
        idx = text.find(root_pat, idx)
        if idx == -1:
            break
        pattern_indices.append(idx)
        idx += 1
    # Fallback to first '{' if pattern not found
    if not pattern_indices:
        try:
            pattern_indices = [text.index('{')]
        except ValueError:
            return None
    for start in pattern_indices:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict) and 'extractions' in obj:
                            return obj
                    except Exception:
                        pass
    return None