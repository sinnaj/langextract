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

PROMPT_FILE = Path("prompts/extraction_prompt.md")
OUTPUT_FILE = Path("rich_norms_full.json")
GLOSSARY_FILE = Path("dsl_glossary.json")
MAX_NORMS_PER_5K = 10  # matches spec guidance
MODEL_ID = "google/gemini-2.5-flash" if USE_OPENROUTER else "gemini-2.5-flash"
MODEL_TEMPERATURE = 0.15

if not PROMPT_FILE.exists():
    print(f"FATAL: Prompt file missing at {PROMPT_FILE}", file=sys.stderr)
    sys.exit(1)

# Base prompt
PROMPT_DESCRIPTION = PROMPT_FILE.read_text(encoding="utf-8")

# Teaching appendix injection & known field paths (if LX_TEACH_MODE=1)
TEACH_MODE = os.getenv("LX_TEACH_MODE") == "1"
APPENDIX_FILE = Path("prompts/prompt_appendix_teaching.md")
ENTITY_SEMANTICS_FILE = Path("prompts/prompt_appendix_entity_semantics.md")

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


# ---------------------------------------------------------------------------
# 1. Few-Shot Examples
# ---------------------------------------------------------------------------
# Multi-entity examples demonstrating Norms, Tags, Parameters, Locations, Questions,
# and Consequences. These DO NOT pre-allocate final IDs – the model must assign
# fresh sequential IDs in its full JSON output. A small rich_demo is embedded to
# illustrate cross-array structure. Attribute keys mirror target schema fields.

