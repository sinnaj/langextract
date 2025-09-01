## BASE PROMPT
Create a comprehensive list of entities: Sections, Norms, Procedures, Classifications and Legal Documents from the provided Building Regulation Documents.

## OUTPUT FORMAT
Produce a single JSON object: {"extractions":[{...required keys...}]}. NO markdown fences, NO extra prose. If data absent use empty lists, never null (except allowed nullable scalar fields noted).

TOP LEVEL REQUIRED KEYS (1 extraction object min): sections[], norms[], procedures[], classifications[], legal_docs[], quality{errors[], warnings[], confidence}.

## Document Section
Sections divide the provided document depending on their content. Sections can take the form of but are not limited to Document Title, Headlines, Article, Apendix etc.

### Norms
A Norm is an atomic statement about regulation that needs to be followed. A norm is always applicable and valid in and of itself without further context being necessary. A valid Norm always has an applies_if statement that fences conditions under which it should be applied. A valid norm further dictates a satisfied_if condition that dictates the minimum requirements to comply with it.

1. Atomicity: split into separate norms if different thresholds OR different applicability triggers OR distinct obligation types.
2. Merge if identical (satisfied_if) AND same location scope.
3. Do NOT fabricate numeric values or enum members; only copy explicitly present or logically derivable from text (e.g., plural implies count >=2 NOT okay unless explicitly numeric).
4. If obligation phrased negatively ("no se admite"), set obligation_type PROHIBITION and encode satisfied_if reflecting the required negative state (e.g., DOOR.OPENING.REQUIRES_KEY == FALSE).
5. If an explicit exemption sentence exists, integrate as exempt_if not separate Norm.
6. If page cannot be confidently determined, set page = -1 and add quality.errors entry PAGE_MISSING (but per spec this should be exceptional).
7. If no location information is present set "COUNTRY": "ES"
8. If a Norm references a section within the same document in a way that makes it a satisfied_if statement, the satisfied_if should be directly made out of the content of that section rather than simply stating satisfied_if complying with that section.

## PROCEDURES
A Procedure is a description of how a specific task is carried out. I can include but is not limited to:

1. Details of how specific calculation should be performed
2. Description of how a certain work should be carried out
3. Description of how an application process should be carried out

## CLASSIFCATIONS
A Classification is a description of how an entity is classified within the context of a Norm. It extends or limits the applicability of a Norm or set of Norms based on the classification of an entity.

## LEGAL DOCUMENT:
A Legal Document is a direct reference to a piece of legislation.

### DSL GUIDELINES
PATHS: UPPERCASE.DOTCASE (segments A-Z0-9 underscore allowed). Examples: DOOR.TYPE, ROUTE.ACCESSIBLE, PROJECT.TYPE, CONSTRUCTION.ELECTORNICAL.RADIO.

LITERALS:
- Strings: single quotes 'VALUE'; enumeration literals are UPPERCASE.WORD or UPPERCASE.WORD.WORD (mirrors tags) but inside quotes they remain as-is.
- Numbers: integers or decimals with dot.
- Booleans: TRUE / FALSE (uppercase).

OPERATORS:
- Comparison: == != < <= > >=
- Logical: AND OR NOT (uppercase) with parentheses for grouping
- Membership: VAR IN['VAL1','VAL2','VAL3'] (no spaces after IN)  
  (If only one value, you MAY use equality instead.)
- No range shorthand; express ranges explicitly: X >= 0 AND X <= 20
- Existence: HAS(DOOR.AUTOMATIC) means tag/path recognized in ontology for this context.
- Geo scoping operators:
  - WITHIN('ES.CT.BCN')  // hierarchical geo code containment
  - OVERLAPS('ZONE:R6.2')
  - ADJACENT_TO('ZONE:PEM2')
Use inside applies_if / exempt_if: (LOCATION.WITHIN('ES.CT.BCN') AND ZONE.CODE IN['R6.2']). Represent these pseudo-functions literally.

