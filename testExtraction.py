from dotenv import load_dotenv
import langextract as lx
import textwrap
import os

# Load environment variables from .env file
load_dotenv()
# 1. Define the prompt and extraction rules
prompt = textwrap.dedent("""\
Extract Norms (individual regulatory provisions) from Spanish building regulations. Text is often structured with numbered paragraphs (e.g., "1 ...", "2 ...") and may contain lettered subparagraphs (a), b), etc.).

A Norm is an atomic obligation or prohibition that defines a concrete compliance action or property:
- It MUST have a specific “WHAT to do / WHAT not to do” expressed in satisfied_if as a DSL condition or action/property.
- It MAY have a “WHEN / FOR WHOM it applies” in applies_if (if none is stated, set TRUE).
- It MAY have explicit exceptions in exempt_if (phrases like “excepto…”, “salvo…”, “no será de aplicación…”, “no se admite…”, “a menos que…”) expressed in DSL.

SCOPE (include/exclude):
- INCLUDE technical requirements on design, products, performance classes, installation, operation, or maintenance that are directly applicable to architectural/building design (e.g., doors, fire resistance, smoke control, evacuation).
- EXCLUDE administrative/procedural items (approvals, Article 5 process, documentation steps) and generic principles without a concrete actionable requirement.
- IGNORE tables/figures and their numeric lookups (do not synthesize values from tables).
- Keep cross-references as text (e.g., “conforme al punto 3”); do NOT resolve them.

SEGMENTATION & ATOMICITY:
- Extract ONE Norm per distinct compliance action/property. If a sentence lists true alternatives (“o bien…/o…”), encode them in a single satisfied_if separated by “; OR …”.
- If a paragraph has lettered sub-items (a, b, c) with different thresholds/scopes, create SEPARATE Norms per sub-item.
- If several sentences impose the SAME satisfied_if under the SAME applies_if, merge into one Norm.
- Prohibitions (“no se admite…”, “no debe…”, “no se considerará…”) are valid Norms; encode satisfied_if as a boolean/relational condition (e.g., exit.use_elevator == false), not free prose.

DSL FOR CONDITIONS (use in applies_if / satisfied_if / exempt_if):
- Comparisons: == != < <= > >=
- Booleans: true false
- Logic: AND OR NOT  (uppercase), parentheses (...)
- Membership: IN { 'a','b' } or IN {1,2,3}
- Units: keep units in the field name when helpful (e.g., door.opening.push_force_N <= 220)
- Strings: single quotes '...'
- Preserve standard names exactly (e.g., 'UNE-EN 179:2009', 'UNE-EN 1125:2009').
- If unconditional, set applies_if to TRUE.

RECOMMENDED ONTOLOGY (use when possible; if a field is unknown, choose a semantically consistent name):
- Door: door.type ('swing','sliding','folding','tilt_turn','automatic','automatic_pedestrian'), door.use ('exit','emergency_exit'), door.axis ('vertical'), door.opening.direction ('evacuation'), door.opening.push_force_N (number), door.opening.requires_key (bool), door.opening.mechanisms_count (int), door.opening.from_evacuation_side (bool), door.state.open_maintained (bool), door.option.swing_allowed (bool), door.clear_width_m (number), door.fire_resistant (bool)
- Context/space: evacuation.persons (int), served.persons (int), space.occupants (int), building.use ('residential_dwelling','other')
- Systems/Events: closing.system.enabled (bool), system.position ('fail_safe_closed'), event.power_failure (bool), event.emergency_signal (bool)
- Routes/Accessibility: route.accessible_dbsua (bool)
- Devices/Standards: device.standard ('UNE-EN 179:2009','UNE-EN 1125:2009'), device.type ('handle','push_button','horizontal_push_bar','sliding_bar')

MAPPING RULES (DSL):
- applies_if: encode triggers as DSL predicates. Examples:
  - “para la evacuación de más de 50 personas” → evacuation.persons > 50
  - “en edificios de uso Residencial Vivienda” → building.use == 'residential_dwelling'
  - “cuando exista fallo de suministro eléctrico o señal de emergencia” → (event.power_failure == true OR event.emergency_signal == true)
  - If unconditional → TRUE
- satisfied_if: encode the minimal compliance state/action as DSL:
  - “puerta abatible con eje de giro vertical” → door.type == 'swing' AND door.axis == 'vertical'
  - “cierres desactivados durante la actividad” → closing.system.enabled == false
  - “apertura sin llave y sin más de un mecanismo” → (door.opening.requires_key == false AND door.opening.mechanisms_count <= 1)
  - Use “; OR …” to separate true alternatives within the same norm.
- exempt_if: ONLY explicit non-applicability, encoded in DSL (e.g., “no aplicable a puertas automáticas” → door.type == 'automatic'). Multiple exemptions separated by “; ”. If none, set null.

PARAGRAPH NUMBER:
- paragraph_number is the integer at the start of the paragraph where the Norm’s span begins. Ignore lettered subparagraphs. If none is identifiable, set null.

OUTPUT FORMAT (STRICT): A SINGLE raw JSON object (UTF-8). BEGIN WITH '{'. NO prose, NO explanations, NO markdown fences, NO backticks:
{
  "extractions": [
    {
      "Norm": "...exact text span...",
      "Norm_attributes": {
        "paragraph_number": <int or null>,
        "applies_if": "...DSL...",
        "satisfied_if": "...DSL...",
        "exempt_if": "...DSL or null"
      }
    }
  ]
}

CONSTRAINTS:
1) Only keys allowed: 'extractions','Norm','Norm_attributes','paragraph_number','applies_if','satisfied_if','exempt_if'.
2) Always return ≥1 extraction if there is regulatory content.
3) “Norm” MUST be a literal substring from the input (no ellipses). If too long, pick the first complete sentence containing the obligation/prohibition verb and its core conditions.
4) Do NOT output tables or compute values from tables.
5) Do NOT create a separate Norm for an exemption sentence; attach it as exempt_if.
6) If unsure about any field, set it to null instead of fabricating.
""")


