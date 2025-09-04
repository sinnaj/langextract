from __future__ import annotations

"""
Renumber all entity IDs across a JSON document to ensure unique, sequential IDs per type.

ID format handled: "<PREFIX>::<NUMBER>" (e.g., "N::0001", "T::0001", "P::0001").
The script walks the entire JSON, collects all IDs, assigns new sequential numbers starting
from 0001 for each distinct PREFIX, builds a mapping old->new, and then rewrites both the
entity "id" fields and any string references anywhere in the JSON that exactly match an
old ID.

Usage (PowerShell):
  python scripts/renumber_ids.py <input.json> [<output.json>] [--preserve-old-id]

Defaults:
  - Output path defaults to a sibling file named "output_ids.json" next to the input.
  - At least 4 digits are used for the numeric part (0001, 0002, ...). If the count exceeds 9999,
    the width grows automatically to fit (e.g., 10000 -> 5 digits).

Notes:
  - This script updates references by replacing any string value that equals an old ID exactly.
    This covers arrays like "extracted_parameters_ids", "consequence_ids", and any other fields
    that store IDs as strings.
  - Non-matching IDs (not in PREFIX::NUMBER form) are left untouched.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ID_RE = re.compile(r"^([A-Z][A-Z0-9_-]*)::(\d+)$")


def _walk_collect_ids(node: Any, found: List[str]) -> None:
  """Collect all id field values (raw) in document order."""
  if isinstance(node, dict):
    v = node.get("id")
    if isinstance(v, str) and ID_RE.match(v):
      found.append(v)
    for _, val in node.items():
      _walk_collect_ids(val, found)
  elif isinstance(node, list):
    for it in node:
      _walk_collect_ids(it, found)
  # primitives ignored


def _format_with_min_width(n: int, min_width: int = 4) -> str:
  s = str(n)
  width = max(min_width, len(s))
  return f"{n:0{width}d}"


def _build_occurrence_counts(ids: List[str]) -> Dict[str, int]:
  counts: Dict[str, int] = {}
  for s in ids:
    counts[s] = counts.get(s, 0) + 1
  return counts


def _renumber_ids_in_place(
    node: Any,
    counters: Dict[str, int],
    id_counts: Dict[str, int],
    unique_ref_map: Dict[str, str],
    preserve_old_id: bool,
    per_prefix_totals: Dict[str, int],
) -> None:
  """Assign new IDs per occurrence and populate unique_ref_map for IDs that were unique originally.

  - counters: per-prefix running counters for new IDs
  - id_counts: count of how many times each old ID string appeared
  - unique_ref_map: mapping from old ID string -> new ID string (only for old IDs with count==1)
  - per_prefix_totals: final totals per prefix (for stats)
  """
  if isinstance(node, dict):
    v = node.get("id")
    if isinstance(v, str):
      m = ID_RE.match(v)
      if m:
        prefix = m.group(1)
        next_n = counters.get(prefix, 0) + 1
        counters[prefix] = next_n
        new_id = f"{prefix}::{_format_with_min_width(next_n)}"
        # if uniquely occurring old ID, remember mapping for reference rewriting
        if id_counts.get(v, 0) == 1:
          unique_ref_map[v] = new_id
        if preserve_old_id and "old_id" not in node:
          node["old_id"] = v
        node["id"] = new_id
        per_prefix_totals[prefix] = per_prefix_totals.get(prefix, 0) + 1
    for k, val in list(node.items()):
      # Avoid recursing into the just-updated values unnecessarily
      if k in ("id", "old_id"):
        continue
      _renumber_ids_in_place(
          val,
          counters,
          id_counts,
          unique_ref_map,
          preserve_old_id,
          per_prefix_totals,
      )
  elif isinstance(node, list):
    for it in node:
      _renumber_ids_in_place(
          it,
          counters,
          id_counts,
          unique_ref_map,
          preserve_old_id,
          per_prefix_totals,
      )
  # primitives ignored


def _rewrite_references(node: Any, safe_map: Dict[str, str]) -> Any:
  """Rewrite string references that exactly match an old ID only when the old ID was unique.

  We deliberately skip dict keys 'id' and 'old_id' in this pass.
  """
  if isinstance(node, dict):
    new_obj: Dict[str, Any] = {}
    for k, v in node.items():
      if k in ("id", "old_id"):
        new_obj[k] = v
        continue
      if isinstance(v, str) and v in safe_map:
        new_obj[k] = safe_map[v]
      else:
        new_obj[k] = _rewrite_references(v, safe_map)
    return new_obj
  if isinstance(node, list):
    return [
        safe_map.get(it, it)
        if isinstance(it, str)
        else _rewrite_references(it, safe_map)
        for it in node
    ]
  if isinstance(node, str) and node in safe_map:
    return safe_map[node]
  return node


def _unique_ordered(seq: Iterable[str]) -> List[str]:
  seen: set[str] = set()
  out: List[str] = []
  for s in seq:
    if s not in seen:
      seen.add(s)
      out.append(s)
  return out


def main(argv: List[str]) -> int:
  if len(argv) < 2:
    print(
        "Usage: renumber_ids.py <input.json> [<output.json>]"
        " [--preserve-old-id]"
    )
    return 2
  inp = Path(argv[1])
  if not inp.exists():
    print(f"Input not found: {inp}")
    return 2
  outp: Path | None = None
  preserve_old_id = False
  for a in argv[2:]:
    if a == "--preserve-old-id":
      preserve_old_id = True
    elif outp is None and not a.startswith("--"):
      outp = Path(a)

  outp = outp or inp.with_name("output_ids.json")

  try:
    data = json.loads(inp.read_text(encoding="utf-8"))
  except Exception as e:
    print(f"Failed to parse JSON: {e}")
    return 1

  found_ids: List[str] = []
  _walk_collect_ids(data, found_ids)
  if not found_ids:
    print("No renumberable IDs found. Writing a copy.")
    outp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote: {outp}")
    return 0

  # Count occurrences of each old ID string
  id_counts = _build_occurrence_counts(found_ids)

  # First pass: renumber ids per occurrence, building a safe mapping for unique old IDs
  counters: Dict[str, int] = {}
  per_prefix_totals: Dict[str, int] = {}
  unique_ref_map: Dict[str, str] = {}
  _renumber_ids_in_place(
      data,
      counters,
      id_counts,
      unique_ref_map,
      preserve_old_id,
      per_prefix_totals,
  )

  # Second pass: rewrite references only for unique old IDs
  new_data = _rewrite_references(data, unique_ref_map)

  outp.write_text(
      json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8"
  )

  total = sum(per_prefix_totals.values())
  per_prefix_str = ", ".join(
      f"{k}={v}" for k, v in sorted(per_prefix_totals.items())
  )
  # Report how many references were safely rewritten
  safe_refs = len(unique_ref_map)
  dup_ids = [k for k, c in id_counts.items() if c > 1]
  if dup_ids:
    print(
        f"Note: {len(dup_ids)} old ID value(s) were duplicated in input and"
        " could not be disambiguated for reference rewriting. Their references"
        " were left unchanged."
    )
  print(f"Renumbered {total} ID object(s): {per_prefix_str}")
  print(f"Rewrote references for {safe_refs} unique old ID value(s).")
  print(f"Wrote: {outp}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main(sys.argv))
