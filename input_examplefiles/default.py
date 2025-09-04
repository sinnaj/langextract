"""Default example set for LangExtract rich schema extraction.

Exports:
    EXAMPLES: List[lx.data.ExampleData]
"""

from __future__ import annotations

from typing import List

import langextract as lx

EXAMPLES: List[lx.data.ExampleData] = [
    # RICH: multi-entity with alternatives & exemption + embedded miniature demo
    lx.data.ExampleData(
        text=(
            "1 Las puertas de salida para la evacuación de más de 50 personas"
            " deben ser abatibles con eje vertical y permitir apertura sin"
            " llave o mantener el sistema de cierre desactivado durante la"
            " actividad.No se aplica a puertas automáticas con sistema de"
            " abatimiento seguro."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Las puertas de salida para la evacuación de más de 50"
                    " personas deben ser abatibles con eje vertical y permitir"
                    " apertura sin llave o mantener el sistema de cierre"
                    " desactivado durante la actividad."
                ),
                attributes={
                    "paragraph_number": 1,
                    "applies_if": "EVACUATION.PERSONS > 50",
                    "satisfied_if": (
                        "(DOOR.TYPE == 'SWING' AND DOOR.AXIS == 'VERTICAL'); OR"
                        " (DOOR.OPENING.REQUIRES_KEY == FALSE AND"
                        " DOOR.OPENING.MECHANISMS_COUNT <= 1); OR"
                        " (CLOSING.SYSTEM.ENABLED == FALSE)"
                    ),
                    "exempt_if": (
                        "DOOR.TYPE == 'AUTOMATIC' AND"
                        " HAS(DOOR.OPTION.SWING_ALLOWED)"
                    ),
                    "rich_demo": {
                        "parameters": [{
                            "id": "P::DEMO1",
                            "field_path": "DOOR.OPENING.MECHANISMS_COUNT",
                            "operator": "<=",
                            "value": 1,
                            "unit": None,
                        }],
                        "tags": [{
                            "id": "T::DEMO1",
                            "tag_path": "DOOR.AUTOMATIC",
                            "parent": "DOOR",
                            "definition": "Puerta automática",
                            "status": "ACTIVE",
                        }],
                        "questions": [{
                            "id": "Q::DEMO1",
                            "tag_path": "DOOR.TYPE",
                            "question_text": "¿Cuál es el tipo de puerta?",
                            "answer_type": "ENUM",
                            "enum_values": [
                                "SWING",
                                "SLIDING",
                                "FOLDING",
                                "AUTOMATIC",
                            ],
                        }],
                        "consequences": [{
                            "id": "C::DEMO1",
                            "kind": "ANNEX",
                            "reference_code": "Anexo III",
                        }],
                        "locations": [{
                            "id": "L::DEMO1",
                            "type": "PLANNING_ZONE",
                            "code": "R6.2",
                            "parent_codes": ["ES", "CAT"],
                        }],
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
        text=(
            "2 No se admite la instalación de dispositivos que requieran llave"
            " en la ruta de evacuación principal cuando la ocupación sea"
            " superior a 100 personas."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "No se admite la instalación de dispositivos que requieran"
                    " llave en la ruta de evacuación principal cuando la"
                    " ocupación sea superior a 100 personas."
                ),
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
            "En la zona R6.2 se requerirá la presentación del Anexo III cuando"
            " la fuerza de apertura sea <= 220 N."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Se requerirá la presentación del Anexo III cuando la"
                    " fuerza de apertura sea <= 220 N."
                ),
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
                    "enum_values": ["PEDESTRIAN", "INDUSTRIAL"],
                    "outputs": ["DOOR.AUTOMATIC.TYPE"],
                },
            ),
        ],
    ),
]

__all__ = ["EXAMPLES"]
