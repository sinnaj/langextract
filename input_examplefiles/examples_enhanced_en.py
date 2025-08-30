"""
Exhaustive example set for LangExtract rich schema extraction.
Covers: obligation types, alternatives, exemptions, DSL operators, enumerations,
locations, tag merges, consequences, parameters (num & string), and branching Qs.
"""

from __future__ import annotations
from typing import List
import langextract as lx


EXAMPLES: List[lx.data.ExampleData] = [
    # 1) RICH: alternatives + exemption + parameters + enumerations
    lx.data.ExampleData(
        text=(
            '1 The exit doors for the evacuation of more than 50 people must be folding with vertical axis and allow opening without key, or keep the locking system disabled during the activity. It does not apply to automatic doors with secure dipping. 2 Installation of key-requiring devices on the main evacuation route is not supported when the occupation exceeds 100 people. 3 In zone R6.2, the presentation of Annex III shall be required when the opening force is < 220 N. 4 Accessible routes must be marked with standard pictogram. 5 In hospitals, automatic doors must be open to power failure, except in operating rooms with specific regulations. 6 It is possible to install outdoor photovoltaic panels in a garden in private single-family homes.'),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    'The exit doors for the evacuation of more than 50 people must be folding with vertical axis and allow opening without key or keep the locking system disabled during the activity. It does not apply to automatic doors with secure dipping.'
                ),
                attributes={
                    "paragraph_number": 1,
                    "obligation_type": "MANDATORY",
                    "applies_if": "EVACUATION.PERSONS > 50",
                    "satisfied_if": (
                        "(DOOR.TYPE == 'SWING' AND DOOR.AXIS == 'VERTICAL' AND DOOR.LOCK_SYSTEM.REQUIRES_KEY == FALSE); OR "
                        "(DOOR.LOCK_SYSTEM == DISABLED OR DOOR.LOCK_SYSTEM == NONE);"
                    ),
                    "exempt_if": "DOOR.TYPE == 'AUTOMATIC' AND HAS(DOOR.OPTION.SWING_ALLOWED)",
                    "topics": ["SAFETY.FIRE"],
                    "project_dimensions": {
                        "PROJECT.TYPE": ["NEW","REFORM"],
                        "WORK.TYPE": ["CONSTRUCTION.DOORS"],
                    },
                    "priority": 5,
                    "priority_factors": {"severity": 0.9, "likelihood": 0.3, "impact": 0.8},
                    "relevant_tags": [
                        "EVACUATION.PERSONS",
                        "DOOR",
                        "DOOR.TYPE",
                        "DOOR.TYPE.AUTOMATIC",
                        "DOOR.TYPE.SWING",
                        "DOOR.AXIS",
                        "DOOR.LOCK_SYSTEM",
                        "DOOR.LOCK_SYSTEM.REQUIRES_KEY",
                        "DOOR.OPTION",
                        "DOOR.OPTION.SWING_ALLOWED",
                    ],
                    "relevant_roles": [],
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": "ES",
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 0.05,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": ["P::EVAC50"],
                    "consequence_ids": [],
                    "confidence": 0.92,
                    "uncertainty": 0.08,
                    "notes": "Puertas de evacuación: requisitos de abatimiento y apertura sin llave; exención para automáticas con abatimiento seguro.",
                    "rich_demo": {
                        "questions": [
                            {
                                "id": "Q::DEMO1",
                                "tag_path": "DOOR.TYPE",
                                "question_text": "¿Cuál es el tipo de puerta?",
                                "answer_type": "ENUM",
                                "enum_values": ["SWING","SLIDING","FOLDING","AUTOMATIC"],
                                "outputs": ["DOOR.TYPE"],
                            }
                        ],
                        "locations": [
                            {"id": "L::DEMO1", "type": "PLANNING_ZONE", "code": "R6.2", "parent_codes": ["ES","CAT"]}
                        ],
                    },
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='> 50 people',
                attributes={
                    "id": "P::0001",
                    "field_path": "EVACUATION.PERSONS",
                    "operator": ">",
                    "value": 50,
                    "unit": None,
                    "original_text": "> 50 personas",
                    "norm_ids": ["N::0001"],
                    "confidence": 0.95,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='EVACUATION.PERSONS',
                attributes={
                    "id": "T::000001",
                    "tag": "EVACUATION.PERSONS",
                    "definition": "Número de personas en evacuación",
                    "synonyms": ["personas en evacuación"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),

            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR',
                attributes={
                    "id": "T::000002",
                    "tag": "DOOR",
                    "definition": "Puerta",
                    "synonyms": ["puerta"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),

            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR.TYPE',
                attributes={
                    "id": "T::000003",
                    "tag": "DOOR.TYPE",
                    "definition": "Tipo de puerta",
                    "synonyms": ["clase de puerta"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),

            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR.AUTOMATIC',
                attributes={
                    "id": "T::000004",
                    "tag": "DOOR.TYPE.AUTOMATIC",
                    "definition": "Puerta automática",
                    "synonyms": ["puerta automática"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),

            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR.TYPE.SWING',
                attributes={
                    "id": "T::000005",
                    "tag": "DOOR.TYPE.SWING",
                    "definition": "Puerta abatible",
                    "synonyms": ["puerta abatible"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),

            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR.AXIS',
                attributes={
                    "id": "T::000006",
                    "tag": "DOOR.AXIS",
                    "definition": "Eje de la puerta",
                    "synonyms": ["eje de la puerta"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR.LOCK_SYSTEM',
                attributes={
                    "id": "T::000007",
                    "tag": "DOOR.LOCK_SYSTEM",
                    "definition": "Sistema de bloqueo de la puerta",
                    "synonyms": ["sistema de bloqueo"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR.LOCK_SYSTEM.REQUIRES_KEY',
                attributes={
                    "id": "T::000008",
                    "tag": "DOOR.LOCK_SYSTEM.REQUIRES_KEY",
                    "definition": "Requiere llave para el sistema de bloqueo",
                    "synonyms": ["requiere llave"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='DOOR.OPTION.SWING_ALLOWED',
                attributes={
                    "id": "T::000009",
                    "tag": "DOOR.OPTION.SWING_ALLOWED",
                    "definition": "Permite apertura abatible",
                    "synonyms": ["apertura abatible permitida"],
                    "used_by_norm_ids": ["N::0001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
        ],
    ),
                      "EVACUATION.PERSONS",
                        "DOOR",
                        "DOOR.TYPE",
                        "DOOR.TYPE.AUTOMATIC",
                        "DOOR.TYPE.SWING",
                        "DOOR.AXIS",
                        "DOOR.LOCK_SYSTEM",
                        "DOOR.LOCK_SYSTEM.REQUIRES_KEY",
                        "DOOR.OPTION.SWING_ALLOWED",

    # 2) MINIMAL PROHIBITION with occupancy trigger
    lx.data.ExampleData(
        text='2 Installation of key-requiring devices on the main evacuation route is not supported when the occupation exceeds 100 people.'       extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='The installation of key-required devices on the main evacuation route is not supported when the occupation exceeds 100 persons.'               attributes={
                    "paragraph_number": 2,
                    "obligation_type": "PROHIBITION",
                    "applies_if": "EVACUATION.PERSONS > 100",
                    "satisfied_if": "DOOR.OPENING.REQUIRES_KEY == FALSE",
                    "exempt_if": None,
                    "topics": ["SAFETY.FIRE"],
                    "priority": 5,
                    "priority_factors": {"severity": 0.9, "likelihood": 0.4, "impact": 0.8},
                    "relevant_tags": ["EVACUATION.PERSONS", "DOOR.OPENING.REQUIRES_KEY"],
                    "relevant_roles": [],
                    "project_dimensions": {},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.9,
                    "uncertainty": 0.1,
                    "notes": "Prohíbe mecanismos con llave en ruta principal para ocupaciones altas.",
                },
            )
        ],
    ),

    # 3) Consequence + question + numeric parameter + zone condition
    lx.data.ExampleData(
        text='In zone R6.2, the presentation of Annex III shall be required when the opening force is < 220 N.'        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='The presentation of Annex III shall be required when the opening force is > 220 N.'                attributes={
                    "paragraph_number": 3,
                    "obligation_type": "MANDATORY",
                    "applies_if": "ZONE.CODE == 'R6.2'",
                    "satisfied_if": "ANNEX.ANEXO_III.SUBMITTED == TRUE",
                    "exempt_if": None,
                    "consequence_ids": ["C::ANX3"],
                    "priority": 3,
                    "priority_factors": {"severity": 0.3, "likelihood": 0.5, "impact": 0.4},
                    "relevant_tags": ["ANNEX.ANEXO_III.SUBMITTED", "ZONE.CODE", "DOOR.OPENING.PUSH_FORCE_N"],
                    "relevant_roles": [],
                    "project_dimensions": {},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": "ES",
                        "STATES": ["CAT"],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": ["R6.2"],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 0.2,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "confidence": 0.86,
                    "uncertainty": 0.14,
                    "notes": "Requiere la presentación del Anexo III en zona R6.2 bajo condición de fuerza de apertura.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='< 220 N',
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
                extraction_text='Annex III',
                attributes={
                    "id": "C::ANX3",
                    "kind": "ANNEX",
                    "reference_code": "Anexo III",
                    "description": "Presentación obligatoria",
                },
            ),
            lx.data.Extraction(
                extraction_class="Question",
                extraction_text='What kind of automatic door is it?'               attributes={
                    "tag_path": "DOOR.AUTOMATIC.TYPE",
                    "question_text": "¿Qué tipo de puerta automática es?",
                    "answer_type": "ENUM",
                    "enum_values": ["PEDESTRIAN","INDUSTRIAL"],
                    "outputs": ["DOOR.AUTOMATIC.TYPE"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Location",
                extraction_text='R6.2',
                attributes={
                    "type": "PLANNING_ZONE",
                    "code": "R6.2",
                    "name": None,
                    "parent_codes": ["ES","CAT"],
                    "classification": ["RESIDENTIAL"],
                },
            ),
        ],
    ),

    # 4) Unconditional accessibility norm + tag creation
    lx.data.ExampleData(
        text='Accessible routes must be marked with standard pictogram.'
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='Accessible routes must be marked with standard pictogram.'
                attributes={
                    "paragraph_number": 1,
                    "obligation_type": "MANDATORY",
                    "applies_if": "TRUE",
                    "satisfied_if": "ROUTE.ACCESSIBLE.SIGNAGE.STANDARDIZED == TRUE",
                    "exempt_if": None,
                    "topics": ["ACCESSIBILITY"],
                    "priority": 3,
                    "priority_factors": {"severity": 0.2, "likelihood": 0.4, "impact": 0.3},
                    "relevant_tags": ["ROUTE.ACCESSIBLE.SIGNAGE.STANDARDIZED"],
                    "relevant_roles": [],
                    "project_dimensions": {},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.9,
                    "uncertainty": 0.1,
                    "notes": "Señalización accesible con pictograma normalizado.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='ROUTE.ACCESSIBLE.SIGNAGE',
                attributes={
                    "tag_path": "ROUTE.ACCESSIBLE.SIGNAGE",
                    "parent": "ROUTE.ACCESSIBLE",
                    "definition": "Señalización de la ruta accesible conforme a pictograma oficial.",
                    "status": "ACTIVE",
                },
            ),
        ],
    ),

    # 5) Hospital fail-safe requirement with exemption using NOT/AND + string param
    lx.data.ExampleData(
        text=(
            'In hospitals, automatic doors must be open to power failure, except in operating rooms with specific regulations.'    ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    'In hospitals, automatic doors must be open to power failure, except in operating rooms with specific regulations.'            ),
                attributes={
                    "paragraph_number": 2,
                    "obligation_type": "MANDATORY",
                    "applies_if": "USAGE == 'HOSPITAL' AND DOOR.TYPE == 'AUTOMATIC'",
                    "satisfied_if": "(DOOR.AUTOMATIC.FAIL_SAFE == 'OPEN'); OR (SYSTEM.POWER.BACKUP == TRUE)",
                    "exempt_if": "ROOM.TYPE == 'OPERATING_ROOM'",
                    "topics": ["SAFETY.USE","HEALTH"],
                    "priority": 5,
                    "priority_factors": {"severity": 0.9, "likelihood": 0.3, "impact": 0.9},
                    "relevant_tags": [
                        "USAGE",
                        "DOOR.TYPE",
                        "DOOR.AUTOMATIC.FAIL_SAFE",
                        "SYSTEM.POWER.BACKUP",
                        "ROOM.TYPE",
                    ],
                    "relevant_roles": [],
                    "project_dimensions": {},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.92,
                    "uncertainty": 0.08,
                    "notes": "En hospitales, puertas automáticas en modo "
                             "fail-safe abierto o respaldo de energía; exención quirófanos.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='FAIL-SAFE=OPEN',
                attributes={
                    "field_path": "DOOR.AUTOMATIC.FAIL_SAFE",
                    "operator": "==",
                    "value": "OPEN",
                    "unit": None,
                    "original_text": "abiertas ante fallo de energía",
                },
            ),
        ],
    ),

    # 6) Permission with enumerations (PV exterior jardín) + ownership/use
    lx.data.ExampleData(
        text='It is possible to install outdoor photovoltaic panels in a garden in private single-family homes.'
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='It is possible to install outdoor photovoltaic panels in a garden in private single-family homes.'
                attributes={
                    "paragraph_number": 1,
                    "obligation_type": "PERMISSION",
                    "applies_if": "USAGE == 'FAMILY.SINGLE' AND OWNERSHIP == 'PRIVATE'",
                    "satisfied_if": "WORK.TYPE == 'ELECTRO.PHOTOVOLTAIC.EXTERIOR.GARDEN'",
                    "exempt_if": None,
                    "topics": ["ENERGYSAVINGS.PV"],
                    "priority": 2,
                    "priority_factors": {"severity": 0.1, "likelihood": 0.5, "impact": 0.2},
                    "relevant_tags": ["USAGE", "OWNERSHIP", "WORK.TYPE"],
                    "relevant_roles": [],
                    "project_dimensions": {
                        "USAGE": ["FAMILY.SINGLE"],
                        "OWNERSHIP": ["PRIVATE"],
                        "WORK.TYPE": ["ELECTRO.PHOTOVOLTAIC.EXTERIOR.GARDEN"],
                    },
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.88,
                    "uncertainty": 0.12,
                    "notes": "Permiso para FV exterior en jardín en vivienda unifamiliar privada.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='ELECTRO.PHOTOVOLTAIC.EXTERIOR.GARDEN',
                attributes={
                    "tag_path": "ELECTRO.PHOTOVOLTAIC.EXTERIOR.GARDEN",
                    "parent": "ELECTRO.PHOTOVOLTAIC.EXTERIOR",
                    "definition": "Instalación FV situada en el jardín.",
                    "status": "ACTIVE",
                },
            ),
        ],
    ),

    # 7) Conditional norm activating inspection if street closure effect occurs
    lx.data.ExampleData(
        text='If the work produces street closure, prior municipal inspection must be requested.'        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='If the work produces street closure, prior municipal inspection must be requested.'                attributes={
                    "paragraph_number": 3,
                    "obligation_type": "CONDITIONAL",
                    "applies_if": "WORK.EFFECTS IN['CLOSURE.STREET']",
                    "satisfied_if": "INSPECTION.MUNICIPAL.REQUESTED == TRUE",
                    "exempt_if": None,
                    "consequence_ids": ["C::INSP1"],
                    "topics": ["SAFETY.ACCIDENTPREVENTION"],
                    "priority": 4,
                    "priority_factors": {"severity": 0.6, "likelihood": 0.4, "impact": 0.7},
                    "relevant_tags": ["WORK.EFFECTS", "INSPECTION.MUNICIPAL.REQUESTED"],
                    "relevant_roles": [],
                    "project_dimensions": {"WORK.EFFECTS": ["CLOSURE.STREET"]},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "confidence": 0.9,
                    "uncertainty": 0.1,
                    "notes": "Obliga a solicitar inspección municipal cuando hay cierre de calle.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Consequence",
                extraction_text='Municipal pre-inspection'
                attributes={
                    "id": "C::INSP1",
                    "kind": "INSPECTION",
                    "reference_code": None,
                    "description": "Inspección previa por cierre de calle",
                    "activates_tag_paths": ["WORK.EFFECTS"],
                },
            ),
        ],
    ),

    # 8) Materials/structural with IN[...] and enumerations (no numeric fabrication)
    lx.data.ExampleData(
        text='The structural elements exposed to wind shall be executed in steel or aluminium according to applicable regulations.'        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='The structural elements exposed to wind shall be executed in steel or aluminium according to applicable regulations.'                attributes={
                    "paragraph_number": 4,
                    "obligation_type": "MANDATORY",
                    "applies_if": "MATERIALSANDEFFECTS IN['WIND']",
                    "satisfied_if": "STRUCTURE.MATERIAL IN['STEEL','ALUMINIUM']",
                    "exempt_if": None,
                    "topics": ["SAFETY.STRUCTURAL"],
                    "priority": 4,
                    "priority_factors": {"severity": 0.7, "likelihood": 0.3, "impact": 0.7},
                    "relevant_tags": ["STRUCTURE.MATERIAL", "MATERIALSANDEFFECTS"],
                    "relevant_roles": [],
                    "project_dimensions": {},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.9,
                    "uncertainty": 0.1,
                    "notes": "Material estructural permitido frente a viento: acero o aluminio.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='STRUCTURE.MATERIAL',
                attributes={
                    "tag_path": "STRUCTURE.MATERIAL",
                    "parent": "STRUCTURE",
                    "definition": "Material principal de los elementos estructurales.",
                    "status": "ACTIVE",
                },
            ),
        ],
    ),

    # 9) Tag merge (legacy to canonical) + prohibition in specific zone using OVERLAPS/ADJACENT_TO
    lx.data.ExampleData(
        text='The installation of auxiliary radio communications antennas in area R6.2 and adjacent areas to PEM2 shall be prohibited.'       extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='The installation of auxiliary radio communications antennas in area R6.2 and adjacent areas to PEM2 shall be prohibited.'               attributes={
                    "paragraph_number": 5,
                    "obligation_type": "PROHIBITION",
                    "applies_if": "WORK.TYPE.AUXILARY == 'ELECTRO.RADIOCOMMUNICATION' AND (LOCATION.OVERLAPS('ZONE:R6.2') OR LOCATION.ADJACENT_TO('ZONE:PEM2'))",
                    "satisfied_if": "INSTALLATION.RADIOCOMMUNICATION == FALSE",
                    "exempt_if": None,
                    "topics": ["PROTECTION.ELECTRONICS"],
                    "priority": 4,
                    "priority_factors": {"severity": 0.5, "likelihood": 0.4, "impact": 0.6},
                    "relevant_tags": [
                        "WORK.TYPE.AUXILARY",
                        "LOCATION.OVERLAPS",
                        "LOCATION.ADJACENT_TO",
                        "INSTALLATION.RADIOCOMMUNICATION",
                    ],
                    "relevant_roles": [],
                    "project_dimensions": {"WORK.TYPE.AUXILARY": ["ELECTRO.RADIOCOMMUNICATION"]},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": "ES",
                        "STATES": ["CAT"],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": ["R6.2", "PEM2"],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 0.3,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.88,
                    "uncertainty": 0.12,
                    "notes": "Prohibición de antenas auxiliares en R6.2 y adyacentes a PEM2.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='ELECTRO.RADIOCOM',
                attributes={
                    "tag_path": "ELECTRO.RADIOCOM",
                    "parent": "ELECTRO",
                    "definition": "Etiqueta legada para radiocomunicación.",
                    "status": "MERGED",
                    "merge_target": "ELECTRO.RADIOCOMMUNICATION",
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='ELECTRO.RADIOCOMMUNICATION',
                attributes={
                    "tag_path": "ELECTRO.RADIOCOMMUNICATION",
                    "parent": "ELECTRO",
                    "definition": "Sistemas y antenas de radiocomunicación.",
                    "status": "ACTIVE",
                },
            ),
            lx.data.Extraction(
                extraction_class="Location",
                extraction_text='PEM2',
                attributes={
                    "type": "PLANNING_ZONE",
                    "code": "PEM2",
                    "name": None,
                    "parent_codes": ["ES","CAT"],
                    "classification": [],
                },
            ),
        ],
    ),

    # 10) Question driving multiple norms (project type) + ENUMs exactly as specified
    lx.data.ExampleData(
        text='The type of project determines the applicable requirements.',
        extractions=[
            lx.data.Extraction(
                extraction_class="Question",
                extraction_text="What's the kind of project?"                attributes={
                    "tag_path": "PROJECT.TYPE",
                    "question_text": "¿Cuál es el tipo de proyecto?",
                    "answer_type": "ENUM",
                    "enum_values": ["NEW","REFORM","AMPLIACION_ESTRUCTURA","LEGALISATION"],
                    "outputs": ["PROJECT.TYPE"],
                    "derived_follow_up_question_ids": [],
                    "trigger_norm_ids": ["N::REFS1","N::REFS2"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='The existing accessibility should be maintained at least in reform projects.'                attributes={
                    "paragraph_number": 6,
                    "obligation_type": "MANDATORY",
                    "applies_if": "PROJECT.TYPE == 'REFORM'",
                    "satisfied_if": "ACCESSIBILITY.LEVEL >= ACCESSIBILITY.EXISTING.LEVEL",
                    "exempt_if": None,
                    "topics": ["ACCESSIBILITY"],
                    "priority": 3,
                    "priority_factors": {"severity": 0.3, "likelihood": 0.4, "impact": 0.5},
                    "relevant_tags": [
                        "PROJECT.TYPE",
                        "ACCESSIBILITY.LEVEL",
                        "ACCESSIBILITY.EXISTING.LEVEL",
                    ],
                    "relevant_roles": [],
                    "project_dimensions": {"PROJECT.TYPE": ["REFORM"]},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.9,
                    "uncertainty": 0.1,
                    "notes": "En reformas, mantener como mínimo la accesibilidad existente.",
                    "id": "N::REFS1",
                },
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='In new projects, full compliance with thermal requirements will be required.'               attributes={
                    "paragraph_number": 7,
                    "obligation_type": "MANDATORY",
                    "applies_if": "PROJECT.TYPE == 'NEW'",
                    "satisfied_if": "ENERGYSAVING.THERMAL.COMPLIANCE == TRUE",
                    "exempt_if": None,
                    "topics": ["ENERGYSAVING.THERMAL"],
                    "priority": 4,
                    "priority_factors": {"severity": 0.5, "likelihood": 0.4, "impact": 0.6},
                    "relevant_tags": ["PROJECT.TYPE", "ENERGYSAVING.THERMAL.COMPLIANCE"],
                    "relevant_roles": [],
                    "project_dimensions": {"PROJECT.TYPE": ["NEW"]},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.9,
                    "uncertainty": 0.1,
                    "notes": "En obra nueva, cumplimiento íntegro de exigencias térmicas.",
                    "id": "N::REFS2",
                },
            ),
        ],
    ),

    # 11) Gas safety with numeric parameter and WITHIN()
    lx.data.ExampleData(
        text='Within the term ES.CT.BCN, the maximum gas supply pressure in kitchens shall be <= 2 bar.'      extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='The maximum gas supply pressure in kitchens shall be <= 2 bar.'               attributes={
                    "paragraph_number": 8,
                    "obligation_type": "MANDATORY",
                    "applies_if": "LOCATION.WITHIN('ES.CT.BCN') AND WORK.TYPE IN['GAS.KITCHEN']",
                    "satisfied_if": "GAS.SUPPLY.PRESSURE_BAR <= 2",
                    "exempt_if": None,
                    "topics": ["HEALTH","SAFETY.USE"],
                    "priority": 4,
                    "priority_factors": {"severity": 0.6, "likelihood": 0.4, "impact": 0.7},
                    "relevant_tags": [
                        "LOCATION.WITHIN",
                        "WORK.TYPE",
                        "GAS.SUPPLY.PRESSURE_BAR",
                    ],
                    "relevant_roles": [],
                    "project_dimensions": {"WORK.TYPE": ["GAS.KITCHEN"]},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": "ES",
                        "STATES": ["CT"],
                        "PROVINCES": ["BCN"],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": ["ES.CT.BCN"],
                        "UNCERTAINTY": 0.2,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.9,
                    "uncertainty": 0.1,
                    "notes": "Presión máxima de suministro de gas en cocinas dentro de ES.CT.BCN.",
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='<= 2 bar',
                attributes={
                    "field_path": "GAS.SUPPLY.PRESSURE_BAR",
                    "operator": "<=",
                    "value": 2,
                    "unit": "bar",
                    "original_text": "<= 2 bar",
                },
            ),
        ],
    ),

    # 12) Optional / Recommendation with lighting efficiency
    lx.data.ExampleData(
        text='It is recommended to use high efficiency luminaires to reduce energy consumption.'
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text='It is recommended to use high efficiency luminaires to reduce energy consumption.'
                attributes={
                    "paragraph_number": 9,
                    "obligation_type": "PERMISSION",
                    "applies_if": "TRUE",
                    "satisfied_if": "ENERGYSAVINGS.LIGHTING.EFFICIENCY == 'HIGH'",
                    "exempt_if": None,
                    "topics": ["ENERGYSAVINGS.LIGHTING.EFFICIENCY"],
                    "priority": 2,
                    "priority_factors": {"severity": 0.2, "likelihood": 0.5, "impact": 0.3},
                    "relevant_tags": ["ENERGYSAVINGS.LIGHTING.EFFICIENCY"],
                    "relevant_roles": [],
                    "project_dimensions": {},
                    "lifecycle_phase": [],
                    "location_scope": {
                        "COUNTRY": None,
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                        "UNCERTAINTY": 1.0,
                    },
                    "source": {
                        "doc_id": "EXAMPLES_ENHANCED",
                        "article": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters_ids": [],
                    "consequence_ids": [],
                    "confidence": 0.85,
                    "uncertainty": 0.15,
                    "notes": "Recomendación modelada como permiso: luminarias de alta eficiencia.",
                },
            ),
        ],
    ),
]

__all__ = ["EXAMPLES"]