EXAMPLES: List[lx.data.ExampleData] = [
    # RICH: multi-entity with alternatives & exemption + embedded miniature demo
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
                    "rich_demo": {
                        "parameters": [
                            {"id": "P::DEMO1", "field_path": "DOOR.OPENING.MECHANISMS_COUNT", "operator": "<=", "value": 1, "unit": None}
                        ],
                        "tags": [
                            {"id": "T::DEMO1", "tag_path": "DOOR.AUTOMATIC", "parent": "DOOR", "definition": "Puerta automática", "status": "ACTIVE"}
                        ],
                        "questions": [
                            {"id": "Q::DEMO1", "tag_path": "DOOR.TYPE", "question_text": "¿Cuál es el tipo de puerta?", "answer_type": "ENUM", "enum_values": ["SWING","SLIDING","FOLDING","AUTOMATIC"]}
                        ],
                        "consequences": [
                            {"id": "C::DEMO1", "kind": "ANNEX", "reference_code": "Anexo III"}
                        ],
                        "locations": [
                            {"id": "L::DEMO1", "type": "PLANNING_ZONE", "code": "R6.2", "parent_codes": ["ES","CAT"]}
                        ],
                    },
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text="> 50 personas",
                attributes={
                    "field_path": "EVACUATION.PERSONS",
                    "operator": ">",
                    "value": 50,
                    "unit": None,
                    "original_text": "> 50 personas",
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text="DOOR.AUTOMATIC",
                attributes={
                    "tag_path": "DOOR.AUTOMATIC",
                    "parent": "DOOR",
                    "definition": "Puerta automática",
                    "status": "ACTIVE",
                },
            ),
        ],
    ),
    # MINIMAL: prohibition norm
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
    # MINIMAL: consequence + question + parameter linkage
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
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text="<= 220 N",
                attributes={
                    "field_path": "DOOR.OPENING.PUSH_FORCE_N",
                    "operator": "<=",
                    "value": 220,
                    "unit": "N",
                    "original_text": "<= 220 N",
                },
            ),
            lx.data.Extraction(
                extraction_class="Consequence",
                extraction_text="Anexo III",
                attributes={
                    "kind": "ANNEX",
                    "reference_code": "Anexo III",
                    "description": "Presentación obligatoria",
                },
            ),
            lx.data.Extraction(
                extraction_class="Question",
                extraction_text="¿Qué tipo de puerta automática es?",
                attributes={
                    "tag_path": "DOOR.AUTOMATIC.TYPE",
                    "question_text": "¿Qué tipo de puerta automática es?",
                    "answer_type": "ENUM",
                    "enum_values": ["PEDESTRIAN","INDUSTRIAL"],
                    "outputs": ["DOOR.AUTOMATIC.TYPE"],
                },
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# 2. Sample Input Text (multi-concept to test breadth)
# ---------------------------------------------------------------------------
INPUT_TEXT = (
  "Cuando existan puertas giratorias, deben disponerse puertas abatibles de apertura manual contiguas a ellas, excepto en el caso de que las giratorias sean automáticas y dispongan de un sistema que permita el abatimiento de sus hojas en el sentido de la evacuación, ante una emergencia o incluso en el caso de fallo de suministro eléctrico, mediante la aplicación manual de una fuerza no superior a 220 N.",
      )



# ---------------------------------------------------------------------------
# 3. Validation & Utility Helpers
# ---------------------------------------------------------------------------
TOP_LEVEL_REQUIRED = [
    "schema_version",
    "ontology_version",
    # (dsl_version, run_info) intentionally excluded from strict required list during transition
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


DSL_TOKEN_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)*$")


def validate_rich(obj: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    # Required keys
    for k in TOP_LEVEL_REQUIRED:
        if k not in obj:
            errors.append(f"MISSING_TOP_LEVEL:{k}")
    # Soft missing (transition)
    for soft in ("dsl_version", "run_info"):
        if soft not in obj:
            errors.append(f"WARN_SOFT_MISSING:{soft}")
    # Basic type checks
    for arr_key in ("norms", "tags", "locations", "questions", "consequences", "parameters"):
        if arr_key in obj and not isinstance(obj[arr_key], list):
            errors.append(f"NOT_LIST:{arr_key}")
    # ID uniqueness & reference integrity
    id_sets: Dict[str, Set[str]] = {k: set() for k in ("N", "T", "L", "Q", "C", "P")}
    def collect_ids(prefix: str, items: Iterable[Dict[str, Any]]):
        for it in items:
            _id = it.get("id")
            if not isinstance(_id, str) or not _id.startswith(prefix + "::"):
                errors.append(f"BAD_ID:{_id}")
                continue
            if _id in id_sets[prefix]:
                errors.append(f"DUP_ID:{_id}")
            id_sets[prefix].add(_id)

    collect_ids("N", obj.get("norms", []))
    collect_ids("T", obj.get("tags", []))
    collect_ids("L", obj.get("locations", []))
    collect_ids("Q", obj.get("questions", []))
    collect_ids("C", obj.get("consequences", []))
    collect_ids("P", obj.get("parameters", []))

    # Cross references (best effort) – only flag missing referenced IDs
    all_ids = set().union(*id_sets.values())
    for norm in obj.get("norms", []):
        for ref_list_key in ("extracted_parameters_ids", "consequence_ids"):
            for rid in norm.get(ref_list_key, []) or []:
                if rid not in all_ids:
                    errors.append(f"MISSING_REF:{rid}")
    for cons in obj.get("consequences", []):
        for ref_list_key in ("activates_norm_ids", "activates_question_ids"):
            for rid in cons.get(ref_list_key, []) or []:
                if rid not in all_ids:
                    errors.append(f"MISSING_REF:{rid}")
    # DSL heuristic (light) – ensure ; OR formatting and membership formatting
    for norm in obj.get("norms", [])[:20]:
        for fld in ("applies_if", "satisfied_if", "exempt_if"):
            val = norm.get(fld)
            if not isinstance(val, str) or val in ("TRUE", "null", "None", ""):
                continue
            # basic check: uppercase OR usage for alternatives separated by '; OR '
            if "; OR" in val and not val.count("; OR "):
                errors.append(f"ALT_FORMAT:{fld}")
    return errors


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
    for param in obj.get("parameters", []):
        fp = param.get("field_path")
        if isinstance(fp, str):
            keys.add(fp)
    return keys

# ---------------------------------------------------------------------------
# 3b. Enrichment / Repair Helpers (post-model)
# ---------------------------------------------------------------------------
PARAM_PATTERN = re.compile(r"(?P<field>[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)+)\s*(?P<op>>=|<=|==|!=|>|<)\s*(?P<val>-?\d+(?:\.\d+)?)")
UNIT_NUMBER_PATTERN = re.compile(r"(?P<val>\d+(?:\.\d+)?)\s?(?P<unit>N|m|kg|personas?|N/m2|kg/m2)\b", re.IGNORECASE)

ParamKey = Tuple[str, str, float, Optional[str]]

def build_existing_param_index(obj: Dict[str, Any]) -> Dict[ParamKey, Dict[str,Any]]:
    index: Dict[ParamKey, Dict[str,Any]] = {}
    for p in obj.get("parameters", []):
        try:
            key = (p.get("field_path"), p.get("operator"), float(p.get("value")), p.get("unit"))
            index[key] = p
        except Exception:
            continue
    return index

def enrich_parameters(obj: Dict[str, Any]):
    """Derive parameter objects from DSL expressions & Norm text if missing.
    Non-destructive: adds only new parameters and links them to norms.
    """
    norms = obj.get("norms", [])
    params = obj.setdefault("parameters", [])
    index = build_existing_param_index(obj)
    next_id_int = len(params) + 1
    created = 0
    for norm in norms:
        collected_ids = set(norm.get("extracted_parameters_ids") or [])
        # DSL fields
        for fld in ("applies_if", "satisfied_if", "exempt_if"):
            expr = norm.get(fld)
            if not isinstance(expr, str):
                continue
            for m in PARAM_PATTERN.finditer(expr):
                field_path = m.group("field")
                op = m.group("op")
                val = float(m.group("val"))
                unit = None  # unit not in DSL component; may capture from norm text later
                key = (field_path, op, val, unit)
                if key not in index:
                    pid = f"P::{next_id_int:04d}"
                    param_obj = {
                        "id": pid,
                        "field_path": field_path,
                        "operator": op,
                        "value": val if val % 1 else int(val),
                        "unit": unit,
                        "original_text": None,
                        "norm_ids": [norm.get("id")],
                        "confidence": 0.75,
                        "uncertainty": 0.25,
                    }
                    params.append(param_obj)
                    index[key] = param_obj
                    next_id_int += 1
                    created += 1
                else:
                    index[key].setdefault("norm_ids", [])
                    nid = norm.get("id")
                    if nid and nid not in index[key]["norm_ids"]:
                        index[key]["norm_ids"].append(nid)
                # ensure linkage in norm
                pid = index[key]["id"]
                if pid not in collected_ids:
                    collected_ids.add(pid)
        # attempt capture of numeric with unit inside Norm text
        text_snip = norm.get("statement_text") or norm.get("Norm") or ""
        for mu in UNIT_NUMBER_PATTERN.finditer(text_snip):
            val = float(mu.group("val"))
            unit_found: Optional[str] = mu.group("unit").upper() if mu.group("unit") else None
            field_path = "DOOR.OPENING.PUSH_FORCE_N" if unit_found == "N" else None
            if not field_path:
                continue
            op = "<="
            key_u = (field_path, op, val, unit_found)
            if key_u not in index:
                pid = f"P::{next_id_int:04d}"
                param_obj = {
                    "id": pid,
                    "field_path": field_path,
                    "operator": op,
                    "value": val if val % 1 else int(val),
                    "unit": unit_found,
                    "original_text": mu.group(0),
                    "norm_ids": [norm.get("id")],
                    "confidence": 0.65,
                    "uncertainty": 0.35,
                }
                params.append(param_obj)
                index[key_u] = param_obj
                next_id_int += 1
                created += 1
            else:
                nid = norm.get("id")
                if nid and nid not in index[key_u]["norm_ids"]:
                    index[key_u]["norm_ids"].append(nid)
            pid = index[key_u]["id"]
            collected_ids.add(pid)
        if collected_ids:
            norm["extracted_parameters_ids"] = sorted(collected_ids)
    if created:
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"PARAMETERS_ENRICHED:{created}")

def merge_duplicate_tags(obj: Dict[str, Any]):
    """Collapse duplicate ACTIVE tags with identical tag_path marking extras as MERGED."""
    tags = obj.get("tags", [])
    seen: Dict[str, Dict[str, Any]] = {}
    merged = 0
    for t in tags:
        if not isinstance(t, dict):
            continue
        path = t.get("tag_path")
        status = t.get("status")
        if not path or status != "ACTIVE":
            continue
        if path in seen:
            # mark duplicate as MERGED
            t["status"] = "MERGED"
            t["merge_target"] = path
            merged += 1
        else:
            seen[path] = t
    if merged:
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"DUPLICATE_TAGS_MERGED:{merged}")

