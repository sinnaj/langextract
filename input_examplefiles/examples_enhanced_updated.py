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
    debe constituir al menos un sector de incendio diferenciado, incluido el posible vesti-bulo común a diferentes salas.(5)"""),
        extractions=[
            lx.data.Extraction(
                extraction_class="Procedure",
                extraction_text=('2 A efectos del computo de la superficie de un sector de incendio, se considera que los locales de riesgo especial, las escaleras y pasillos protegidos, los vestibulos de independencia y las escaleras compartmentadas como sector de incendios, que esten contenidos en dicho sector no forman parte del mismo.'),
                attributes={
                    "id": "PD::000001",
                    "Procedure": "Computation of fire sector area excludes special risk rooms, protected stairs and corridors, independence vestibules, and stairs compartmentalized as fire sectors contained within the sector.",
                    "extraction_text": ('2 A efectos del computo de la superficie de un sector de incendio, se considera que los locales de riesgo especial, las escaleras y pasillos protegidos, los vestibulos de independencia y las escaleras compartmentadas como sector de incendios, que esten contenidos en dicho sector no forman parte del mismo.'),
                    "target_reference": ["Table 1.1 Condiciones de compartmentacion en sectores de incendio"],
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
                        "doc_id": "EXAMPLES_ENHANCED",
                        "Chapter": 1,
                        "article": 2,
                        "table": None  ,
                        "illustration": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                }
            ),

            lx.data.Extraction(
                extraction_class="Procedure",
                extraction_text=('Las superficies maximas indicadas en dicha tabla para los sectores de incendio pueden duplicarse cuando esten protegidos con una instalacion automatica de extincion.'),
                attributes={
                    "id": "PD::000002",
                    "Procedure": "Maximum surface areas indicated in this table for fire sectors may be doubled when protected by an automatic extinguishing system.",
                    "extraction_text": ('Las superficies maximas indicadas en dicha tabla para los sectores de incendio pueden duplicarse cuando esten protegidos con una instalacion automatica de extincion.'),
                    "target_reference": ["Table 1.1 Condiciones de compartmentacion en sectores de incendio"],
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
                        "doc_id": "EXAMPLES_ENHANCED",
                        "Chapter": 1,
                        "article": 2,
                        "table": None,
                        "illustration": None,
                        "page": 1,
                        "span_char_start": None,
                        "span_char_end": None,
                        "visual_refs": [],
                    },
                }
            ),

            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    """Table 1.1 Condiciones de compartmentacion en sectores de incendio  
                    <table><tr><td>Uso previsto del edifi-cio o establecimiento</td><td>Condiciones</td></tr><tr><td>En general</td><td>- Todo establecimiento debe constituir sector de incendio diferenciado del resto del edificio excepto, en edificios cuyo uso principal sea Residencial Vivienda, los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público."""
                ),
                attributes={
                    "id": "N::000001",
                    "paragraph_number": 1,
                    "obligation_type": "MANDATORY",
                    "extraction_text":"""Table 1.1 Condiciones de compartmentacion en sectores de incendio  
                    <table><tr><td>Uso previsto del edifi-cio o establecimiento</td><td>Condiciones</td></tr><tr><td>En general</td><td>- Todo establecimiento debe constituir sector de incendio diferenciado del resto del edificio excepto, en edificios cuyo uso principal sea Residencial Vivienda, los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público."""
                    ,
                    "norm_statement": "Every establishment must constitute a fire sector differentiated from the rest of the building",
                    "applies_if": "TRUE",
                    "satisfied_if": (
                        "ESTABLISHMENT.AREA.IS_FIRE_SECTOR == TRUE"
                    ),
                    "exempt_if": "BUILDING.USAGE == 'RESIDENTIAL.HOUSING' AND ESTABLISHMENT.AREA.SIZE <= 500 sq_m AND (ESTABLISHMENT.USAGE == 'EDUCATION' OR ESTABLISHMENT.USAGE == 'ADMINISTRATIVE' OR ESTABLISHMENT.USAGE == 'PUBLIC.RESIDENTIAL')",
                    "topics": ["SAFETY.FIRE"],
                    "project_dimensions": {
                        "PROJECT.TYPE": ["NEW","REFORM"],
                        "BUILDING.USAGE":["GENERAL"]
                    },
                    "priority": 5,
                    "priority_factors": {"severity": 0.9, "likelihood": 0.9, "impact": 0.8},
                    "relevant_tags": [
                        "FIRE.SECTOR",
                        "BUILDING.USAGE.RESIDENTIAL.HOUSING",
                        "ESTABLISHMENT.AREA",
                        "ESTABLISHMENT.USAGE.EDUCATION",
                        "ESTABLISHMENT.USAGE.ADMINISTRATIVE",
                        "ESTABLISHMENT.USAGE.PUBLIC.RESIDENTIAL",
                        "FIRE.EXTINGUISH_SYSTEM.TYPE.AUTOMATIC"
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
                    "extracted_parameters_ids": ["P::000007"],
                    "consequence_ids": [],
                    "confidence": 0.92,
                    "uncertainty": 0.08,
                    "notes": "sq_m can be doubled if automatic extinguish system is present",
                },
            ),
            lx.data.Extraction(  extraction_class="Norm",
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
                    "paragraph_number": 1,
                    "obligation_type": "MANDATORY",
                    "extraction_text": """- Toda zona cuyo uso previsto sea diferente y subsidiario del principal del edificio o establecimiento en el que esté integrada debe constituir un sector de incendio diffe-rente cuando supere los siguientes límites: Zona de uso Residencial Vivienda en todo caso.
                    Zona de alojamiento (1) o de uso Administrativo, Comercial, Docente cuya superficie construida exceda de 500 m² o cuya superficie construida exceda de 250 m² en caso de uso principal Almacén.
                    Zona de uso Pública concurrencia cuya ocupación exceda de 500 personas, o cuya superficie exceda de 250 m² en el caso de uso principal Almacén.
                    Zona de uso Aparcamiento cuya superficie construida exceda de 100 m² (2) Cualquier comunicación con zonas de otro uso se debe hacer a través de vestí-bulos de independencia.
                    Zona que englobe varios de los usos anteriormente enunciados y en conjunto superior los 250 m², siendo el uso principal Almacén.
                    Zona de uso Almacén cuya carga de fuego total ponderada y corregida (Qr), cal-culada según el anexo I del RSCIEI, sea igual o superior a tres millones de me-gajulios."""
                    ,
                    "norm_statement": "Any area with a different and subsidiary use from the main use of the building or establishment in which it is integrated must constitute a different fire sector when it exceeds the mentioned limits",
                    "applies_if": "AREA.USAGE != BUILDING.USAGE AND (AREA.USAGE == RESIDENTIAL.HOUSING) OR (AREA.USAGE == LODGING OR AREA.USAGE == ADMINISTRATIVE OR AREA.USAGE == COMMERCIAL) AND AREA.SIZE > 500 sq_m OR (AREA.USAGE == LODGING OR AREA.USAGE == ADMINISTRATIVE OR AREA.USAGE == COMMERCIAL) AND BUILDING.USAGE == STORAGE AND AREA.SIZE > 250 sq_m OR (AREA.USAGE == PUBLIC.RESIDENTIAL OR AREA.USAGE == PUBLIC.ASSEMBLY OR AREA.USAGE == PUBLIC.GOV OR AREA.USAGE == PUBLIC.HOSPITAL OR AREA.USAGE == PUBLIC.PARK OR AREA.USAGE == PUBLIC.COMMERCIAL) AND AREA.OCCUPANCY > 500 persons OR (AREA.USAGE == PUBLIC.RESIDENTIAL OR AREA.USAGE == PUBLIC.ASSEMBLY OR AREA.USAGE == PUBLIC.GOV OR AREA.USAGE == PUBLIC.HOSPITAL OR AREA.USAGE == PUBLIC.PARK OR AREA.USAGE == PUBLIC.COMMERCIAL) AND BUILDING.USAGE == STORAGE AND AREA.SIZE > 250 sq_m OR (AREA.USAGE == PARKING) AND AREA.SIZE > 100 sq_m OR AREA.USAGE > 1 AND AREA.SIZE > 250 sq_m AND BUILDING.USAGE == STORAGE OR (AREA.USAGE == STORAGE) AND AREA.FIRE.LOAD_TOTAL_CORRECTED >= 3000000 MJ",
                    "satisfied_if": (
                        "AREA.IS_FIRE_SECTOR == TRUE"
                    ),
                    "exempt_if": "FALSE",
                    "topics": ["SAFETY.FIRE"],
                    "project_dimensions": {
                        "PROJECT.TYPE": ["NEW","REFORM"],
                        "BUILDING.USAGE":["GENERAL"]
                    },
                    "priority": 5,
                    "priority_factors": {"severity": 0.9, "likelihood": 0.9, "impact": 0.8},
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
                    "extracted_parameters_ids": ["P::000002","P::000003","P::000004","P::000005","P::000006","P::000001"],
                    "consequence_ids": [],
                    "confidence": 0.92,
                    "uncertainty": 0.08,
                    "notes": "sq_m can be doubled if automatic extinguish system is present",
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='superficie construida exceda de 500 m²',
                attributes={
                    "id": "P::000001",
                    "extraction_text": 'superficie construida exceda de 500 m²',
                    "field_path": "AREA.SIZE",
                    "operator": ">",
                    "value": 500,
                    "unit": "sq_m",
                    "norm_ids": ["N::000002"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='superficie construida exceda de 250 m²',
                attributes={
                    "id": "P::000002",
                    "extraction_text": 'superficie construida exceda de 250 m²',
                    "field_path": "AREA.SIZE",
                    "operator": ">",
                    "value": 250,
                    "unit": "sq_m",
                    "norm_ids": ["N::000002"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='ocupación exceda de 500 personas',
                attributes={
                    "id": "P::000003",
                    "extraction_text": 'ocupación exceda de 500 personas',
                    "field_path": "AREA.OCCUPANCY",
                    "operator": ">",
                    "value": 500,
                    "unit": "persons",
                    "norm_ids": ["N::000002"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='superficie construida exceda de 100 m²',
                attributes={
                    "id": "P::000004",
                    "extraction_text": 'superficie construida exceda de 100 m²',
                    "field_path": "AREA.SIZE",
                    "operator": ">",
                    "value": 100,
                    "unit": "sq_m",
                    "norm_ids": ["N::000002"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='englobe varios de los usos anteriormente enunciados',
                attributes={
                    "id": "P::000005",
                    "extraction_text": 'englobe varios de los usos anteriormente enunciados',
                    "field_path": "AREA.USAGE.COUNT",
                    "operator": ">",
                    "value": 1,
                    "unit": None,
                    "norm_ids": ["N::000002"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='sea igual o superior a tres millones de me-gajulios',
                attributes={
                    "id": "P::000006",
                    "extraction_text": 'sea igual o superior a tres millones de me-gajulios',
                    "field_path": "AREA.FIRE.LOAD_TOTAL_CORRECTED",
                    "operator": ">=",
                    "value": 3000000,
                    "unit": "MJ",
                    "norm_ids": ["N::000002"],
                },
            ),
            lx.data.Extraction(
                extraction_class="Parameter",
                extraction_text='no exceda de 500 m²',
                attributes={
                    "id": "P::000007",
                    "extraction_text": 'no exceda de 500 m²',
                    "field_path": "SIZE",
                    "operator": "<=",
                    "value": 500,
                    "unit": "sq_m",
                    "norm_ids": ["N::000001"],
                    "confidence": 0.95,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='sectores de incendio',
                attributes={
                    "id": "T::000001",
                    "extraction_text": 'sectores de incendio',
                    "tag": "FIRE.SECTOR",
                    "definition": "Sector de incendio",
                    "synonyms": ["sector de incendio"],
                    "used_by_norm_ids": ["N::000001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='edificios cuyo uso principal sea Residencial Vivienda',
                attributes={
                    "id": "T::000002",
                    "extraction_text": 'edificios cuyo uso principal sea Residencial Vivienda',
                    "tag": "BUILDING.USAGE.RESIDENTIAL.HOUSING",
                    "definition": "Uso principal",
                    "synonyms": ["uso principal"],
                    "used_by_norm_ids": ["N::000001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='esta-blecimientos cuya superficie construida no exceda de 500 m²',
                attributes={
                    "id": "T::000003",
                    "extraction_text": 'esta-blecimientos cuya superficie construida no exceda de 500 m²',
                    "tag": "ESTABLISHMENT.AREA",
                    "definition": "Area of an Establishment",
                    "synonyms": ["area"],
                    "used_by_norm_ids": ["N::000001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='instalacion automatica de extincion',
                attributes={
                    "id": "T::000004",
                    "extraction_text": 'instalacion automatica de extincion',
                    "tag": "FIRE.EXTINGUISH_SYSTEM.TYPE.AUTOMATIC",
                    "definition": "Sistema de extinción de incendios automático",
                    "synonyms": ["sistema de extinción de incendios automático"],
                    "used_by_norm_ids": ["N::000001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público.',
                attributes={
                    "id": "T::000005",
                    "extraction_text": 'los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público.',
                    "tag": "ESTABLISHMENT.USAGE.PUBLIC.RESIDENTIAL",
                    "definition": "Uso público residencial de un establecimiento",
                    "synonyms": ["uso público residencial de un establecimiento"],
                    "used_by_norm_ids": ["N::000001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público.',
                attributes={
                    "id": "T::000006",
                    "extraction_text": 'los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público.',
                    "tag": "ESTABLISHMENT.USAGE.EDUCATION",
                    "definition": "Uso educativo de un establecimiento",
                    "synonyms": ["uso educativo de un establecimiento"],
                    "used_by_norm_ids": ["N::000001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
            lx.data.Extraction(
                extraction_class="Tag",
                extraction_text='los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público.',
                attributes={
                    "id": "T::000007",
                    "extraction_text": 'los esta-blecimientos cuya superficie construida no exceda de 500 m² y cuyo uso sea Docente, Administrativo o Residencial Público.',
                    "tag": "ESTABLISHMENT.USAGE.ADMINISTRATIVE",
                    "definition": "Uso administrativo de un establecimiento",
                    "synonyms": ["uso administrativo de un establecimiento"],
                    "used_by_norm_ids": ["N::000001"],
                    "related_topics": ["SAFETY.FIRE"],
                    "confidence": 0.9,
                },
            ),
        ],
    ),


]

__all__ = ["EXAMPLES"]
