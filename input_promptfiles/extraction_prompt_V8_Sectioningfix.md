## TASK
Extract a comprehensive set of **Document Metadata, Sections, Norms, Procedures, Classifications, and Document References** from the provided Building Regulation documents.

Only return data that is explicitly stated or **logically derivable without inventing values**.
If a datum is absent, leave it empty (not null, except where nullable scalars are allowed in your schema provided elsewhere).

## OUTPUT FORMAT
Produce a single JSON object: {"extractions":[{...required keys...}]}. NO markdown fences, NO extra prose. If data absent use empty lists, never null (except allowed nullable scalar fields noted).

---

## ENTITIES & RULES

### Sections (document structure)
- Model the document’s outline as a strict hierarchy. Each section has **exactly one parent**.
- Cache Section output between
- Typical forms: Chapter, Headline (Level 1 - Level n), Article, Appendix (non-exhaustive), Table, Image.
- Valid hierarchies:
  - `Document > Chapter > Headline L1 > Headline L2> Headline L...> Article`
  - `Document > Appendix`
- Always include a **parent reference** so the structure can be reconstructed.
- Capture page numbers if confidently available; if not, set `page = -1` and add `quality.errors: ["PAGE_MISSING"]` (exceptional case).
- Documents will often Start with an Index / Table of Content. Ignore these for the Section extraction.
- Tables and Images might occur at any step within the hierarchy.

### Norms
Atomic, self-sufficient obligations that are applicable without extra context.
- **Must include**: `applies_if` (conditions for applicability) and `satisfied_if` (minimum compliance).
- **Atomicity**: Split norms when:
  1. Thresholds differ
  2. Applicability triggers differ
  3. Obligation types differ
- **Merge** norms when `satisfied_if` is identical **AND** location scope is the same.
- **Numbers/enums**: never fabricate; copy only explicit or strictly derivable facts. (E.g., don’t infer counts from plurals.)
- **Negative obligations** (e.g., “no se admite”): set `obligation_type = PROHIBITION` and encode `satisfied_if` to reflect the **required negative state** (e.g., `DOOR.OPENING.REQUIRES_KEY == FALSE`).
- **Exemptions**: if an explicit exemption exists, encode as `exempt_if` within the **same** norm (don’t create a second norm).
- **Location default**: if location info is absent, set `"COUNTRY": "ES"`.
- **Cross-references**: when a norm’s compliance depends on a section in the same doc, **inline** that section’s substantive conditions into `satisfied_if` rather than saying “complies with Section X”.
- **Parenting**: each Norm should have a parent section.

### Procedures
Operational “how-to” descriptions, including but not limited to:
1. How a calculation is performed
2. How specific works must be executed
3. How an application/administrative process is carried out

### Classifications
Taxonomic labels that **scope or modulate** norms (e.g., applicability by building type, usage, ownership).
Use them to **extend/restrict** where norms apply.

### Legal Documents
Direct references to legislation (acts, decrees, directives, standards).
Capture citation details as present (title, code, year, article, etc.).

---

## DSL REQUIREMENTS

**Paths**
- Format: `UPPERCASE.DOTCASE` (A–Z, 0–9, underscore allowed).
- Examples: `DOOR.TYPE`, `ROUTE.ACCESSIBLE`, `PROJECT.TYPE`, `CONSTRUCTION.ELECTRO.RADIOCOMMUNICATION`.

**Literals**
- Strings: `'VALUE'`
- Enums: `UPPERCASE.WORD(.WORD)*` (inside quotes as-is)
- Numbers: integers/decimals (dot decimal)
- Booleans: `TRUE` / `FALSE`

**Operators**
- Comparison: `== != < <= > >=`
- Logical: `AND OR NOT` (use parentheses to group)
- Membership: `VAR IN['VAL1','VAL2','VAL3']` (no space after `IN`).
  - For singletons you may use equality instead.
- Ranges: no shorthand; write both bounds (e.g., `X >= 0 AND X <= 20`)
- Existence: `HAS(DOOR.AUTOMATIC)` = tag/path recognized in ontology
- Geo scoping (use literally inside `applies_if`/`exempt_if`):
  - `WITHIN('ES.CT.BCN')`
  - `OVERLAPS('ZONE:R6.2')`
  - `ADJACENT_TO('ZONE:PEM2')`
  Example: `(LOCATION.WITHIN('ES.CT.BCN') AND ZONE.CODE IN['R6.2'])`

**Syntax discipline**
- No free prose outside DSL tokens in `applies_if/satisfied_if/exempt_if`.
- In `satisfied_if`, separate alternative compliance clauses with **exactly** `"; OR "`.
- When structural alternatives **and** numeric thresholds are present, order from simplest structure → more complex thresholds.

---