def apply_enrichment_pipeline(obj: Dict[str, Any]):
    enrich_parameters(obj)
    merge_duplicate_tags(obj)
    autophrase_questions(obj)
    if TEACH_MODE:
        infer_relationships(obj)

# ---------------------------------------------------------------------------
# 3c. Relationship Inference (Tags, Questions, Consequences, Locations)
# ---------------------------------------------------------------------------
LOCATION_CODE_FIELDS = ["ZONES", "PROVINCES", "REGIONS", "STATES", "COMMUNES", "GEO_CODES"]
SINGLE_QUOTED_LITERAL_PATTERN = re.compile(r"'([^'\\]{1,40})'")

def ensure_tag(obj: Dict[str, Any], tag_path: str) -> Optional[str]:
    if not tag_path or not isinstance(tag_path, str):
        return None
    tags = obj.setdefault("tags", [])
    for t in tags:
        if t.get("tag_path") == tag_path:
            return t.get("id")
    # create new tag id
    new_id = f"T::{len(tags)+1:04d}"
    parent = tag_path.rsplit('.', 1)[0] if '.' in tag_path else None
    tags.append({
        "id": new_id,
        "tag_path": tag_path,
        "parent": parent,
        "definition": "AUTO-GENERATED PLACEHOLDER",
        "status": "ACTIVE",
    })
    obj.setdefault("quality", {}).setdefault("warnings", []).append(f"PLACEHOLDER_TAG_CREATED:{tag_path}")
    return new_id

