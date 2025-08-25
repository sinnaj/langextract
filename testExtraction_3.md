# testExtraction_3 Semantic Teaching Guide

This document explains the semantic training / conditioning approach used by `testExtraction_3.py` to elicit the full rich schema defined in `prompts/extraction_prompt.md` from a single model pass, focusing on entities, relationships, and normalization — not merely code mechanics.

> Goal: Maximize correct emergence of `norms`, `tags`, `locations`, `questions`, `consequences`, and `parameters` with robust cross-link integrity and ontology restructuring behavior.

---
## 1. Core Schema Surfaces

| Array | Purpose | Key Relationship Axes |
|-------|---------|-----------------------|
| norms | Atomic regulatory obligations/prohibitions/permissions | references `parameters`, `consequences`, plus ontology tags & location scope |
| tags | Dynamic hierarchical ontology nodes | parent/child edges; MERGED / REPLACED lineage; referenced by norms, questions, consequences |
| locations | Jurisdiction + planning zones | geographic containment (parent_codes) and zone associations |
| questions | Decision branching over ambiguous, high-level or high-frequency tag paths | triggers norms; activated by consequences |
| consequences | Annexes, declarations, inspections, triggers | can activate questions, tags, or downstream norms |
| parameters | Normalized threshold constraints (value, operator, unit) | referenced by multiple norms; unify duplicates |

---
## 2. Semantic Extraction Principles

1. **Atomicity**: One norm per distinct applicability + obligation + threshold composition. Splitting early reduces downstream ambiguity in parameter and question linkage.
2. **Ontology Stability**: Prefer reuse of existing tag paths; create new mid-chain nodes only when text explicitly distinguishes a meaningful subclass. Immediately update earlier definitions if semantics shift (MERGED pattern).
3. **Bidirectional Traceability**: Every cross-reference (norm → parameter, consequence → norm, question → norm) must point to an existing ID. Missing reference is always an error, not a warning.
4. **Numeric Normalization**: Extract once, reuse everywhere. Distinguish semantic reuse (same threshold) from representational variety (e.g., “≤ 25 N” vs “no excederá 25 N”).
5. **Branch Modeling**: Questions arise where tag state or enumeration influences applicability/threshold logic across multiple norms (frequency ≥ 3, or root with ≥ 2 specialized children, or threshold branching by discrete variants).
6. **Confidence Discipline**: High confidence implies low uncertainty; never set both extremes. Missing structural data (page, article) must inflate uncertainty and produce error codes.
7. **Priority Calibration**: Safety / evacuation / fire => 5; accessibility structural performance => 4; standard technical norms => 3; niche zoning or edge-case conditional norms => 2; clarifying minor notes => 1.

---
## 3. Ontology Restructuring Workflow

1. Detect emergent subclass: new textual evidence differentiates DOOR.AUTOMATIC into pedestrian vs industrial.
2. Introduce `DOOR.AUTOMATIC.PEDESTRIAN` & `DOOR.AUTOMATIC.INDUSTRIAL` tags with parent = `DOOR.AUTOMATIC`.
3. If previous leaf semantics of `DOOR.AUTOMATIC` were over-specific, mark original as `{status: "MERGED", merge_target: "DOOR.AUTOMATIC"}` *and* re-output updated children + updated parent definition.
4. Update all affected norms’ `relevant_tags` to the most granular applicable paths; avoid leaving obsolete parent-only references if more precise child evident.

---
## 4. Parameter Unification Algorithm (Deterministic)

```text
For each numeric candidate:
  - Capture surface form (original_text), value (float/int), unit (if any), operator context (<=, >=, ==, etc.).
  - Infer field_path lexically (e.g. "fuerza" → DOOR.OPENING.PUSH_FORCE_N) using glossary / prior DSL tokens.
  - Canonical key = (field_path, operator, value, unit).
  - If key seen: append norm_id to existing parameter.norm_ids.
  - Else: create new parameter with sequential ID.
  - Inject parameter ID into each referencing norm.extracted_parameters_ids.
```

Heuristics: multi-token unit patterns ("kg/m2") treat entire token as `unit`; absence of explicit unit => `unit: null` (never infer).

---
## 5. Question Generation Criteria

Trigger a question if ANY:
* Tag path appears in ≥ 3 norms’ DSL expressions.
* Tag path depth=1 (root category) with ≥ 2 active child tags in output.
* Parameter threshold differs by enumerated values of the tag path.

Enumeration assembly: gather unique literals or leaf tag suffixes associated with conditional branching; discard obviously spurious values (non-uppercase / out-of-grammar tokens). Output stable ordered list (original discovery order or sorted alphabetically if ambiguous).

---
## 6. Consequence Activation Pattern

1. Detect lexical markers: *Anexo*, *Declaración*, *Certificación*, *Inspección*, *Formulario*.
2. Create consequence with `kind` mapped to marker.
3. Link to source norm (`source_norm_ids`).
4. If consequence logically triggers further evaluation (e.g., completion of Annex triggers a follow-up question), populate `activates_question_ids` or `activates_norm_ids`.
5. If presence of the consequence is itself conditional, represent that conditionality inside the relevant norm’s DSL (not in the consequence object).

---
## 7. DSL Expression Integrity

Requirements:
* Uppercase path tokens separated by dots; no stray lowercase tokens.
* Alternatives separated by EXACT `; OR ` sequences (semicolon + space + OR + space).
* Membership lists: `FIELD IN['A','B','C']` (no internal spaces after `IN`).
* Functions (HAS, WITHIN, OVERLAPS, ADJACENT_TO) used verbatim; do not paraphrase.
* No invented operators; record as error `UNSUPPORTED_OPERATOR:<token>` if encountered.

