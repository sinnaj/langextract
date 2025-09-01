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
    MAX_CHAR_BUFFER: int,
    EXTRACTION_PASSES: int,
    INPUT_PROMPTFILE: str,
    INPUT_GLOSSARYFILE: str,
    INPUT_EXAMPLESFILE: str,
    INPUT_SEMANTCSFILE: str,
    INPUT_TEACHFILE: str,
):
    print(f"makeRun called with RUN_ID={RUN_ID}, MODEL_ID={MODEL_ID}, MODEL_TEMPERATURE={MODEL_TEMPERATURE}, MAX_NORMS_PER_5K={MAX_NORMS_PER_5K}, MAX_CHAR_BUFFER={MAX_CHAR_BUFFER}, EXTRACTION_PASSES={EXTRACTION_PASSES}, INPUT_PROMPTFILE={INPUT_PROMPTFILE}, INPUT_GLOSSARYFILE={INPUT_GLOSSARYFILE}, INPUT_EXAMPLESFILE={INPUT_EXAMPLESFILE}, INPUT_SEMANTCSFILE={INPUT_SEMANTCSFILE}, INPUT_TEACHFILE={INPUT_TEACHFILE}")
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
    # New: folder to persist raw annotated outputs before any processing/enrichment
    lx_output_dir = run_dir / "lx output"
    run_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    lx_output_dir.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE = run_dir / "output.json"
    # Default glossary path to run_dir when not provided
    GLOSSARY_FILE = Path(INPUT_GLOSSARYFILE) if INPUT_GLOSSARYFILE else (run_dir / "glossary.json")

    # Honor the provided cap; do not override. Fallback default remains 10 if an invalid value is passed.
    try:
        MAX_NORMS_PER_5K = int(MAX_NORMS_PER_5K)
    except Exception:
        MAX_NORMS_PER_5K = 10
    try:
        MAX_CHAR_BUFFER = int(MAX_CHAR_BUFFER) if MAX_CHAR_BUFFER is not None else 5000
    except Exception:
        MAX_CHAR_BUFFER = 5000
    try:
        EXTRACTION_PASSES = int(EXTRACTION_PASSES) if EXTRACTION_PASSES is not None else 2
    except Exception:
        EXTRACTION_PASSES = 1
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
        try:
            files = [p for p in _run_folder.iterdir() if p.is_file()]
        except FileNotFoundError:
            files = []
        # Prioritize text-like files and skip known generated outputs
        preferred = [
            p for p in files
            if p.suffix.lower() in allowed_exts and not p.name.endswith("_output.json")
        ]
        fallback = [
            p for p in files
            if not p.name.endswith("_output.json")
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
        use_schema_constraints=False,
        max_char_buffer=MAX_CHAR_BUFFER,
        extraction_passes=EXTRACTION_PASSES,   # Improves recall through multiple passes
        resolver_params={
                "fence_output": False,
                "format_type": lx.data.FormatType.JSON,
                ## "suppress_parse_errors_default": True,
                # Disabled alignment allowlist: only align extraction_text for these classes
                ##"align_only_classes_default": ["Norm", "Tag", "Parameter"],
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
                "max_char_buffer": MAX_CHAR_BUFFER,
                "extraction_passes": EXTRACTION_PASSES,
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

        # Persist the annotated document outputs BEFORE any processing/enrichment
        try:
            def _ci_dict(ci):
                if not ci:
                    return None
                # CharInterval has start_pos/end_pos
                return {
                    "start_pos": getattr(ci, "start_pos", None),
                    "end_pos": getattr(ci, "end_pos", None),
                }

            def _ti_dict(ti):
                if not ti:
                    return None
                # TokenInterval has start_index/end_index
                return {
                    "start_index": getattr(ti, "start_index", None),
                    "end_index": getattr(ti, "end_index", None),
                }

            raw_items = []
            for e in (getattr(annotated, "extractions", []) or []):
                item = {
                    "extraction_class": getattr(e, "extraction_class", None),
                    "extraction_text": getattr(e, "extraction_text", None),
                    "attributes": getattr(e, "attributes", None),
                    "char_interval": _ci_dict(getattr(e, "char_interval", None)),
                    "alignment_status": getattr(getattr(e, "alignment_status", None), "value", None),
                    "extraction_index": getattr(e, "extraction_index", None),
                    "group_index": getattr(e, "group_index", None),
                    "description": getattr(e, "description", None),
                    "token_interval": _ti_dict(getattr(e, "token_interval", None)),
                }
                raw_items.append(item)

            raw_legacy = {
                "document_id": getattr(annotated, "document_id", None),
                "extractions": raw_items,
            }
            raw_name = f"annotated_extractions_{idx:03}.json" if idx is not None else "annotated_extractions_single.json"
            (lx_output_dir / raw_name).write_text(
                json.dumps(raw_legacy, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as pe:
            print(f"[WARN] Failed to persist raw annotated outputs: {pe}", file=sys.stderr)

        # Build a rich-schema shaped JSON from legacy extractions (classed)
        legacy_extractions = list(getattr(annotated, "extractions", []) or [])
        print(f"[DEBUG] Legacy extractions returned: {len(legacy_extractions)}")

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
                "max_char_buffer": MAX_CHAR_BUFFER,
                "extraction_passes": EXTRACTION_PASSES,
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
        # Accumulators with content-based de-duplication (more robust than raw id-based)
        norms: List[Dict[str, Any]] = []
        _norm_sigs: set[tuple] = set()
        _norm_raw_count = 0

        tags: List[Dict[str, Any]] = []
        _tag_sigs: set[tuple] = set()
        _tag_raw_count = 0

        locations: List[Dict[str, Any]] = []
        _loc_sigs: set[tuple] = set()
        _loc_raw_count = 0

        questions: List[Dict[str, Any]] = []
        _q_sigs: set[tuple] = set()
        _q_raw_count = 0

        consequences: List[Dict[str, Any]] = []
        _cons_sigs: set[tuple] = set()
        _cons_raw_count = 0

        parameters: List[Dict[str, Any]] = []
        _param_sigs: set[tuple] = set()
        _param_raw_count = 0

        def _as_str(x: Any) -> str:
            try:
                if isinstance(x, (dict, list)):
                    return json.dumps(x, sort_keys=True, ensure_ascii=False)
                return str(x) if x is not None else ""
            except Exception:
                return str(x)

        def _norm_signature(item: Dict[str, Any]) -> tuple:
            # Focus on semantic core to avoid duplicate drops due to id reuse across chunks/passes
            stmt = _as_str(item.get("statement_text", "")).strip().lower()
            applies = _as_str(item.get("applies_if", "")).strip().lower()
            satisfied = _as_str(item.get("satisfied_if", "")).strip().lower()
            exempt = _as_str(item.get("exempt_if", "")).strip().lower()
            obl = _as_str(item.get("obligation_type", "")).strip().upper()
            # tags in any order shouldn't change identity
            rtags = item.get("relevant_tags", [])
            if isinstance(rtags, list):
                try:
                    rtags = sorted([_as_str(t).strip().lower() for t in rtags])
                except Exception:
                    rtags = []
            else:
                rtags = []
            return (stmt, applies, satisfied, exempt, obl, tuple(rtags))

        def _tag_signature(item: Dict[str, Any]) -> tuple:
            path = _as_str(item.get("tag_path", "")).strip().lower()
            parent = _as_str(item.get("parent", "")).strip().lower()
            return (path, parent)

        def _location_signature(item: Dict[str, Any]) -> tuple:
            # Use structured fields when present, else full JSON
            scope = item.get("location_scope")
            if isinstance(scope, dict):
                return ("scope", _as_str(scope))
            return ("raw", _as_str(item))

        def _question_signature(item: Dict[str, Any]) -> tuple:
            txt = _as_str(item.get("question_text", "")).strip().lower()
            tagp = _as_str(item.get("tag_path", "")).strip().lower()
            at = _as_str(item.get("answer_type", "")).strip().upper()
            outs = item.get("outputs", [])
            outs_norm = tuple(sorted([_as_str(o).strip().lower() for o in outs])) if isinstance(outs, list) else tuple()
            return (txt, tagp, at, outs_norm)

        def _consequence_signature(item: Dict[str, Any]) -> tuple:
            # Generic fallback
            return ("cons", _as_str(item))

        def _parameter_signature(item: Dict[str, Any]) -> tuple:
            # Try name + path style identity; fallback to full JSON
            name = _as_str(item.get("name", "")).strip().lower()
            pth = _as_str(item.get("parameter_path", item.get("tag_path", ""))).strip().lower()
            unit = _as_str(item.get("unit", "")).strip().lower()
            if name or pth or unit:
                return (name, pth, unit)
            return ("param", _as_str(item))

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
                for item in parsed:
                    if isinstance(item, dict):
                        _norm_raw_count += 1
                        sig = _norm_signature(item)
                        if sig in _norm_sigs:
                            continue
                        _norm_sigs.add(sig)
                        norms.append(item)
            elif cls == "tags" and isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        _tag_raw_count += 1
                        sig = _tag_signature(item)
                        if sig in _tag_sigs:
                            continue
                        _tag_sigs.add(sig)
                        tags.append(item)
            elif cls == "locations" and isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        _loc_raw_count += 1
                        sig = _location_signature(item)
                        if sig in _loc_sigs:
                            continue
                        _loc_sigs.add(sig)
                        locations.append(item)
            elif cls == "questions" and isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        _q_raw_count += 1
                        sig = _question_signature(item)
                        if sig in _q_sigs:
                            continue
                        _q_sigs.add(sig)
                        questions.append(item)
            elif cls == "consequences" and isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        _cons_raw_count += 1
                        sig = _consequence_signature(item)
                        if sig in _cons_sigs:
                            continue
                        _cons_sigs.add(sig)
                        consequences.append(item)
            elif cls == "parameters" and isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        _param_raw_count += 1
                        sig = _parameter_signature(item)
                        if sig in _param_sigs:
                            continue
                        _param_sigs.add(sig)
                        parameters.append(item)

        # Debug counters
        meta["window_config"].update({
            "extracted_norm_count": len(norms),
            "debug_counts": {
                "norms_pre": _norm_raw_count,
                "norms_post_dedup": len(norms),
                "tags_pre": _tag_raw_count,
                "tags_post_dedup": len(tags),
                "locations_pre": _loc_raw_count,
                "locations_post_dedup": len(locations),
                "questions_pre": _q_raw_count,
                "questions_post_dedup": len(questions),
                "consequences_pre": _cons_raw_count,
                "consequences_post_dedup": len(consequences),
                "parameters_pre": _param_raw_count,
                "parameters_post_dedup": len(parameters),
                # post_cap_* can be added later if cap is enforced here; for now equals post_dedup
                "norms_post_cap": len(norms),
                "tags_post_cap": len(tags),
                "locations_post_cap": len(locations),
                "questions_post_cap": len(questions),
                "consequences_post_cap": len(consequences),
                "parameters_post_cap": len(parameters),
            }
        })

        print(
            f"[DEBUG] Aggregation counts — norms: pre={_norm_raw_count}, post_dedup={len(norms)}; "
            f"tags: pre={_tag_raw_count}, post_dedup={len(tags)}; "
            f"params: pre={_param_raw_count}, post_dedup={len(parameters)}"
        )
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
    wc.setdefault("max_char_buffer", MAX_CHAR_BUFFER)
    wc.setdefault("extraction_passes", EXTRACTION_PASSES)
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
