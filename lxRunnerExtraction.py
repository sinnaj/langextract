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

# Import modularized extraction functions
from postprocessing.extract_tags import extract_tags_from_norms
from postprocessing.extract_params import extract_parameters_from_norms

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
                "suppress_parse_errors_default": True,  ## TODODisable this for proper runs!!!
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

        # Save RAW annotated document as-is for structure analysis (BEFORE any processing)
        print(f"[DEBUG] Starting to save raw annotated document for chunk {idx if idx is not None else 'single'}", file=sys.stderr)
        try:
            raw_annotated_name = f"raw_annotated_document_{idx:03}.json" if idx is not None else "raw_annotated_document_single.json"
            
            # First, try to serialize the entire annotated object using its built-in methods if available
            raw_annotated_data = {}
            
            # Basic metadata about the annotated object
            raw_annotated_data["object_type"] = str(type(annotated))
            raw_annotated_data["object_is_none"] = annotated is None
            raw_annotated_data["object_attributes"] = [attr for attr in dir(annotated) if not attr.startswith('_')] if annotated is not None else []
            
            # Try to serialize using common serialization methods
            serialization_attempts = {}
            
            # Attempt 1: Check for to_dict method
            try:
                if hasattr(annotated, 'to_dict'):
                    raw_annotated_data["to_dict_result"] = annotated.to_dict()
                    serialization_attempts["to_dict"] = "success"
                else:
                    serialization_attempts["to_dict"] = "method_not_available"
            except Exception as dict_err:
                serialization_attempts["to_dict"] = f"error: {str(dict_err)}"
            
            # Attempt 2: Check for __dict__ attribute
            try:
                if hasattr(annotated, '__dict__'):
                    # Convert __dict__ to JSON-serializable format
                    dict_data = {}
                    for key, value in annotated.__dict__.items():
                        try:
                            # Test JSON serialization
                            json.dumps(value)
                            dict_data[key] = value
                        except (TypeError, ValueError):
                            # Not JSON serializable, store as string representation
                            dict_data[key] = str(value)
                    raw_annotated_data["__dict___result"] = dict_data
                    serialization_attempts["__dict__"] = "success"
                else:
                    serialization_attempts["__dict__"] = "attribute_not_available"
            except Exception as dict_err:
                serialization_attempts["__dict__"] = f"error: {str(dict_err)}"
            
            # Attempt 3: Manual attribute extraction for key properties
            try:
                manual_extraction = {}
                key_attributes = ["document_id", "extractions", "text", "metadata", "config", "results"]
                
                for attr_name in key_attributes:
                    try:
                        if hasattr(annotated, attr_name):
                            attr_value = getattr(annotated, attr_name)
                            # Try to serialize, fall back to string representation
                            try:
                                json.dumps(attr_value)
                                manual_extraction[attr_name] = attr_value
                            except (TypeError, ValueError):
                                manual_extraction[attr_name] = {
                                    "type": str(type(attr_value)),
                                    "string_repr": str(attr_value),
                                    "is_none": attr_value is None,
                                    "has_len": hasattr(attr_value, '__len__'),
                                    "length": len(attr_value) if hasattr(attr_value, '__len__') else None,
                                    "is_iterable": hasattr(attr_value, '__iter__'),
                                }
                                # If it's extractions, try to get more details
                                if attr_name == "extractions" and attr_value is not None:
                                    try:
                                        if hasattr(attr_value, '__iter__') and not isinstance(attr_value, str):
                                            first_few = []
                                            for i, item in enumerate(attr_value):
                                                if i >= 3:  # Only first 3 items
                                                    break
                                                first_few.append({
                                                    "index": i,
                                                    "type": str(type(item)),
                                                    "string_repr": str(item)[:300] + "..." if len(str(item)) > 300 else str(item),
                                                    "attributes": [attr for attr in dir(item) if not attr.startswith('_')] if hasattr(item, '__dict__') else []
                                                })
                                            manual_extraction[attr_name]["sample_items"] = first_few
                                    except Exception as sample_err:
                                        manual_extraction[attr_name]["sample_error"] = str(sample_err)
                        else:
                            manual_extraction[attr_name] = "attribute_not_found"
                    except Exception as attr_err:
                        manual_extraction[attr_name] = f"error: {str(attr_err)}"
                
                raw_annotated_data["manual_extraction"] = manual_extraction
                serialization_attempts["manual_extraction"] = "success"
                
            except Exception as manual_err:
                serialization_attempts["manual_extraction"] = f"error: {str(manual_err)}"
            
            raw_annotated_data["serialization_attempts"] = serialization_attempts
            
            # Save the raw annotated document structure
            (lx_output_dir / raw_annotated_name).write_text(
                json.dumps(raw_annotated_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[DEBUG] Raw annotated document saved to: {raw_annotated_name}", file=sys.stderr)
            
        except Exception as raw_annotated_err:
            print(f"[WARN] Failed to save raw annotated document: {raw_annotated_err}", file=sys.stderr)

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
            
            def _get_alignment_status_value(alignment_status):
                """Extract alignment status value from enum or string"""
                if alignment_status is None:
                    return None
                # Handle enum objects with .value attribute
                if hasattr(alignment_status, "value"):
                    return alignment_status.value
                # Handle string values directly
                return alignment_status

            raw_items = []
            
            extractions = getattr(annotated, "extractions", [])
            extraction_count = 0

            for extraction_index, e in enumerate(extractions):
                if e is None:
                    continue
                
                extraction_count += 1
                attributes = getattr(e, "attributes", {})
                item = {
                    "extraction_class": getattr(e, "extraction_class", None),
                    "extraction_text": getattr(e, "extraction_text", None),
                    "attributes": attributes,
                    "char_interval": _ci_dict(getattr(e, "char_interval", None)),
                    "alignment_status": _get_alignment_status_value(getattr(e, "alignment_status", None)),
                    "extraction_index": getattr(e, "extraction_index", None),
                    "group_index": getattr(e, "group_index", None),
                    "description": getattr(e, "description", None),
                    "token_interval": _ti_dict(getattr(e, "token_interval", None)),
                }
                raw_items.append(item)

            # Derive Tags and Parameters from Norms and append to annotated outputs
            # Tag schema:
            # extraction_class="Tag"
            # attributes={"id": "T::000001", "tag": <tag_path>, "used_by_norm_ids": [norm_id], "related_topics": <topics>}
            # Parameter schema:
            # extraction_class="Parameter"
            # attributes={"id": "P::000001", "applies_for_tag": <path>, "operator": op, "value": val, "unit": unit, "norm_ids": [norm_id]}

            # Scan items for norms to process
            norms_to_process = []
            for item in raw_items:
                if item and isinstance(item, dict) and item.get("extraction_class") == "NORM":
                    norms_to_process.append(item.get("attributes", {}))
            
            # Extract tags and parameters using modularized functions
            derived_tags = extract_tags_from_norms(norms_to_process, tag_counter_start=1)
            derived_params = extract_parameters_from_norms(norms_to_process, param_counter_start=1)

            # Append derived Tags and Parameters
            if derived_tags:
                raw_items.extend(derived_tags)
            if derived_params:
                raw_items.extend(derived_params)

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
    
