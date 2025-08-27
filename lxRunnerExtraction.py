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
from xml.parsers.expat import model
import ast
import re

from dotenv import load_dotenv
import langextract as lx
from langextract import factory
from langextract import providers
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

    # Ensure provider registry is populated (mirrors simpleExtraction pattern)
    providers.load_builtins_once()
    providers.load_plugins_once()
    try:
        avail = providers.list_providers()
        print(f"[DEBUG] Providers available: {sorted(list(avail.keys()))}")
    except Exception:
        pass

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
    run_dir = Path("output_runs") / RUN_ID
    chunks_dir = run_dir / "chunks"
    run_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE = run_dir / "output.json"
    # Default glossary path to run_dir when not provided
    GLOSSARY_FILE = Path(INPUT_GLOSSARYFILE) if INPUT_GLOSSARYFILE else (run_dir / "glossary.json")

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
        _run_folder = run_dir / "input"
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


    # Explicitly route to OpenAI-compatible provider via OpenRouter
    cfg = factory.ModelConfig(
        model_id=MODEL_ID,
        provider="OpenAILanguageModel",  # Explicit provider class to route via OpenRouter's OpenAI-compatible API
        provider_kwargs={
            "api_key": OPENROUTER_KEY,
            "base_url": "https://openrouter.ai/api/v1",
            "temperature": MODEL_TEMPERATURE,
            # Prefer strict JSON mode
            "format_type": lx.data.FormatType.JSON,
            "max_workers": 20,
        },
    )

    # Define Extraction Args
    extract_kwargs = dict(
        text_or_documents=INPUT_TEXT,
        prompt_description=PROMPT_DESCRIPTION,
        examples=EXAMPLES,
        config=cfg,
        fence_output=False,
        use_schema_constraints=True,
        max_char_buffer=5000,
        resolver_params={
                "fence_output": False,
                "format_type": lx.data.FormatType.JSON,
                "suppress_parse_errors_default": True,
        },
    )

    if USE_OPENROUTER:
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

    print(f"[INFO] Using {'OpenRouter' if USE_OPENROUTER else 'Direct Gemini'} provider with model_id={MODEL_ID}")

    all_extractions: List[Dict[str, Any]] = []
    run_warnings: List[str] = []

    def _synthesize_extraction(text: str, norms: List[Dict[str, Any]] | None = None, errors: List[str] | None = None, warnings: List[str] | None = None) -> Dict[str, Any]:
        nn = norms or []
        return {
            "schema_version": "1.0.0",
            "ontology_version": "0.0.1",
            "truncated": False,
            "has_more": False,
            "window_config": {
                "input_chars": len(text),
                "max_norms_per_5k_tokens": MAX_NORMS_PER_5K,
                "extracted_norm_count": len(nn),
            },
            "global_disclaimer": "NO LEGAL ADVICE",
            "document_metadata": {
                "doc_id": str(INPUT_FILE.name if INPUT_FILE else "unknown"),
                "doc_title": "",
                "source_language": "es",
                "received_chunk_span": {"char_start": 0, "char_end": len(text)},
                "page_range": {"start": -1, "end": -1},
                "topics": [],
                "location_scope": {"COUNTRY": "", "STATES": [], "PROVINCES": [], "REGIONS": [], "COMMUNES": [], "ZONES": [], "GEO_CODES": [], "UNCERTAINTY": 0.5},
            },
            "norms": nn,
            "tags": [],
            "locations": [],
            "questions": [],
            "consequences": [],
            "parameters": [],
            "quality": {"errors": errors or [], "warnings": warnings or [], "confidence_global": 0.5, "uncertainty_global": 0.5},
        }

    def _call_and_capture(text: str, idx: int | None = None) -> Optional[Dict[str, Any]]:
        nonlocal run_warnings
        
        def _sanitize_for_log(raw: str, limit: int = 2000) -> str:
            try:
                s = str(raw)
            except Exception:
                s = "<unprintable>"
            # Redact obvious secrets
            try:
                if OPENROUTER_KEY:
                    s = s.replace(OPENROUTER_KEY, "[REDACTED]")
            except Exception:
                pass
            # Redact common api_key patterns
            try:
                s = re.sub(r"(api_key\s*[=:]\s*)([A-Za-z0-9_\-\.]+)", r"\1[REDACTED]", s, flags=re.IGNORECASE)
                s = re.sub(r"(Authorization:\s*Bearer\s+)([A-Za-z0-9_\-\.]+)", r"\1[REDACTED]", s, flags=re.IGNORECASE)
            except Exception:
                pass
            if len(s) > limit:
                s = s[:limit] + " ... [truncated]"
            return s
        # Let the library handle internal chunking via extract_kwargs["max_char_buffer"]
        # (Do not override max_char_buffer here so internal chunking can occur.)
        extract_kwargs["text_or_documents"] = text
        try:
            annotated = lx.extract(**extract_kwargs)  # returns AnnotatedDocument
        except Exception as e:
            safe_err = _sanitize_for_log(e)
            msg = f"[WARN] Extract failed for chunk {idx if idx is not None else 'single'}: {safe_err}"
            print(msg, file=sys.stderr)
            run_warnings.append(msg)
            # Synthesize a minimal valid rich object so the run completes
            synthesized = _synthesize_extraction(text, norms=[], errors=[safe_err], warnings=run_warnings)
            result = {"extractions": [synthesized]}
            raw_name = f"chunk_{idx:03}.json" if idx is not None else "chunk_single.json"
            try:
                (chunks_dir / raw_name).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            return result

        # Build a rich-schema shaped JSON from legacy extractions (classed)
        legacy_extractions = list(getattr(annotated, "extractions", []) or [])

        def _parse_literal(val: Any) -> Any:
            if isinstance(val, (dict, list, int, float, bool)) or val is None:
                return val
            if not isinstance(val, str):
                return None
            s = val.strip()
            # Try JSON first
            try:
                return json.loads(s)
            except Exception:
                pass
            # Fall back to Python literal (single quotes etc.)
            try:
                return ast.literal_eval(s)
            except Exception:
                return None

        meta: Dict[str, Any] = {
            "schema_version": "1.0.0",
            "ontology_version": "0.0.1",
            "truncated": False,
            "has_more": False,
            "window_config": {
                "input_chars": len(text),
                "max_norms_per_5k_tokens": MAX_NORMS_PER_5K,
                "extracted_norm_count": 0,
            },
            "global_disclaimer": "NO LEGAL ADVICE",
            "document_metadata": {
                "doc_id": str(INPUT_FILE.name if INPUT_FILE else "unknown"),
                "doc_title": "",
                "source_language": "es",
                "received_chunk_span": {"char_start": 0, "char_end": len(text)},
                "page_range": {"start": -1, "end": -1},
                "topics": [],
                "location_scope": {"COUNTRY": "", "STATES": [], "PROVINCES": [], "REGIONS": [], "COMMUNES": [], "ZONES": [], "GEO_CODES": [], "UNCERTAINTY": 0.5},
            },
            "quality": {"errors": [], "warnings": [], "confidence_global": 0.5, "uncertainty_global": 0.5},
        }
        norms: List[Dict[str, Any]] = []
        tags: List[Dict[str, Any]] = []
        locations: List[Dict[str, Any]] = []
        questions: List[Dict[str, Any]] = []
        consequences: List[Dict[str, Any]] = []
        parameters: List[Dict[str, Any]] = []

        for e in legacy_extractions:
            cls = getattr(e, "extraction_class", None)
            txt = getattr(e, "extraction_text", None)
            parsed = _parse_literal(txt)
            if cls == "schema_version" and isinstance(parsed, str):
                meta["schema_version"] = parsed
            elif cls == "ontology_version" and isinstance(parsed, str):
                meta["ontology_version"] = parsed
            elif cls == "truncated" and isinstance(parsed, (bool, str)):
                meta["truncated"] = bool(parsed) if not isinstance(parsed, bool) else parsed
            elif cls == "has_more" and isinstance(parsed, (bool, str)):
                meta["has_more"] = bool(parsed) if not isinstance(parsed, bool) else parsed
            elif cls == "window_config" and isinstance(parsed, dict):
                meta["window_config"].update(parsed)
            elif cls == "global_disclaimer" and isinstance(parsed, str):
                meta["global_disclaimer"] = parsed
            elif cls == "document_metadata" and isinstance(parsed, dict):
                meta["document_metadata"].update(parsed)
            elif cls == "quality" and isinstance(parsed, dict):
                meta["quality"].update(parsed)
            elif cls == "norms" and isinstance(parsed, list):
                norms = parsed
            elif cls == "tags" and isinstance(parsed, list):
                tags = parsed
            elif cls == "locations" and isinstance(parsed, list):
                locations = parsed
            elif cls == "questions" and isinstance(parsed, list):
                questions = parsed
            elif cls == "consequences" and isinstance(parsed, list):
                consequences = parsed
            elif cls == "parameters" and isinstance(parsed, list):
                parameters = parsed

        meta["window_config"]["extracted_norm_count"] = len(norms)
        synthesized: Dict[str, Any] = {
            **{k: meta[k] for k in ("schema_version","ontology_version","truncated","has_more","window_config","global_disclaimer","document_metadata")},
            "norms": norms,
            "tags": tags,
            "locations": locations,
            "questions": questions,
            "consequences": consequences,
            "parameters": parameters,
            "quality": meta["quality"],
        }

        result = {"extractions": [synthesized]}

        # Persist the raw output per chunk for traceability
        raw_name = f"chunk_{idx:03}.json" if idx is not None else "chunk_single.json"
        try:
            (chunks_dir / raw_name).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        # Optional: generate a visualization of the annotated document.
        # Guarded by LX_WRITE_VIS=1 to avoid side effects in CI/headless runs.
        # Note: visualize expects an AnnotatedDocument, not the synthesized dict result.
        if os.getenv("LX_WRITE_VIS", "0") == "1":
            try:
                html_content = lx.visualize(annotated)
                vis_path = run_dir / ("visualization.html" if idx is None else f"visualization_{idx:03}.html")
                with open(vis_path, "w", encoding="utf-8") as f:
                    if hasattr(html_content, "data"):
                        f.write(html_content.data)  # For Jupyter/Colab objects
                    else:
                        f.write(str(html_content))
                print(f"[INFO] Saved visualization → {vis_path}")
            except Exception as ve:
                print(f"[WARN] Visualization failed: {ve}", file=sys.stderr)


        return result
 
    

    print("[INFO] Library-managed chunking enabled (max_char_buffer governs internal splits)")
    pr = _call_and_capture(INPUT_TEXT, None)
    if pr and isinstance(pr.get("extractions"), list):
        all_extractions.extend(pr["extractions"])

    # If nothing was extracted, synthesize a single empty object so run can complete
    if not all_extractions:
        err = "No valid extractions produced across all chunks."
        print(f"[WARN] {err}", file=sys.stderr)
        synthesized = _synthesize_extraction(INPUT_TEXT, norms=[], errors=[err] + run_warnings, warnings=run_warnings)
        all_extractions.append(synthesized)

    parsed_root: Dict[str, Any] = {"extractions": all_extractions}

    # Expect root with single key 'extractions'
    if not (isinstance(parsed_root, dict) and isinstance(parsed_root.get("extractions"), list) and parsed_root["extractions"]):
        print("[WARN] Model output missing 'extractions' non-empty list; synthesizing fallback.")
        parsed_root = {"extractions": [_synthesize_extraction(INPUT_TEXT, norms=[], errors=["Invalid root structure"], warnings=run_warnings)]}

    extractions_list = parsed_root["extractions"]
    invalid_objects = [i for i, obj in enumerate(extractions_list) if not pp_schema.is_rich_schema(obj)]
    if invalid_objects:
        print(f"[WARN] One or more extraction objects missing required keys (indices: {invalid_objects}). Will annotate errors and continue.")
        # Replace invalid objects with synthesized shells preserving index order
        for i in invalid_objects:
            parsed_root["extractions"][i] = _synthesize_extraction(INPUT_TEXT, norms=[], errors=["Missing required keys"], warnings=run_warnings)

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
