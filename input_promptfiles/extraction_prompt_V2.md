## COMPACT SPEC (v1)
Purpose: Create a comprehensive list of entities: Norms, Procedures, Tags, Parameters & Questions from the provided Building Regulation Documents. Produce a single JSON object: {"extractions":[{...required keys...}]}. NO markdown fences, NO extra prose. If data absent use empty lists, never null (except allowed nullable scalar fields noted).

TOP LEVEL REQUIRED KEYS (1 extraction object min): norms[], tags[], locations[], questions[], consequences[], parameters[], quality{errors[],warnings[],confidence_global,uncertainty_global}.

INVALID: legacy top arrays, missing root key, markdown fences, legacy keys NORM/NORM_attributes, null for required arrays, extra top-level keys.

SELF-CHECK (must pass before emitting): single root key extractions; each extraction has all required keys; arrays exist; JSON parses; no legacy keys; ids referenced exist; DSL tokens valid.

### NORM FIELDS
Each norm: id, statement_text, obligation_type ∈ {MANDATORY, PROHIBITION, PERMISSION, CONDITIONAL, OPTIONAL, RECOMMENDATION}, paragraph_number (int|null), applies_if (DSL or TRUE), satisfied_if (DSL), exempt_if (DSL|null), priority (1..5), priority_factors (optional object), relevant_tags[], relevant_roles[], project_dimensions (optional object), lifecycle_phase[], topics[], location_scope (object), source{doc_id,page,span_char_start,span_char_end,...}, extracted_parameters_ids[], consequence_ids[], confidence, uncertainty, notes(optional).
Rules: split by differing triggers/thresholds/obligation_type; merge only identical core logic; no fabrication; negative phrasing → PROHIBITION + encode state; unconditional → applies_if TRUE; use exempt_if not extra norm; page unknown → page=-1 plus PAGE_MISSING error.

### DSL
Tokens UPPERCASE.DOTCASE. Operators: == != < <= > >= AND OR NOT IN[...] WITHIN() OVERLAPS() ADJACENT_TO() HAS(). Booleans TRUE/FALSE. Strings single quotes. Alternatives in satisfied_if separated by "; OR ". No free prose.

### TAG OBJECT
id, tag_path, parent|null, definition, synonyms[], introduced_by_norm_ids[], refined_by_norm_ids[], related_tag_paths[], status ∈ {ACTIVE,MERGED,REPLACED}, merge_target|null, confidence, uncertainty.

### LOCATION OBJECT
id, type ∈ {COUNTRY,STATE,PROVINCE,REGION,COMMUNE,PLANNING_ZONE,INDUSTRIAL_ZONE}, code, name|null, parent_codes[], classification[], related_zone_codes[], source{doc_id,page,span_char_start,span_char_end}, confidence, uncertainty.

### QUESTION OBJECT
id, tag_path, question_text, answer_type ∈ {BOOLEAN,ENUM,NUMBER,STRING}, enum_values[], outputs[], derived_follow_up_question_ids[], trigger_norm_ids[], confidence, uncertainty.

### CONSEQUENCE OBJECT
id, kind ∈ {ANNEX,DECLARATION,STATEMENT,CERTIFICATION,INSPECTION,SURVEY,TRIGGER,QUESTIONNAIRE,NORM_ACTIVATION,TAG_ACTIVATION}, reference_code|null, description, activates_norm_ids[], activates_tag_paths[], activates_question_ids[], required_documents[], source_norm_ids[], confidence, triggers[] (optional), effects[] (optional), uncertainty.

### PARAMETER OBJECT
id, field_path, operator ∈ {<=,<,>=,>,==,!=}, value (num|string), unit|null, original_text, norm_ids[], confidence, uncertainty.

### QUALITY
quality.errors[], quality.warnings[], confidence_global, uncertainty_global. Common errors: PAGE_MISSING, QUALITY_TRUNCATED, DUPLICATE_TAG_COLLAPSED:<tag>, UNSUPPORTED_OPERATOR:<tok>, INVALID_DSL_SYNTAX:<reason>, MISSING_REQUIRED_FIELD:<field>.

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

### AUTO-REPAIR (pre-output): If any required key missing / invalid structure / legacy key present / arrays null / JSON invalid → rebuild internally then emit only corrected final JSON once.

