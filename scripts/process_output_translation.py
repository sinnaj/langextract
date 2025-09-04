from __future__ import annotations

"""
End-to-end processor for extraction outputs:
  1) Translate Spanish 'statement_text' (and optionally 'notes') to English using Helsinki-NLP/opus-mt-es-en
  2) Renumber IDs to sequential, unique values per prefix and rewrite references

Usage (PowerShell):
  python scripts/process_output_translation.py <input.json> [--out-en <path>] [--out-ids <path>] [--also-notes] [--batch-size 64] [--model Helsinki-NLP/opus-mt-es-en] [--preserve-old-id]

Outputs (defaults next to input):
  - output_en.json  (translated)
  - output_ids.json (translated + renumbered)
"""

import argparse
import copy
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Sequence, Tuple

# Ensure project root is on sys.path so 'scripts.*' imports work when running this file directly
_THIS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _THIS_DIR.parent
if str(_ROOT_DIR) not in sys.path:
  sys.path.insert(0, str(_ROOT_DIR))

from scripts.renumber_ids import _build_occurrence_counts  # type: ignore
from scripts.renumber_ids import _renumber_ids_in_place  # type: ignore
from scripts.renumber_ids import _rewrite_references  # type: ignore
from scripts.renumber_ids import _walk_collect_ids  # type: ignore
from scripts.translate_statement_text_mt import _collect_translation_targets
from scripts.translate_statement_text_mt import _set_by_path
from scripts.translate_statement_text_mt import translate_spanish_to_english
from scripts.translate_statement_text_mt import TranslatorConfig


def _renumber_in_memory(
    data: Any, preserve_old_id: bool = False
) -> tuple[Any, Dict[str, int], int, int]:
  """Renumber IDs in-memory using the same logic as scripts/renumber_ids.py main().

  Returns (new_data, per_prefix_totals, total_objects, safe_refs_rewritten)
  """
  found_ids: List[str] = []
  _walk_collect_ids(data, found_ids)
  if not found_ids:
    return data, {}, 0, 0

  id_counts = _build_occurrence_counts(found_ids)
  counters: Dict[str, int] = {}
  per_prefix_totals: Dict[str, int] = {}
  unique_ref_map: Dict[str, str] = {}
  # Mutates in place, so operate on a deepcopy to keep input data intact for other consumers
  work = copy.deepcopy(data)
  _renumber_ids_in_place(
      work,
      counters,
      id_counts,
      unique_ref_map,
      preserve_old_id,
      per_prefix_totals,
  )
  new_data = _rewrite_references(work, unique_ref_map)

  total = sum(per_prefix_totals.values())
  safe_refs = len(unique_ref_map)
  return new_data, per_prefix_totals, total, safe_refs


def main() -> int:
  ap = argparse.ArgumentParser(
      description="Translate and renumber an extraction output JSON."
  )
  ap.add_argument("input", type=Path, help="Path to input output.json")
  ap.add_argument(
      "--out-en",
      dest="out_en",
      type=Path,
      default=None,
      help=(
          "Path to write translated JSON (default: output_en.json next to"
          " input)"
      ),
  )
  ap.add_argument(
      "--out-ids",
      dest="out_ids",
      type=Path,
      default=None,
      help=(
          "Path to write renumbered JSON (default: output_ids.json next to"
          " input)"
      ),
  )
  ap.add_argument(
      "--also-notes",
      action="store_true",
      dest="also_notes",
      help="Also translate 'notes' fields",
  )
  ap.add_argument(
      "--batch-size",
      type=int,
      default=64,
      help="Batch size for translation (default: 64)",
  )
  ap.add_argument(
      "--model",
      default="Helsinki-NLP/opus-mt-es-en",
      help="Hugging Face model id (default: Helsinki-NLP/opus-mt-es-en)",
  )
  ap.add_argument(
      "--preserve-old-id",
      action="store_true",
      help="Preserve original IDs in an 'old_id' field during renumbering",
  )
  args = ap.parse_args()

  if not args.input.exists():
    print(f"Input not found: {args.input}")
    return 2

  try:
    data = json.loads(args.input.read_text(encoding="utf-8"))
  except Exception as e:
    print(f"Failed to parse JSON: {e}")
    return 1

  # 1) Translate fields
  keys: Tuple[str, ...] = ("statement_text",) + (
      ("notes",) if args.also_notes else tuple()
  )
  targets = _collect_translation_targets(data, keys)
  texts = [t[1] for t in targets]
  if texts:
    print(f"Translating {len(texts)} field(s): {', '.join(keys)}")
    try:
      translated = translate_spanish_to_english(
          texts,
          TranslatorConfig(
              model_name=args.model,
              batch_size=args.batch_size,
              show_progress=True,
          ),
      )
    except Exception as e:
      print(
          "Error during translation. Ensure 'transformers', 'sentencepiece',"
          " and 'torch' are installed."
      )
      print(f"Exact error: {e}")
      return 1

    for (path, _), new_val in zip(targets, translated):
      _set_by_path(data, path, new_val)
  else:
    print("No fields to translate.")

  out_en = args.out_en or args.input.with_name("output_en.json")
  out_en.write_text(
      json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
  )
  print(f"Wrote translated JSON: {out_en}")

  # 2) Renumber IDs on the translated data
  new_data, per_prefix, total_objs, safe_refs = _renumber_in_memory(
      data, preserve_old_id=args.preserve_old_id
  )
  out_ids = args.out_ids or args.input.with_name("output_ids.json")
  out_ids.write_text(
      json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8"
  )

  if total_objs:
    per_prefix_str = ", ".join(
        f"{k}={v}" for k, v in sorted(per_prefix.items())
    )
    print(f"Renumbered {total_objs} object(s): {per_prefix_str}")
    print(f"Rewrote references for {safe_refs} unique old ID value(s).")
  else:
    print("No renumberable IDs found.")
  print(f"Wrote renumbered JSON: {out_ids}")

  return 0


if __name__ == "__main__":
  raise SystemExit(main())
