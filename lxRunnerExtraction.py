"""Annotated-only extraction runner.

Purpose:
    - Load prompt and few-shot examples, call the model, and persist the annotated outputs exactly
        as returned by the library (per-extraction records) into a per-run folder "lx output".
    - Derive lightweight Tag and Parameter entries directly from Norm attributes and append them to
        the annotated outputs.

Out of scope (removed):
    - Legacy rich-schema building, validation, normalization, relationship inference, enrichment,
        and glossary generation. This file intentionally avoids any post-processing beyond simple
        Tag/Parameter derivation from Norms.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import importlib.util
import re

from dotenv import load_dotenv
import langextract as lx
from langextract import factory
from langextract import providers

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

    # This runner only persists annotated outputs and derived Tags/Parameters.

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
    # Default glossary path to run_dir when not provided (optional, only read for TEACH_MODE appendices)
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

    # Base prompt (be tolerant in web/worker context)
    if not PROMPT_FILE.exists():
        print(f"[WARN] Prompt file missing at {PROMPT_FILE}; using minimal default prompt.", file=sys.stderr)
        PROMPT_DESCRIPTION = (
            "Extract Norms, Tags, and Parameters. Return a JSON object with an 'extractions' array."
        )
    else:
        PROMPT_DESCRIPTION = PROMPT_FILE.read_text(encoding="utf-8")

    if not INPUT_FILE or not INPUT_FILE.exists():
        print(f"[WARN] Input file missing at {INPUT_FILE}; proceeding with empty input text.", file=sys.stderr)
        # Leave INPUT_FILE as None; later section sets INPUT_TEXT = "" accordingly.

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
    # 3. Extract
    # ---------------------------------------------------------------------------


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
        
        print(f"[DEBUG] About to call lx.extract for chunk {idx if idx is not None else 'single'}", file=sys.stderr)
        print(f"[DEBUG] Extract kwargs keys: {list(extract_kwargs.keys())}", file=sys.stderr)
        
        try:
            annotated = lx.extract(**extract_kwargs)  # returns AnnotatedDocument
            print(f"[DEBUG] lx.extract succeeded for chunk {idx if idx is not None else 'single'}", file=sys.stderr)
            print(f"[DEBUG] annotated type: {type(annotated)}", file=sys.stderr)
            print(f"[DEBUG] annotated is None: {annotated is None}", file=sys.stderr)
            
            # Immediate safety check
            if annotated is None:
                raise ValueError("lx.extract returned None - this should not happen")
                
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

        # Save RAW resolver output for debugging (before any processing)
        print(f"[DEBUG] Starting to save raw resolver output for chunk {idx if idx is not None else 'single'}", file=sys.stderr)
        try:
            raw_resolver_name = f"raw_resolver_output_{idx:03}.json" if idx is not None else "raw_resolver_output_single.json"
            
            # Check annotated object attributes safely
            print(f"[DEBUG] Checking annotated object attributes...", file=sys.stderr)
            document_id = getattr(annotated, "document_id", None)
            print(f"[DEBUG] document_id: {document_id}", file=sys.stderr)
            
            extractions_attr = getattr(annotated, "extractions", None)
            print(f"[DEBUG] extractions attribute type: {type(extractions_attr)}", file=sys.stderr)
            print(f"[DEBUG] extractions attribute is None: {extractions_attr is None}", file=sys.stderr)
            
            # Convert the annotated object to a serializable format
            raw_resolver_data = {
                "document_id": document_id,
                "extractions_raw": str(extractions_attr),  # Convert to string for safety
                "extractions_is_none": extractions_attr is None,
                "extractions_type": str(type(extractions_attr)),
                "metadata": {
                    "type": str(type(annotated)),
                    "attributes": [attr for attr in dir(annotated) if not attr.startswith('_')],
                },
            }
            # Try to get the actual extractions data more safely
            try:
                extractions = getattr(annotated, "extractions", None)
                if extractions is not None:
                    raw_resolver_data["extractions_count"] = len(extractions) if hasattr(extractions, '__len__') else "unknown"
                    # Try to serialize first few extractions for debugging
                    if hasattr(extractions, '__iter__'):
                        sample_extractions = []
                        for i, ext in enumerate(extractions):
                            if i >= 3:  # Only save first 3 for debugging
                                break
                            try:
                                sample_extractions.append({
                                    "index": i,
                                    "type": str(type(ext)),
                                    "attributes": [attr for attr in dir(ext) if not attr.startswith('_')],
                                    "extraction_class": getattr(ext, "extraction_class", "unknown"),
                                    "extraction_text_preview": str(getattr(ext, "extraction_text", ""))[:200] + "..." if len(str(getattr(ext, "extraction_text", ""))) > 200 else str(getattr(ext, "extraction_text", "")),
                                })
                            except Exception as sample_err:
                                sample_extractions.append({"index": i, "error": str(sample_err)})
                        raw_resolver_data["sample_extractions"] = sample_extractions
            except Exception as extract_err:
                raw_resolver_data["extraction_error"] = str(extract_err)
            
            (lx_output_dir / raw_resolver_name).write_text(
                json.dumps(raw_resolver_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as raw_save_err:
            print(f"[WARN] Failed to save raw resolver output: {raw_save_err}", file=sys.stderr)

        # Persist the annotated document outputs BEFORE any processing/enrichment
        try:
            # Save debug info to file for analysis
            debug_log_path = lx_output_dir / f"debug_log_{idx if idx is not None else 'single'}.txt"
            debug_log = []
            
            def log_debug(msg):
                debug_log.append(msg)
                print(f"[DEBUG] {msg}", file=sys.stderr)
            
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

            log_debug(f"Starting post-processing with annotated type: {type(annotated)}")
            log_debug(f"Annotated is None: {annotated is None}")
            log_debug(f"Annotated has extractions attr: {hasattr(annotated, 'extractions')}")
            
            raw_items = []
            
            try:
                extractions = getattr(annotated, "extractions", None)
                log_debug(f"Raw extractions from getattr: {type(extractions)}")
                log_debug(f"Raw extractions is None: {extractions is None}")
                
                if extractions is None:
                    extractions = []
                    log_debug("Set extractions to empty list")
                else:
                    # More detailed analysis of what we got
                    if hasattr(extractions, '__len__'):
                        log_debug(f"Extractions length: {len(extractions)}")
                    else:
                        log_debug("Extractions has no __len__ method")
                    
                    if hasattr(extractions, '__iter__'):
                        log_debug("Extractions is iterable")
                    else:
                        log_debug("Extractions is NOT iterable - this might be the problem")
                        extractions = []  # Force to empty list if not iterable
                        
            except Exception as extract_access_err:
                log_debug(f"ERROR accessing extractions: {extract_access_err}")
                extractions = []  # Safe fallback
                
            log_debug(f"Final extractions type: {type(extractions)}")
            log_debug(f"Final extractions length: {len(extractions) if hasattr(extractions, '__len__') else 'no_len'}")
            
            # Defensive iteration with detailed tracking
            extraction_count = 0
            try:
                log_debug(f"Starting iteration over extractions of type {type(extractions)}")
                
                # Additional safety check
                if extractions is None:
                    log_debug("Extractions is None, skipping iteration")
                    extractions = []
                elif not hasattr(extractions, '__iter__'):
                    log_debug(f"Extractions of type {type(extractions)} is not iterable, converting to list")
                    try:
                        extractions = [extractions]  # Wrap single item in list
                    except Exception:
                        log_debug("Failed to wrap in list, using empty list")
                        extractions = []
                
                # Test iteration capability before the main loop
                try:
                    test_iter = iter(extractions)
                    log_debug("Successfully created iterator for extractions")
                except Exception as iter_err:
                    log_debug(f"CRITICAL: Cannot create iterator for extractions: {iter_err}")
                    # This is likely our problem - force to empty list
                    extractions = []
                
                for extraction_index, e in enumerate(extractions):
                    extraction_count += 1
                    log_debug(f"Processing extraction {extraction_index}: type={type(e)}, is_none={e is None}")
                    
                    # Skip null extractions
                    if e is None:
                        log_debug(f"Skipping null extraction at index {extraction_index}")
                        continue
                        
                    # Handle both old object-based and new dictionary-based extraction formats
                    item = None
                    if isinstance(e, dict):
                        log_debug(f"Processing dict extraction at index {extraction_index}")
                        # New V5 format: {'SECTION': '...', 'SECTION_attributes': {...}}
                        if e is None or not hasattr(e, 'keys'):
                            log_debug(f"Dict extraction {extraction_index} has no keys, skipping")
                            continue
                        keys = e.keys()
                        if keys is None:
                            log_debug(f"Dict extraction {extraction_index} keys() returned None, skipping")
                            continue
                        extraction_keys = [k for k in keys if not k.endswith('_attributes')]
                        if extraction_keys:
                            extraction_class = extraction_keys[0]
                            extraction_text = e.get(extraction_class, "")
                            attributes_key = f"{extraction_class}_attributes"
                            attributes = e.get(attributes_key, {})
                            if attributes is None:
                                attributes = {}
                            item = {
                                "extraction_class": extraction_class,
                                "extraction_text": extraction_text,
                                "attributes": attributes,
                                "char_interval": None,
                                "alignment_status": None,
                                "extraction_index": None,
                                "group_index": None,
                                "description": None,
                                "token_interval": None,
                            }
                            log_debug(f"Created dict item for {extraction_class}")
                        else:
                            log_debug(f"Dict extraction {extraction_index} has no valid extraction keys, skipping")
                            continue  # Skip malformed extractions
                    else:
                        log_debug(f"Processing object extraction at index {extraction_index}")
                        # Object format: handle both new extraction objects and legacy objects
                        try:
                            # Check if it's a new extraction object with direct properties
                            if hasattr(e, "extraction_class") and hasattr(e, "extraction_text"):
                                attributes = getattr(e, "attributes", None)
                                if attributes is None:
                                    attributes = {}
                                item = {
                                    "extraction_class": getattr(e, "extraction_class", None),
                                    "extraction_text": getattr(e, "extraction_text", None),
                                    "attributes": attributes,
                                    "char_interval": _ci_dict(getattr(e, "char_interval", None)),
                                    "alignment_status": getattr(getattr(e, "alignment_status", None), "value", None) if hasattr(getattr(e, "alignment_status", None), "value") else getattr(e, "alignment_status", None),
                                    "extraction_index": getattr(e, "extraction_index", None),
                                    "group_index": getattr(e, "group_index", None),
                                    "description": getattr(e, "description", None),
                                    "token_interval": _ti_dict(getattr(e, "token_interval", None)),
                                }
                                log_debug(f"Created object item for {getattr(e, 'extraction_class', 'Unknown')}")
                            else:
                                # Legacy format processing - skip since this format is deprecated
                                log_debug(f"Object extraction {extraction_index} is legacy format, skipping")
                                continue
                        except Exception as attr_err:
                            log_debug(f"ERROR processing object extraction {extraction_index}: {attr_err}")
                            print(f"[WARN] Failed to process extraction attributes: {attr_err}", file=sys.stderr)
                            # Create minimal item to continue processing
                            item = {
                                "extraction_class": str(getattr(e, "extraction_class", "Unknown")),
                                "extraction_text": str(getattr(e, "extraction_text", "")),
                                "attributes": {},
                                "char_interval": None,
                                "alignment_status": None,
                                "extraction_index": None,
                                "group_index": None,
                                "description": None,
                                "token_interval": None,
                            }
                            log_debug(f"Created minimal fallback item")
                    
                    if item is not None:
                        raw_items.append(item)
                        log_debug(f"Successfully processed extraction {extraction_index}, total raw_items: {len(raw_items)}")
                    else:
                        log_debug(f"No item created for extraction {extraction_index}")
                
            except Exception as main_iteration_err:
                log_debug(f"ERROR during main extraction iteration: {main_iteration_err}")
                import traceback
                log_debug(f"Iteration traceback: {traceback.format_exc()}")
                # Continue with whatever we have so far
                
            log_debug(f"Completed processing {extraction_count} extractions, collected {len(raw_items)} raw items")

            # Write debug log to file
            try:
                debug_log_path.write_text('\n'.join(debug_log), encoding='utf-8')
                log_debug(f"Debug log written to: {debug_log_path}")
            except Exception as log_write_err:
                print(f"[ERROR] Failed to write debug log: {log_write_err}", file=sys.stderr)

            # Derive Tags and Parameters from Norms and append to annotated outputs
            # Tag schema:
            # extraction_class="Tag"
            # attributes={"id": "T::000001", "tag": <tag_path>, "used_by_norm_ids": [norm_id], "related_topics": <topics>}
            # Parameter schema:
            # extraction_class="Parameter"
            # attributes={"id": "P::000001", "applies_for_tag": <path>, "operator": op, "value": val, "unit": unit, "norm_ids": [norm_id]}

            # Build maps to avoid duplicates and aggregate used_by_norm_ids
            tag_map: dict[str, Dict[str, Any]] = {}
            param_list: List[Dict[str, Any]] = []
            tag_counter = 1
            param_counter = 1

            def _next_tid() -> str:
                nonlocal tag_counter
                tid = f"T::{tag_counter:06d}"
                tag_counter += 1
                return tid

            def _next_pid() -> str:
                nonlocal param_counter
                pid = f"P::{param_counter:06d}"
                param_counter += 1
                return pid

            def _parse_param(expr: str) -> Optional[Tuple[str, str, Any, Optional[str]]]:
                if not isinstance(expr, str):
                    return None
                m = re.match(r"^\s*([A-Z0-9_.]+)\s*(==|>=|<=|>|<)\s*(.+?)\s*$", expr)
                if not m:
                    return None
                path, op, val_str = m.group(1), m.group(2), m.group(3)
                # Try numeric value with optional decimal comma/dot, keep unit remainder
                m2 = re.match(r"^\s*([0-9]+(?:[\.,][0-9]+)?)\s*(.*)$", val_str)
                if m2:
                    num = m2.group(1).replace(',', '.')
                    try:
                        val: Any = float(num) if ('.' in num) else int(num)
                    except Exception:
                        try:
                            val = float(num)
                        except Exception:
                            val = num
                    unit = m2.group(2).strip() or None
                    return (path, op, val, unit)
                # Non-numeric value (enum/string)
                return (path, op, val_str.strip(), None)

            # Scan norms - handle both old individual Norm items and new format with norms in extraction_text
            norms_to_process = []
            
            log_debug("Starting norms processing phase")
            
            # Ensure raw_items is valid before processing
            if raw_items is None:
                log_debug("raw_items is None, creating empty list")
                raw_items = []
            elif not isinstance(raw_items, list):
                log_debug(f"raw_items is not a list (type: {type(raw_items)}), creating empty list")
                raw_items = []
            
            log_debug(f"Processing {len(raw_items)} raw items for norms")
            
            try:
                for item_index, item in enumerate(raw_items):
                    # Skip None items
                    if item is None or not isinstance(item, dict):
                        log_debug(f"Skipping non-dict item at index {item_index}: type={type(item)}")
                        continue
                    extraction_class = item.get("extraction_class")
                    
                    log_debug(f"Processing extraction_class: {extraction_class} at index {item_index}")
                    
                    # Handle the new format where norms are in JSON arrays
                    if extraction_class == "norms":
                        log_debug("Processing norms format (new)")
                        # New format - norms stored as JSON in extraction_text
                        extraction_text = item.get("extraction_text", "")
                        if isinstance(extraction_text, str) and extraction_text.strip():
                            try:
                                # Parse the JSON string containing the list of norms
                                norms_list = json.loads(extraction_text)
                                log_debug(f"Successfully parsed norms JSON, type: {type(norms_list)}")
                            except (json.JSONDecodeError, TypeError) as json_err:
                                # If parsing fails, skip this item
                                log_debug(f"Failed to parse norms JSON: {json_err}")
                                continue
                            # Defensive: ensure norms_list is a list
                            if isinstance(norms_list, list):
                                norms_to_process.extend(norms_list)
                                log_debug(f"Extended norms_to_process with {len(norms_list)} items")
                            elif norms_list is not None:
                                # Sometimes a single dict is returned, not a list
                                if isinstance(norms_list, dict):
                                    norms_to_process.append(norms_list)
                                    log_debug("Added single norm dict to norms_to_process")
                                # else: skip if not a list or dict
                            else:
                                log_debug("Parsed norms_list is None, skipping")
                        else:
                            log_debug(f"Extraction text is not a valid string: {type(extraction_text)}")
                    elif extraction_class == "Norm":
                        log_debug("Processing Norm format (legacy)")
                        # Handle individual norm item (legacy format)
                        attrs = item.get("attributes", {})
                        if attrs is None:
                            log_debug("Norm attributes is None, using empty dict")
                            attrs = {}
                        norms_to_process.append(attrs)
                        log_debug("Added legacy Norm to norms_to_process")
                    else:
                        log_debug(f"Extraction class '{extraction_class}' is not a norm type, skipping")
                        
            except Exception as norms_scan_err:
                log_debug(f"ERROR during norms scanning: {norms_scan_err}")
                import traceback
                log_debug(f"Norms scan traceback: {traceback.format_exc()}")
                
            log_debug(f"Completed norms scanning, found {len(norms_to_process)} norms to process")
            
            # Process all norms regardless of format
            log_debug("Starting individual norms processing")
            norms_processed_count = 0
            try:
                for norm_index, norm_data in enumerate(norms_to_process):
                    if not isinstance(norm_data, dict):
                        log_debug(f"Skipping non-dict norm at index {norm_index}: type={type(norm_data)}")
                        continue
                        
                    norm_id = norm_data.get("id")
                    if not norm_id:
                        log_debug(f"Skipping norm at index {norm_index}: no ID")
                        continue
                    
                    norms_processed_count += 1
                    log_debug(f"Processing norm {norm_index} with ID: {norm_id}")
                        
                    topics = norm_data.get("topics")
                    if topics is None:
                        topics = []
                    elif not isinstance(topics, list):
                        topics = []

                    # Relevant tags - ensure it's a list
                    relevant_tags = norm_data.get("relevant_tags")
                    if relevant_tags is None:
                        relevant_tags = []
                    elif not isinstance(relevant_tags, list):
                        relevant_tags = []
                    
                    for tag_path in relevant_tags:
                        if not isinstance(tag_path, str):
                            log_debug(f"Skipping non-string tag_path: {type(tag_path)}")
                            continue
                        if tag_path not in tag_map:
                            tag_map[tag_path] = {
                                "extraction_class": "Tag",
                                "extraction_text": tag_path,
                                "attributes": {
                                    "id": _next_tid(),
                                    "tag": tag_path,
                                    "used_by_norm_ids": [norm_id],
                                    "related_topics": topics,
                                },
                            }
                            log_debug(f"Added new tag to tag_map: {tag_path}")
                        else:
                            try:
                                u = tag_map[tag_path]["attributes"].setdefault("used_by_norm_ids", [])
                                if u is None:
                                    log_debug(f"WARNING: used_by_norm_ids is None for tag {tag_path}, creating new list")
                                    u = []
                                    tag_map[tag_path]["attributes"]["used_by_norm_ids"] = u
                                if norm_id not in u:
                                    u.append(norm_id)
                                log_debug(f"Updated existing tag: {tag_path}, used_by_norm_ids now: {u}")
                            except Exception as tag_update_err:
                                log_debug(f"ERROR updating tag {tag_path}: {tag_update_err}")
                                # Recreate the tag to be safe
                                tag_map[tag_path] = {
                                    "extraction_class": "Tag",
                                    "extraction_text": tag_path,
                                    "attributes": {
                                        "id": _next_tid(),
                                        "tag": tag_path,
                                        "used_by_norm_ids": [norm_id],
                                        "related_topics": topics,
                                    },
                                }

                    # Extracted parameters - ensure it's a list
                    extracted_parameters = norm_data.get("extracted_parameters")
                    if extracted_parameters is None:
                        extracted_parameters = []
                    elif not isinstance(extracted_parameters, list):
                        extracted_parameters = []
                        
                    for expr in extracted_parameters:
                        parsed = _parse_param(expr)
                        if not parsed:
                            continue
                        path, op, val, unit = parsed
                        param_list.append({
                            "extraction_class": "Parameter",
                            "extraction_text": expr,
                            "attributes": {
                                "id": _next_pid(),
                                "applies_for_tag": path,
                                "operator": op,
                                "value": val,
                                "unit": unit,
                                "norm_ids": [norm_id],
                            },
                        })
                        
            except Exception as norms_processing_err:
                log_debug(f"ERROR during individual norms processing: {norms_processing_err}")
                import traceback
                log_debug(f"Norms processing traceback: {traceback.format_exc()}")
                
            log_debug(f"Completed processing {norms_processed_count} individual norms")

            # Append derived Tags and Parameters
            log_debug(f"Appending tags and parameters - tag_map type: {type(tag_map)}, param_list type: {type(param_list)}")
            log_debug(f"tag_map is None: {tag_map is None}, param_list is None: {param_list is None}")
            log_debug(f"tag_map length: {len(tag_map) if tag_map else 'N/A'}, param_list length: {len(param_list) if param_list else 'N/A'}")
            
            try:
                if tag_map and isinstance(tag_map, dict):
                    tag_values = tag_map.values()
                    log_debug(f"tag_map.values() type: {type(tag_values)}")
                    log_debug(f"tag_map.values() is None: {tag_values is None}")
                    
                    if tag_values is not None:
                        tag_list = list(tag_values)
                        log_debug(f"Converting to list successful, length: {len(tag_list)}")
                        if tag_list:
                            raw_items.extend(tag_list)
                            log_debug(f"Successfully extended raw_items with {len(tag_list)} tags")
                        else:
                            log_debug("tag_list is empty, no tags to extend")
                    else:
                        log_debug("tag_map.values() returned None!")
                else:
                    log_debug(f"tag_map is not valid for processing: {tag_map}")
                    
            except Exception as tag_err:
                log_debug(f"ERROR extending tag_map values: {tag_err}")
                import traceback
                log_debug(f"Tag extension traceback: {traceback.format_exc()}")
                print(f"[WARN] Failed to extend tag_map values: {tag_err}", file=sys.stderr)
                
            try:
                if param_list and isinstance(param_list, list):
                    log_debug(f"Extending raw_items with {len(param_list)} parameters")
                    raw_items.extend(param_list)
                    log_debug("Successfully extended raw_items with parameters")
                else:
                    log_debug(f"param_list is not valid for extending: {param_list}")
                    
            except Exception as param_err:
                log_debug(f"ERROR extending param_list: {param_err}")
                import traceback
                log_debug(f"Parameter extension traceback: {traceback.format_exc()}")
                print(f"[WARN] Failed to extend param_list: {param_err}", file=sys.stderr)

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

        # Annotated outputs saved; no legacy pipeline to run.
        return None

 
    

    print("[INFO] Library-managed chunking enabled (max_char_buffer governs internal splits)")
    _call_and_capture(INPUT_TEXT, None)
    print(f"[INFO] Raw annotated outputs saved to: {lx_output_dir}. Annotated-only mode complete.")
    return
    