END OF COMPACT SPEC.
Each element of "norms":
{
  "id": "N::<stable_local_id>",          // e.g., N::0001 (unique within output)
  "statement_text": "<canonical extracted sentence/span in source language (Spanish/Catalan), normalized whitespace>",
  "obligation_type": "MANDATORY" | "PROHIBITION" | "PERMISSION" | "CONDITIONAL",
  "paragraph_number": <int | null>,
  "applies_if": "<DSL or TRUE>",
  "satisfied_if": "<DSL>",               // minimal compliance state
  "exempt_if": "<DSL or null>",
  "priority": <int 1..5>,                 // 5 = critical (e.g., safety, emergency); derive heuristically
  "priority_factors": {                   // OPTIONAL decomposition
    "severity": <float|null>,
    "likelihood": <float|null>,
    "impact": <float|null>
  },
  "relevant_tags": ["DOOR.AUTOMATIC", ...],
  "relevant_roles": ["ARCHITECT", "OWNER", ...] | [],
  "project_dimensions": {                 // only include if referenced or implied
    "PROJECT.TYPE": ["NEW", "REFORM"],
    "OWNERSHIP": ["PRIVATE"],
    "USAGE": ["FAMILY.SINGLE"],
    "WORK.TYPE": ["CONSTRUCTION.DOORS"],
    "WORK.EFFECTS": ["CLOSURE.STREET"],
    "WORK.TYPE.AUXILARY": ["SWIMMINGPOOL"]
  },
  "lifecycle_phase": ["DESIGN", "EXECUTION", "MAINTENANCE"] | [],
  "topics": ["SAFETY.FIRE", ...],
  "location_scope": {                     // same structure as in document_metadata but may be narrower
    "COUNTRY": "ES", "STATES": ["CAT"], "PROVINCES": [], "REGIONS": [], "COMMUNES": [], "ZONES": ["R6.2"], "GEO_CODES": ["ES.CT.BCN"], "UNCERTAINTY": <float>
  },
  "source": {
    "doc_id": "...", "article": "...", "page": <int>,
    "span_char_start": <int>, "span_char_end": <int>,
    "visual_refs": [ {"type": "TABLE" | "IMAGE" | "MAP", "label": "Tabla 3", "page": <int>} ]
  },
  "extracted_parameters_ids": ["P::0005", ...],  // if parameters apply
  "consequence_ids": ["C::0010", ...],           // consequences triggered by this norm
  "confidence": <float 0..1>,
  "uncertainty": <float 0..1>,
  "notes": "<optional clarifying note or rationale>"
}

RULES:
1. Atomicity: split into separate norms if different thresholds OR different applicability triggers OR distinct obligation types.
2. Merge if identical (satisfied_if) AND same location scope.
3. Do NOT fabricate numeric values or enum members; only copy explicitly present or logically derivable from text (e.g., plural implies count >=2 NOT okay unless explicitly numeric).
4. If obligation phrased negatively ("no se admite"), set obligation_type PROHIBITION and encode satisfied_if reflecting the required negative state (e.g., DOOR.OPENING.REQUIRES_KEY == FALSE).
5. If unconditional: applies_if = TRUE.
6. If an explicit exemption sentence exists, integrate as exempt_if not separate Norm.
7. If a statement about application/exemption is made
7. If page cannot be confidently determined, set page = -1 and add quality.errors entry PAGE_MISSING (but per spec this should be exceptional).
8. If no location information is present set "COUNTRY": "ES"

--------------------------------------------------------------------------------
## 4. DSL GRAMMAR (STRICT)
FIELD & TAG PATHS: UPPERCASE.DOTCASE (segments A-Z0-9 underscore allowed). Examples: DOOR.TYPE, ROUTE.ACCESSIBLE, PROJECT.TYPE, CONSTRUCTION.ELECTORNICAL.RADIO.

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

