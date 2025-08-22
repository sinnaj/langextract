"""Norms-only extraction runner aligned with `prompts/extraction_prompt_norms_min.md`.

Focus: Emit only Norms using a compact minimal prompt. All non-Norm arrays must exist but
remain empty. We still use the same manual chunking + aggregation pipeline, robust parsing from
resolver_raw_output.txt, and minimal validation.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
import langextract as lx

# ---------------------------------------------------------------------------
# 0. Environment / Config
# ---------------------------------------------------------------------------
load_dotenv()

USE_OPENROUTER = os.getenv("USE_OPENROUTER", "1").lower() in {"1","true","yes"}
OPENROUTER_KEY = os.environ.get("OPENAI_API_KEY")  # repurposed for OpenRouter
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if USE_OPENROUTER:
    if not OPENROUTER_KEY:
        print("WARNING: OPENROUTER (OPENAI_API_KEY) key not set – OpenRouter call will fail.", file=sys.stderr)
else:
    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set – direct Gemini call will likely fail.", file=sys.stderr)

PROMPT_FILE = Path("prompts/extraction_prompt_norms_min.md")
OUTPUT_FILE = Path("rich_norms_min.json")
GLOSSARY_FILE = Path("dsl_glossary_min.json")
MAX_NORMS_PER_5K = 35  # minimal spec recommends a higher cap
MODEL_ID = "google/gemini-2.5-flash" if USE_OPENROUTER else "gemini-2.5-flash"
MODEL_TEMPERATURE = 0.15

if not PROMPT_FILE.exists():
    print(f"FATAL: Prompt file missing at {PROMPT_FILE}", file=sys.stderr)
    sys.exit(1)

# Base prompt
PROMPT_DESCRIPTION = PROMPT_FILE.read_text(encoding="utf-8")

TEACH_MODE = os.getenv("LX_TEACH_MODE") == "1"
USE_FEWSHOTS = os.getenv("LX_USE_FEWSHOTS", "0").lower() in {"1","true","yes"}

# ---------------------------------------------------------------------------
# 1. Few-Shot Examples (Norms only)
# ---------------------------------------------------------------------------
# Keep examples minimal: only Norms with applies_if/satisfied_if/exempt_if and paragraph_number.
EXAMPLES: List[lx.data.ExampleData] = [
    lx.data.ExampleData(
        text=(
            "1 Las puertas de salida para la evacuación de más de 50 personas deben ser abatibles con eje vertical y permitir apertura sin llave o mantener el sistema de cierre desactivado durante la actividad."
            "No se aplica a puertas automáticas con sistema de abatimiento seguro."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Las puertas de salida para la evacuación de más de 50 personas deben ser abatibles con eje vertical y permitir apertura sin llave o mantener el sistema de cierre desactivado durante la actividad."
                ),
                attributes={
                    "paragraph_number": 1,
                    "applies_if": "EVACUATION.PERSONS > 50",
                    "satisfied_if": (
                        "(DOOR.TYPE == 'SWING' AND DOOR.AXIS == 'VERTICAL'); OR "
                        "(DOOR.OPENING.REQUIRES_KEY == FALSE AND DOOR.OPENING.MECHANISMS_COUNT <= 1); OR "
                        "(CLOSING.SYSTEM.ENABLED == FALSE)"
                    ),
                    "exempt_if": "DOOR.TYPE == 'AUTOMATIC' AND HAS(DOOR.OPTION.SWING_ALLOWED)",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text="2 No se admite la instalación de dispositivos que requieran llave en la ruta de evacuación principal cuando la ocupación sea superior a 100 personas.",
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="No se admite la instalación de dispositivos que requieran llave en la ruta de evacuación principal cuando la ocupación sea superior a 100 personas.",
                attributes={
                    "paragraph_number": 2,
                    "applies_if": "EVACUATION.PERSONS > 100",
                    "satisfied_if": "DOOR.OPENING.REQUIRES_KEY == FALSE",
                    "exempt_if": None,
                },
            )
        ],
    ),
    lx.data.ExampleData(
        text=(
            "En la zona R6.2 se requerirá la presentación del Anexo III cuando la fuerza de apertura sea <= 220 N."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="Se requerirá la presentación del Anexo III cuando la fuerza de apertura sea <= 220 N.",
                attributes={
                    "paragraph_number": 3,
                    "applies_if": "ZONE.CODE == 'R6.2'",
                    "satisfied_if": "ANNEX.ANEXO_III.SUBMITTED == TRUE",
                    "exempt_if": None,
                },
            ),
        ],
    ),
]

# By default, do NOT include few-shots to avoid any chance of extracting from examples.
# Enable by setting LX_USE_FEWSHOTS=1 if you want in-context guidance.
EXAMPLES_TO_USE: List[lx.data.ExampleData] = EXAMPLES if USE_FEWSHOTS else []

# ---------------------------------------------------------------------------
# 2. Sample Input Text
# ---------------------------------------------------------------------------
from testExtraction_3 import INPUT_TEXT  # reuse the same test text

# ---------------------------------------------------------------------------
# 3. Minimal Validation Helpers (shared from main runner via small copies)
# ---------------------------------------------------------------------------
TOP_LEVEL_REQUIRED = [
    "schema_version",
    "ontology_version",
    "truncated",
    "has_more",
    "window_config",
    "global_disclaimer",
    "document_metadata",
    "norms",
    "tags",
    "locations",
    "questions",
    "consequences",
    "parameters",
    "quality",
]

def is_rich_schema(d: Any) -> bool:
    return isinstance(d, dict) and all(k in d for k in TOP_LEVEL_REQUIRED)

# Extract DSL field paths for glossary
def collect_dsl_keys(obj: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    dsl_fields = ("applies_if", "satisfied_if", "exempt_if")
    pattern = re.compile(r"[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+")
    for norm in obj.get("norms", []):
        for f in dsl_fields:
            v = norm.get(f)
            if isinstance(v, str):
                for m in pattern.findall(v):
                    keys.add(m)
    return keys

# ---------------------------------------------------------------------------
# 4. Chunking + Extraction (same strategy)
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_chars: int = 3500, overlap: int = 300) -> List[Tuple[int,str]]:
    spans: List[Tuple[int,str]] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(n, i + max_chars)
        spans.append((i, text[i:end]))
        if end >= n:
            break
        i = end - overlap
        if i < 0 or i >= n:
            break
    return spans

ATOMIC_DIRECTIVE = "\nSTRICT_NORM_GRANULARITY: Emit ONE norm per distinct obligation/prohibition statement (do not merge separate lettered bullets a), b), c)... nor separate numeric paragraphs).\n"
EXAMPLES_NOT_SOURCE_DIRECTIVE = "\nDO_NOT_EXTRACT_FROM_EXAMPLES: Examples are guidance only and are NOT part of the source text. Extract exclusively from the provided TEXT chunk.\n"
prompt_with_directive = PROMPT_DESCRIPTION + ATOMIC_DIRECTIVE + EXAMPLES_NOT_SOURCE_DIRECTIVE

spans = chunk_text(INPUT_TEXT, max_chars=3500, overlap=300)
print(f"[INFO] Created {len(spans)} manual chunk(s) (total chars={len(INPUT_TEXT)})")
all_chunk_objs: List[Dict[str, Any]] = []
for idx, (offset, subtxt) in enumerate(spans, start=1):
    print(f"[INFO] Invoking model for chunk {idx}/{len(spans)} char_offset={offset} len={len(subtxt)} ...")
    lm_params = {"temperature": MODEL_TEMPERATURE}
    extract_kwargs = dict(
        text_or_documents=subtxt,
        prompt_description=prompt_with_directive,
    examples=EXAMPLES_TO_USE,
        model_id=MODEL_ID,
        fence_output=False,
        use_schema_constraints=False,
        temperature=MODEL_TEMPERATURE,
        resolver_params={
            "fence_output": False,
            "format_type": lx.data.FormatType.JSON,
        },
        language_model_params=lm_params,
    )
    if USE_OPENROUTER:
        extract_kwargs["api_key"] = OPENROUTER_KEY
        lm_extra = extract_kwargs.setdefault("language_model_params", {})
        lm_extra.update({
            "base_url": "https://openrouter.ai/api/v1",
            "openrouter_referer": os.getenv("OPENROUTER_REFERER"),
            "openrouter_title": os.getenv("OPENROUTER_TITLE", "LangExtract Norms-Only Runner"),
        })
    else:
        extract_kwargs.update({"api_key": GOOGLE_API_KEY})
    extract_kwargs["max_char_buffer"] = 5000

    _ = lx.extract(**extract_kwargs)
    raw_file = Path("resolver_raw_output.txt")
    if not raw_file.exists():
        print(f"[WARN] Chunk {idx} missing resolver_raw_output.txt – skipping.")
        continue
    raw_text = raw_file.read_text(encoding="utf-8").strip()
    try:
        parsed = json.loads(raw_text)
    except Exception:
        parsed = None
    if not (isinstance(parsed, dict) and isinstance(parsed.get("extractions"), list)):
        snippet = (raw_text[:160] if isinstance(raw_text, str) else "").replace('\n',' ')
        print(f"[WARN] Chunk {idx} not rich schema (snippet='{snippet}'); skipping.")
        continue
    for obj in parsed.get("extractions", []):
        if not is_rich_schema(obj):
            continue
        # Normalize to minimal expectations: keep arrays present; norms only populated.
        obj.setdefault("tags", [])
        obj.setdefault("locations", [])
        obj.setdefault("questions", [])
        obj.setdefault("consequences", [])
        obj.setdefault("parameters", [])
        # Adjust source span offsets & normalize statement_text field name
        for norm in obj.get("norms", []):
            if isinstance(norm, dict):
                if "statement_text" not in norm:
                    for alt_key in ("Norm", "norm", "text", "NORM"):
                        if isinstance(norm.get(alt_key), str):
                            norm["statement_text"] = norm.get(alt_key)
                            break
                src = norm.get("source") or {}
                if isinstance(src, dict):
                    if isinstance(src.get("span_char_start"), int):
                        src["span_char_start"] += offset
                    if isinstance(src.get("span_char_end"), int):
                        src["span_char_end"] += offset
                    norm["source"] = src
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"CHUNK_INDEX:{idx}")
        wc = obj.get("window_config") or {}
        if isinstance(wc, dict):
            wc["input_chars"] = len(subtxt)
            wc["max_norms_per_5k_tokens"] = MAX_NORMS_PER_5K
            obj["window_config"] = wc
        all_chunk_objs.append(obj)

if not all_chunk_objs:
    print("[FATAL] No chunk produced a valid rich schema object.")
    sys.exit(3)

parsed_root = {"extractions": all_chunk_objs}
print(f"[INFO] Parsed {len(all_chunk_objs)} rich chunk object(s); aggregating ...")

# ---------------------------------------------------------------------------
# 5. Aggregation (lightweight, norms-focused)
# ---------------------------------------------------------------------------

def aggregate_extractions(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not chunks:
        return {}
    if len(chunks) == 1:
        return chunks[0]
    merged: Dict[str, Any] = {k: chunks[0].get(k) for k in chunks[0].keys() if k not in {"norms","tags","locations","questions","consequences","parameters","quality","window_config","document_metadata"}}
    merged["norms"] = [n for c in chunks for n in c.get("norms", [])]
    merged["tags"] = []
    merged["locations"] = []
    merged["questions"] = []
    merged["consequences"] = []
    merged["parameters"] = []

    # window_config
    total_chars = 0
    for c in chunks:
        wc = c.get("window_config", {}) or {}
        total_chars += int(wc.get("input_chars") or 0)
    merged["window_config"] = {
        "input_chars": total_chars,
        "max_norms_per_5k_tokens": MAX_NORMS_PER_5K,
        "extracted_norm_count": len(merged["norms"]),
    }

    merged["truncated"] = any(c.get("truncated") for c in chunks)
    merged["has_more"] = any(c.get("has_more") for c in chunks)

    # quality
    errors: List[Any] = []
    warnings: List[Any] = []
    seen_e: Set[str] = set(); seen_w: Set[str] = set()
    def norm_item(x: Any) -> str:
        if isinstance(x, (str,int,float)):
            return str(x)
        try:
            return json.dumps(x, sort_keys=True, ensure_ascii=False)
        except Exception:
            return repr(x)
    for c in chunks:
        q = c.get("quality", {}) or {}
        for e in q.get("errors", []) or []:
            k = norm_item(e)
            if k not in seen_e:
                seen_e.add(k); errors.append(e)
        for w in q.get("warnings", []) or []:
            k = norm_item(w)
            if k not in seen_w:
                seen_w.add(k); warnings.append(w)
    warnings.append(f"AGGREGATED_CHUNKS:{len(chunks)}")
    merged["quality"] = {"errors": errors, "warnings": warnings}

    # reindex Norm IDs sequentially
    new_norms: List[Dict[str, Any]] = []
    for i, n in enumerate(merged.get("norms", []), start=1):
        if isinstance(n, dict):
            n["id"] = f"N::{i:04d}"
            new_norms.append(n)
    merged["norms"] = new_norms

    return merged

primary = aggregate_extractions(all_chunk_objs)

# set minimal defaults
wc = primary.setdefault("window_config", {})
wc.setdefault("max_norms_per_5k_tokens", MAX_NORMS_PER_5K)
wc["extracted_norm_count"] = len(primary.get("norms", []))

# ---------------------------------------------------------------------------
# 6. Persist Results
# ---------------------------------------------------------------------------
OUTPUT_FILE.write_text(json.dumps({"extractions":[primary]}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved norms-only JSON root → {OUTPUT_FILE}")

# Glossary of DSL field paths
from typing import Any as _Any  # avoid linter clash
keys = sorted(collect_dsl_keys(primary))
GLOSSARY_FILE.write_text(json.dumps({k: "" for k in keys}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved DSL glossary stub ({len(keys)} keys) → {GLOSSARY_FILE}")

print("Done (norms-only).")
