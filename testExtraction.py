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
- It MUST have a specific “WHAT to do / WHAT not to do” you can state in satisfied_if.
- It MAY have a “WHEN / FOR WHOM it applies” you can state in applies_if; if none is stated, set "Siempre".
- It MAY have explicit exceptions you can state in exempt_if (phrases like “excepto…”, “salvo…”, “no será de aplicación…”, “no se admite…”, “a menos que…”).

SCOPE (include/exclude):
- INCLUDE technical requirements on design, products, performance classes, installation, operation, or maintenance that are directly applicable to architectural/building design (e.g., door behavior, fire resistance, smoke control, evacuation rules).
- EXCLUDE purely administrative/procedural content (e.g., “Article 5 procedure”, approvals, project documentation steps) and generic principles without a concrete actionable requirement.
- IGNORE tables, figures, and their numeric lookups in this task (do not synthesize values from tables).
- Keep cross-references (e.g., “conforme al punto 3”) as text; do NOT resolve them.

SEGMENTATION & ATOMICITY:
- Extract ONE Norm per distinct compliance action/property. If a sentence lists alternatives (“o bien… / o …”) that are true alternatives for the same obligation, put them in a single satisfied_if separated by “; O …”.
- If a paragraph has multiple lettered sub-items (a), b), c) with different thresholds or scopes, create SEPARATE Norms per sub-item (do NOT merge across different applies_if).
- If several sentences impose the SAME satisfied_if under the SAME applies_if, merge into one Norm; otherwise keep them separate.
- Prohibitions (“no se considerará…”, “no se admite…”, “no debe…”) are valid Norms; write satisfied_if as a concise “No …” action.

MAPPING RULES:
- “applies_if”: quote or tightly grounded paraphrase of the condition triggers (signals: “cuando…”, “si…”, “en caso de…”, “para…”, “en edificios de uso…”, thresholds like “> 50 personas”). If unconditional, use "Siempre".
- “satisfied_if”: the minimal concrete action/property needed to comply (concise, exact units/classes kept, e.g., “empuje ≤ 220 N”, “EI 60”). No expansion beyond the text; preserve standard names (UNE-EN xxxx:yyyy) exactly.
- “exempt_if”: ONLY explicit non-applicability phrases. Do NOT create separate Norms for exemptions; fold them here. If multiple, separate with “; ”. If none, set null.
- Keep quoted names, units, and standards exactly as in the source (do not translate or normalize). Preserve hyphenation as it appears in the input.

PARAGRAPH NUMBER:
- paragraph_number is the integer at the start of the paragraph where the Norm’s text span BEGINS. Ignore lettered subparagraphs. If no leading integer is identifiable for that span, use null.

OUTPUT FORMAT (STRICT): A SINGLE raw JSON object (UTF-8). BEGIN WITH '{'. NO prose, NO explanations, NO markdown fences, NO backticks:
{
  "extractions": [
    {
      "Norm": "...exact text span...",
      "Norm_attributes": {
        "paragraph_number": <int or null>,
        "applies_if": "...",
        "satisfied_if": "...",
        "exempt_if": "... or null"
      }
    }
  ]
}

CONSTRAINTS:
1) Only keys allowed: 'extractions', 'Norm', 'Norm_attributes', 'paragraph_number', 'applies_if', 'satisfied_if', 'exempt_if'.
2) Always return ≥1 extraction if there is regulatory content.
3) “Norm” MUST be a literal substring from the input (no ellipses). If the span is too long for the model, prefer the first complete sentence that contains the obligation/prohibition verb and its core conditions.
4) Do NOT output tables or compute values from tables.
5) Do NOT create a separate Norm for an exemption sentence; attach it as exempt_if to the relevant Norm.
6) If unsure about any field, set it to null (do not fabricate).
""")

examples = [
    # 1) Obligación con exención explícita en el mismo párrafo (puertas de salida) + alternativas en “o bien…”
    lx.data.ExampleData(
        text="""