--------------------------------------------------------------------------------
## 5. TAG (ONTOLOGY) OBJECT SPECIFICATION
Each element of "tags":
{
  "id": "T::<id>",
  "tag_path": "DOOR.AUTOMATIC.FAIL_SAFE",   // canonical, stable within this output
  "parent": "DOOR.AUTOMATIC" | null,       // null only for root-level
  "definition": "<concise definition in Spanish (or Catalan if source chunk majority is Catalan)>",
  "synonyms": ["puerta automática fail-safe"],
  "introduced_by_norm_ids": ["N::0008"],
  "refined_by_norm_ids": ["N::0010"],
  "related_tag_paths": ["SAFETY.FIRE"],
  "status": "ACTIVE" | "MERGED" | "REPLACED",
  "merge_target": "<other tag_path if status MERGED/Replaced else null>",
  "confidence": <float>,
  "uncertainty": <float>
}

RULES:
1. Generate new tags when needed; BEFORE adding, check semantic equivalence with existing (case-insensitive, synonyms, head terms).
2. If a mid-chain tag emerges (e.g., previously DOOR.AUTOMATIC but now DOOR.AUTOMATIC.PEDESTRIAN distinct from DOOR.AUTOMATIC.INDUSTRIAL), restructure: update parents and include updated definitions for impacted tags - if not possible, mark it for later change
3. Keep depth only as deep as necessary; avoid leaf explosion with singletons unless semantically critical.

--------------------------------------------------------------------------------
## 6. LOCATION ENTITY OBJECT SPECIFICATION
Each in "locations":
{
  "id": "L::<id>",
  "type": "COUNTRY" | "STATE" | "PROVINCE" | "REGION" | "COMMUNE" | "PLANNING_ZONE",
  "code": "ES" | "CAT" | "BARCELONA" | "R6.2" | "PEM2",
  "name": "Cataluña" | "Barcelona" | null (if code only),
  "parent_codes": ["ES", "CAT", ...],       // ordered root→parent
  "classification": ["RESIDENTIAL", "INDUSTRIAL"] | [],
  "related_zone_codes": ["R6.2","PEM2"],
  "source": {"doc_id": "...", "page": <int>, "span_char_start": <int>, "span_char_end": <int>},
  "confidence": <float>,
  "uncertainty": <float>
}

RULES:
1. Capture EVERY explicit administrative or planning code.
2. If classification (residential/industrial/protected/etc.) is implied, include in classification; never invent.
3. Use GEO_CODES like ES.CT.BCN for composite referencing inside DSL only if derivable.

--------------------------------------------------------------------------------
## 7. QUESTION OBJECT SPECIFICATION
Each in "questions":
{
  "id": "Q::<id>",
  "tag_path": "DOOR.TYPE",                // the target variable/tag cluster
  "question_text": "¿Qué tipo de puerta es?", // Spanish/Catalan matching source document language
  "answer_type": "BOOLEAN" | "ENUM" | "NUMBER" | "STRING",
  "enum_values": ["SWING","SLIDING","FOLDING","TILT_TURN","AUTOMATIC","AUTOMATIC_PEDESTRIAN"] | [],
  "outputs": ["DOOR.TYPE"],               // DSL variables this question informs (may be >1)
  "derived_follow_up_question_ids": ["Q::0015"],
  "trigger_norm_ids": ["N::0001","N::0004"],  // norms whose applicability can be decided by the answer
  "confidence": <float>,
  "uncertainty": <float>
}

TRIGGERING GUIDELINES:
Generate a question for a high-level tag IF it is broad, ambiguous, appears in >=3 norms OR is a critical branching dimension (e.g., PROJECT.TYPE, USAGE, DOOR.TYPE, SAFETY.FIRE). Use domain-appropriate professional phrasing derived from context; do not create leading or biased wording.

--------------------------------------------------------------------------------
## 8. CONSEQUENCE OBJECT SPECIFICATION
Each in "consequences":
{
  "id": "C::<id>",
  "kind": "ANNEX" | "DECLARATION" | "STATEMENT" | "CERTIFICATION" | "INSPECTION" | "SURVEY" | "TRIGGER" | "QUESTIONNAIRE" | "NORM_ACTIVATION" | "TAG_ACTIVATION",
  "reference_code": "Anexo III" | null,
  "description": "<concise Spanish/Catalan text>",
  "activates_norm_ids": ["N::0012"],
  "activates_tag_paths": ["ENERGYSAVING.PV"],
  "activates_question_ids": ["Q::0007"],
  "required_documents": ["FORM-ER-999"],
  "source_norm_ids": ["N::0005"],
  "confidence": <float>,
  "triggers": [],                 // OPTIONAL future structured trigger predicates
  "effects": [],                  // OPTIONAL future structured effect descriptors
  "uncertainty": <float>
}

