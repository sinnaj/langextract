## COMPACT SPEC (v1)
Purpose: Create a comprehensive list of entities: Norms, Procedures, Classifications, Tags, Parameters & Questions from the provided Building Regulation Documents. Produce a single JSON object: {"extractions":[{...required keys...}]}. NO markdown fences, NO extra prose. If data absent use empty lists, never null (except allowed nullable scalar fields noted).

TOP LEVEL REQUIRED KEYS (1 extraction object min): norms[], tags[], locations[], questions[], consequences[], parameters[], quality{errors[],warnings[],confidence_global,uncertainty_global}.

INVALID: legacy top arrays, missing root key, markdown fences, legacy keys NORM/NORM_attributes, null for required arrays, extra top-level keys.

SELF-CHECK (must pass before emitting): single root key extractions; each extraction has all required keys; arrays exist; JSON parses; no legacy keys; ids referenced exist; DSL tokens valid.

### Norms
A Norm is an atomic statement about regulation that needs to be followed. A Norm valid always has an applies_if statement that fences conditions under which it should be applied. A valid norm further dictates a satisfied_if condition that dictates the minimum requirements to comply with it.

1. Atomicity: split into separate norms if different thresholds OR different applicability triggers OR distinct obligation types.
2. Merge if identical (satisfied_if) AND same location scope.
3. Do NOT fabricate numeric values or enum members; only copy explicitly present or logically derivable from text (e.g., plural implies count >=2 NOT okay unless explicitly numeric).
4. If obligation phrased negatively ("no se admite"), set obligation_type PROHIBITION and encode satisfied_if reflecting the required negative state (e.g., DOOR.OPENING.REQUIRES_KEY == FALSE).
5. If unconditional: applies_if = TRUE.
6. If an explicit exemption sentence exists, integrate as exempt_if not separate Norm.
7. If a statement about application/exemption is made
7. If page cannot be confidently determined, set page = -1 and add quality.errors entry PAGE_MISSING (but per spec this should be exceptional).
8. If no location information is present set "COUNTRY": "ES"

## TAGS:
Tags reflect mentioned entities and states they can be in in DSL Language. If Tag is an entity that has sub entities or attributes, make sure the more general Entity is the parent.

1. Generate new tags when needed; BEFORE adding, check semantic equivalence with existing (case-insensitive, synonyms, head terms).
2. If a mid-chain tag emerges (e.g., previously DOOR.AUTOMATIC but now DOOR.AUTOMATIC.PEDESTRIAN distinct from DOOR.AUTOMATIC.INDUSTRIAL), restructure: update parents and include updated definitions for impacted tags - if not possible, mark it for later change
3. Keep depth only as deep as necessary; avoid leaf explosion with singletons unless semantically critical.

## LOCATIONS:
1. Capture EVERY explicit administrative or planning code.
2. If classification (residential/industrial/protected/etc.) is implied, include in classification; never invent.
3. Use GEO_CODES like ES.CT.BCN for composite referencing inside DSL only if derivable.

## QUESTIONS GUIDELINES:
Generate a question for a high-level tag IF it is broad, ambiguous, appears in >=3 norms OR is a critical branching dimension (e.g., PROJECT.TYPE, USAGE, DOOR.TYPE, SAFETY.FIRE). Use domain-appropriate professional phrasing derived from context; do not create leading or biased wording.

## RULES FOR CONSEQUENCES:
Identify any kind of explicitly mentioned or implied consequences that arise from Norms or the failure to adhere to them.

## PARAMETERS:
1. Extract each distinct numeric threshold only once; link to all norms referencing it.
2. Preserve unit; if no explicit unit, set null (never invent).

### DSL
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

### PRIORITY HEURISTICS
5 safety/emergency/legal gate; 4 major design impact; 3 standard technical; 2 narrow edge case; 1 minor clarifier.

### TRUNCATION
If truncation: truncated=true + QUALITY_TRUNCATED in errors; if more norms than emitted set has_more=true.

## PRIORITY HEURISTICS
Assign priority (1..5) using strongest applicable rule:
5: Safety-critical (seguridad, emergencia, evacuación, incendio, estructural failure risk) OR legal compliance gate / prerequisite for permitting.
4: Major design-impacting dimension (accessibility, structural loads, critical energy performance).
3: Standard technical requirement (materials, installation detail) with moderate scope.
2: Narrow edge-case requirement (rare zoning condition).
1: Minor clarifying or low-impact note with enforceable condition.

## VOLUME MANAGEMENT & TRUNCATION
If more norms exist than emitted, set has_more=true. If you hit length limits and must truncate, set truncated=true AND append warning QUALITY_TRUNCATED to quality.errors. Never produce partial JSON (must always be syntactically valid).

## GUARDRAILS (STRICT PROHIBITIONS)
1. DO NOT hallucinate numbers, units, page numbers, codes, or zone classifications.
2. DO NOT merge semantically distinct obligations.
3. DO NOT invent parent tags purely to reduce depth unless an actual semantic grouping is implied.
4. DO NOT output free prose outside specified fields.
5. If a function/operator outside grammar is needed, omit and note in quality.warnings (UNSUPPORTED_OPERATOR:<token>).
6. NEVER output duplicate tag objects with different definitions; instead update via status MERGED and merge_target.


END OF SPECIFICATION.
