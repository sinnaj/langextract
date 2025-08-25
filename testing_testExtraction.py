"""
Test harness for extraction pipeline using a static raw model output file instead of querying the LLM.

This script loads the model output from 'raw_model_output.txt', parses it, and runs the same normalization, validation, and enrichment pipeline as 'testExtraction_3.py'.
"""
import json
from pathlib import Path
from typing import Any, Dict

from apply_enrichment_pipeline import apply_enrichment_pipeline
from collect_dsl_keys import collect_dsl_keys
from is_rich_schema import is_rich_schema
from validate_rich import validate_rich

RAW_OUTPUT_FILE = Path("raw_model_output.txt")
OUTPUT_FILE = Path("rich_norms_full.json")
GLOSSARY_FILE = Path("dsl_glossary.json")

# Import helpers from main extraction script
from testExtraction_3 import (
    legacy_wrap,
    TEACH_MODE,
    MAX_NORMS_PER_5K,
)

# Load raw model output
raw_text = RAW_OUTPUT_FILE.read_text(encoding="utf-8")
parsed: Dict[str, Any] | None = None
if raw_text.strip():
    try:
        parsed = json.loads(raw_text)
    except Exception as e:
        print(f"[ERROR] Could not parse raw model output: {e}")
        parsed = None

if parsed is None:
    raise RuntimeError("No valid JSON could be loaded from raw_model_output.txt")

# Use same logic as testExtraction_3.py for schema detection and fallback
def convert_flat_extractions_to_rich_schema(flat_extractions):
    # Build empty rich schema skeleton
    rich = {
        "schema_version": "1.0.0",
        "ontology_version": "0.0.1",
        "truncated": False,
        "has_more": False,
        "window_config": {
            "input_chars": 0,
            "max_norms_per_5k_tokens": MAX_NORMS_PER_5K,
            "extracted_norm_count": 0
        },
        "global_disclaimer": "NO LEGAL ADVICE",
        "document_metadata": {},
        "norms": [],
        "tags": [],
        "locations": [],
        "questions": [],
        "consequences": [],
        "parameters": [],
        "quality": {"errors": [], "warnings": []}
    }
    # Map extraction_class to rich schema arrays
    class_map = {
        "Norm": "norms",
        "Tag": "tags",
        "Location": "locations",
        "Question": "questions",
        "Consequence": "consequences",
        "Parameter": "parameters"
    }
    for item in flat_extractions:
        cls = item.get("extraction_class")
        arr = class_map.get(cls)
        if arr:
            # Use attributes if present, else fallback to extraction_text
            obj = item.get("attributes") or {}
            if isinstance(obj, dict):
                obj = obj.copy()
            else:
                obj = {}
            # Always add extraction_text for traceability
            obj.setdefault("extraction_text", item.get("extraction_text"))
            # Optionally add char_interval, alignment_status, etc. for debugging
            for k in ("char_interval", "alignment_status", "extraction_index", "group_index", "description"):
                if k in item:
                    obj[k] = item[k]
            rich[arr].append(obj)
    # Fill in counts
    rich["window_config"]["extracted_norm_count"] = len(rich["norms"])
    return rich

if not is_rich_schema(parsed):
    if isinstance(parsed, dict) and "extractions" in parsed and isinstance(parsed["extractions"], list) and parsed["extractions"]:
        parsed = parsed["extractions"][0]
        print("[INFO] Model output in 'extractions' array format – using first extraction as rich schema.")
    elif isinstance(parsed, list) and all(isinstance(x, dict) and "extraction_class" in x for x in parsed):
        print("[INFO] Detected flat extraction list – converting to rich schema.")
        parsed = convert_flat_extractions_to_rich_schema(parsed)
    elif isinstance(parsed, dict) and "extraction_class" in parsed:
        print("[INFO] Detected single flat extraction – converting to rich schema.")
        parsed = convert_flat_extractions_to_rich_schema([parsed])
    else:
        print("[WARN] Model did not emit full rich schema – applying legacy wrapper.")
        parsed = legacy_wrap(parsed)

# Validate structure & append any errors
schema_errors = validate_rich(parsed)
if schema_errors:
    parsed.setdefault("quality", {}).setdefault("errors", []).extend(schema_errors)

# Ensure window_config present & updated counts if model omitted or incorrect.
wc = parsed.setdefault("window_config", {})
wc.setdefault("input_chars", 0)
wc.setdefault("max_norms_per_5k_tokens", MAX_NORMS_PER_5K)
wc["extracted_norm_count"] = len(parsed.get("norms", []))

# Optional enrichment (post-validation)
if TEACH_MODE:
    apply_enrichment_pipeline(parsed)

# Persist result (wrap in 'extractions' array)
wrapped_output = {"extractions": [parsed]}
OUTPUT_FILE.write_text(json.dumps(wrapped_output, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved rich schema JSON (wrapped in 'extractions') → {OUTPUT_FILE}")

dsl_keys = sorted(collect_dsl_keys(parsed))
glossary = {k: "" for k in dsl_keys}
GLOSSARY_FILE.write_text(json.dumps(glossary, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved DSL glossary stub ({len(dsl_keys)} keys) → {GLOSSARY_FILE}")
