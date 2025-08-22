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
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from datetime import datetime

from dotenv import load_dotenv
import langextract as lx
from postprocessing.is_rich_schema import (
    is_rich_schema,
    validate_rich,
    validate_rich_verbose,
    collect_dsl_keys
)
from postprocessing.enrich_parameters import enrich_parameters

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
def validate_rich_schema():
    try:
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        primary, ok, _errs = validate_rich_verbose(data, print_fn=lambda m: print(m))
        if primary is not None:
            # Apply enrichment/repairs and persist if anything changed materially
            before_params = len(primary.get("parameters", []) or [])
            enrich_parameters(primary)
            merge_duplicate_tags(primary)
            autophrase_questions(primary)
            ensure_consequence_ids(primary)
            compute_extended_metrics(primary)
            after_params = len(primary.get("parameters", []) or [])
            # If wrapped, reassign back into data
            if isinstance(data, dict) and isinstance(data.get("extractions"), list) and data["extractions"]:
                data["extractions"][0] = primary
            else:
                data = primary
            if after_params > before_params:
                OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[INFO] Wrote enriched output to {OUTPUT_FILE} (parameters: {before_params} -> {after_params})")
    except Exception as e:
        print(f"[WARN] Could not validate/enrich rich schema from {OUTPUT_FILE}: {e}", file=sys.stderr)

## RELATIONSHIP INFERENCE

LOCATION_CODE_FIELDS = ["ZONES", "PROVINCES", "REGIONS", "STATES", "COMMUNES", "GEO_CODES"]
SINGLE_QUOTED_LITERAL_PATTERN = re.compile(r"'([^'\\]{1,40})'")


def chunk_text(text: str, max_chars: int = 4000, overlap: int = 350) -> List[Tuple[int,str]]:
    """Produce (offset, substring) pairs covering full text.
    Keeps mild overlap to avoid boundary loss. Offsets are absolute char positions in original text.
    """
    spans: List[Tuple[int,str]] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(n, i + max_chars)
        spans.append((i, text[i:end]))
        if end >= n:
            break
        # step forward with overlap
        i = end - overlap
        if i < 0 or i >= n:
            break
    return spans

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

# --- Salvage logic: extract first balanced JSON object if wrapper text present ---
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