examples = [
    # 1) SI 3 §6.1 — exits or evacuation > 50; alternatives in satisfied_if; exemption = automatic door
    lx.data.ExampleData(
        text="""
1 Las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50 personas serán abatibles con eje de giro vertical y su sistema de cierre, o bien no actuará mientras haya actividad en las zonas a evacuar, o bien consistirá en un dispositivo de fácil y rápida apertura desde el lado del cual provenga dicha evacuación, sin tener que utilizar una llave y sin tener que actuar sobre más de un mecanismo. Las anteriores condiciones no son aplicables cuando se trate de puertas automáticas.
""".strip(),
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
                    "applies_if": "door.use == 'exit' OR evacuation.persons > 50",
                    "satisfied_if": (
                        "door.type == 'swing' AND door.axis == 'vertical'; OR "
                        "closing.system.enabled == false; OR "
                        "(door.opening.from_evacuation_side == true AND door.opening.requires_key == false AND door.opening.mechanisms_count <= 1)"
                    ),
                    "exempt_if": "door.type == 'automatic'"
                }
            ),
        ]
    ),

    # 2) SI 3 §6.2 — device by familiarity / evacuation direction
    lx.data.ExampleData(
        text="""
2 Se considera que satisfacen el anterior requisito funcional los dispositivos de apertura mediante manilla o pulsador conforme a la norma UNE-EN 179:2009, cuando se trate de la evacuación de zonas ocupadas por personas que en su mayoría estén familiarizados con la puerta considerada, así como en caso contrario, cuando se trate de puertas con apertura en el sentido de la evacuación conforme al punto 3 siguiente, los de barra horizontal de empuje o de deslizamiento conforme a la norma UNE EN 1125:2009.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="Se considera que satisfacen el anterior requisito funcional los dispositivos de apertura mediante manilla o pulsador conforme a la norma UNE-EN 179:2009, cuando se trate de la evacuación de zonas ocupadas por personas que en su mayoría estén familiarizados con la puerta considerada",
                attributes={
                    "paragraph_number": 2,
                    "applies_if": "occupants.familiar_with_door == true",
                    "satisfied_if": "device.standard == 'UNE-EN 179:2009' AND device.type IN { 'handle','push_button' }",
                    "exempt_if": None
                }
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="así como en caso contrario, cuando se trate de puertas con apertura en el sentido de la evacuación conforme al punto 3 siguiente, los de barra horizontal de empuje o de deslizamiento conforme a la norma UNE EN 1125:2009.",
                attributes={
                    "paragraph_number": 2,
                    "applies_if": "occupants.familiar_with_door == false AND door.opening.direction == 'evacuation'",
                    "satisfied_if": "device.standard == 'UNE-EN 1125:2009' AND device.type IN { 'horizontal_push_bar','sliding_bar' }",
                    "exempt_if": None
                }
            ),
        ]
    ),

    # 3) SI 3 §6.3 — door opens in evacuation direction by capacity/use thresholds
    lx.data.ExampleData(
        text="""
3 Abrirá en el sentido de la evacuación toda puerta de salida:
a) prevista para el paso de más de 200 personas en edificios de uso Residencial Vivienda o de 100 personas en los demás casos, o bien
b) prevista para más de 50 ocupantes del recinto o espacio en el que esté situada.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="Abrirá en el sentido de la evacuación toda puerta de salida: a) prevista para el paso de más de 200 personas en edificios de uso Residencial Vivienda o de 100 personas en los demás casos",
                attributes={
                    "paragraph_number": 3,
                    "applies_if": "(building.use == 'residential_dwelling' AND served.persons > 200) OR (building.use == 'other' AND served.persons > 100)",
                    "satisfied_if": "door.opening.direction == 'evacuation'",
                    "exempt_if": None
                }
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="b) prevista para más de 50 ocupantes del recinto o espacio en el que esté situada.",
                attributes={
                    "paragraph_number": 3,
                    "applies_if": "space.occupants > 50",
                    "satisfied_if": "door.opening.direction == 'evacuation'",
                    "exempt_if": None
                }
            ),
        ]
    ),

    # 4) SI 3 §6.4 — revolving doors: adjacent manual swing doors; exemption; width sizing
    lx.data.ExampleData(
        text="""
4 Cuando existan puertas giratorias, deben disponerse puertas abatibles de apertura manual contiguas a ellas, excepto en el caso de que las giratorias sean automáticas y dispongan de un sistema que permita el abatimiento de sus hojas en el sentido de la evacuación, ante una emergencia o incluso en el caso de fallo de suministro eléctrico, mediante la aplicación manual de una fuerza no superior a 220 N. La anchura útil de este tipo de puertas y de las de giro automático después de su abatimiento, debe estar dimensionada para la evacuación total prevista.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="Cuando existan puertas giratorias, deben disponerse puertas abatibles de apertura manual contiguas a ellas",
                attributes={
                    "paragraph_number": 4,
                    "applies_if": "revolving_door.exists == true",
                    "satisfied_if": "adjacent.manual_swing_doors == true",
                    "exempt_if": "door.type == 'automatic' AND door.option.swing_allowed == true AND door.opening.push_force_N <= 220 AND (event.power_failure == true OR event.emergency_signal == true)"
                }
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="La anchura útil de este tipo de puertas y de las de giro automático después de su abatimiento, debe estar dimensionada para la evacuación total prevista.",
                attributes={
                    "paragraph_number": 4,
                    "applies_if": "adjacent.manual_swing_doors == true OR (door.type == 'automatic' AND door.option.swing_allowed == true)",
                    "satisfied_if": "door.clear_width_m >= evacuation.required_width_m",
                    "exempt_if": None
                }
            ),
        ]
    ),

    # 5) SI 3 §6.5 — automatic pedestrian doors: behavior by type; accessible-route forces
    lx.data.ExampleData(
        text="""
5 Las puertas peatonales automáticas dispondrán de un sistema que en caso de fallo en el suministro eléctrico o en caso de señal de emergencia, cumplirá las siguientes condiciones, excepto en posición de cerrado seguro:
a) Cuando se trate de una puerta corredera o plegable, abrir y mantenerse abierta, o permitir apertura abatible en el sentido de la evacuación mediante simple empuje con una fuerza total que no exceda de 220 N. La opción de apertura abatible no se admite cuando la puerta esté situada en un itinerario accesible según DB SUA.
b) Cuando se trate de una puerta abatible o giro-batiente (oscilo-batiente), abrir y mantenerse abierta, o permitir su abatimiento en el sentido de la evacuación mediante simple empuje con una fuerza total que no exceda de 150 N.
Cuando la puerta esté situada en un itinerario accesible según DB SUA, dicha fuerza no excederá de 25 N, en general, y de 65 N cuando sea resistente al fuego.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="a) ... corredera o plegable ... abrir y mantenerse abierta ... o apertura abatible ... ≤ 220 N. No se admite apertura abatible en itinerario accesible según DB SUA.",
                attributes={
                    "paragraph_number": 5,
                    "applies_if": "door.type == 'automatic_pedestrian' AND (event.power_failure == true OR event.emergency_signal == true) AND door.operation IN { 'sliding','folding' } AND system.position != 'fail_safe_closed'",
                    "satisfied_if": "door.state.open_maintained == true; OR (door.option.swing_allowed == true AND door.opening.push_force_N <= 220)",
                    "exempt_if": "route.accessible_dbsua == true AND door.option.swing_allowed == true"
                }
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="b) ... abatible o giro-batiente ... abrir y mantenerse abierta; o permitir abatimiento ... ≤ 150 N.",
                attributes={
                    "paragraph_number": 5,
                    "applies_if": "door.type == 'automatic_pedestrian' AND (event.power_failure == true OR event.emergency_signal == true) AND door.operation IN { 'swing','tilt_turn' } AND system.position != 'fail_safe_closed'",
                    "satisfied_if": "door.state.open_maintained == true; OR (door.option.swing_allowed == true AND door.opening.push_force_N <= 150)",
                    "exempt_if": None
                }
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="Cuando la puerta esté situada en un itinerario accesible según DB SUA, dicha fuerza no excederá de 25 N, en general, y de 65 N cuando sea resistente al fuego.",
                attributes={
                    "paragraph_number": 5,
                    "applies_if": "route.accessible_dbsua == true",
                    "satisfied_if": "(door.opening.push_force_N <= 25 AND door.fire_resistant == false); OR (door.opening.push_force_N <= 65 AND door.fire_resistant == true)",
                    "exempt_if": None
                }
            ),
        ]
    ),
]