def infer_relationships(obj: Dict[str, Any]):
    id_index = {item.get("id"): item for k in ("norms","tags","locations","questions","consequences","parameters") for item in obj.get(k, []) if isinstance(item, dict)}
    tag_by_path = {t.get("tag_path"): t for t in obj.get("tags", []) if isinstance(t, dict)}
    # 1. Questions -> ensure tag existence & outputs tags
    for q in obj.get("questions", []):
        tp = q.get("tag_path")
        if tp and tp not in tag_by_path:
            ensure_tag(obj, tp)
        for out in q.get("outputs", []) or []:
            if isinstance(out, str) and out not in tag_by_path:
                ensure_tag(obj, out)
    # Refresh tag index after possible additions
    tag_by_path = {t.get("tag_path"): t for t in obj.get("tags", []) if isinstance(t, dict)}
    # 2. Consequence ↔ Norm linking via ANNEX code in Norm DSL and consequence reference_code
    annex_map: Dict[str, List[Dict[str, Any]]] = {}
    for cons in obj.get("consequences", []):
        code = cons.get("reference_code")
        if code:
            annex_map.setdefault(code, []).append(cons)
    for norm in obj.get("norms", []):
        for fld in ("satisfied_if","applies_if","exempt_if"):
            expr = norm.get(fld)
            if not isinstance(expr, str):
                continue
            # pattern ANNEX.<CODE>.SUBMITTED
            for m in re.finditer(r"ANNEX\.([A-Z0-9_]+)\.SUBMITTED", expr):
                code = f"Anexo {m.group(1)}" if not m.group(1).startswith("Anexo") else m.group(1)
                if code in annex_map:
                    for cons in annex_map[code]:
                        # link norm -> consequence
                        cid = cons.get("id") or ensure_consequence_id(cons, obj)
                        norm.setdefault("consequence_ids", [])
                        if cid not in norm["consequence_ids"]:
                            norm["consequence_ids"].append(cid)
                        # link consequence -> norm
                        cons.setdefault("source_norm_ids", [])
                        nid = norm.get("id")
                        if nid and nid not in cons["source_norm_ids"]:
                            cons["source_norm_ids"].append(nid)
    # 3. Location codes propagation from DSL literals
    location_codes = {loc.get("code"): loc for loc in obj.get("locations", []) if isinstance(loc, dict)}
    for norm in obj.get("norms", []):
        collected = []
        for fld in ("applies_if","satisfied_if","exempt_if"):
            expr = norm.get(fld)
            if not isinstance(expr, str):
                continue
            for lit in SINGLE_QUOTED_LITERAL_PATTERN.findall(expr):
                if lit in location_codes:
                    collected.append(lit)
        if collected:
            scope = norm.setdefault("location_scope", {})
            scope.setdefault("COUNTRY", "ES")
            for arr_name in LOCATION_CODE_FIELDS:
                scope.setdefault(arr_name, [])
            # naive classification: treat codes with pattern letter+digits+dot as ZONES
            for code in sorted(set(collected)):
                if code not in scope["ZONES"]:
                    scope["ZONES"].append(code)

