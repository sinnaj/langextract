from __future__ import annotations

"""
Machine-translation powered translator for JSON "statement_text" fields.

This script uses Hugging Face Transformers (Helsinki-NLP/opus-mt-es-en) to
translate all values of keys named "statement_text" from Spanish to English.
Optionally, include "notes" with --also-notes.

Usage (PowerShell):
  python scripts/translate_statement_text_mt.py <input.json> [<output.json>] [--also-notes] [--batch-size 64] [--model Helsinki-NLP/opus-mt-es-en]

Requires: transformers, sentencepiece, and torch.
Install (example):
  pip install transformers sentencepiece torch
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


def _collect_translation_targets(obj: Any, keys: Tuple[str, ...]) -> List[Tuple[List[str], str]]:
  """Return a list of (path, text) to translate.

  path is a list of keys/indexes from root to the value.
  """
  results: List[Tuple[List[str], str]] = []

  def walk(node: Any, path: List[str]):
    if isinstance(node, dict):
      for k, v in node.items():
        if k in keys and isinstance(v, str):
          results.append((path + [k], v))
        else:
          walk(v, path + [k])
    elif isinstance(node, list):
      for i, v in enumerate(node):
        walk(v, path + [str(i)])

  walk(obj, [])
  return results


def _set_by_path(obj: Any, path: Sequence[str], value: Any) -> None:
  cur = obj
  for p in path[:-1]:
    cur = cur[int(p)] if p.isdigit() else cur[p]
  last = path[-1]
  if last.isdigit():
    cur[int(last)] = value
  else:
    cur[last] = value


@dataclass
class TranslatorConfig:
  model_name: str = "Helsinki-NLP/opus-mt-es-en"
  batch_size: int = 64
  show_progress: bool = True


def _chunks(seq: Sequence[str], n: int) -> Iterable[Sequence[str]]:
  for i in range(0, len(seq), n):
    yield seq[i : i + n]


def translate_spanish_to_english(texts: List[str], config: TranslatorConfig) -> List[str]:
  from transformers import pipeline  # Imported lazily to improve UX

  pipe = pipeline(
      "translation",
      model=config.model_name,
      device=-1,  # CPU
  )
  out: List[str] = []
  total = len(texts)
  processed = 0
  if config.show_progress:
    print(f"Translating {total} field(s) in batches of {config.batch_size} using '{config.model_name}' (CPU)")
  for batch in _chunks(texts, config.batch_size):
    # pipeline returns list of dicts: [{"translation_text": "..."}, ...]
    preds = pipe(list(batch))
    out.extend([p["translation_text"] for p in preds])
    processed += len(batch)
    if config.show_progress:
      pct = int(processed * 100 / total) if total else 100
      print(f"  Progress: {processed}/{total} ({pct}%)")
  return out


def main() -> int:
  ap = argparse.ArgumentParser(description="Translate JSON 'statement_text' fields from Spanish to English using HF Transformers.")
  ap.add_argument("input", type=Path, help="Input JSON file")
  ap.add_argument("output", type=Path, nargs="?", help="Output JSON path (default: output_en.json next to input)")
  ap.add_argument("--also-notes", action="store_true", dest="also_notes", help="Also translate 'notes' fields")
  ap.add_argument("--batch-size", type=int, default=64, help="Batch size for translation requests (default: 64)")
  ap.add_argument("--model", default="Helsinki-NLP/opus-mt-es-en", help="Hugging Face model id (default: Helsinki-NLP/opus-mt-es-en)")
  args = ap.parse_args()

  if not args.input.exists():
    print(f"Input not found: {args.input}")
    return 2

  try:
    data = json.loads(args.input.read_text(encoding="utf-8"))
  except Exception as e:
    print(f"Failed to parse JSON: {e}")
    return 1

  keys: Tuple[str, ...] = ("statement_text",) + (("notes",) if args.also_notes else tuple())
  targets = _collect_translation_targets(data, keys)
  texts = [t[1] for t in targets]
  if not texts:
    outp = args.output or args.input.with_name("output_en.json")
    outp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"No fields to translate. Wrote: {outp}")
    return 0

  try:
    print(f"Found {len(texts)} field(s) to translate: {', '.join(keys)}")
    translated = translate_spanish_to_english(
      texts,
      TranslatorConfig(
        model_name=args.model,
        batch_size=args.batch_size,
        show_progress=True,
      ),
    )
  except Exception as e:
    print("Error during translation. Ensure 'transformers', 'sentencepiece', and 'torch' are installed.")
    print(f"Exact error: {e}")
    return 1

  # Reinsert translations by path order
  for (path, _), new_val in zip(targets, translated):
    _set_by_path(data, path, new_val)

  outp = args.output or args.input.with_name("output_en.json")
  outp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
  count_str = ", ".join(keys)
  print(f"Translated {len(translated)} field(s) ({count_str}). Wrote: {outp}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