# The input text to be processed
input_text = "1 Las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50 personas serán abatibles con eje de giro vertical y su sistema de cierre, o bien no actuará mientras haya actividad en las zonas a evacuar, o bien consistirá en un dispositivo de fácil y rápida apertura desde el lado del cual provenga dicha evacuación, sin tener que utilizar una llave y sin tener que actuar sobre más de un mecanismo. Las anteriores condiciones no son aplicables cuando se tra-te de puertas automáticas. 2 Se considera que satisfacen el anterior requisito funcional los dispositivos de apertura mediante ma-nilla o pulsador conforme a la norma UNE-EN 179:2009, cuando se trate de la evacuación de zonas ocupadas por personas que en su mayoría estén familiarizados con la puerta considerada, así como en caso contrario, cuando se trate de puertas con apertura en el sentido de la evacuación conforme al punto 3 siguiente, los de barra horizontal de empuje o de deslizamiento conforme a la norma UNE EN 1125:2009. 3 Abrirá en el sentido de la evacuación toda puerta de salida: a) prevista para el paso de más de 200 personas en edificios de uso Residencial Vivienda o de 100 personas en los demás casos, o bien. b) prevista para más de 50 ocupantes del recinto o espacio en el que esté situada. Para la determinación del número de personas que se indica en a) y b) se deberán tener en cuenta los criterios de asignación de los ocupantes establecidos en el apartado 4.1 de esta Sección. 4 Cuando existan puertas giratorias, deben disponerse puertas abatibles de apertura manual contiguas a ellas, excepto en el caso de que las giratorias sean automáticas y dispongan de un sistema que permita el abatimiento de sus hojas en el sentido de la evacuación, ante una emergencia o incluso en el caso de fallo de suministro eléctrico, mediante la aplicación manual de una fuerza no superior a 220 N. La anchura útil de este tipo de puertas y de las de giro automático después de su abatimiento, debe estar dimensionada para la evacuación total prevista. 5 Las puertas peatonales automáticas dispondrán de un sistema que en caso de fallo en el suministro eléctrico o en caso de señal de emergencia, cumplirá las siguientes condiciones, excepto en posición de cerrado seguro: a) Que, cuando se trate de una puerta corredera o plegable, abra y mantenga la puerta abierta o bien permita su apertura abatible en el sentido de la evacuación mediante simple empuje con una fuerza total que no exceda de 220 N. La opción de apertura abatible no se admite cuando la puerta esté situada en un itinerario accesible según DB SUA. b) Que, cuando se trate de una puerta abatible o giro-batiente (oscilo-batiente), abra y mantenga la puerta abierta o bien permita su abatimiento en el sentido de la evacuación mediante simple empuje con una fuerza total que no exceda de 150 N. Cuando la puerta esté situada en un itine-rario accesible según DB SUA, dicha fuerza no excederá de 25 N, en general, y de 65 N cuando sea resistente al fuego. La fuerza de apertura abatible se considera aplicada de forma estática en el borde de la hoja, per-pendicularmente a la misma y a una altura de 1000 ±10 mm, Las puertas peatonales automáticas se someterán obligatoriamente a las condiciones de manteni-miento conforme a la norma UNE 85121:2018."

