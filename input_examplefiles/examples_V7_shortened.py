"""
Adding proper hierarchy Examples for langextract
"""

from __future__ import annotations

from typing import List

import langextract as lx

EXAMPLES: List[lx.data.ExampleData] = [
    lx.data.ExampleData(
        ### 1) Basic Section Hierarchy
        text=(
            """
              # I Amito de aplicacion El ambito de aplicacion de este DB es el que se establece con caracter general para el conjunto del CTE en su articulo 2 (Parte I) exacyendo los edificios, establecimientos y zonas de uso industrial a los que les sea de aplicacion el "Reglamento de seguridad contra incendios en los establecimientos industriales"."""
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="DOCUMENT_METADATA",
                extraction_text="""# I Amito de aplicacion El ambito de aplicacion de este DB es el que se establece con caracter general para el conjunto del CTE en su articulo 2 (Parte I) exacyendo los edificios, establecimientos y zonas de uso industrial a los que les sea de aplicacion el "Reglamento de seguridad contra incendios en los establecimientos industriales".""",
                attributes={
                    "id": "DM::000001",
                    "author": None,
                    "date": None,
                    "source": None,
                    "document_summary": (
                        "Establish rules and procedures for fire safety"
                    ),
                    "meta_applies_if": "TRUE",
                    "meta_exempt_if": "BUILDING.USAGE == 'INDUSTRIAL'",
                    "related_documents": ["CTE"],
                    "related_documents_sections": ["CTE.ARTICLE.2.1"],
                    "location_scope": {
                        "COUNTRY": "ES",
                        "STATES": [],
                        "PROVINCES": [],
                        "REGIONS": [],
                        "COMMUNES": [],
                        "ZONES": [],
                        "GEO_CODES": [],
                    },
                },
            ),
            lx.data.Extraction(
                extraction_class="SECTION",
                extraction_text="# I Amito de aplicacion",
                attributes={
                    "id": "SE::000001",
                    "sectioning_type": "Chapter",
                    "section_level": 1,
                    "section_title": "I Amito de aplicacion",
                    "parent_type": "Document",
                    "parent_id": "SE::000001",
                    "author": None,
                    "date": None,
                    "source": None,
                    "section_summary": (
                        "Scope of application of the basic document for fire"
                        " safety"
                    ),
                    "applies_if": "TRUE",
                    "exempt_if": "FALSE",
                },
            ),
        ],
    ),
    # 1) Comprehensive example with many features
    lx.data.ExampleData(
        text=(
            """# 1 Compartimentación en sectores de incendio

1 Los edificios se deben compartmentar en sectores de incendio según las condiciones que se esta. becen en la tabla 1.1 de esta Seccion. Las superficies maximas indicadas en dicha tabla para los sectores de incendio pueden duplicarse cuando esten protegidos con una instalacion automatica de extincion.

2 A efectos del computo de la superficie de un sector de incendio, se considera que los locales de riesgo especial, las escaleras y pasillos protegidos, los vestibulos de independencia y las escaleras compartmentadas como sector de incendios, que esten contenidos en dicho sector no forman parte del mismo.

3 La resistencia al fuego de los elementos separadores de los sectores de incendio debe satisfacer las condiciones que se establecen en la tabla 1.2 de esta Seccion. Como alternativa, cuando, conforme a lo establecido en la Seccion SI 6, se haya adoptado el tiempo equivalente de exposicion al fuego para los elementos estructurales,pora adoptarse ese mismo tiempo para la resistencia al fuego que deben aportar los elementos separadores de los sectores de incendio.

4 Las escaleras y los ascensores que comuniquen sectores de incendio diferentes o bien zonas de riesgo especial con el resto del edificio estaran compartmentados conforme a lo que se establece en el punto 3 anterior. Los ascensores dispondran en cada acceso, o bien de puertas E  $30^{\circ}$  o bien de un vestibulo de independencia con una puerta  $\mathsf{E}1_{2}$  30- C5, excepto en zonas de riesgo especial o de uso Aparcamiento, en las que se debe disponer siempre el citado vestibulo. Cuando, considerando dos sectores, el mas bago sea un sector de riesgo minimo, o bien si no lo es se opte por disponer en el tanto una puerta  $\mathsf{E}1_{2}$  30- C5 de acceso al vestibulo de independencia del ascensor, como una puerta E 30 de acceso al asensor, en el sector mas alto no se precisa ninguna de dichas medidas.

Table 1.1 Condiciones de compartmentacion en sectores de incendio

<table><tr><td>Uso previsto del edifi-cio o establecimiento</td><td>Condiciones</td></tr><tr><td>En general</td><td>- Todo establecimiento debe constituir sector de incendio diferenciado del resto del edificio excepto, en edificios cuyo uso principal sea Residencial Vivienda, los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público.
- Toda zona cuyo uso previsto sea diferente y subsidiario del principal del edificio o establecimiento en el que esté integrada debe constituir un sector de incendio diffe-rente cuando supere los siguientes límites:</td></tr></table>

Determinado conforme a la norma UNE- EN 81- 58:2004 "Reglas de seguridad para la construcción e instalación de ascensores. Exámenes y ensayos - Parte 58: Ensayo de resistencia al fuego de las puertas de piso".

<table><tr><td></td><td>Zona de uso Residencial Vivienda en todo caso.
Zona de alojamiento (1) o de uso Administrativo, Comercial, Docente cuya superficie construida exceda de 500 m² o cuya superficie construida exceda de 250 m² en caso de uso principal Almacén.
Zona de uso Pública concurrencia cuya ocupación exceda de 500 personas, o cuya superficie exceda de 250 m² en el caso de uso principal Almacén.
Zona de uso Aparcamiento cuya superficie construida exceda de 100 m² (2) Cualquier comunicación con zonas de otro uso se debe hacer a través de vestí-bulos de independencia.
Zona que englobe varios de los usos anteriormente enunciados y en conjunto superior los 250 m², siendo el uso principal Almacén.
Zona de uso Almacén cuya carga de fuego total ponderada y corregida (Qr), cal-culada según el anexo I del RSCIEI, sea igual o superior a tres millones de me-gajulios.
- Un espacio diáfano puede constituir un único sector de incendio que supere los límites de superficie construida que se establecen, siempre que al menos el 90% de esta se desarrolló en una planta, sus salidas comunique directamente con el español libre exterior, al menos el 75% de su perimetro sea fachada y no exista sobre dicho recinto ninguna zona habitable.
- No se establece límite de superficie para los sectores de riesgo mínimo.</td></tr><tr><td>Residencial Vivienda</td><td>- La superficie construida de todo sector de incendio no debe exceder de 2.500 m².
- Los elementos que separan viviendas entre sí deben ser al menos el 60.</td></tr><tr><td>Administrativo</td><td>- La superficie construida de todo sector de incendio no debe exceder de 2.500 m².</td></tr><tr><td>Comercial(3)</td><td>- Excepto en los casos contemplados en los guiones siguientes, la superficie construi-da de todo sector de incendio no debe exceder de:
    0 2.500 m², en general;
    1) 10.000 m² en los establecimientos o centros comerciales que ocupen en su tota-lidad un edificio integramente protegido con una instalación automática de ex-tinción y cuya altura de evolución no exceeding de 10 m.(4)
- En establecimientos o centros comerciales que ocupen en su totalidad un edificio exento integramente protegido con una instalación automática de extinción, las zo-has destinadas al público pueden constituir un único sector de incendio cuando en ellas la altura de evolución descendente no exceeds de 10 m ni la ascendente ex-ceda de 4 m y cada planta tenga la evacuación de todos sus ocupantes resuelta mediante salidas de edificio situadas en la propia planta y salidas de planta que den acceso a escaleras protegidas o a pasillos protegidos que conduzcan directamente al espacio exterior seguro.(4)
- En centros comerciales, cada establecimiento de uso Pública Concurrencia:
    1) En el que se prevea la existencia de espectaculars (includidos cines, teatros, dis-cotecas, salas de baile, etc.), cualquier que sea su superficie;
    1) destinado a otro tipo de actividad, cuando su superficie construida exceda de 500 m²;
    debe constituir al menos un sector de incendio diferenciado, incluido el posible vesti-bulo común a diferentes salas.(5)"""
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="SECTION",
                extraction_text="1 Compartimentación en sectores de incendio",
                attributes={
                    "id": "SE::000003",
                    "sectioning_type": "Headline",
                    "section_level": 2,
                    "section_title": (
                        "Compartimentación en sectores de incendio"
                    ),
                    "parent_type": "Chapter",
                    "parent_id": "SE::000002",
                    "author": None,
                    "date": None,
                    "source": None,
                    "section_summary": (
                        "Establish rules for compartmentalization in fire"
                        " sectors"
                    ),
                    "applies_if": "TRUE",
                    "exempt_if": "FALSE",
                },
            ),
            lx.data.Extraction(
                extraction_class="Procedure",
                extraction_text=(
                    "2 A efectos del computo de la superficie de un sector de"
                    " incendio, se considera que los locales de riesgo"
                    " especial, las escaleras y pasillos protegidos, los"
                    " vestibulos de independencia y las escaleras"
                    " compartmentadas como sector de incendios, que esten"
                    " contenidos en dicho sector no forman parte del mismo."
                ),
                attributes={
                    "id": "PD::000001",
                    "parent_section_id": "SE::000001",
                    "Procedure": (
                        "Computation of fire sector area excludes special risk"
                        " rooms, protected stairs and corridors, independence"
                        " vestibules, and stairs compartmentalized as fire"
                        " sectors contained within the sector."
                    ),
                    "target_reference": [
                        "Table 1.1 Condiciones de compartmentacion en sectores"
                        " de incendio"
                    ],
                    "Tags": ["FIRE.SECTOR", "FIRE.SECTOR.COMPUTATION"],
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
                        "doc_id": "examples_V6.py",
                        "Chapter": 1,
                        "article": 2,
                        "table": None,
                        "illustration": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                },
            ),
            lx.data.Extraction(
                extraction_class="Procedure",
                extraction_text=(
                    "Las superficies maximas indicadas en dicha tabla para los"
                    " sectores de incendio pueden duplicarse cuando esten"
                    " protegidos con una instalacion automatica de extincion."
                ),
                attributes={
                    "id": "PD::000002",
                    "parent_section_id": "SE::000003",
                    "Procedure": (
                        "Maximum surface areas indicated in this table for fire"
                        " sectors may be doubled when protected by an automatic"
                        " extinguishing system."
                    ),
                    "target_reference": [
                        "Table 1.1 Condiciones de compartmentacion en sectores"
                        " de incendio"
                    ],
                    "Tags": ["FIRE.SECTOR", "FIRE.SECTOR.AREA.COMPUTATION"],
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
                        "doc_id": "examples_V6.py",
                        "Chapter": 1,
                        "article": 2,
                        "table": None,
                        "illustration": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                },
            ),
            lx.data.Extraction(
                extraction_class="NORM",
                extraction_text=(
                    """Table 1.1 Condiciones de compartmentacion en sectores de incendio
                    <table><tr><td>Uso previsto del edifi-cio o establecimiento</td><td>Condiciones</td></tr><tr><td>En general</td><td>- Todo establecimiento debe constituir sector de incendio diferenciado del resto del edificio excepto, en edificios cuyo uso principal sea Residencial Vivienda, los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público."""
                ),
                attributes={
                    "id": "N::000001",
                    "parent_section_id": "SE::000001",
                    "paragraph_number": 1,
                    "obligation_type": "MANDATORY",
                    "norm_statement": (
                        "Every establishment must constitute a fire sector"
                        " differentiated from the rest of the building"
                    ),
                    "applies_if": "TRUE",
                    "satisfied_if": "ESTABLISHMENT.AREA.IS_FIRE_SECTOR == TRUE",
                    "exempt_if": (
                        "BUILDING.USAGE == 'RESIDENTIAL.HOUSING' AND"
                        " ESTABLISHMENT.AREA.SIZE <= 500 sq_m AND"
                        " (ESTABLISHMENT.USAGE == 'EDUCATION' OR"
                        " ESTABLISHMENT.USAGE == 'ADMINISTRATIVE' OR"
                        " ESTABLISHMENT.USAGE == 'PUBLIC.RESIDENTIAL')"
                    ),
                    "topics": ["SAFETY.FIRE"],
                    "project_dimensions": {
                        "PROJECT.TYPE": ["NEW", "REFORM"],
                        "BUILDING.USAGE": ["GENERAL"],
                    },
                    "priority": 5,
                    "priority_factors": {
                        "severity": 0.9,
                        "likelihood": 0.9,
                        "impact": 0.8,
                    },
                    "relevant_tags": [
                        "FIRE.SECTOR",
                        "BUILDING.USAGE.RESIDENTIAL.HOUSING",
                        "ESTABLISHMENT.AREA",
                        "ESTABLISHMENT.USAGE.EDUCATION",
                        "ESTABLISHMENT.USAGE.ADMINISTRATIVE",
                        "ESTABLISHMENT.USAGE.PUBLIC.RESIDENTIAL",
                        "FIRE.EXTINGUISH_SYSTEM.TYPE.AUTOMATIC",
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
                        "table": "1.1",
                        "illustration": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters": ["AREA.SIZE <= 500 sq_m"],
                    "consequence_ids": [],
                    "confidence": 0.92,
                    "uncertainty": 0.08,
                    "notes": (
                        "sq_m can be doubled if automatic extinguish system is"
                        " present"
                    ),
                },
            ),
            lx.data.Extraction(
                extraction_class="NORM",
                extraction_text=(
                    """- Toda zona cuyo uso previsto sea diferente y subsidiario del principal del edificio o establecimiento en el que esté integrada debe constituir un sector de incendio diffe-rente cuando supere los siguientes límites: Zona de uso Residencial Vivienda en todo caso.
                    Zona de alojamiento (1) o de uso Administrativo, Comercial, Docente cuya superficie construida exceda de 500 m² o cuya superficie construida exceda de 250 m² en caso de uso principal Almacén.
                    Zona de uso Pública concurrencia cuya ocupación exceda de 500 personas, o cuya superficie exceda de 250 m² en el caso de uso principal Almacén.
                    Zona de uso Aparcamiento cuya superficie construida exceda de 100 m² (2) Cualquier comunicación con zonas de otro uso se debe hacer a través de vestí-bulos de independencia.
                    Zona que englobe varios de los usos anteriormente enunciados y en conjunto superior los 250 m², siendo el uso principal Almacén.
                    Zona de uso Almacén cuya carga de fuego total ponderada y corregida (Qr), cal-culada según el anexo I del RSCIEI, sea igual o superior a tres millones de me-gajulios."""
                ),
                attributes={
                    "id": "N::000002",
                    "parent_section_id": "SE::000003",
                    "paragraph_number": 1,
                    "obligation_type": "MANDATORY",
                    "norm_statement": (
                        "Any area with a different and subsidiary use from the"
                        " main use of the building or establishment in which it"
                        " is integrated must constitute a different fire sector"
                        " when it exceeds the mentioned limits"
                    ),
                    "applies_if": (
                        "AREA.USAGE != BUILDING.USAGE AND (\n                  "
                        "      (AREA.USAGE == 'RESIDENTIAL.HOUSING') OR\n      "
                        "                  (AREA.USAGE IN ['LODGING',"
                        " 'ADMINISTRATIVE', 'COMMERCIAL', 'EDUCATION'] AND"
                        " AREA.SIZE > 500) OR\n                       "
                        " (AREA.USAGE IN ['LODGING', 'ADMINISTRATIVE',"
                        " 'COMMERCIAL', 'EDUCATION'] AND BUILDING.USAGE =="
                        " 'STORAGE' AND AREA.SIZE > 250) OR\n                  "
                        "      (AREA.USAGE == 'PUBLIC.ASSEMBLY' AND"
                        " AREA.OCCUPANCY > 500) OR\n                       "
                        " (AREA.USAGE == 'PUBLIC.ASSEMBLY' AND BUILDING.USAGE"
                        " == 'STORAGE' AND AREA.SIZE > 250) OR\n               "
                        "         (AREA.USAGE == 'PARKING' AND AREA.SIZE > 100)"
                        " OR\n                        (AREA.USAGE == 'STORAGE'"
                        " AND AREA.FIRE.LOAD_TOTAL_CORRECTED >= 3000000)\n     "
                        "               )"
                    ),
                    "satisfied_if": "AREA.IS_FIRE_SECTOR == TRUE",
                    "exempt_if": "FALSE",
                    "topics": ["SAFETY.FIRE"],
                    "project_dimensions": {
                        "PROJECT.TYPE": ["NEW", "REFORM"],
                        "BUILDING.USAGE": ["GENERAL"],
                    },
                    "priority": 5,
                    "priority_factors": {
                        "severity": 0.9,
                        "likelihood": 0.9,
                        "impact": 0.8,
                    },
                    "relevant_tags": [
                        "AREA.USAGE.RESIDENTIAL.HOUSING",
                        "AREA.USAGE.LODGING",
                        "AREA.USAGE.ADMINISTRATIVE",
                        "AREA.USAGE.COMMERCIAL",
                        "AREA.USAGE.PUBLIC.RESIDENTIAL",
                        "AREA.USAGE.PUBLIC.ASSEMBLY",
                        "AREA.USAGE.PUBLIC.GOV",
                        "AREA.USAGE.PUBLIC.HOSPITAL",
                        "AREA.USAGE.PUBLIC.PARK",
                        "AREA.USAGE.PUBLIC.COMMERCIAL",
                        "AREA.USAGE.PARKING",
                        "AREA.USAGE.STORAGE",
                        "BUILDING.USAGE.STORAGE",
                        "AREA.OCCUPANCY",
                        "AREA.USAGE",
                        "BUILDING.USAGE",
                        "AREA.SIZE",
                        "AREA.FIRE.LOAD_TOTAL_CORRECTED",
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
                        "table": "1.1",
                        "illustration": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                    "extracted_parameters": [
                        "AREA.SIZE > 500 sq_m",
                        "AREA.SIZE > 250 sq_m",
                        "AREA.OCCUPANCY > 500 persons",
                        "AREA.SIZE > 100 sq_m",
                        "AREA.SIZE > 250 sq_m",
                        "AREA.FIRE.LOAD_TOTAL_CORRECTED >= 3000000 MJ",
                    ],
                    "consequence_ids": [],
                    "confidence": 0.92,
                    "uncertainty": 0.08,
                    "notes": (
                        "sq_m can be doubled if automatic extinguish system is"
                        " present"
                    ),
                },
            ),
        ],
    ),
    # 2) Section hierarchy example
    lx.data.ExampleData(
        text=(
            """# Introducción

# I Objeto

Este Documento Básico (DB) tiene por objeto establecer reglas y procedimientos que permiten cumplir las exigencias básicas de seguridad en caso de incendio. Las secaciones de este DB se corresponden con las exigencias básicas SI 1 a SI 6. La correcta aplicación de cada Sección supone el cumplimiento de la exigencia básica correspondiente. La correcta aplicación del conjunto del DB supone que se satisface el requisito básico "Seguridad en caso de incendio"."""
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="SECTION",
                extraction_text="""# Introducción # I Objeto Este Documento Básico (DB) tiene por objeto establecer reglas y procedimientos que permiten cumplir las exigencias básicas de seguridad en caso de incendio. Las secaciones de este DB se corresponden con las exigencias básicas SI 1 a SI 6. La correcta aplicación de cada Sección supone el cumplimiento de la exigencia básica correspondiente. La correcta aplicación del conjunto del DB supone que se satisface el requisito básico "Seguridad en caso de incendio".""",
                attributes={
                    "id": "SE::000003",
                    "sectioning_type": "CHAPTER",
                    "section_title": "Introducción",
                    "parent_type": "DOCUMENT",
                    "parent_id": "SE::000002",
                    "author": None,
                    "date": None,
                    "source": None,
                    "section_summary": (
                        "Introduction to the basic document establishing rules"
                        " and procedures for fire safety"
                    ),
                    "applies_if": "TRUE",
                    "exempt_if": "FALSE",
                },
            ),
            lx.data.Extraction(
                extraction_class="SECTION",
                extraction_text=(
                    "# I Objeto Este Documento Básico (DB) tiene por objeto"
                    " establecer reglas y procedimientos que permiten cumplir"
                    " las exigencias básicas de seguridad en caso de incendio."
                    " Las secaciones de este DB se corresponden con las"
                    " exigencias básicas SI 1 a SI 6. La correcta aplicación de"
                    " cada Sección supone el cumplimiento de la exigencia"
                    " básica correspondiente. La correcta aplicación del"
                    " conjunto del DB supone que se satisface el requisito"
                    " básico 'Seguridad en caso de incendio'."
                ),
                attributes={
                    "id": "SE::000004",
                    "sectioning_type": "Headline",
                    "section_level": 2,
                    "section_title": "I Objeto",
                    "parent_type": "CHAPTER",
                    "parent_id": "SE::000003",
                    "author": None,
                    "date": None,
                    "source": None,
                    "section_summary": (
                        "Objective of the basic document establishing rules and"
                        " procedures for fire safety"
                    ),
                    "applies_if": "TRUE",
                    "exempt_if": "FALSE",
                },
            ),
        ],
    ),
]

__all__ = ["EXAMPLES"]
