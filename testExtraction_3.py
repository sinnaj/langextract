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

from dotenv import load_dotenv
import langextract as lx

# ---------------------------------------------------------------------------
# 0. Environment / Config
# ---------------------------------------------------------------------------
load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY not set – model call will likely fail.", file=sys.stderr)

PROMPT_FILE = Path("prompts/extraction_prompt.md")
OUTPUT_FILE = Path("rich_norms_full.json")
GLOSSARY_FILE = Path("dsl_glossary.json")
MAX_NORMS_PER_5K = 10  # matches spec guidance
MODEL_ID = "gemini-2.5-flash"
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
    # Example A: MANDATORY Norm with alternatives & exemption + embedded rich demo
    lx.data.ExampleData(
        text=(
            "1 Las puertas de salida para la evacuación de más de 50 personas deben ser abatibles con eje vertical y permitir apertura sin llave o mantener el sistema de cierre desactivado durante la actividad."
            "Se incluye solamente las puertas que forman parte del itinerario principal de evacuación y que sirven a ocupaciones simultáneas."
            "La exigencia se centra en reducir fricción operativa y eliminar barreras de salida en situaciones de emergencia."
            "La alternativa de mantener el sistema de cierre desactivado es válida siempre que el control de acceso quede asegurado por otros medios pasivos."
            "No se aplica a puertas automáticas con sistema de abatimiento seguro que garantice apertura libre en caso de fallo energético."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Las puertas de salida para la evacuación de más de 50 personas deben ser abatibles con eje vertical y permitir apertura sin llave "
                    "o mantener el sistema de cierre desactivado durante la actividad."
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
                    # Pedagogical micro multi-array snapshot (placeholder IDs)
                    "rich_demo": {
                        "norms": [
                            {
                                "id": "N::DEMO1",
                                "obligation_type": "MANDATORY",
                                "priority": 5,
                                "extracted_parameters_ids": ["P::DEMO1"],
                                "consequence_ids": ["C::DEMO1"],
                                "relevant_tags": ["DOOR.AUTOMATIC", "EVACUATION"],
                            }
                        ],
                        "tags": [
                            {
                                "id": "T::DEMO1",
                                "tag_path": "DOOR.AUTOMATIC",
                                "parent": "DOOR",
                                "definition": "Puerta accionada automáticamente",
                                "status": "ACTIVE",
                            }
                        ],
                        "parameters": [
                            {
                                "id": "P::DEMO1",
                                "field_path": "DOOR.OPENING.MECHANISMS_COUNT",
                                "operator": "<=",
                                "value": 1,
                                "unit": None,
                            }
                        ],
                        "questions": [
                            {
                                "id": "Q::DEMO1",
                                "tag_path": "DOOR.TYPE",
                                "question_text": "¿Cuál es el tipo de puerta?",
                                "answer_type": "ENUM",
                                "enum_values": [
                                    "SWING",
                                    "SLIDING",
                                    "FOLDING",
                                    "AUTOMATIC",
                                    "AUTOMATIC_PEDESTRIAN",
                                ],
                            }
                        ],
                        "consequences": [
                            {
                                "id": "C::DEMO1",
                                "kind": "ANNEX",
                                "reference_code": "Anexo III",
                                "source_norm_ids": ["N::DEMO1"],
                                "activates_question_ids": ["Q::DEMO1"],
                            }
                        ],
                        "locations": [
                            {
                                "id": "L::DEMO1",
                                "type": "PLANNING_ZONE",
                                "code": "R6.2",
                                "parent_codes": ["ES", "CAT", "BARCELONA"],
                            }
                        ],
                    },
                },
            )
        ],
    ),
    # Example B: PROHIBITION Norm (negative phrasing)
    lx.data.ExampleData(
        text=(
            "2 No se admite la instalación de dispositivos que requieran llave en la ruta de evacuación principal cuando la ocupación sea superior a 100 personas."
            "La 'ruta de evacuación principal' comprende vestíbulos, corredores y puertas de salida de planta designadas como primarias."
            "Esta prohibición evita retrasos de apertura generados por localización de llaves u obstrucciones de mecanismos."
            "El criterio de ocupación se evalúa sobre el cálculo aprobado y no sobre mediciones eventuales de uso real."
            "Se aceptan mecanismos accionados por barra antipánico que no requieren llave para desbloqueo desde el interior."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "No se admite la instalación de dispositivos que requieran llave en la ruta de evacuación principal cuando la ocupación sea superior a 100 personas."
                ),
                attributes={
                    "paragraph_number": 2,
                    "applies_if": "EVACUATION.PERSONS > 100 AND ROUTE.ACCESSIBLE == TRUE",
                    "satisfied_if": "DOOR.OPENING.REQUIRES_KEY == FALSE",
                    "exempt_if": None,
                },
            )
        ],
    ),
    # Example C: Standalone ontology & parameter emergence plus consequence and question
    lx.data.ExampleData(
        text=(
            "En la zona urbanística R6.2 se requerirá la presentación del Anexo III para cualquier reforma estructural que afecte salidas de emergencia."
            "La mención a la zona R6.2 implica verificación de código urbanístico local y su jerarquía administrativa."
            "El Anexo III documenta medidas de seguridad y justificaciones técnicas asociadas a la intervención."
            "La fuerza de apertura máxima permitida para salidas de emergencia se controla mediante parámetros adicionales (<= 220 N)."
            "Las reformas menores de acabado que no alteren elementos de evacuación quedan excluidas implícitamente."
        ),
        extractions=[
            # A conditional Norm referencing a parameter & consequence
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Se requerirá la presentación del Anexo III para cualquier reforma estructural que afecte salidas de emergencia."
                ),
                attributes={
                    "paragraph_number": 4,
                    "applies_if": "ZONE.CODE == 'R6.2' AND WORK.TYPE IN['CONSTRUCTION.STRUCTURAL','REFORM']",
                    "satisfied_if": "ANNEX.ANEXO_III.SUBMITTED == TRUE",
                    "exempt_if": None,
                },
            ),
            # Tag introduction
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text="DOOR.AUTOMATIC.PEDESTRIAN",
                attributes={
                    "tag_path": "DOOR.AUTOMATIC.PEDESTRIAN",
                    "parent": "DOOR.AUTOMATIC",
                    "definition": "Puerta automática destinada a tránsito peatonal",
                    "status": "ACTIVE",
                },
            ),
            # Location entity
            lx.data.Extraction(
                extraction_class="Location",
                extraction_text="R6.2",
                attributes={
                    "type": "PLANNING_ZONE",
                    "code": "R6.2",
                    "parent_codes": ["ES", "CAT"],
                },
            ),
            # Parameter
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text="220 N",
                attributes={
                    "field_path": "DOOR.OPENING.PUSH_FORCE_N",
                    "operator": "<=",
                    "value": 220,
                    "unit": "N",
                    "original_text": "<= 220 N",
                },
            ),
            # Consequence (Annex)
            lx.data.Extraction(
                extraction_class="Consequence",
                extraction_text="Anexo III",
                attributes={
                    "kind": "ANNEX",
                    "reference_code": "Anexo III",
                    "description": "Presentación del Anexo III obligatoria en zona R6.2",
                },
            ),
            # Question triggered by tag variability
            lx.data.Extraction(
                extraction_class="Question",
                extraction_text="¿Qué tipo de puerta automática es?",
                attributes={
                    "tag_path": "DOOR.AUTOMATIC.TYPE",
                    "question_text": "¿Qué tipo de puerta automática es?",
                    "answer_type": "ENUM",
                    "enum_values": ["PEDESTRIAN", "INDUSTRIAL"],
                    "outputs": ["DOOR.AUTOMATIC.TYPE"],
                },
            ),
        ],
    ),
    # Example D: OPTIONAL Norm with multi-parameter IN[] list, NOT operator, HAS() predicate and decimal value capture
    lx.data.ExampleData(
        text=(
            "7 Para recintos de reunión de tipo A o B con ocupación entre 80 y 150 personas se recomienda disponer de apertura asistida."
            "El carácter de recomendación implica mejora de usabilidad y reducción de fatiga operativa."
            "Se activa la recomendación cuando la fuerza manual excede 180 N o el peso de la hoja supera 65 kg."
            "Un mecanismo redundante certificado puede justificar la no adopción del sistema asistido."
            "La evaluación de peso se basa en la hoja individual y no en conjuntos múltiples articulados."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Se recomienda disponer de sistema de apertura asistida si la fuerza manual excede 180 N o la puerta pesa más de 65 kg."
                ),
                attributes={
                    "paragraph_number": 7,
                    "obligation_type": "RECOMMENDATION",
                    "applies_if": "VENUE.TYPE IN['A','B'] AND OCCUPANCY.PERSONS >= 80 AND OCCUPANCY.PERSONS <= 150",
                    "satisfied_if": "(DOOR.OPENING.ASSISTED == TRUE); OR (DOOR.OPENING.PUSH_FORCE_N <= 180); OR (DOOR.WEIGHT_KG <= 65)",
                    "exempt_if": "HAS(DOOR.MECHANISM.REDUNDANT_CERTIFIED) AND NOT DOOR.OPENING.ASSISTED",
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text="180 N",
                attributes={
                    "field_path": "DOOR.OPENING.PUSH_FORCE_N",
                    "operator": ">",
                    "value": 180,
                    "unit": "N",
                    "original_text": "> 180 N",
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text="65 kg",
                attributes={
                    "field_path": "DOOR.WEIGHT_KG",
                    "operator": ">",
                    "value": 65,
                    "unit": "kg",
                    "original_text": "> 65 kg",
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text="DOOR.MECHANISM.REDUNDANT_CERTIFIED",
                attributes={
                    "tag_path": "DOOR.MECHANISM.REDUNDANT_CERTIFIED",
                    "parent": "DOOR.MECHANISM",
                    "definition": "Mecanismo redundante con certificación homologada",
                    "status": "ACTIVE",
                },
            ),
        ],
    ),
    # Example E: PROHIBITION with ADJACENT_TO and OVERLAPS geo logic & location, plus consequence referencing future annex
    lx.data.ExampleData(
        text=(
            "8 No se permitirá instalar salidas de emergencia que abran hacia zonas de carga con interferencias de riesgo."
            "La condición aplica si el área de evacuación se superpone o es adyacente a la zona de almacenamiento peligrosa ZH-41."
            "Se busca evitar corrientes cruzadas entre flujos de evacuación y operaciones de manipulación peligrosa."
            "Cuando exista esta proximidad, se exige un rediseño de orientación o barrera física validada."
            "El incumplimiento desencadena requerimiento de informe técnico adicional (Anexo IV)."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "No se permitirá instalar salidas de emergencia que abran hacia zonas de carga si el área de evacuación se superpone o es adyacente a una zona de almacenamiento de materiales peligrosos ZH-41."
                ),
                attributes={
                    "paragraph_number": 8,
                    "obligation_type": "PROHIBITION",
                    "applies_if": "EVACUATION.AREA.OVERLAPS('ZH-41') OR EVACUATION.AREA.ADJACENT_TO('ZH-41')",
                    "satisfied_if": "EMERGENCY.EXIT.ORIENTATION != 'TOWARDS_LOADING_AREA'",
                    "exempt_if": "STORAGE.MATERIALS_HAZARD_CLASS NOT IN['P1','P2']",
                },
            ),
            lx.data.Extraction(
                extraction_class="Location",
                extraction_text="ZH-41",
                attributes={
                    "type": "INDUSTRIAL_ZONE",
                    "code": "ZH-41",
                    "parent_codes": ["ES", "CAT", "BARCELONA"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Consequence",
                extraction_text="Anexo IV",
                attributes={
                    "kind": "ANNEX",
                    "reference_code": "Anexo IV",
                    "description": "Requiere informe técnico adicional por proximidad a zona peligrosa",
                },
            ),
        ],
    ),
    # Example F: OPTIONAL norm with question enumeration & parameter reuse, demonstrates HAS() negation
    lx.data.ExampleData(
        text=(
            "9 Se podrá omitir el dispositivo de cierre automático bajo condiciones específicas controladas."
            "Debe existir sistema de supervisión activo y la ocupación servida ser <= 45 personas."
            "La puerta no debe poseer clasificación cortafuego ya que perdería una función de contención crítica."
            "La supervisión puede ser continua, temporizada o inexistente (caso que desactiva la posibilidad de omisión)."
            "Se interroga al operador: ¿Cuál es el sistema de supervisión instalado?"
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Se podrá omitir el dispositivo de cierre automático si la puerta peatonal automática dispone de sistema de supervisión y la ocupación servida es <= 45 personas, siempre que no sea cortafuego."
                ),
                attributes={
                    "paragraph_number": 9,
                    "obligation_type": "OPTIONAL",
                    "applies_if": "DOOR.TYPE == 'AUTOMATIC_PEDESTRIAN' AND HAS(DOOR.SUPERVISION.SYSTEM) AND OCCUPANCY.SERVED <= 45",
                    "satisfied_if": "DOOR.CLOSING.AUTOMATIC_DEVICE == FALSE",
                    "exempt_if": "DOOR.FIRE_RATING == 'FIRE_RESISTANT'",
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text="<= 45 personas",
                attributes={
                    "field_path": "OCCUPANCY.SERVED",
                    "operator": "<=",
                    "value": 45,
                    "unit": "PERSONAS",
                    "original_text": "<= 45 personas",
                },
            ),
            lx.data.Extraction(
                extraction_class="Question",
                extraction_text="¿Cuál es el sistema de supervisión instalado?",
                attributes={
                    "tag_path": "DOOR.SUPERVISION.SYSTEM",
                    "question_text": "¿Cuál es el sistema de supervisión instalado?",
                    "answer_type": "ENUM",
                    "enum_values": ["SENSOR_CONTINUO", "TEMPORIZADO", "NINGUNO"],
                    "outputs": ["DOOR.SUPERVISION.SYSTEM"],
                },
            ),
        ],
    ),
    # Example G: Consequence activating multiple norms & questions; tag hierarchy depth 4
    lx.data.ExampleData(
        text=(
            "10 La activación del protocolo de evacuación avanzada (Anexo V) obedece a umbrales combinados."
            "Se activa cuando la fuerza de apertura excede 220 N en más de dos puertas críticas designadas."
            "También se activa cuando el sistema de supervisión declarado es 'NINGUNO'."
            "La finalidad del protocolo es incrementar vigilancia operacional y redundancia documental."
            "El Anexo V consolida procedimientos escalonados y verificaciones post-evento."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Consequence",
                extraction_text="Anexo V",
                attributes={
                    "kind": "ANNEX",
                    "reference_code": "Anexo V",
                    "description": "Protocolo de evacuación avanzada",
                    # The model in full output should fill in source_norm_ids / activates_question_ids appropriately
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text="DOOR.OPENING.MONITOR.METHOD",
                attributes={
                    "tag_path": "DOOR.OPENING.MONITOR.METHOD",
                    "parent": "DOOR.OPENING.MONITOR",
                    "definition": "Método de monitorización de apertura de puerta",
                    "status": "ACTIVE",
                },
            ),
            lx.data.Extraction(
                extraction_class="Question",
                extraction_text="¿Qué método de monitorización de apertura está instalado?",
                attributes={
                    "tag_path": "DOOR.OPENING.MONITOR.METHOD",
                    "question_text": "¿Qué método de monitorización de apertura está instalado?",
                    "answer_type": "ENUM",
                    "enum_values": ["SENSOR_CONTINUO", "TEMPORIZADO", "NINGUNO"],
                    "outputs": ["DOOR.OPENING.MONITOR.METHOD"],
                },
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# 2. Sample Input Text (multi-concept to test breadth)
# ---------------------------------------------------------------------------
INPUT_TEXT = (
    "1 Las puertas de salida para la evacuación de más de 50 personas deben ser abatibles con eje vertical y permitir apertura sin llave o mantener el sistema de cierre desactivado durante la actividad. "
    "No se aplica a puertas automáticas con sistema de abatimiento seguro. "
    "2 No se admite la instalación de dispositivos que requieran llave en la ruta de evacuación principal cuando la ocupación sea superior a 100 personas. "
    "3 Para edificios de uso Residencial Vivienda en la Provincia de Barcelona (CAT) la puerta principal de evacuación abrirá en el sentido de la salida cuando SERVED personas exceda 200. "
    "4 En la zona urbanística R6.2 se requerirá la presentación del Anexo III para cualquier reforma estructural que afecte salidas de emergencia. "
    "5 Cuando exista fallo de suministro eléctrico o señal de emergencia las puertas peatonales automáticas correderas o plegables deberán abrir y mantenerse abiertas o permitir apertura abatible con fuerza <= 220 N. "
    "6 Cuando la puerta esté situada en itinerario accesible según DB SUA la fuerza para apertura abatible no excederá 25 N (65 N si resistente al fuego)."
)


# ---------------------------------------------------------------------------
# 3. Validation & Utility Helpers
# ---------------------------------------------------------------------------
TOP_LEVEL_REQUIRED = [
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


def is_rich_schema(d: Any) -> bool:
    return isinstance(d, dict) and all(k in d for k in TOP_LEVEL_REQUIRED)


def legacy_wrap(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap classic `extractions` output into rich schema skeleton.

    This is a last-resort fallback; downstream logic should still function albeit with sparse fields.
    """
    raw_extractions = doc.get("extractions", [])
    norms: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_extractions, start=1):
        attrs = item.get("Norm_attributes") or item.get("attributes", {})
        norms.append(
            {
                "id": f"N::{idx:04d}",
                "Norm": item.get("Norm", item.get("extraction_text", "")),
                "obligation_type": "MANDATORY",
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
                    "UNCERTAINTY": 1.0,
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
                "notes": "Legacy fallback",
            }
        )

    return {
        "schema_version": "1.0.0",
        "ontology_version": "0.0.1",
        "truncated": False,
        "has_more": False,
        "window_config": {
            "input_chars": len(INPUT_TEXT),
            "max_norms_per_5k_tokens": MAX_NORMS_PER_5K,
            "extracted_norm_count": len(norms),
        },
        "global_disclaimer": "NO LEGAL ADVICE",
        "document_metadata": {
            "doc_id": "UNKNOWN",
            "doc_title": None,
            "source_language": "es",
            "received_chunk_span": {"char_start": 0, "char_end": len(INPUT_TEXT)},
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


DSL_TOKEN_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)*$")


def validate_rich(obj: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    # Required keys
    for k in TOP_LEVEL_REQUIRED:
        if k not in obj:
            errors.append(f"MISSING_TOP_LEVEL:{k}")
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
        text_snip = norm.get("Norm") or ""
        for mu in UNIT_NUMBER_PATTERN.finditer(text_snip):
            val = float(mu.group("val"))
            unit_found: Optional[str] = mu.group("unit").upper() if mu.group("unit") else None
            # Guess field_path from nearby heuristic tokens
            field_path = "DOOR.OPENING.PUSH_FORCE_N" if unit_found == "N" else None
            if not field_path:
                continue
            op = "<="  # heuristic default; refine later
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
    collapsed = []
    for t in tags:
        path = t.get("tag_path")
        status = t.get("status", "ACTIVE")
        if not path or status != "ACTIVE":
            continue
        if path not in seen:
            seen[path] = t
        else:
            # merge duplicate
            t["status"] = "MERGED"
            t["merge_target"] = path
            collapsed.append(path)
    if collapsed:
        obj.setdefault("quality", {}).setdefault("warnings", []).extend(sorted(set(f"DUPLICATE_TAG_COLLAPSED:{c}" for c in collapsed)))

def repair_cross_refs(obj: Dict[str, Any]):
    """Ensure all referenced IDs exist; remove dangling references or create placeholders (prefer removal to fabrication)."""
    id_map = {item.get("id"): item for key in ("norms","tags","locations","questions","consequences","parameters") for item in obj.get(key, []) if isinstance(item, dict) and item.get("id")}
    # Norm references
    for norm in obj.get("norms", []):
        for fld in ("extracted_parameters_ids", "consequence_ids"):
            ids = norm.get(fld)
            if not ids:
                continue
            norm[fld] = [i for i in ids if i in id_map]
    # Consequence activations
    for cons in obj.get("consequences", []):
        for fld in ("activates_norm_ids", "activates_question_ids"):
            ids = cons.get(fld)
            if not ids:
                continue
            cons[fld] = [i for i in ids if i in id_map]

def compute_metrics(obj: Dict[str, Any]) -> Dict[str, float]:
    norms = obj.get("norms", [])
    params = obj.get("parameters", [])
    questions = obj.get("questions", [])
    tags = obj.get("tags", [])
    # Parameter reuse ratio: average norm_ids per parameter
    if params:
        avg_param_reuse = sum(len(p.get("norm_ids", [])) for p in params)/len(params)
    else:
        avg_param_reuse = 0.0
    # Question coverage: fraction of root-level tags (depth 1) that have questions referencing them (tag_path exact match or prefix)
    root_tags = {t.get("tag_path") for t in tags if t.get("tag_path") and t.get("tag_path").count('.')==0}
    questioned = set()
    for q in questions:
        tp = q.get("tag_path")
        if not isinstance(tp, str):
            continue
        root = tp.split('.')[0]
        questioned.add(root)
    root_coverage = (len(questioned & root_tags)/len(root_tags)) if root_tags else 0.0
    return {
        "avg_param_reuse": round(avg_param_reuse, 3),
        "root_question_coverage": round(root_coverage, 3),
        "norm_count": float(len(norms)),
    }

def apply_enrichment_pipeline(obj: Dict[str, Any]):
    enrich_parameters(obj)
    merge_duplicate_tags(obj)
    repair_cross_refs(obj)
    autophrase_questions(obj)
    metrics = compute_metrics(obj)
    # Store metrics as warnings (non-breaking) for observability
    obj.setdefault("quality", {}).setdefault("warnings", []).append(f"METRICS:{json.dumps(metrics)}")
    # Extended relationship inference & metrics (teach mode only)
    if TEACH_MODE:
        infer_relationships(obj)
        extended = compute_extended_metrics(obj)
        obj.setdefault("quality", {}).setdefault("warnings", []).append(f"EXT_METRICS:{json.dumps(extended)}")

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
# 4. Execute Extraction
# ---------------------------------------------------------------------------
print("[INFO] Invoking model for rich extraction ...")
result = lx.extract(
    text_or_documents=INPUT_TEXT,
    prompt_description=PROMPT_DESCRIPTION,
    examples=EXAMPLES,
    model_id=MODEL_ID,
    api_key=GOOGLE_API_KEY,
    fence_output=False,
    use_schema_constraints=False,
    temperature=MODEL_TEMPERATURE,
    resolver_params={
        "fence_output": False,
        "format_type": lx.data.FormatType.JSON,
    },
    language_model_params={"temperature": MODEL_TEMPERATURE},
)


# Try to access raw JSON directly if model produced it verbatim.
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

parsed: Dict[str, Any] | None = None
if to_parse:
    try:
        parsed = json.loads(to_parse)
    except Exception:
        parsed = None

if parsed is None:
    # Convert annotated doc (legacy style) -> potential dict
    from langextract import data_lib  # local import to avoid overhead earlier

    legacy_dict = data_lib.annotated_document_to_dict(result)
    if is_rich_schema(legacy_dict):
        parsed = legacy_dict
    else:
        parsed = legacy_dict  # maybe has only 'extractions'

if not is_rich_schema(parsed):
    print("[WARN] Model did not emit full rich schema – applying legacy wrapper.")
    parsed = legacy_wrap(parsed)

# Validate structure & append any errors
schema_errors = validate_rich(parsed)
if schema_errors:
    parsed.setdefault("quality", {}).setdefault("errors", []).extend(schema_errors)

# Ensure window_config present & updated counts if model omitted or incorrect.
wc = parsed.setdefault("window_config", {})
wc.setdefault("input_chars", len(INPUT_TEXT))
wc.setdefault("max_norms_per_5k_tokens", MAX_NORMS_PER_5K)
wc["extracted_norm_count"] = len(parsed.get("norms", []))

# Optional enrichment (post-validation) – only if teach mode or explicitly requested
if TEACH_MODE:
    apply_enrichment_pipeline(parsed)

# ---------------------------------------------------------------------------
# 5. Persist Result
# ---------------------------------------------------------------------------
OUTPUT_FILE.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved rich schema JSON → {OUTPUT_FILE}")

# ---------------------------------------------------------------------------
# 6. DSL Glossary Draft
# ---------------------------------------------------------------------------
dsl_keys = sorted(collect_dsl_keys(parsed))
glossary = {k: "" for k in dsl_keys}
GLOSSARY_FILE.write_text(json.dumps(glossary, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[INFO] Saved DSL glossary stub ({len(dsl_keys)} keys) → {GLOSSARY_FILE}")

# ---------------------------------------------------------------------------
# 7. Console Summary
# ---------------------------------------------------------------------------
print("=== Extraction Summary ===")
print(f"Norms: {len(parsed.get('norms', []))}")
print(f"Tags: {len(parsed.get('tags', []))}")
print(f"Locations: {len(parsed.get('locations', []))}")
print(f"Questions: {len(parsed.get('questions', []))}")
print(f"Consequences: {len(parsed.get('consequences', []))}")
print(f"Parameters: {len(parsed.get('parameters', []))}")
print(f"Errors: {parsed.get('quality', {}).get('errors', [])}")
print(f"Warnings: {parsed.get('quality', {}).get('warnings', [])}")

print("Done.")