# Run the extraction
# Load environment variables from .env file


result = lx.extract(
    text_or_documents=input_text,
    prompt_description=prompt,
    examples=examples,
    model_id="google/gemini-2.5-flash-lite",  # or any OpenRouter-supported model
    api_key=os.environ["OPENAI_API_KEY"],
    fence_output=False,
    use_schema_constraints=False,
    temperature=0.2,
    resolver_params={
        "fence_output": False,
        "format_type": lx.data.FormatType.JSON,
    },
    language_model_params={"temperature": 0.2},
)

print(result)
for ex in result.extractions:
    print(ex.extraction_class, ex.extraction_text[:60], ex.attributes)

# Save result directly as pretty multi-line JSON (UTF-8, unescaped accents)
import json

from langextract import data_lib
from langextract import schema as lx_schema

# Convert to plain dict

doc_dict = data_lib.annotated_document_to_dict(result)

output_path = "norms.json"  # pretty JSON file
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(doc_dict, f, ensure_ascii=False, indent=2)
print(f"Saved pretty JSON to {output_path}")

# --- DSL Glossary Extraction ---
import re

def extract_dsl_keys_from_norms(norms):
    """Extract all unique DSL keys from applies_if, satisfied_if, exempt_if fields in all extractions."""
    dsl_keys = set()
    dsl_fields = ["applies_if", "satisfied_if", "exempt_if"]
    # Regex: matches foo.bar, foo.bar_baz, foo, foo.bar[0], etc.
    dsl_key_pattern = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*")
    for extraction in norms.get("extractions", []):
        # Try both 'Norm_attributes' and 'attributes' for compatibility
        attrs = extraction.get("Norm_attributes")
        if attrs is None:
            attrs = extraction.get("attributes", {})
        if not attrs:
            continue
        for field in dsl_fields:
            val = attrs.get(field)
            if isinstance(val, str):
                for match in dsl_key_pattern.findall(val):
                    dsl_keys.add(match)
    return sorted(dsl_keys)

def get_ontology_explanations(keys):
    """Try to get explanations for each DSL key from LangExtract's ontology, fallback to empty string."""
    # Try to use LangExtract's schema/ontology if available
    explanations = {}
    # Try to get ontology from lx_schema if available
    ontology = getattr(lx_schema, "ONTOLOGY", None)
    for key in keys:
        # Try to find explanation in ontology (nested dict)
        explanation = ""
        if ontology:
            parts = key.split(".")
            node = ontology
            for part in parts:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    node = None
                    break
            if isinstance(node, dict) and "description" in node:
                explanation = node["description"]
            elif isinstance(node, str):
                explanation = node
        explanations[key] = explanation
    return explanations

# Extract DSL keys from the just-saved doc_dict
dsl_keys = extract_dsl_keys_from_norms(doc_dict)
glossary = get_ontology_explanations(dsl_keys)

glossary_path = "dsl_glossary.json"
with open(glossary_path, "w", encoding="utf-8") as f:
    json.dump(glossary, f, ensure_ascii=False, indent=2)
print(f"Saved DSL glossary to {glossary_path}")