Common Anti-Patterns (reject):
* Mixing prose: "La puerta ( DOOR.TYPE == 'SWING' )".
* Lowercase variable segments: `door.type`.
* JSON-like equality: `FIELD === 'X'`.

---
## 8. Self-Repair Loop (Pre-Emission Audit)

Before final JSON emission the model (or downstream validator) MUST re-check:

| Condition | Repair Action |
|-----------|---------------|
| Numeric pattern present & parameters empty | Re-scan thresholds, rebuild `parameters` & link IDs |
| Annex/Declaration token present & consequences empty | Extract minimal consequence object(s) |
| Zone code pattern (e.g. R6.2) present & locations empty | Create PLANNING_ZONE location entity |
| Tag frequency rule violated (≥3) & missing question | Generate question for tag path |
| Parameter referenced in DSL but missing object | Add parameter object or drop DSL reference (prefer add) |

If any repair performed → recompute cross-references & re-validate.

---
## 9. Priority Determination Table

| Keyword Regex | Base Priority | Notes |
|---------------|--------------|-------|
| (evacuación|incendio|emergencia|fuego) | 5 | Safety-critical |
| accesibil | 4 | Accessibility / usability |
| anexo|documentación requerida | +1 (cap 5) | Elevate norm enforcing procedural gate |
| reforma estructural | 4 | Structural design impact |
| mantenimiento menor | 2 | Typically low impact |

Final priority = clamp( base + adjustments ).

---
## 10. Confidence & Uncertainty Calibration

| Situation | confidence | uncertainty |
|-----------|-----------|-------------|
| Explicit numeric threshold & unambiguous subject | ≥0.85 | ≤0.10 |
| Implicit subject or pronoun resolution required | 0.6–0.75 | 0.25–0.4 |
| Missing page/article metadata | ≤0.55 | ≥0.45 + add `PAGE_MISSING` |
| Aggregated normative paraphrase risk | ≤0.50 | ≥0.50 |

Never set `confidence=1.0` unless trivial deterministic enumeration (rare) and `uncertainty` must then be very low (<0.02).

---
## 11. ID Sequencing & Collision Avoidance

All IDs are sequential within *output scope* per entity type. When deriving from teaching micro-demos:
* Discard demo placeholder IDs (e.g. `N::DEMO1`).
* Re-index starting at `0001` per type.
* Ensure deterministic formatting: zero-padded 4 digits recommended (`N::0001`).

Cross-reference resolution occurs only after final reindexing; intermediate indexes MUST NOT leak into final JSON.

---
## 12. Glossary Feedback Loop

1. After each run, extracted DSL field paths appended to `dsl_glossary.json` (value placeholders remain empty until curated).
2. Next run (optional) injects known field paths section to bias reuse.
3. Manual curation (definitions, alias mapping) can prune redundant or noisy paths; keep this glossary source of truth for semantic normalization.

---
## 13. Extension Roadmap (Future Enhancements)

| Area | Planned Improvement |
|------|---------------------|
| DSL Parsing | Implement a formal tokenizer + grammar (Lark / bespoke) for deterministic validation & auto-repair. |
| Parameter Linking | Fuzzy lexical alignment to retro-link missed thresholds post-run. |
| Ontology Evolution | Maintain persistent store of tag lineage & merge events across documents (graph). |
| Multi-Chunk Aggregation | Merge partial outputs with ontology refactoring passes and global ID allocator. |
| Visual Evidence | Align `visual_refs` with extracted bounding boxes / figure captions from PDF parse layer. |
| Evaluation Metrics | Coverage ratio, parameter reuse ratio, branching efficiency, false positive rate in tag creation. |

---
## 14. Usage Flow Summary

1. Run `testExtraction_3.py` with base prompt for initial pass.
2. Review output JSON + glossary for missing semantic structures.
3. (Optional) Add curated definitions / prune erroneous field paths in glossary.
4. Enable teaching appendix injection (planned env var `LX_TEACH_MODE=1`) to intensify multi-entity emergence in subsequent iterations.
5. Compare metrics across runs to assess semantic recall improvements.

---
## 15. Quick Quality Checklist

| Check | Pass Criteria |
|-------|---------------|
| Arrays present | All required top-level arrays exist (may be empty) |
| ID integrity | Every referenced ID resolves │
| Ontology merges | No conflicting ACTIVE duplicates │
| DSL syntax | All expressions pass grammar heuristics │
| Parameter reuse | No duplicate objects with identical (field_path, operator, value, unit) │
| Consequence link | Every consequence has ≥1 source_norm_id │
| Question necessity | Every high-frequency root tag has question │
| Confidence logic | confidence + uncertainty consistent with heuristics │

---
## 16. Minimal Developer Hooks

Potential lightweight hooks to integrate next:
* `enrich_parameters(parsed_json)` – derive missing parameters from raw text spans.
* `repair_cross_refs(parsed_json)` – ensure dangling references removed or objects synthesized.
* `compute_metrics(parsed_json)` – produce coverage & normalization KPIs for evaluation.

---
## 17. FAQ

**Q:** Why not produce multi-class examples directly?  
**A:** Current example interface centers around per-extraction-class objects; richer emergence is steered via prompt appendix + embedded micro-demos instead.

**Q:** How to avoid over-fragmented tags?  
**A:** Require explicit textual differentiation; avoid single-use leaf expansion unless it affects branching logic (question or threshold divergence).

**Q:** When to create a question vs keep a tag only?  
**A:** If downstream norms vary by enumerated values or the tag resolves multi-norm applicability uncertainty.

**Q:** Should parameters reference consequences?  
**A:** No; link parameters only to norms. Consequences are triggered artifacts / activation nodes.

---
## 18. License & Attribution

This guide accompanies internal extraction logic; reuse subject to repository license terms.

---
**End of Guide**