SYNTAX VALIDATION:
- No free prose outside DSL tokens.
- Separate alternative compliance clauses in satisfied_if with "; OR " EXACTLY.
- When both structural alternative sets and parameter thresholds present, order from simplest structural predicate to more complex threshold forms.

### ENUM BLOCKS (use exactly; no invention; omit unused in DSL but keep tag paths in norms/questions):
ENUM.PROJECT.TYPE=[NEW,REFORM,AMPLIACION_ESTRUCTURA,LEGALISATION]
ENUM.OWNERSHIP=[PRIVATE,COMMERCIAL,EDUCATION,PUBLIC]
ENUM.USAGE=[PUBLIC.EDUCATION,PUBLIC.GOV,PUBLIC.PARK,PUBLIC.HOSPITAL,AGRICULTURE,GENERAL,RESIDENTIAL.HOUSING,ADMINISTRATIVE,PUBLIC.COMMERCIAL,PUBLIC.RESIDENTIAL,PUBLIC.ASSEMBLY,PARKING]
ENUM.WORK.TYPE=[NEW_BUILD,DEMOLITION.PARTIAL,DEMOLITION.TOTAL,USAGE.CHANGE.WHOLE,USAGE.CHANGE.PARTIAL,CONSTRUCTION.INSIDE,CONSTRUCTION.OUTSIDE,CONSTRUCTION.STRUCTURAL,CONSTRUCTION.FLOORS,CONSTRUCTION.DOORS,CONSTRUCTION.WINDOWS,CONSTRUCTION.STAIRS,CONSTRUCTION.EMERGENCYPATH,ELECTRO.ELEVATOR,ELECTRO.HEATING,ELECTRO.CLIMATE,ELECTRO.PHOTOVOLTAIC,ELECTRO.PHOTOVOLTAIC.INTERIOR,ELECTRO.PHOTOVOLTAIC.EXTERIOR,ELECTRO.PHOTOVOLTAIC.EXTERIOR.GARDEN,ELECTRO.RADIOCOMMUNICATION,ELECTRO.OTHER,GAS.HEATING,GAS.KITCHEN,GAS.OTHER]
ENUM.WORK.EFFECTS=[CLOSURE.STREET,CLOSURE.PARK,CLOSURE.AREA,CONSTRUCTION.FACILITIES]
ENUM.WORK.TYPE.AUXILARY=[CONSTRUCTION,SWIMMINGPOOL,ELECTRO.RADIOCOMMUNICATION]
ENUM.TOPICS=[SAFETY.STRUCTURAL,SAFETY.FIRE,SAFETY.USE,ACCESSIBILITY,SAFETY.ACCIDENTPREVENTION,HEALTH,SANITATION,PROTECTION.DAMP,PROTECTION.INDOOR.AIR,PROTECTION.ELECTRONICS,PROTECTION.SUPPLY.WATER,PROTECTION.NOISE,ENERGYSAVING,ENERGYSAVING.THERMAL,ENERGYSAVINGS.SOLAR,ENERGYSAVINGS.PV,ENERGYSAVINGS.HVAC.EFFICIENCY,ENERGYSAVINGS.LIGHTING.EFFICIENCY]
ENUM.MATERIALSANDEFFECTS=[LOADS,SNOW,WIND,EARTHQUAKES,RAIN,FOUNDATIONS,STEEL,MASONRY,TIMBER,ALUMINIUM]

## GUARDRAILS (STRICT PROHIBITIONS)
1. DO NOT hallucinate numbers, units, page numbers, codes, or zone classifications.
2. DO NOT merge semantically distinct obligations.
3. DO NOT invent parent tags purely to reduce depth unless an actual semantic grouping is implied.
4. DO NOT output free prose outside specified fields.
5. If a function/operator outside grammar is needed, omit and note in quality.warnings (UNSUPPORTED_OPERATOR:<token>).
6. NEVER output duplicate tag objects with different definitions; instead update existing.


END OF SPECIFICATION.
