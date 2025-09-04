from __future__ import annotations

"""
Translate only ExampleData.text and Extraction.extraction_text string literals in a Python examples file.

- Parses the Python source with AST and locates keyword arguments named
  'text' and 'extraction_text' whose values are constant strings
  (including parenthesized adjacent string literals which Python concatenates).
- Uses a Hugging Face translation pipeline (es -> en) to translate those strings.
- Rewrites the source by replacing just those string literal spans, preserving the rest of the file intact.
- Writes to a new file (default: <input> with _en.py suffix) to avoid overwriting.

Usage (PowerShell):
  python scripts/translate_examples_enhanced.py input_examplefiles/examples_enhanced.py \
         [<output.py>] [--batch-size 64] [--model Helsinki-NLP/opus-mt-es-en]

Requires: transformers, sentencepiece, torch
"""

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

TargetKeys = {"text", "extraction_text"}


@dataclass
class StringSpan:
  key: str
  value: str
  start: int
  end: int


def _offsets_from_lines(source: str) -> List[int]:
  """Return cumulative offsets per line index (1-based lineno)."""
  offsets: List[int] = [0]  # dummy for 0 index
  total = 0
  for line in source.splitlines(keepends=True):
    total += len(line)
    offsets.append(total)
  return offsets


def _node_span_to_offsets(
    node: ast.AST, line_offsets: List[int]
) -> Tuple[int, int]:
  # Requires Python >= 3.8 for end_lineno/end_col_offset
  start = line_offsets[node.lineno - 1] + node.col_offset
  end = line_offsets[node.end_lineno - 1] + node.end_col_offset
  return start, end


def collect_string_spans(py_source: str) -> List[StringSpan]:
  tree = ast.parse(py_source)
  line_offsets = _offsets_from_lines(py_source)
  spans: List[StringSpan] = []

  class Visitor(ast.NodeVisitor):

    def visit_Call(self, call: ast.Call) -> Any:
      # We don't restrict by function name; just look for keywords
      for kw in call.keywords:
        if not isinstance(kw, ast.keyword):
          continue
        if (
            kw.arg in TargetKeys
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
          start, end = _node_span_to_offsets(kw.value, line_offsets)
          spans.append(StringSpan(kw.arg, kw.value.value, start, end))
      self.generic_visit(call)

  Visitor().visit(tree)
  return spans


@dataclass
class TranslatorConfig:
  model_name: str = "Helsinki-NLP/opus-mt-es-en"
  batch_size: int = 64
  show_progress: bool = True


def _chunks(seq: Sequence[str], n: int) -> Iterable[Sequence[str]]:
  for i in range(0, len(seq), n):
    yield seq[i : i + n]


def translate_spanish_to_english(
    texts: List[str], config: TranslatorConfig
) -> List[str]:
  """Translate using AutoTokenizer/AutoModelForSeq2SeqLM to avoid heavy pipeline imports."""
  import torch
  from transformers import AutoModelForSeq2SeqLM
  from transformers import AutoTokenizer

  if config.show_progress:
    print(
        f"Translating {len(texts)} field(s) in batches of"
        f" {config.batch_size} using '{config.model_name}' (CPU)"
    )

  tokenizer = AutoTokenizer.from_pretrained(config.model_name)
  model = AutoModelForSeq2SeqLM.from_pretrained(config.model_name)
  model.eval()

  out: List[str] = []
  done = 0
  for batch in _chunks(texts, config.batch_size):
    inputs = tokenizer(
        list(batch),
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )
    with torch.no_grad():
      generated = model.generate(
          **inputs,
          num_beams=4,
          length_penalty=1.0,
          max_new_tokens=256,
      )
    decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
    out.extend(decoded)
    done += len(batch)
    if config.show_progress:
      pct = int(done * 100 / len(texts)) if texts else 100
      print(f"  Progress: {done}/{len(texts)} ({pct}%)")
  return out


def apply_replacements(
    source: str, spans: List[StringSpan], replacements: List[str]
) -> str:
  # Build edit list and apply from the end to preserve offsets
  edits = list(zip(spans, replacements))
  edits.sort(key=lambda e: e[0].start, reverse=True)
  out = source
  for span, new_text in edits:
    # Use repr to generate a safe Python string literal
    out = out[: span.start] + repr(new_text) + out[span.end :]
  return out


def main() -> int:
  ap = argparse.ArgumentParser(
      description=(
          "Translate ExampleData.text and Extraction.extraction_text string"
          " literals in a Python examples file."
      )
  )
  ap.add_argument(
      "input",
      type=Path,
      help="Input .py file (e.g., input_examplefiles/examples_enhanced.py)",
  )
  ap.add_argument(
      "output",
      type=Path,
      nargs="?",
      help="Output .py (default: *_en.py next to input)",
  )
  ap.add_argument(
      "--batch-size", type=int, default=64, help="Translation batch size"
  )
  ap.add_argument(
      "--model",
      default="Helsinki-NLP/opus-mt-es-en",
      help="Hugging Face model id",
  )
  args = ap.parse_args()

  if not args.input.exists():
    print(f"Input not found: {args.input}")
    return 2
  src = args.input.read_text(encoding="utf-8")

  spans = collect_string_spans(src)
  # Filter to only those spans that look like Spanish. We keep it simple and translate all we found.
  if not spans:
    outp = args.output or args.input.with_name(args.input.stem + "_en.py")
    outp.write_text(src, encoding="utf-8")
    print(f"No eligible string literals found. Wrote copy to: {outp}")
    return 0

  # Prepare texts for translation
  texts = [s.value for s in spans]
  print(
      f"Found {len(texts)} string literal(s) to translate: keys in"
      f" {sorted(TargetKeys)}"
  )

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
        "Error during translation. Ensure 'transformers', 'sentencepiece', and"
        " 'torch' are installed."
    )
    print(f"Exact error: {e}")
    return 1

  new_src = apply_replacements(src, spans, translated)
  outp = args.output or args.input.with_name(args.input.stem + "_en.py")
  outp.write_text(new_src, encoding="utf-8")
  print(f"Translated {len(translated)} string(s). Wrote: {outp}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