--------------------------------------------------------------------------------
## 9. PARAMETER OBJECT SPECIFICATION
Each in "parameters":
{
  "id": "P::<id>",
  "field_path": "DOOR.OPENING.PUSH_FORCE_N",    // DSL variable referenced
  "operator": "<=" | "<" | ">=" | ">" | "==" | "!=",
  "value": 220,                                   // numeric or string literal (unquoted in JSON)
  "unit": "N" | "m" | null,
  "original_text": "220 N",                     // exact source fragment
  "norm_ids": ["N::0001","N::0002"],
  "confidence": <float>,
  "uncertainty": <float>
}

RULES:
1. Extract each distinct numeric threshold only once; link to all norms referencing it.
2. Preserve unit; if no explicit unit, set null (never invent).

--------------------------------------------------------------------------------
## 10. PROJECT / TOPIC DIMENSIONS (ENUM REFERENCES)
Use these enumerations EXACTLY when applicable (do not create variants unless new concept explicit):
- PROJECT.TYPE: NEW, REFORM, AMPLIACION_ESTRUCTURA, LEGALISATION
- OWNERSHIP: PRIVATE, COMMERCIAL, EDUCATION, PUBLIC, (others only if explicitly present)
- USAGE: FAMILY.SINGLE, FAMILY.MULTIPLE, PUBLIC.EDUCATION, PUBLIC.GOV, PUBLIC.PARK, HOSPITAL, AGRICULTURE
- WORK.TYPE: NEW_BUILD, DEMOLITION.PARTIAL, DEMOLITION.TOTAL, USAGE.CHANGE.WHOLE, USAGE.CHANGE.PARTIAL, CONSTRUCTION.INSIDE, CONSTRUCTION.OUTSIDE, CONSTRUCTION.STRUCTURAL, CONSTRUCTION.FLOORS, CONSTRUCTION.DOORS, CONSTRUCTION.WINDOWS, CONSTRUCTION.STAIRS, CONSTRUCTION.EMERGENCYPATH, ELECTRO.ELEVATOR, ELECTRO.HEATING, ELECTRO.CLIMATE, ELECTRO.PHOTOVOLTAIC, ELECTRO.PHOTOVOLTAIC.INTERIOR, ELECTRO.PHOTOVOLTAIC.EXTERIOR, ELECTRO.PHOTOVOLTAIC.EXTERIOR.GARDEN, ELECTRO.RADIOCOMMUNICATION, ELECTRO.OTHER, GAS.HEATING, GAS.KITCHEN, GAS.OTHER
- WORK.EFFECTS: CLOSURE.STREET, CLOSURE.PARK, CLOSURE.AREA, CONSTRUCTION.FACILITIES
- WORK.TYPE.AUXILARY: CONSTRUCTION, SWIMMINGPOOL, ELECTRO.RADIOCOMMUNICATION (extend only if explicit)
- TOPICS: SAFETY.STRUCTURAL, SAFETY.FIRE, SAFETY.USE, ACCESSIBILITY, SAFETY.ACCIDENTPREVENTION, HEALTH, SANITATION, PROTECTION.DAMP, PROTECTION.INDOOR.AIR, PROTECTION.ELECTRONICS, PROTECTION.SUPPLY.WATER, PROTECTION.NOISE, ENERGYSAVING, ENERGYSAVING.THERMAL, ENERGYSAVINGS.SOLAR, ENERGYSAVINGS.PV, ENERGYSAVINGS.HVAC.EFFICIENCY, ENERGYSAVINGS.LIGHTING.EFFICIENCY
- MATERIALSANDEFFECTS: LOADS, SNOW, WIND, EARTHQUAKES, RAIN, FOUNDATIONS, STEEL, MASONRY, TIMBER, ALUMINIUM

--------------------------------------------------------------------------------
## 11. PRIORITY HEURISTICS
Assign priority (1..5) using strongest applicable rule:
5: Safety-critical (seguridad, emergencia, evacuación, incendio, estructural failure risk) OR legal compliance gate / prerequisite for permitting.
4: Major design-impacting dimension (accessibility, structural loads, critical energy performance).
3: Standard technical requirement (materials, installation detail) with moderate scope.
2: Narrow edge-case requirement (rare zoning condition).
1: Minor clarifying or low-impact note with enforceable condition.