## ENUM BLOCKS
*(use exactly; no invention; you may omit unused enums in DSL, but keep tag paths where needed)*
ENUM.PROJECT.TYPE=[NEW,REFORM,AMPLIACION_ESTRUCTURA,LEGALISATION]
ENUM.OWNERSHIP=[PRIVATE,COMMERCIAL,EDUCATION,PUBLIC]
ENUM.USAGE=[PUBLIC.EDUCATION,PUBLIC.GOV,PUBLIC.PARK,PUBLIC.HOSPITAL,AGRICULTURE,GENERAL,RESIDENTIAL.HOUSING,ADMINISTRATIVE,PUBLIC.COMMERCIAL,PUBLIC.RESIDENTIAL,PUBLIC.ASSEMBLY,PARKING]
ENUM.WORK.TYPE=[NEW_BUILD,DEMOLITION.PARTIAL,DEMOLITION.TOTAL,USAGE.CHANGE.WHOLE,USAGE.CHANGE.PARTIAL,CONSTRUCTION.INSIDE,CONSTRUCTION.OUTSIDE,CONSTRUCTION.STRUCTURAL,CONSTRUCTION.FLOORS,CONSTRUCTION.DOORS,CONSTRUCTION.WINDOWS,CONSTRUCTION.STAIRS,CONSTRUCTION.EMERGENCYPATH,ELECTRO.ELEVATOR,ELECTRO.HEATING,ELECTRO.CLIMATE,ELECTRO.PHOTOVOLTAIC,ELECTRO.PHOTOVOLTAIC.INTERIOR,ELECTRO.PHOTOVOLTAIC.EXTERIOR,ELECTRO.PHOTOVOLTAIC.EXTERIOR.GARDEN,ELECTRO.RADIOCOMMUNICATION,ELECTRO.OTHER,GAS.HEATING,GAS.KITCHEN,GAS.OTHER]
ENUM.WORK.EFFECTS=[CLOSURE.STREET,CLOSURE.PARK,CLOSURE.AREA,CONSTRUCTION.FACILITIES]
ENUM.WORK.TYPE.AUXILARY=[CONSTRUCTION,SWIMMINGPOOL,ELECTRO.RADIOCOMMUNICATION]
ENUM.TOPICS=[SAFETY.STRUCTURAL,SAFETY.FIRE,SAFETY.USE,ACCESSIBILITY,SAFETY.ACCIDENTPREVENTION,HEALTH,SANITATION,PROTECTION.DAMP,PROTECTION.INDOOR.AIR,PROTECTION.ELECTRONICS,PROTECTION.SUPPLY.WATER,PROTECTION.NOISE,ENERGYSAVING,ENERGYSAVING.THERMAL,ENERGYSAVINGS.SOLAR,ENERGYSAVINGS.PV,ENERGYSAVINGS.HVAC.EFFICIENCY,ENERGYSAVINGS.LIGHTING.EFFICIENCY]
ENUM.MATERIALSANDEFFECTS=[LOADS,SNOW,WIND,EARTHQUAKES,RAIN,FOUNDATIONS,STEEL,MASONRY,TIMBER,ALUMINIUM]


---

## GUARDRAILS (strict)
1. **No hallucinations**: numbers, units, page numbers, codes, zone classes.
2. **Do not merge** semantically distinct obligations.
3. **No invented parent tags** unless the text implies a true semantic grouping.
4. **No free prose** outside specified fields.
5. If you need a function/operator outside the grammar, **omit it** and add `quality.warnings += ['UNSUPPORTED_OPERATOR:<token>']`.
6. **No duplicate tag objects with different definitions**; update instead.

---

## QUALITY & ERROR REPORTING
- Populate `quality.errors` and `quality.warnings` precisely (e.g., `PAGE_MISSING`, `UNSUPPORTED_OPERATOR:FOO`, `MISSING_LOCATION_DEFAULTED_TO_ES`, `AMBIGUOUS_THRESHOLD`, `MERGE_CANDIDATE`).
- Set `quality.confidence` ∈ [0,1]. Penalize confidence for ambiguous norms, missing pages, or uncertain thresholds.
- Prefer fewer, precise norms over broad, conflated ones; add warnings when you **split or merge**.

---

## EXTRACTION WORKFLOW
1. **Parse structure**: enumerate all Sections with hierarchy + parent refs (and pages if certain).
2. **Pass 1 (candidates)**: scan text for obligation sentences; draft candidate Norms (no merging yet).
3. **Normalize DSL**: fill `applies_if`, `satisfied_if`, `exempt_if`; enforce enums; add location default if needed.
4. **Atomicity check**: split where triggers/thresholds/obligation type differ.
5. **Merge pass**: merge only when `satisfied_if` **and** location scope are identical; log `MERGE_CANDIDATE` when in doubt.
6. **Classify**: attach Classifications that gate norms (usage, ownership, project/work type, topics, materials/effects, etc.).
7. **Procedures**: extract any methods, calculations, or process steps.
8. **Legal references**: collect explicit legislative citations.
9. **Validate syntax**: membership spacing (`IN[...]`), alt clauses `"; OR "`, explicit ranges, parentheses, booleans uppercase.
10. **Finalize**: ensure required top-level keys are present per your external schema; fill empties appropriately; set confidence.
