## COMPACT SPEC — Norms Only (Minimal)
Purpose: emit a single JSON object of the shape {"extractions":[{...}]}. No markdown fences, no extra prose. Focus exclusively on extracting Norms. Keep all top-level arrays present but leave non-Norm arrays empty.

OUTPUT CONTRACT
- Root: {"extractions": [ { <one extraction object> } ]}
- The extraction object MUST include these keys (arrays exist even if empty):
  - norms: []  ← populate this
  - tags: []
  - quality: { errors:[], warnings:[], confidence_global, uncertainty_global }

NORMS — REQUIRED FIELDS (per item)
- id: "N::<stable_local_id>" (e.g., N::0001)
- statement_text: canonical sentence/span from source (Spanish/Catalan), normalized whitespace
- obligation_type: one of {MANDATORY, PROHIBITION, PERMISSION, CONDITIONAL, OPTIONAL, RECOMMENDATION}
- paragraph_number: int|null
- applies_if: DSL expression or TRUE
- satisfied_if: DSL expression (minimal compliance state)
- exempt_if: DSL|null
- priority: integer 1..5 (5 = critical)
- priority_factors: optional object
- relevant_tags: [] (keep empty in this minimal spec unless trivially available)
- relevant_roles: []
- project_dimensions: optional object
- lifecycle_phase: []
- topics: []
- location_scope: object (same shape as document_metadata.location_scope; can be broad, e.g., COUNTRY:"ES")
- source: { doc_id, article|null, page:int (or -1 if unknown), span_char_start:int, span_char_end:int, visual_refs:[] }
- extracted_parameters_ids: [] (keep empty)
- consequence_ids: [] (keep empty)
- confidence: float 0..1
- uncertainty: float 0..1
- notes: optional string

NORMS — RULES
1) Atomicity: one norm per distinct obligation/prohibition/threshold. Do not merge distinct bullets or paragraphs.
2) Unconditional → applies_if = TRUE.
3) Negative phrasing ("no se admite", "queda prohibido") → PROHIBITION and reflect negative state in satisfied_if.
4) Exemptions stay in exempt_if, not a new norm.
5) If page unknown: set page = -1 and append PAGE_MISSING in quality.errors.

DSL (MINIMAL)
- UPPERCASE.DOTCASE tokens only; operators: == != < <= > >= AND OR NOT IN[] HAS() WITHIN() OVERLAPS() ADJACENT_TO().
- Booleans TRUE/FALSE; strings in single quotes.
- Separate alternatives in satisfied_if exactly with "; OR ".
- No free prose inside DSL fields.

TRUNCATION & LIMITS
- Choose a reasonable window_config.max_norms_per_5k_tokens (e.g., 35).
- If not all norms fit, set has_more=true. If text was truncated internally, set truncated=true and add QUALITY_TRUNCATED to quality.errors.

SELF-CHECK BEFORE EMITTING
- JSON parses; root is exactly {"extractions":[...]}. 
- All required keys present; arrays exist (tags/locations/questions/consequences/parameters remain empty).
- Each norm has required fields; IDs are unique.
- DSL uses only allowed tokens/operators; alternatives formatted with "; OR ".

MINIMAL ILLUSTRATIVE EXAMPLE
{
  "extractions": [
    {
      "schema_version": "1.0.0",
      "ontology_version": "0.0.1",
      "dsl_version": "1",
      "run_info": {},
      "truncated": false,
      "has_more": false,
      "window_config": {"input_chars": 1200, "max_norms_per_5k_tokens": 35, "extracted_norm_count": 1},
      "global_disclaimer": "NO LEGAL ADVICE",
      "document_metadata": {
        "doc_id": "doc_xyz.pdf",
        "doc_title": "CTE SI 3 (extracto)",
        "source_language": "es",
        "received_chunk_span": {"char_start": 0, "char_end": 1200},
        "page_range": {"start": 1, "end": 2},
        "topics": ["SAFETY.FIRE"],
        "location_scope": {"COUNTRY": "ES", "STATES": [], "PROVINCES": [], "REGIONS": [], "COMMUNES": [], "ZONES": [], "GEO_CODES": [], "UNCERTAINTY": 0.05}
      },
      "norms": [
        {
          "id": "N::0001",
          "statement_text": "Las salidas para evacuación de más de 50 personas deberán ser abatibles...",
          "obligation_type": "MANDATORY",
          "paragraph_number": 1,
          "applies_if": "EVACUATION.PERSONS > 50",
          "satisfied_if": "DOOR.TYPE == 'SWING' AND DOOR.AXIS == 'VERTICAL'",
          "exempt_if": "DOOR.TYPE == 'AUTOMATIC'",
          "priority": 5,
          "priority_factors": {},
          "relevant_tags": [],
          "relevant_roles": [],
          "project_dimensions": {},
          "lifecycle_phase": [],
          "topics": ["SAFETY.FIRE"],
          "location_scope": {"COUNTRY": "ES", "STATES": [], "PROVINCES": [], "REGIONS": [], "COMMUNES": [], "ZONES": [], "GEO_CODES": [], "UNCERTAINTY": 0.05},
          "source": {"doc_id": "doc_xyz.pdf", "article": null, "page": -1, "span_char_start": 15, "span_char_end": 200, "visual_refs": []},
          "extracted_parameters_ids": [],
          "consequence_ids": [],
          "confidence": 0.9,
          "uncertainty": 0.1,
          "notes": ""
        }
      ],
      "tags": [],
      "locations": [],
      "questions": [],
      "consequences": [],
      "parameters": [],
      "quality": {"errors": [], "warnings": [], "confidence_global": 0.9, "uncertainty_global": 0.1}
    }
  ]
}

END OF SPEC.