--------------------------------------------------------------------------------
## 12. CONFIDENCE & UNCERTAINTY
For each object, provide confidence (model internal certainty) and uncertainty (expected error probability) both floats 0..1. If confident, confidence ~0.9+, uncertainty ~0.05 or less. Never set both extremes simultaneously (no confidence=1 with uncertainty>0.0). If a required datum (page, doc_id) absent -> mark uncertainty >=0.5 for that object and add quality.errors code.

--------------------------------------------------------------------------------
## 13. VOLUME MANAGEMENT & TRUNCATION
Choose a reasonable max_norms_per_5k_tokens (e.g., 35) to ensure JSON integrity. If more norms exist than emitted, set has_more=true. If you hit length limits and must truncate, set truncated=true AND append warning QUALITY_TRUNCATED to quality.errors. Never produce partial JSON (must always be syntactically valid).

--------------------------------------------------------------------------------
## 14. GUARDRAILS (STRICT PROHIBITIONS)
1. DO NOT hallucinate numbers, units, page numbers, codes, or zone classifications.
2. DO NOT merge semantically distinct obligations.
3. DO NOT invent parent tags purely to reduce depth unless an actual semantic grouping is implied.
4. DO NOT output free prose outside specified fields.
5. If a function/operator outside grammar is needed, omit and note in quality.warnings (UNSUPPORTED_OPERATOR:<token>).
6. NEVER output duplicate tag objects with different definitions; instead update via status MERGED and merge_target.

--------------------------------------------------------------------------------
## 15. ALGORITHM (STEP EXECUTION STRATEGY)
1. SCAN & SEGMENT: Identify candidate normative sentences (obligation verbs: deberá, se debe, no se admite, será, tiene que, queda prohibido, está permitido, etc.).
2. CLASSIFY & SPLIT: For each candidate, derive obligation_type & split distinct applicability thresholds.
3. DSL MAP: Extract variables (UPPERCASE dot path). Reuse existing; create new tags if needed.
4. EXEMPTIONS: Attach negative applicability / exceptions into exempt_if.
5. PARAMETERS: Collect numeric thresholds (220 N, 50 personas) → parameter objects; connect to norms.
6. LOCATION: Extract all jurisdiction and zone references, generate location entities, relate to norms.
7. TAG HIERARCHY: Insert or restructure tag paths; mark merges where necessary.
8. QUESTIONS: For broad tags or high branching topics produce questions (question_text matches source language).
9. CONSEQUENCES: Capture annex/form/activation triggers & link them via consequence_ids.
10. PRIORITY & METRICS: Assign priority, confidence, uncertainty.
11. CONSOLIDATE & VALIDATE: Ensure references (IDs) exist; ensure DSL syntax; ensure arrays present.
12. OUTPUT final JSON object.

--------------------------------------------------------------------------------

