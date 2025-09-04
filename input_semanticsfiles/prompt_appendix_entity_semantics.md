## 27. Entity Semantics: Tags, Questions, Consequences, Locations & Relationships

This section teaches the model how structural entities interrelate so output JSON expresses a coherent ontology and activation graph.

### 27.1 Tag Semantics
- A `Tag` defines a canonical ontology node. `tag_path` is UPPERCASE.DOTCASE hierarchical (e.g., `DOOR.OPENING.PUSH_FORCE_N`).
- Parent relationship: `parent` must be the immediate ancestor path (everything before the last dot) or omitted if root.
- Status values: `ACTIVE` (usable), `DEPRECATED` (do not newly attach, keep for legacy references), `MERGED` (points to replacement via `merge_target`).
- Tags SHOULD be unique by `tag_path`. If duplicates exist, only one stays ACTIVE; others become MERGED.
- Depth Guidance: prefer semantic NOT morphological splits. Avoid redundant tails like `DOOR.DOOR_WIDTH` (instead `DOOR.WIDTH`).

### 27.2 Question Semantics
- A `Question` exists to resolve uncertainty for one ontology path (`tag_path`) or set of paths listed in `outputs`.
- `tag_path` SHOULD either equal one of `outputs` or represent a parent grouping implying multiple outputs.
- `answer_type` governs the shape: ENUM -> `enum_values` required; NUMERIC -> optional `unit` & numeric range; BOOLEAN -> no enum; TEXT -> freeform.
- Each `Question` SHOULD contribute to at least one Norm (directly or via a Consequence activation graph). If a Norm references a field that is unresolved (unknown enumeration), a Question can be generated to capture it.
- If `enum_values` includes `OTRO`/`OTHER`, provide a separate follow-up free text question OR include guidance to record alternative value.

### 27.3 Consequence Semantics
- A `Consequence` encodes secondary procedural or documentary obligations triggered by Norm(s).
- `kind` examples: ANNEX, FINE, ACTION, NOTIFICATION, PROTOCOL.
- `reference_code` identifies external artifact (e.g., `Anexo III`).
- `source_norm_ids`: IDs of Norms whose satisfaction triggers or requires the consequence.
- `activates_norm_ids`: Norms that become applicable only after the consequence occurs (e.g., approval stage). Use sparingly.
- `activates_question_ids`: Questions that should be asked only upon consequence trigger (conditional data capture). Empty if unconditional.
- A Consequence with `kind == 'ANNEX'` SHOULD link to any Norm whose `satisfied_if` references `ANNEX.<ANNEX_CODE>.SUBMITTED == TRUE`.

### 27.4 Location Semantics
- A `Location` provides a geospatial or administrative scoping code (e.g., planning zone, province code, industrial zone).
- Norms often filter on location via DSL tokens: `ZONE.CODE == 'R6.2'`, `PROVINCE.CODE == 'BARCELONA'`.
- When a specific code literal appears in a Norm DSL expression matching a `Location.code`, the Norm's `location_scope` SHOULD include that code in the appropriate array (`ZONES`, `PROVINCES`, etc.).
- A `Location` may define hierarchical ancestry via `parent_codes`. Maintain ordering from largest (country) to smallest (local zone) where possible.

### 27.5 Relationship Inference Rules
1. TAG ↔ QUESTION: For each `Question.tag_path`, ensure a corresponding Tag exists or create a placeholder Tag (status `ACTIVE`, minimal definition). All `outputs` paths should exist as Tags.
2. NORM ↔ CONSEQUENCE: If a Consequence `reference_code` (ANNEX) appears in a Norm DSL (`ANNEX.<CODE>.SUBMITTED`), link both: add consequence ID to `norm.consequence_ids` and the norm ID to `consequence.source_norm_ids`.
3. LOCATION ↔ NORM: Inspect Norm DSL for single-quoted literals that match a `Location.code`. Populate `norm.location_scope` accordingly (zones, provinces, etc.).
4. PARAMETER ↔ QUESTION: A Question of type ENUM that defines enumerated states for an ontology node used in a Norm DSL condition establishes that Norm's satisfaction may depend on resolved value; no ID link required but coverage metric should consider it.
5. CONSISTENCY: Do not fabricate IDs; only attach existing IDs or create properly prefixed new Tag IDs following sequence if truly missing (rare, but allowed for placeholder Tag creation when Question introduces a new path).

### 27.6 Quality Metrics Extensions
Add (non-blocking) metrics:
- `question_tag_alignment_rate`: fraction of Questions whose `tag_path` exists as a Tag.
- `consequence_linkage_rate`: fraction of Consequences with at least one `source_norm_id` or `activates_norm_ids`.
- `location_scope_population_rate`: fraction of Norms where a location code literal in DSL was propagated into `location_scope`.

### 27.7 Guardrails
- Never guess geographical parents not provided; leave arrays empty instead of hallucinating.
- Do not duplicate Tag creation if already ACTIVE or MERGED.
- Avoid linking a Consequence multiple times to the same Norm.
- If ambiguous annex code mapping (multiple annexes share prefix), link only when exact match.

### 27.8 Output Enforcement Summary
The model should:
- Emit Tags for each unique path referenced in Questions or Parameters.
- Ensure Consequences referencing annexes link to triggering Norms.
- Populate Norm `location_scope` based on recognized location codes.
- Maintain stable ID references consistent with prefix conventions.

END_OF_ENTITY_SEMANTICS
