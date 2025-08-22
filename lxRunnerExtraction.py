"""Comprehensive extraction runner aligned with `prompts/extraction_prompt.md`.

Imperative Goal:
  Exercise the full rich schema (Norms, Tags, Locations, Questions, Consequences, Parameters)
  specified in `extraction_prompt.md`, provide diverse few-shot guidance, invoke the model,
  validate & normalize output, and persist structured JSON for downstream ingestion.

Key Features:
  * Loads authoritative prompt from file (single source of truth).
  * Few-shot examples for each extraction class (Norm, Tag, Location, Question, Consequence, Parameter) using the specified DSL grammar (UPPERCASE.DOTCASE, IN[], ; OR separation, geo operators, HAS()).
  * Post-run validation: required top-level keys, ID reference integrity, DSL surface heuristics.
  * Legacy fallback wrapper (if model returns only classic `extractions` list) → upgrade into rich schema skeleton.
  * Optional heuristic enrichment (priority scoring, parameter derivation) if missing.
  * Glossary creation for discovered DSL field paths.

NOTE: This is an iterative development harness. For production scaling (multi-chunk PDF ingestion,
ontology merging across runs, persistent ID registry, and deduplication) implement specialized
pipelines beyond this script.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from datetime import datetime

from dotenv import load_dotenv
from postprocessing.aggregate_extractions import aggregate_extractions
from preprocessing.chunk_text import chunk_text
import langextract as lx
from postprocessing.is_rich_schema import (
    is_rich_schema,
    validate_rich,
    collect_dsl_keys
)
from postprocessing.validate_and_enhance_rich_schema import validate_and_enhance_rich_schema

# Optional postprocessors (may not be present in all workspaces)
def _opt_import(module: str, name: str):
    try:
        mod = __import__(module, fromlist=[name])
        return getattr(mod, name)
    except Exception:
        return None

merge_duplicate_tags = _opt_import("postprocessing.merge_duplicate_tags", "merge_duplicate_tags") or (lambda _obj: None)
autophrase_questions = _opt_import("postprocessing.autophrase_questions", "autophrase_questions") or (lambda _obj: None)
compute_extended_metrics = _opt_import("postprocessing.compute_extended_metrics", "compute_extended_metrics") or (lambda _obj: None)
ensure_consequence_ids = _opt_import("postprocessing.ensure_consequence_ids", "ensure_consequence_ids") or (lambda _obj: None)
humanize_segment = _opt_import("postprocessing.humanize_segment", "humanize_segment") or (lambda _obj: None)

USE_OPENROUTER = os.getenv("USE_OPENROUTER", "1").lower() in {"1","true","yes"}
OPENROUTER_KEY = os.environ.get("OPENAI_API_KEY")  # repurposed for OpenRouter
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if USE_OPENROUTER:
    if not OPENROUTER_KEY:
        print("WARNING: OPENROUTER (OPENAI_API_KEY) key not set – OpenRouter call will fail.", file=sys.stderr)
else:
    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set – direct Gemini call will likely fail.", file=sys.stderr)

PROMPT_FILE = Path("input_promptfiles/extraction_prompt.md")
OUTPUT_FILE = Path("rich_norms_full.json")
GLOSSARY_FILE = Path("dsl_glossary.json")

MAX_NORMS_PER_5K = 10  # matches spec guidance
MODEL_ID = "google/gemini-2.5-flash" if USE_OPENROUTER else "gemini-2.5-flash"
MODEL_TEMPERATURE = 0.15
EXAMPLES_FILE = Optional[Path] = None
SEMANTICS_FILE = Optional[Path] = None
INPUT_FILE: Optional[Path] = None
TEACH_FILE: Optional[Path] = None


def makeRun(
    RUN_ID: str,
    MODEL_ID: str,
    MODEL_TEMPERATURE: float,
    MAX_NORMS_PER_5K: int,
    INPUT_PROMPTFILE: str,
    INPUT_GLOSSARYFILE: str,
    INPUT_EXAMPLESFILE: str,
    INPUT_SEMANTCSFILE: str,
    INPUT_TEACHFILE: str,
):
    g[PROMPT_FILE] = Path(INPUT_PROMPTFILE)
    g[OUTPUT_FILE] = Path("outputs") / f"{RUN_ID}_output.json"
    g[GLOSSARY_FILE] = Path(INPUT_GLOSSARYFILE)
    g[EXAMPLES_FILE] = Path(INPUT_EXAMPLESFILE)
    g[SEMANTICS_FILE] = Path(INPUT_SEMANTCSFILE)
    g[TEACH_FILE] = Path(INPUT_TEACHFILE)
    g[INPUT_FILE] = Path(INPUT_FILE)

PROMPT_DESCRIPTION = [PROMPT_FILE].read_text(encoding="utf-8")

# Teaching appendix injection & known field paths (if LX_TEACH_MODE=1)
TEACH_MODE = os.getenv("LX_TEACH_MODE") == "1"
APPENDIX_FILE = Path("input_promptfiles/prompt_appendix_teaching.md")
ENTITY_SEMANTICS_FILE = Path("input_promptfiles/prompt_appendix_entity_semantics.md")

def load_glossary_field_paths() -> List[str]:
    if not GLOSSARY_FILE.exists():
        return []
    try:
        data = json.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return sorted([k for k in data.keys() if isinstance(k, str)])
    except Exception:
        return []
    return []

if TEACH_MODE:
    if APPENDIX_FILE.exists():
        PROMPT_DESCRIPTION += "\n\n" + APPENDIX_FILE.read_text(encoding="utf-8")
    if ENTITY_SEMANTICS_FILE.exists():
        PROMPT_DESCRIPTION += "\n\n" + ENTITY_SEMANTICS_FILE.read_text(encoding="utf-8")
    known_paths = load_glossary_field_paths()
    if known_paths:
        # Append known field paths markers (teaching consumption) with clear delimiters
        PROMPT_DESCRIPTION += "\nKNOWN_FIELD_PATHS_START\n" + json.dumps(known_paths, ensure_ascii=False) + "\nKNOWN_FIELD_PATHS_END\n"

## LOAD EXAMPLES

if EXAMPLES_FILE.exists():
    EXAMPLES = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))

## LOAD INPUT TEXT
if INPUT_FILE.exists():
    INPUT_TEXT = INPUT_FILE.read_text(encoding="utf-8")

## VALIDATE RICH SCHEMA (+ enrichment)
## Identify Location Codes
LOCATION_CODE_FIELDS = ["ZONES", "PROVINCES", "REGIONS", "STATES", "COMMUNES", "GEO_CODES"]
SINGLE_QUOTED_LITERAL_PATTERN = re.compile(r"'([^'\\]{1,40})'")


# Inject directive to enforce atomic (bullet-level) norms
ATOMIC_DIRECTIVE = "\nSTRICT_NORM_GRANULARITY: Emit ONE norm per distinct obligation/prohibition statement (do not merge separate lettered bullets a), b), c)... nor separate numeric paragraphs).\n"
prompt_with_directive = PROMPT_DESCRIPTION + ATOMIC_DIRECTIVE

spans = chunk_text(INPUT_TEXT, max_chars=3500, overlap=300)
print(f"[INFO] Created {len(spans)} manual chunk(s) (total chars={len(INPUT_TEXT)})")
all_chunk_objs: List[Dict[str, Any]] = []
for idx, (offset, subtxt) in enumerate(spans, start=1):
    print(f"[INFO] Invoking model for chunk {idx}/{len(spans)} char_offset={offset} len={len(subtxt)} ...")
    lm_params = {"temperature": MODEL_TEMPERATURE}
    extract_kwargs = dict(
        text_or_documents=subtxt,
        prompt_description=prompt_with_directive,
        examples=EXAMPLES,
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
            "openrouter_title": os.getenv("OPENROUTER_TITLE", "LangExtract Rich Schema Runner"),
        })
    else:
        extract_kwargs.update({"api_key": GOOGLE_API_KEY})
    extract_kwargs["max_char_buffer"] = 5000
    # Perform extraction; AnnotatedDocument doesn't expose raw JSON rich schema, so read resolver_raw_output.txt
    _ = lx.extract(**extract_kwargs)
    raw_file = Path("resolver_raw_output.txt")
    if not raw_file.exists():
        print(f"[WARN] Chunk {idx} missing resolver_raw_output.txt – skipping.")
        continue
    raw_text = raw_file.read_text(encoding="utf-8").strip()
    parsed: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(raw_text)
    except Exception:
        # Attempt salvage if noise present
        try:
            if 'salvage_first_json' in globals():
                parsed = salvage_first_json(raw_text)  # type: ignore
        except Exception:
            parsed = None
    if not (isinstance(parsed, dict) and isinstance(parsed.get("extractions"), list)):
        snippet = raw_text[:160].replace('\n',' ')
        print(f"[WARN] Chunk {idx} not rich schema (snippet='{snippet}'); skipping.")
        continue
    for obj in parsed.get("extractions", []):
        if not is_rich_schema(obj):
            continue
        # Adjust source span offsets & normalize statement_text
        for norm in obj.get("norms", []):
            if isinstance(norm, dict):
                # Normalize statement_text if absent
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
            obj["window_config"] = wc
        all_chunk_objs.append(obj)

# If no chunks yielded, abort
if not all_chunk_objs:
    print("[FATAL] No chunk produced a valid rich schema object.")
    sys.exit(3)
print(f"[INFO] Parsed {len(all_chunk_objs)} rich chunk object(s); aggregating ...")
parsed_root = {"extractions": all_chunk_objs}

if parsed_root is None:
    # Secondary recovery path: the internal Resolver already writes the raw JSON
    # it successfully parsed (or attempted to) to resolver_raw_output.txt. If
    # the AnnotatedDocument string repr hides the original JSON, we can often
    # still recover the rich schema root from that file.
    resolver_raw_path = Path("resolver_raw_output.txt")
    if resolver_raw_path.exists():
        try:
            candidate_text = resolver_raw_path.read_text(encoding="utf-8")
            candidate_obj = json.loads(candidate_text)
            if isinstance(candidate_obj, dict) and isinstance(candidate_obj.get("extractions"), list):
                parsed_root = candidate_obj
                print("[INFO] Loaded rich schema JSON from resolver_raw_output.txt (fallback).")
        except Exception:
            pass

if parsed_root is None:
    # No alternate raw string variable retained after refactor; cannot salvage further.
    print("[FATAL] Model did not return parseable JSON (no rich root after chunk attempts). Failing fast.")
    sys.exit(2)

# Expect root with single key 'extractions'
if not (isinstance(parsed_root, dict) and isinstance(parsed_root.get("extractions"), list) and parsed_root["extractions"]):
    print("[FATAL] Model output is not a valid rich schema root (missing 'extractions' non-empty list). Failing.")
    sys.exit(3)

extractions_list = parsed_root["extractions"]
invalid_objects = [i for i, obj in enumerate(extractions_list) if not is_rich_schema(obj)]
if invalid_objects:
    print(f"[FATAL] One or more extraction objects missing required keys (indices: {invalid_objects}).")
    sys.exit(4)

# Aggregate if multiple chunks
primary = aggregate_extractions(extractions_list)
if len(extractions_list) > 1:
    print(f"[INFO] Aggregated {len(extractions_list)} chunk extraction objects into one unified schema.")

# Validate structure & append any errors
schema_errors = validate_rich(primary)
if schema_errors:
    primary.setdefault("quality", {}).setdefault("errors", []).extend(schema_errors)

# Ensure window_config present & updated counts if model omitted or incorrect.
wc = primary.setdefault("window_config", {})
wc.setdefault("input_chars", len(INPUT_TEXT))
wc.setdefault("max_norms_per_5k_tokens", MAX_NORMS_PER_5K)
wc["extracted_norm_count"] = len(primary.get("norms", []))

# Optional enrichment (post-validation) – only if teach mode or explicitly requested
if TEACH_MODE:
    validate_and_enhance_rich_schema(primary)

# ---------------------------------------------------------------------------
# 5. Persist Result
# ---------------------------------------------------------------------------

# Persist root as provided (may contain >1 extraction objects)
OUTPUT_FILE.write_text(json.dumps(parsed_root, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved rich schema JSON root → {OUTPUT_FILE}")

# ---------------------------------------------------------------------------
# 6. DSL Glossary Draft
# ---------------------------------------------------------------------------
dsl_keys = sorted(collect_dsl_keys(primary))
glossary = {k: "" for k in dsl_keys}
GLOSSARY_FILE.write_text(json.dumps(glossary, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved DSL glossary stub ({len(dsl_keys)} keys) → {GLOSSARY_FILE}")

# ---------------------------------------------------------------------------
# 7. Console Summary
# ---------------------------------------------------------------------------
print("=== Extraction Summary ===")
print(f"Norms: {len(primary.get('norms', []))}")
print(f"Tags: {len(primary.get('tags', []))}")
print(f"Locations: {len(primary.get('locations', []))}")
print(f"Questions: {len(primary.get('questions', []))}")
print(f"Consequences: {len(primary.get('consequences', []))}")
print(f"Parameters: {len(primary.get('parameters', []))}")
print(f"Errors: {primary.get('quality', {}).get('errors', [])}")
print(f"Warnings: {primary.get('quality', {}).get('warnings', [])}")

print("Done.")