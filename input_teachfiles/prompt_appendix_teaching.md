--------------------------------------------------------------------------------
## 19. MULTI-ENTITY MICRO DEMO (INFORMATIVE ONLY – DO NOT COPY IDS)
Refer to internal guide: demonstrates cross-array linking. Model MUST regenerate fresh sequential IDs.
--------------------------------------------------------------------------------
## 20. ONTOLOGY RESTRUCTURING & MERGE EXAMPLE
When a prior leaf tag splits into children:
1. Create children with parent reference.
2. Update parent definition.
3. Mark obsolete duplicates as {"status":"MERGED","merge_target":"<canonical>"}.
4. Re-output all impacted tag objects in updated canonical form.
--------------------------------------------------------------------------------
## 21. PARAMETER UNIFICATION ALGORITHM
Canonical key = (field_path, operator, value, unit). If key already exists append norm_id; else create new parameter. Never duplicate identical threshold objects.
--------------------------------------------------------------------------------
## 22. QUESTION GENERATION CRITERIA
Generate if tag_path frequency ≥3, or root with ≥2 children, or thresholds branch by enumeration.
--------------------------------------------------------------------------------
## 23. CONSEQUENCE ACTIVATION PATTERN
Annex / Declaración / Certificación / Inspección => consequence.kind. Link via source_norm_ids; populate activations if they trigger further decision points.
--------------------------------------------------------------------------------
## 24. SELF-REPAIR LOOP
If evidence of numbers/annex/zones/questions missing corresponding arrays → rebuild internally then emit only final valid JSON.
--------------------------------------------------------------------------------
## 25. PRIORITY & CONFIDENCE QUICK TABLE
evacuación|incendio|emergencia|fuego => priority 5 ; accesibil* => 4 ; anexo|documentación requerida => +1 (cap 5).
Confidence couples inversely with uncertainty.
--------------------------------------------------------------------------------
## 26. KNOWN FIELD PATHS (Will be appended dynamically when available)
--------------------------------------------------------------------------------