def aggregate_extractions(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple chunk extraction objects into a single unified object.

    Strategy:
      1. Concatenate arrays preserving chunk order.
      2. Re-index IDs sequentially per entity type (N/T/L/Q/C/P) to avoid collisions.
      3. Remap all reference fields to new IDs.
      4. Merge metadata: doc_id must match across chunks else fallback MULTI_CHUNK; page_range union; topics union.
      5. window_config: input_chars = sum of chunk window_config.input_chars (fallback length of INPUT_TEXT), extracted_norm_count updated, max_norms_per_5k_tokens = max across chunks.
      6. truncated / has_more true if any chunk true.
      7. quality.errors & warnings union (deduplicated, order preserved by first appearance).
    """
    if not chunks:
        return {}
    if len(chunks) == 1:
        return chunks[0]
    # Base skeleton from first chunk (shallow copy of scalar sections)
    merged: Dict[str, Any] = {k: chunks[0].get(k) for k in chunks[0].keys() if k not in {"norms","tags","locations","questions","consequences","parameters","quality","window_config","document_metadata"}}
    # Collect arrays
    merged["norms"] = [n for idx,c in enumerate(chunks) for n in c.get("norms", [])]
    merged["tags"] = [t for c in chunks for t in c.get("tags", [])]
    merged["locations"] = [l for c in chunks for l in c.get("locations", [])]
    merged["questions"] = [q for c in chunks for q in c.get("questions", [])]
    merged["consequences"] = [cns for c in chunks for cns in c.get("consequences", [])]
    merged["parameters"] = [p for c in chunks for p in c.get("parameters", [])]

    # Metadata merge
    doc_ids = {c.get("document_metadata", {}).get("doc_id") for c in chunks if c.get("document_metadata")}
    first_md = chunks[0].get("document_metadata", {})
    md: Dict[str, Any] = dict(first_md)
    if len(doc_ids) > 1:
        md["doc_id"] = "MULTI_CHUNK"
    # Page range
    starts = [c.get("document_metadata", {}).get("page_range", {}).get("start") for c in chunks if c.get("document_metadata", {}).get("page_range")]
    ends = [c.get("document_metadata", {}).get("page_range", {}).get("end") for c in chunks if c.get("document_metadata", {}).get("page_range")]
    if starts and ends:
        md.setdefault("page_range", {})
        md["page_range"]["start"] = min(s for s in starts if isinstance(s, int)) if any(isinstance(s,int) for s in starts) else -1
        md["page_range"]["end"] = max(e for e in ends if isinstance(e, int)) if any(isinstance(e,int) for e in ends) else -1
    # Topics union
    topics_union: List[str] = []
    seen_topics = set()
    for c in chunks:
        for t in c.get("document_metadata", {}).get("topics", []) or []:
            if t not in seen_topics:
                seen_topics.add(t)
                topics_union.append(t)
    if topics_union:
        md["topics"] = topics_union
    merged["document_metadata"] = md

    # window_config merge
    wc_total_chars = 0
    max_norms_setting = 0
    for c in chunks:
        cw = c.get("window_config", {}) or {}
        wc_total_chars += int(cw.get("input_chars") or 0)
        max_norms_setting = max(max_norms_setting, int(cw.get("max_norms_per_5k_tokens") or 0))
    merged_wc = {
        "input_chars": wc_total_chars or len(INPUT_TEXT),
        "max_norms_per_5k_tokens": max_norms_setting or MAX_NORMS_PER_5K,
        "extracted_norm_count": len(merged["norms"]),
    }
    merged["window_config"] = merged_wc

    # truncated / has_more
    merged["truncated"] = any(c.get("truncated") for c in chunks)
    merged["has_more"] = any(c.get("has_more") for c in chunks)

    # Quality combine
    def combine_quality(chunks):
        def norm_item(x: Any) -> str:
            if isinstance(x, (str, int, float)):
                return str(x)
            try:
                return json.dumps(x, sort_keys=True, ensure_ascii=False)
            except Exception:
                return repr(x)
        err_order: List[Any] = []
        warn_order: List[Any] = []
        err_seen: Set[str] = set(); warn_seen: Set[str] = set()
        for c in chunks:
            q = c.get("quality", {}) or {}
            for e in q.get("errors", []) or []:
                key = norm_item(e)
                if key not in err_seen:
                    err_seen.add(key); err_order.append(e)
            for w in q.get("warnings", []) or []:
                key = norm_item(w)
                if key not in warn_seen:
                    warn_seen.add(key); warn_order.append(w)
        return {"errors": err_order, "warnings": warn_order}
    merged_quality = combine_quality(chunks)
    merged_quality.setdefault("errors", [])
    merged_quality.setdefault("warnings", [])
    merged_quality["errors"].append(f"AGGREGATED_CHUNKS:{len(chunks)}")
    merged["quality"] = merged_quality

    # Re-index IDs
    id_prefixes = [
        ("norms", "N"),
        ("tags", "T"),
        ("locations", "L"),
        ("questions", "Q"),
        ("consequences", "C"),
        ("parameters", "P"),
    ]
    mapping: Dict[str, str] = {}
    for collection, prefix in id_prefixes:
        new_list = []
        counter = 1
        for obj in merged.get(collection, []):
            if not isinstance(obj, dict):
                continue
            old_id = obj.get("id")
            new_id = f"{prefix}::{counter:04d}"
            mapping[old_id] = new_id
            obj["id"] = new_id
            counter += 1
            new_list.append(obj)
        merged[collection] = new_list

    # Patch references with new IDs
    for n in merged.get("norms", []):
        for fld in ("extracted_parameters_ids", "consequence_ids"):
            ids = n.get(fld) or []
            n[fld] = [mapping.get(i, i) for i in ids]
    for t in merged.get("tags", []):
        for fld in ("introduced_by_norm_ids", "refined_by_norm_ids"):
            ids = t.get(fld) or []
            if ids:
                t[fld] = [mapping.get(i, i) for i in ids]
    for q in merged.get("questions", []):
        ids = q.get("trigger_norm_ids") or []
        if ids:
            q["trigger_norm_ids"] = [mapping.get(i, i) for i in ids]
    for cns in merged.get("consequences", []):
        for fld in ("activates_norm_ids", "activates_question_ids", "source_norm_ids"):
            ids = cns.get(fld) or []
            if ids:
                cns[fld] = [mapping.get(i, i) for i in ids]
    for p in merged.get("parameters", []):
        ids = p.get("norm_ids") or []
        if ids:
            p["norm_ids"] = [mapping.get(i, i) for i in ids]

    return merged

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
    validate_rich_schema(primary)

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