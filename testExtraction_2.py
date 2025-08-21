"""Enhanced extraction runner using the new comprehensive prompt spec.

This script:
1. Loads the structured extraction prompt from `prompts/extraction_prompt.md`.
2. Provides updated few-shot examples (UPPERCASE DSL + membership IN[...] usage).
3. Invokes langextract to produce rich JSON (norms, tags, locations, questions, consequences, parameters).
4. Validates the returned JSON structure against required top-level keys & field expectations.
5. Falls back to wrapping legacy `extractions` output into the new schema if the model fails to follow the new format (to avoid losing data while iterating on prompt tuning).
6. Extracts DSL field paths & saves a glossary stub.

Run (PowerShell):
  python .\testExtraction_2.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

from dotenv import load_dotenv
import langextract as lx

# ---------------------------------------------------------------------------
# 0. Environment
# ---------------------------------------------------------------------------
load_dotenv()

PROMPT_PATH = Path("prompts/extraction_prompt.md")
OUTPUT_JSON_PATH = Path("rich_norms.json")
GLOSSARY_PATH = Path("dsl_glossary.json")

if not PROMPT_PATH.exists():  # Fail fast with actionable guidance.
    print(f"FATAL: Prompt file not found at {PROMPT_PATH}", file=sys.stderr)
    sys.exit(1)

prompt_description = PROMPT_PATH.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1. Updated Few-Shot Examples (normalized to UPPERCASE DSL + IN[])
#    Keep them concise: they mainly anchor Norm atomicity + DSL style.
# ---------------------------------------------------------------------------
examples: List[lx.data.ExampleData] = [
    lx.data.ExampleData(
        text=(
            "1 Las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50 personas serán abatibles "
            "con eje de giro vertical y su sistema de cierre, o bien no actuará mientras haya actividad en las zonas a evacuar, o bien consistirá en "
            "un dispositivo de fácil y rápida apertura desde el lado del cual provenga dicha evacuación, sin tener que utilizar una llave y sin tener que actuar sobre más de un mecanismo. "
            "Las anteriores condiciones no son aplicables cuando se trate de puertas automáticas."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50 personas serán abatibles "
                    "con eje de giro vertical y su sistema de cierre, o bien no actuará mientras haya actividad en las zonas a evacuar, o bien consistirá "
                    "en un dispositivo de fácil y rápida apertura desde el lado del cual provenga dicha evacuación, sin tener que utilizar una llave y "
                    "sin tener que actuar sobre más de un mecanismo."
                ),
                attributes={
                    "paragraph_number": 1,
                    "applies_if": "DOOR.USE == 'EXIT' OR EVACUATION.PERSONS > 50",
                    "satisfied_if": (
                        "DOOR.TYPE == 'SWING' AND DOOR.AXIS == 'VERTICAL'; OR "
                        "CLOSING.SYSTEM.ENABLED == FALSE; OR "
                        "(DOOR.OPENING.FROM_EVACUATION_SIDE == TRUE AND DOOR.OPENING.REQUIRES_KEY == FALSE AND DOOR.OPENING.MECHANISMS_COUNT <= 1)"
                    ),
                    "exempt_if": "DOOR.TYPE == 'AUTOMATIC'",
                },
            ),
        ],
    ),
    lx.data.ExampleData(
        text=(
            "3 Abrirá en el sentido de la evacuación toda puerta de salida: a) prevista para el paso de más de 200 personas en edificios de uso Residencial Vivienda o de 100 personas en los demás casos, "
            "b) prevista para más de 50 ocupantes del recinto o espacio en el que esté situada."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Abrirá en el sentido de la evacuación toda puerta de salida: a) prevista para el paso de más de 200 personas en edificios de uso Residencial Vivienda o de 100 personas en los demás casos"
                ),
                attributes={
                    "paragraph_number": 3,
                    "applies_if": "(BUILDING.USE == 'RESIDENTIAL_DWELLING' AND SERVED.PERSONS > 200) OR (BUILDING.USE == 'OTHER' AND SERVED.PERSONS > 100)",
                    "satisfied_if": "DOOR.OPENING.DIRECTION == 'EVACUATION'",
                    "exempt_if": None,
                },
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="b) prevista para más de 50 ocupantes del recinto o espacio en el que esté situada.",
                attributes={
                    "paragraph_number": 3,
                    "applies_if": "SPACE.OCCUPANTS > 50",
                    "satisfied_if": "DOOR.OPENING.DIRECTION == 'EVACUATION'",
                    "exempt_if": None,
                },
            ),
        ],
    ),
]

# ---------------------------------------------------------------------------
# 2. Input Text (placeholder sample) – in production load documents / chunks.
# ---------------------------------------------------------------------------
input_text = (
    "1 Las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50 personas serán abatibles con eje de giro vertical y su sistema de cierre, o bien no actuará mientras haya actividad en las zonas a evacuar, o bien consistirá en un dispositivo de fácil y rápida apertura desde el lado del cual provenga dicha evacuación, sin tener que utilizar una llave y sin tener que actuar sobre más de un mecanismo. Las anteriores condiciones no son aplicables cuando se trate de puertas automáticas. "
    "3 Abrirá en el sentido de la evacuación toda puerta de salida: a) prevista para el paso de más de 200 personas en edificios de uso Residencial Vivienda o de 100 personas en los demás casos, b) prevista para más de 50 ocupantes del recinto o espacio en el que esté situada."
)

# ---------------------------------------------------------------------------
# 3. Helper – Validator & Legacy Fallback
# ---------------------------------------------------------------------------
REQUIRED_TOP_LEVEL = [
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


def is_rich_schema(obj: Any) -> bool:
    return isinstance(obj, dict) and all(k in obj for k in REQUIRED_TOP_LEVEL)


def wrap_legacy_extractions(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap older `extractions` style into the new rich schema skeleton.

    This allows iterative improvement without losing current extraction output.
    """
    norms = []
    for i, ex in enumerate(doc.get("extractions", []), start=1):
        attrs = ex.get("Norm_attributes") or ex.get("attributes", {})
        norms.append(
            {
                "id": f"N::{i:04d}",
                "Norm": ex.get("Norm") or ex.get("Norm_text", ""),
                "obligation_type": "MANDATORY",  # best-effort default
                "paragraph_number": attrs.get("paragraph_number"),
                "applies_if": attrs.get("applies_if", "TRUE"),
                "satisfied_if": attrs.get("satisfied_if", "TRUE"),
                "exempt_if": attrs.get("exempt_if"),
                "priority": 3,
                "relevant_tags": [],
                "relevant_roles": [],
                "project_dimensions": {},
                "lifecycle_phase": [],
                "topics": [],
                "location_scope": {
                    "COUNTRY": "ES",
                    "STATES": [],
                    "PROVINCES": [],
                    "REGIONS": [],
                    "COMMUNES": [],
                    "ZONES": [],
                    "GEO_CODES": [],
                    "UNCERTAINTY": 0.9,
                },
                "source": {
                    "doc_id": "UNKNOWN",
                    "article": None,
                    "page": -1,
                    "span_char_start": -1,
                    "span_char_end": -1,
                    "visual_refs": [],
                },
                "extracted_parameters_ids": [],
                "consequence_ids": [],
                "confidence": 0.4,
                "uncertainty": 0.6,
                "notes": "Legacy wrapping – enrich on re-run",
            }
        )

    skeleton = {
        "schema_version": "1.0.0",
        "ontology_version": "0.0.1",
        "truncated": False,
        "has_more": False,
        "window_config": {
            "input_chars": len(input_text),
            "max_norms_per_5k_tokens": 35,
            "extracted_norm_count": len(norms),
        },
        "global_disclaimer": "NO LEGAL ADVICE",
        "document_metadata": {
            "doc_id": "UNKNOWN",
            "doc_title": None,
            "source_language": "es",
            "received_chunk_span": {"char_start": 0, "char_end": len(input_text)},
            "page_range": {"start": -1, "end": -1},
            "topics": [],
            "location_scope": {
                "COUNTRY": "ES",
                "STATES": [],
                "PROVINCES": [],
                "REGIONS": [],
                "COMMUNES": [],
                "ZONES": [],
                "GEO_CODES": [],
                "UNCERTAINTY": 1.0,
            },
        },
        "norms": norms,
        "tags": [],
        "locations": [],
        "questions": [],
        "consequences": [],
        "parameters": [],
        "quality": {
            "errors": ["LEGACY_FALLBACK"],
            "warnings": [],
            "confidence_global": 0.4,
            "uncertainty_global": 0.6,
        },
    }
    return skeleton


