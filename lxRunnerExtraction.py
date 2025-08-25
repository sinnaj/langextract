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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import importlib.util

from dotenv import load_dotenv
import langextract as lx
from postprocessing import enrich_outputdata as pp_enrich
from postprocessing import output_schema_validation as pp_schema
from postprocessing import relationship_inference as pp_rel
from preprocessing.chunk_input import chunk_document

# ---------------------------------------------------------------------------
# 0. Environment / Config
# ---------------------------------------------------------------------------

# Explicitly export makeRun for dynamic loader usage

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
    print(f"makeRun called with RUN_ID={RUN_ID}, MODEL_ID={MODEL_ID}, MODEL_TEMPERATURE={MODEL_TEMPERATURE}, MAX_NORMS_PER_5K={MAX_NORMS_PER_5K}, INPUT_PROMPTFILE={INPUT_PROMPTFILE}, INPUT_GLOSSARYFILE={INPUT_GLOSSARYFILE}, INPUT_EXAMPLESFILE={INPUT_EXAMPLESFILE}, INPUT_SEMANTCSFILE={INPUT_SEMANTCSFILE}, INPUT_TEACHFILE={INPUT_TEACHFILE}")
    """Configure globals for this run. Values are set via globals() mapping."""

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


    PROMPT_FILE = Path(INPUT_PROMPTFILE)
    OUTPUT_FILE = Path("output_runs") / f"{RUN_ID}_output.json"
    GLOSSARY_FILE = Path(INPUT_GLOSSARYFILE) if INPUT_GLOSSARYFILE else None

    MAX_NORMS_PER_5K = 10  # matches spec guidance
    MODEL_ID = "google/gemini-2.5-flash" if USE_OPENROUTER else "gemini-2.5-flash"
    MODEL_TEMPERATURE = 0.15
    EXAMPLES_FILE = Path(INPUT_EXAMPLESFILE) if INPUT_EXAMPLESFILE else None
    SEMANTICS_FILE = Path(INPUT_SEMANTCSFILE) if INPUT_SEMANTCSFILE else None
    # Determine input file: prefer explicit override, then text-like inputs in run folder
    input_override = os.getenv("LE_INPUT_FILE")
    if input_override:
        INPUT_FILE = Path(input_override)
    else:
        _run_folder = Path("output_runs") / RUN_ID / "input"
        allowed_exts = {".txt", ".md"}
        exclude_names = {
            "raw_model_output.txt",
            "resolver_raw_output.txt",
            "stats.json",
        }
        try:
            files = [p for p in _run_folder.iterdir() if p.is_file()]
        except FileNotFoundError:
            files = []
        # Prioritize text-like files and skip known generated outputs
        preferred = [
            p for p in files
            if p.suffix.lower() in allowed_exts and p.name not in exclude_names and not p.name.endswith("_output.json")
        ]
        fallback = [
            p for p in files
            if p.name not in exclude_names and not p.name.endswith("_output.json")
        ]
        candidates = preferred or fallback
        INPUT_FILE = candidates[0] if candidates else None
    if INPUT_FILE:
        print(f"[INFO] Selected input file: {INPUT_FILE}")
    TEACH_FILE = Path(INPUT_TEACHFILE) if INPUT_TEACHFILE else None

    # Default examples module if EXAMPLES_FILE is not provided via makeRun
    DEFAULT_EXAMPLES_PATH = Path("input_examplefiles/default.py")


    if not PROMPT_FILE.exists():
        print(f"FATAL: Prompt file missing at {PROMPT_FILE}", file=sys.stderr)
        sys.exit(1)

    if not INPUT_FILE or not INPUT_FILE.exists():
        print(f"FATAL: Input file missing at {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    # Base prompt
    PROMPT_DESCRIPTION = PROMPT_FILE.read_text(encoding="utf-8")

    # Teaching appendix injection & known field paths (if LX_TEACH_MODE=1)
    TEACH_MODE = os.getenv("LX_TEACH_MODE") == "1"
    APPENDIX_FILE = Path("prompts/prompt_appendix_teaching.md")
    ENTITY_SEMANTICS_FILE = Path("prompts/prompt_appendix_entity_semantics.md")

    def load_glossary_field_paths() -> List[str]:
        if GLOSSARY_FILE is None or not GLOSSARY_FILE.exists():
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


    # ---------------------------------------------------------------------------
    # 1. Few-Shot Examples
    # ---------------------------------------------------------------------------
    """
    Multi-entity examples demonstrating Norms, Tags, Parameters, Locations, Questions,
    and Consequences are loaded from EXAMPLES_FILE if provided (Python module exporting
    EXAMPLES), otherwise from input_examplefiles/default.py.
    """

    def _load_examples_from_py(py_path: Path) -> List[Any]:
        if not py_path or not py_path.exists():
            print(f"[WARN] Examples file not found at {py_path}. Using empty examples.", file=sys.stderr)
            return []
        try:
            spec = importlib.util.spec_from_file_location("lx_examples", str(py_path))
            if not spec or not spec.loader:
                print(f"[WARN] Could not create module spec for examples at {py_path}", file=sys.stderr)
                return []
            module = importlib.util.module_from_spec(spec)
            # type: ignore[attr-defined]
            spec.loader.exec_module(module)  # pyright: ignore[reportAttributeAccessIssue]
            ex = getattr(module, "EXAMPLES", None)
            if isinstance(ex, list):
                return ex
            print(f"[WARN] No list named EXAMPLES found in {py_path}.", file=sys.stderr)
            return []
        except Exception as e:
            print(f"[WARN] Failed to load EXAMPLES from {py_path}: {e}", file=sys.stderr)
            return []

    _examples_path = EXAMPLES_FILE or DEFAULT_EXAMPLES_PATH
    EXAMPLES: List[Any] = _load_examples_from_py(_examples_path)
    print(f"[INFO] Loaded {len(EXAMPLES)} few-shot examples from {_examples_path}")


    # ---------------------------------------------------------------------------
    # 2. Sample Input Text (multi-concept to test breadth)
    # ---------------------------------------------------------------------------
    if not INPUT_FILE or not INPUT_FILE.exists():
        print(f"[WARN] Input file not found at {INPUT_FILE}. Using empty input.", file=sys.stderr)
        INPUT_TEXT = ""
    else:
        INPUT_TEXT = INPUT_FILE.read_text(encoding="utf-8")



    # ---------------------------------------------------------------------------
    # 3. Enrich Output
    # ---------------------------------------------------------------------------



    def apply_enrichment_pipeline(obj: Dict[str, Any]):
        pp_enrich.enrich_parameters(obj)
        pp_enrich.merge_duplicate_tags(obj)
        pp_rel.autophrase_questions(obj)
        if TEACH_MODE:
            pp_rel.infer_relationships(obj)



    ## Infer Relationships refactored to individual file

    # ---------------------------------------------------------------------------
    # 4. Execute Extraction
    # ---------------------------------------------------------------------------
    print("[INFO] Invoking model for rich extraction ...")

    lm_params = {
        "temperature": MODEL_TEMPERATURE,
    }

    extract_kwargs = dict(
        text_or_documents=INPUT_TEXT,
        prompt_description=PROMPT_DESCRIPTION,
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
        # OpenRouter (OpenAI-compatible) path.
        # NOTE: Only pass arguments accepted by extract(); provider-specific values must go inside
        # language_model_params so they propagate to provider_kwargs. Top-level unsupported kwargs
        # like base_url would raise TypeError (as observed).
        extract_kwargs["api_key"] = OPENROUTER_KEY
        lm_extra = extract_kwargs.setdefault("language_model_params", {})
        lm_extra.update({
            "base_url": "https://openrouter.ai/api/v1",  # forwarded to OpenAI-compatible client
            # Optional attribution headers (OpenRouter specific)
            "openrouter_referer": os.getenv("OPENROUTER_REFERER"),
            "openrouter_title": os.getenv("OPENROUTER_TITLE", "LangExtract Rich Schema Runner"),
        })
    else:
        # Direct Gemini path
        extract_kwargs.update({
            "api_key": GOOGLE_API_KEY,
        })

    extract_kwargs["max_char_buffer"] = 5000

    print(f"[INFO] Using {'OpenRouter' if USE_OPENROUTER else 'Direct Gemini'} provider with model_id={MODEL_ID}")

    words = INPUT_TEXT.split()
    if len(words) > 5000:
        chunks = chunk_document(INPUT_TEXT)
        for chunk in chunks:
            print(f"[INFO] Processing chunk (length: {len(chunk.split())} words)")
            extract_kwargs["text_or_documents"] = chunk
            result = lx.extract(**extract_kwargs)
    else:
        print(f"[INFO] Processing single chunk (length: {len(words)} words)")
        result = lx.extract(**extract_kwargs)

    # Try to access raw JSON directly (model MUST produce rich schema root object with 'extractions').
    raw_candidate = getattr(result, "raw_response", None)

    # --- Save the string that will actually be parsed ---
    RAW_OUTPUT_FILE = Path("raw_model_output.txt")
    to_parse = None
    if isinstance(raw_candidate, str) and raw_candidate.strip():
        to_parse = raw_candidate
    elif hasattr(result, 'content') and isinstance(result.content, str):
        to_parse = result.content
    elif isinstance(result, str):
        to_parse = result
    else:
        to_parse = str(result)
    RAW_OUTPUT_FILE.write_text(to_parse or '', encoding="utf-8")

    parsed_root: Dict[str, Any] | None = None
    if to_parse:
        try:
            parsed_root = json.loads(to_parse)
        except Exception:
            parsed_root = None

    ##I BELIEVE THIS WAS A HELPER TO DEAL WITH UNEXPECTED JSON STRUCTURE.
    ### COMMENTED OUT FOR TESTING

    # --- Salvage logic: extract first balanced JSON object if wrapper text present ---
    def salvage_first_json(text: str) -> Optional[Dict[str, Any]]:
    #     """Attempt to locate the first balanced JSON object within an arbitrary wrapper string.

    #     Strategy:
    #       1. Find first '{'.
    #       2. Incrementally scan, tracking nesting depth; when depth returns to 0, slice candidate.
    #       3. Attempt json.loads on slice; if fails, progressively extend forward searching for next '}' occurrences.
    #       4. If object loads and has 'extractions' key (rich schema root) OR is an object whose key 'extractions' appears nested at top-level, return it.
    #     This intentionally refuses arrays at root to maintain strict contract. Returns None if no valid object found.
    #     """
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
        salvaged = salvage_first_json(to_parse or '')
        if salvaged is not None:
            print("[INFO] Salvaged embedded JSON object from wrapper text.")
            parsed_root = salvaged
        else:
            snippet = (to_parse or '')[:200].replace('\n', ' ') if to_parse else ''
            print(f"[FATAL] Model did not return parseable JSON (first200='{snippet}'). Failing fast (legacy output no longer accepted).")
            sys.exit(2)

    # Expect root with single key 'extractions'
    if not (isinstance(parsed_root, dict) and isinstance(parsed_root.get("extractions"), list) and parsed_root["extractions"]):
        print("[FATAL] Model output is not a valid rich schema root (missing 'extractions' non-empty list). Failing.")
        sys.exit(3)

    extractions_list = parsed_root["extractions"]
    invalid_objects = [i for i, obj in enumerate(extractions_list) if not pp_schema.is_rich_schema(obj)]
    if invalid_objects:
        print(f"[FATAL] One or more extraction objects missing required keys (indices: {invalid_objects}).")
        sys.exit(4)

    # For downstream enrichment/summary we operate on first extraction object (could be extended to iterate)
    primary = extractions_list[0]

    # Validate structure & append any errors
    schema_errors = pp_schema.validate_rich(primary)
    if schema_errors:
        primary.setdefault("quality", {}).setdefault("errors", []).extend(schema_errors)

    # Ensure window_config present & updated counts if model omitted or incorrect.
    wc = primary.setdefault("window_config", {})
    wc.setdefault("input_chars", len(INPUT_TEXT))
    wc.setdefault("max_norms_per_5k_tokens", MAX_NORMS_PER_5K)
    wc["extracted_norm_count"] = len(primary.get("norms", []))

    # Optional enrichment (post-validation) – only if teach mode or explicitly requested
    if TEACH_MODE:
        apply_enrichment_pipeline(primary)

    # ---------------------------------------------------------------------------
    # 5. Persist Result
    # ---------------------------------------------------------------------------

    # Persist root as provided (may contain >1 extraction objects)
    OUTPUT_FILE.write_text(json.dumps(parsed_root, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] Saved rich schema JSON root → {OUTPUT_FILE}")

    # ---------------------------------------------------------------------------
    # 6. DSL Glossary Draft
    # ---------------------------------------------------------------------------
    dsl_keys = sorted(pp_enrich.collect_dsl_keys(primary))
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