## 16. MINIMAL EXAMPLE (ABBREVIATED – Illustrative ONLY)
{
  "extractions":
      "norms": [
        {
          "id": "N::0001",
          "statement_text": "Las puertas previstas como salida ... serán abatibles ...",
          "Norm": "Las puertas previstas como salida ... serán abatibles ...",  // legacy duplicate (optional)
          "obligation_type": "MANDATORY",
          "paragraph_number": 1,
          "applies_if": "DOOR.USE == 'EXIT' OR EVACUATION.PERSONS > 50",
          "satisfied_if": "DOOR.TYPE == 'SWING' AND DOOR.AXIS == 'VERTICAL'; OR CLOSING.SYSTEM.ENABLED == FALSE; OR (DOOR.OPENING.FROM_EVACUATION_SIDE == TRUE AND DOOR.OPENING.REQUIRES_KEY == FALSE AND DOOR.OPENING.MECHANISMS_COUNT <= 1)",
          "exempt_if": "DOOR.TYPE == 'AUTOMATIC'",
          "priority": 5,
          "priority_factors": {"severity": null, "likelihood": null, "impact": null},
          "relevant_tags": ["DOOR.SWING","EVACUATION"],
          "relevant_roles": ["ARCHITECT"],
          "project_dimensions": {"PROJECT.TYPE": ["NEW","REFORM"]},
          "lifecycle_phase": ["DESIGN"],
          "topics": ["SAFETY.FIRE"],
          "location_scope": {"COUNTRY": "ES", "STATES": [], "PROVINCES": [], "REGIONS": [], "COMMUNES": [], "ZONES": [], "GEO_CODES": [], "UNCERTAINTY": 0.05},
          "source": {"doc_id": "ccte_si.pdf", "article": "SI 3 6", "page": 120, "span_char_start": 15, "span_char_end": 390, "visual_refs": []},
          "extracted_parameters_ids": ["P::0001","P::0002"],
          "consequence_ids": [],
          "confidence": 0.92,
          "uncertainty": 0.07,
          "notes": "Alternatives represented via ; OR"
        }
      ],
      "tags": [
        {"id": "T::0001", "tag_path": "DOOR.SWING", "parent": "DOOR", "definition": "Puerta abatible", "synonyms": ["puerta abatible"], "introduced_by_norm_ids": ["N::0001"], "refined_by_norm_ids": [], "related_tag_paths": ["EVACUATION"], "status": "ACTIVE", "merge_target": null, "confidence": 0.9, "uncertainty": 0.1}
      ],
      "locations": [],
      "questions": [
        {"id": "Q::0001", "tag_path": "DOOR.TYPE", "question_text": "¿Qué tipo de puerta es?", "answer_type": "ENUM", "enum_values": ["SWING","SLIDING","FOLDING","TILT_TURN","AUTOMATIC","AUTOMATIC_PEDESTRIAN"], "outputs": ["DOOR.TYPE"], "derived_follow_up_question_ids": [], "trigger_norm_ids": ["N::0001"], "confidence": 0.9, "uncertainty": 0.1}
      ],
      "consequences": [],
      "parameters": [
        {"id": "P::0001", "field_path": "DOOR.OPENING.MECHANISMS_COUNT", "operator": "<=", "value": 1, "unit": null, "original_text": "más de un mecanismo", "norm_ids": ["N::0001"], "confidence": 0.85, "uncertainty": 0.15},
        {"id": "P::0002", "field_path": "EVACUATION.PERSONS", "operator": ">", "value": 50, "unit": null, "original_text": "> 50 personas", "norm_ids": ["N::0001"], "confidence": 0.9, "uncertainty": 0.1}
      ],
      "quality": {"errors": [], "warnings": [], "confidence_global": 0.9, "uncertainty_global": 0.1}
    }
  ]
}

--------------------------------------------------------------------------------
## 17. COMMON ERROR CODES
- PAGE_MISSING
- QUALITY_TRUNCATED
- DUPLICATE_TAG_COLLAPSED:<tag_path>
- UNSUPPORTED_OPERATOR:<token>
- INVALID_DSL_SYNTAX:<reason>
- MISSING_REQUIRED_FIELD:<field>

--------------------------------------------------------------------------------
## 18. FINAL CHECKLIST (MODEL MUST SELF-VERIFY BEFORE OUTPUT)
1. JSON parses & all required top-level keys present.
2. Arrays exist even if empty.
3. Every referenced ID exists (norms, tags, questions, consequences, parameters).
4. DSL expressions contain ONLY allowed tokens & operators.
5. No hallucinated numeric/unit values.
6. No duplicate tag_path with conflicting ACTIVE definitions.
7. page present (not -1) unless error logged.
8. has_more/truncated flags consistent with counts.

### 19. AUTO-REPAIR / REGENERATION DIRECTIVE (STRICT)
IF during your internal self-check ANY of the following issues are detected you MUST discard the draft and rebuild a corrected JSON before emitting:
 - Root object not exactly {"extractions": [...]}
 - Any extraction object missing a required key
 - Any norm missing "statement_text"
 - Null instead of [] for any required array
 - Trailing commas or other JSON syntax errors

You have ONE opportunity: only emit the final corrected JSON once. Never emit explanations, apologies, or fences. Never emit a partial first then a corrected second (only the corrected final). If constraints cannot be satisfied, still emit a syntactically valid minimal JSON following the template with empty arrays and at least one extraction object.

END OF SPECIFICATION.