def validate_rich_schema(obj: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in obj:
            errors.append(f"MISSING_TOP_LEVEL:{key}")
    if "norms" in obj and not isinstance(obj["norms"], list):
        errors.append("NORMS_NOT_LIST")
    # Minimal DSL syntax sanity (very light – deep validation can be added):
    dsl_pattern = re.compile(r"^[A-Z0-9_.()'\s><=!-\[\];,:]+IN\[|HAS\(|WITHIN\(|OVERLAPS\(|ADJACENT_TO\(|OR|AND|NOT|TRUE|FALSE")
    # Only check a sample to avoid huge overhead.
    for norm in obj.get("norms", [])[:10]:
        for field in ("applies_if", "satisfied_if", "exempt_if"):
            v = norm.get(field)
            if isinstance(v, str) and v not in ("TRUE", "null") and len(v) > 0:
                # This is a heuristic placeholder; can be replaced with a parser.
                if ".." in v:  # simple illegal pattern example
                    errors.append(f"DSL_SUSPECT_DOUBLE_DOT:{field}")
    return errors


# ---------------------------------------------------------------------------
# 4. Run extraction
# ---------------------------------------------------------------------------
print("Running extraction with rich prompt …")
result = lx.extract(
    text_or_documents=input_text,
    prompt_description=prompt_description,
    examples=examples,  # keep few-shot Norm grounding
    model_id="gemini-2.5-flash",
    api_key=os.environ.get("GOOGLE_API_KEY"),
    fence_output=False,
    use_schema_constraints=False,
    temperature=0.15,
    resolver_params={
        "fence_output": False,
        "format_type": lx.data.FormatType.JSON,
    },
    language_model_params={"temperature": 0.15},
)

# The library returns an AnnotatedDocument; we try to recover raw text if needed.
raw_text = None
try:
    # If result.raw_response exists (depending on library internals) – fallback path.
    raw_text = getattr(result, "raw_response", None)
except Exception:  # noqa: BLE001
    pass

# Attempt to parse as JSON – first from printed representation.
parsed: Dict[str, Any] | None = None
if raw_text:
    try:
        parsed = json.loads(raw_text)
    except Exception:
        parsed = None

if parsed is None:
    # Try if the result was already coerced into dict form by data_lib.
    from langextract import data_lib  # local import to avoid cost if not needed

    try:
        legacy_dict = data_lib.annotated_document_to_dict(result)
        # If legacy style, will have 'extractions'
        if "extractions" in legacy_dict:
            parsed = wrap_legacy_extractions(legacy_dict)
        else:
            parsed = legacy_dict  # hope it's already rich
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: Unable to convert result to dict: {e}", file=sys.stderr)
        sys.exit(2)

# Validate / fallback if needed
if not is_rich_schema(parsed):
    print("Model did not emit rich schema – wrapping legacy output.")
    if "extractions" in parsed:
        parsed = wrap_legacy_extractions(parsed)
    else:
        parsed = wrap_legacy_extractions({"extractions": []})

schema_errors = validate_rich_schema(parsed)
if schema_errors:
    parsed.setdefault("quality", {}).setdefault("errors", []).extend(schema_errors)

# ---------------------------------------------------------------------------
# 5. Save JSON
# ---------------------------------------------------------------------------
with OUTPUT_JSON_PATH.open("w", encoding="utf-8") as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
print(f"Saved rich extraction JSON to {OUTPUT_JSON_PATH}")

# ---------------------------------------------------------------------------
# 6. DSL Key Glossary (Very light pass – from norms' DSL fields & parameters)
# ---------------------------------------------------------------------------
def collect_dsl_keys(obj: Dict[str, Any]) -> Set[str]:
    keys: Set[str] = set()
    dsl_fields = ["applies_if", "satisfied_if", "exempt_if"]
    token_pattern = re.compile(r"[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+")
    for norm in obj.get("norms", []):
        for fld in dsl_fields:
            val = norm.get(fld)
            if isinstance(val, str):
                for m in token_pattern.findall(val):
                    keys.add(m)
    for param in obj.get("parameters", []):
        fp = param.get("field_path")
        if isinstance(fp, str):
            keys.add(fp)
    return keys


dsl_keys = sorted(collect_dsl_keys(parsed))
glossary = {k: "" for k in dsl_keys}
with GLOSSARY_PATH.open("w", encoding="utf-8") as f:
    json.dump(glossary, f, ensure_ascii=False, indent=2)
print(f"Saved DSL glossary to {GLOSSARY_PATH} (empty definitions – fill via ontology pipeline)")

# Basic console summary
print("--- Summary ---")
print(f"Norms: {len(parsed.get('norms', []))}  Tags: {len(parsed.get('tags', []))}  Parameters: {len(parsed.get('parameters', []))}")
print(f"Quality errors: {parsed.get('quality', {}).get('errors', [])}")