1 Las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50 personas serán abatibles con eje de giro vertical y su sistema de cierre, o bien no actuará mientras haya actividad en las zonas a evacuar, o bien consistirá en un dispositivo de fácil y rápida apertura desde el lado del cual provenga dicha evacuación, sin tener que utilizar una llave y sin tener que actuar sobre más de un mecanismo. Las anteriores condiciones no son aplicables cuando se trate de puertas automáticas.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Las puertas previstas como salida de planta o de edificio y las previstas para la evacuación de más de 50 personas serán abatibles "
                    "con eje de giro vertical y su sistema de cierre, o bien no actuará durante la actividad, o bien consistirá en un dispositivo de "
                    "fácil y rápida apertura desde el lado de evacuación, sin llave y sin más de un mecanismo."
                ),
                attributes={
                    "paragraph_number": 1,
                    "applies_if": "Puerta es salida de planta o edificio, o evacuación > 50 personas",
                    "satisfied_if": "Puerta abatible (eje vertical) y cierre desactivado durante actividad; O dispositivo de apertura fácil sin llave y sin más de un mecanismo",
                    "exempt_if": "Puerta automática"
                }
            ),
        ]
    ),

    # 2) Condición técnica en pasos de instalaciones (sellado EI) con alternativa de cumplimiento (“o conducto equivalente”)
    lx.data.ExampleData(
        text="""
Los pasos de instalaciones a través de elementos separadores de sectores de incendio deben garantizar una resistencia al fuego equivalente a la del elemento atravesado.
Este requisito se considerará satisfecho mediante sellados específicos con clasificación al menos equivalente, o mediante conductos/elementos de instalación que mantengan dicha resistencia de forma continua en su recorrido.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Los pasos de instalaciones a través de elementos separadores de sectores de incendio deben garantizar una resistencia al fuego "
                    "equivalente a la del elemento atravesado."
                ),
                attributes={
                    "paragraph_number": None,
                    "applies_if": "Paso de instalaciones atraviesa elemento separador de sectores de incendio",
                    "satisfied_if": "Resistencia al fuego del paso equivalente a la del elemento atravesado",
                    "exempt_if": None
                }
            ),
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Este requisito se considerará satisfecho mediante sellados específicos con clasificación equivalente, "
                    "o mediante conductos/elementos que mantengan dicha resistencia de forma continua en su recorrido."
                ),
                attributes={
                    "paragraph_number": None,
                    "applies_if": "Se exige equivalencia de resistencia al fuego en el paso de instalaciones",
                    "satisfied_if": "Sellado EI equivalente; O conducto/elemento que mantenga resistencia equivalente de forma continua",
                    "exempt_if": None
                }
            ),
        ]
    ),

    # 3) Prohibición con excepción (“no se considerarán medios de evacuación… salvo ascensor de emergencia”)
    lx.data.ExampleData(
        text="""
Los ascensores no se considerarán medios de evacuación. No obstante, podrán emplearse ascensores específicamente diseñados como de emergencia, siempre que cumplan las condiciones de seguridad y autonomía establecidas para tal fin.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text="Los ascensores no se considerarán medios de evacuación.",
                attributes={
                    "paragraph_number": None,
                    "applies_if": "Siempre",
                    "satisfied_if": "No utilizar ascensores como medio de evacuación",
                    "exempt_if": "Ascensor de emergencia diseñado específicamente y conforme a las condiciones de seguridad y autonomía aplicables"
                }
            ),
        ]
    ),

    # 4) Seguridad de uso en salidas: cierre sin llave durante ocupación con excepción “liberación automática”
    lx.data.ExampleData(
        text="""
Durante la ocupación del edificio, las puertas previstas como salida de emergencia no dispondrán de dispositivos de cierre que requieran llave desde el lado de evacuación; se admite el control por sistemas que liberen automáticamente el cierre en caso de alarma o fallo de suministro eléctrico.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Durante la ocupación del edificio, las puertas previstas como salida de emergencia no dispondrán de dispositivos de cierre que "
                    "requieran llave desde el lado de evacuación."
                ),
                attributes={
                    "paragraph_number": None,
                    "applies_if": "Edificio en uso (ocupación) y puerta es salida de emergencia",
                    "satisfied_if": "Ausencia de cierre que requiera llave desde el lado de evacuación",
                    "exempt_if": "Sistema de control que libere automáticamente el cierre ante alarma o fallo eléctrico"
                }
            ),
        ]
    ),

    # 5) Exigencia funcional con alternativas (ventilación natural o presión diferencial) y exención por tipología abierta
    lx.data.ExampleData(
        text="""
Las escaleras protegidas deben contar con evacuación de humos mediante ventilación directa al exterior o mediante sistema de presión diferencial que garantice el control de humos en caso de incendio.
Esta exigencia no será de aplicación a escaleras abiertas permanentemente al exterior en todos sus tramos.
""".strip(),
        extractions=[
            lx.data.Extraction(
                extraction_class="Norm",
                extraction_text=(
                    "Las escaleras protegidas deben contar con evacuación de humos mediante ventilación directa al exterior "
                    "o mediante sistema de presión diferencial que garantice el control de humos."
                ),
                attributes={
                    "paragraph_number": None,
                    "applies_if": "Escalera protegida",
                    "satisfied_if": "Ventilación directa al exterior; O sistema de presión diferencial que garantice control de humos",
                    "exempt_if": "Escalera abierta permanentemente al exterior en todos sus tramos"
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
    model_id="gemini-2.5-flash",
    api_key=os.environ["GOOGLE_API_KEY"],
    fence_output=False,
    use_schema_constraints=False, # Schema constraints not enforced for local model
    temperature=0.2,
    resolver_params={
        "fence_output": False,  # Parse raw JSON (no markers)
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
from dotenv import load_dotenv

# Convert to plain dict
doc_dict = data_lib.annotated_document_to_dict(result)

output_path = "norms.json"  # pretty JSON file
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(doc_dict, f, ensure_ascii=False, indent=2)

print(f"Saved pretty JSON to {output_path}")