def ensure_consequence_id(cons: Dict[str, Any], obj: Dict[str, Any]) -> str:
    if cons.get("id"):
        return cons["id"]
    cons_list = obj.get("consequences", [])
    new_id = f"C::{len(cons_list)+1:04d}"
    cons["id"] = new_id
    return new_id

def compute_extended_metrics(obj: Dict[str, Any]) -> Dict[str, float]:
    tags = obj.get("tags", [])
    questions = obj.get("questions", [])
    consequences = obj.get("consequences", [])
    norms = obj.get("norms", [])
    tag_paths = {t.get("tag_path") for t in tags if t.get("tag_path")}
    q_align = 0
    for q in questions:
        if q.get("tag_path") in tag_paths:
            q_align += 1
    question_tag_alignment_rate = q_align/len(questions) if questions else 0.0
    cons_linked = 0
    for c in consequences:
        if c.get("source_norm_ids") or c.get("activates_norm_ids"):
            cons_linked += 1
    consequence_linkage_rate = cons_linked/len(consequences) if consequences else 0.0
    # location scope population
    norms_with_codes = 0
    for n in norms:
        loc_scope = n.get("location_scope") or {}
        if any(loc_scope.get(k) for k in ("ZONES","PROVINCES","REGIONS","STATES","COMMUNES","GEO_CODES")):
            norms_with_codes += 1
    location_scope_population_rate = norms_with_codes/len(norms) if norms else 0.0
    return {
        "question_tag_alignment_rate": round(question_tag_alignment_rate,3),
        "consequence_linkage_rate": round(consequence_linkage_rate,3),
        "location_scope_population_rate": round(location_scope_population_rate,3),
    }

QUESTION_VERB_MAP = {
    "TYPE": "¿Cuál es el tipo?",
    "METHOD": "¿Cuál es el método?",
    "SYSTEM": "¿Qué sistema se utiliza?",
    "CLASS": "¿Cuál es la clase?",
    "RATING": "¿Cuál es la clasificación?",
}

def humanize_segment(seg: str) -> str:
    seg_clean = seg.replace('_',' ').lower()
    return seg_clean

def build_question_from_tag_path(tag_path: str) -> str:
    parts = tag_path.split('.') if tag_path else []
    leaf = parts[-1] if parts else ''
    if leaf in QUESTION_VERB_MAP:
        return QUESTION_VERB_MAP[leaf]
    # Generic fallback
    base = humanize_segment(leaf or 'valor')
    return f"¿Cuál es el {base}?" if not base.endswith('?') else base

def autophrase_questions(obj: Dict[str, Any]):
    qs = obj.get("questions", [])
    created = 0
    for q in qs:
        if q.get("question_text"):
            continue
        tp = q.get("tag_path") or (q.get("outputs") or [None])[0]
        if not isinstance(tp, str):
            continue
        phrased = build_question_from_tag_path(tp)
        q["question_text"] = phrased + " (auto)"
        created += 1
    if created:
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"AUTO_QUESTION_PHRASED:{created}")


# ---------------------------------------------------------------------------
# 4. Execute Extraction (manual chunking + aggregation)
# ---------------------------------------------------------------------------

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
