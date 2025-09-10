Review the current Pipeline ran via lxRunnerExtraction.py. Make Changes to it in accordance to the plan outlined in this Document.
Ask for Feedback if you are unsure about something or have alternative Solutions in mind.

## Short Summary
- **Chunk by ToC intervals only** (no arbitrary fixed sizes) and attach a **stable path-based ID** to every Section and Norm.
- **Use LX to extract Norms**
- Implement robust **text anchoring back to PDF** with a deterministic, page-scoped matcher: exact → normalized → fuzzy (with tight bounds), and emit **highlight quads** from Docling line prov.
- Keep a clean **data model** (Section, Norm, Parameter, Reference, Tag), with **deterministic IDs** and **confidence** for review.
- Add **consistency checks** across chunks (no cross-section parenting, no orphan Norms, page/char spans inside Section bounds).
- Provide **review surfaces** (low-confidence queue, extraction coverage metrics, unmatched Tables/References list).

---

## Pre-processing (keep it simple & robust)

### 1) Pre-processing Pipeline
- Generate Docling Document via scripts\pdf_to_markdown.py
- Extract ToC from PDF via scripts\pdf_toc_extractor.py
- Perform Headline fixes via scripts\pdf_toc_extractor.py
- Chunk the fixed Docling Document by Sections, create a json containing the Output Chunks for Testing/Quality Assurance.
- Prune the Chunks down to their content to create the Chunks that can be passed to lxRunnerExtraction.py

### 2) ToC → Sections with intervals
- You already compute `[start_page, end_page]` per ToC node. Use that as the **sole source** for chunk boundaries.
- Assign each Section a **stable ID**:  
  `section_id = sha1(f"{toc_path}|{start_page}|{title_normalized}")`
- Persist the **path** (e.g., `["Sección SI 3", "4 Dimensionado", "4.1 Criterios"]`) for tagging and context.

### 3) Docling alignment sanity checks
- After headline fixes, verify:
  - Every `section_header` page ∈ its ToC interval.
  - Ignore Sections under “Índice”.
  - Ignore Sections under "Document Info"
  - Keep **Anejo** and **Sección** families isolated

### 4) Chunking strategy
- Extract Sections for processin from the fixed Docling Document
- **One chunk per ToC Section**. If a section is very large (token-heavy), split **by page windows** *inside the Section interval* with **5–10% sentence overlap** to avoid boundary cuts.
- Add a **context header** to each chunk (Section path + title + short blurb).
- Keep **verbatim** text to improve anchoring.


---

## Anchoring & highlights (critical for UX)

### 1) Deterministic anchoring back to PDF
Given each Norm’s `text` and its parent **Section interval**, do:

- **Scope**: restrict search to pages `[section.start_page, section.end_page]`.
- Build per page a **search corpus** from Docling **line texts** with their `charspan` + `bbox`.
- **3-stage match per page** (stop on first unambiguous hit):
  1) **Exact** substring match (identity, case sensitive); if multiple exact hits, prefer the one whose surrounding 20–40 chars best match the norm’s context (left/right neighbors).
  2) **Normalized** match: case-fold, collapse whitespace, canonicalize punctuation, but **keep parentheses and numbers** (so “(1)” still matches).
  3) **Fuzzy** match (e.g., token-set ratio ≥ 90 within the page text). Guardrails:
     - Only accept if the matched window length is **≥ 80%** of the norm text length.
     - If >1 candidate within 2% score, **mark as ambiguous** and fall back to Section-level highlight.

- **Span → quads**:
  - Map matched character range to affected Docling lines (using their `charspan` windows if you preserve an accumulating “page_text” → line index map).
  - For each line slice, compute sub-bbox (approximate horizontally by proportion of characters).
  - Emit `[{page, quads:[{x1,y1,x2,y2,x3,y3,x4,y4}], source:"exact|normalized|fuzzy", confidence}]`.

- If **no anchor**: attach `locator = {page_range, reason:"not_found|ambiguous"}` so you can still jump to section.

---

## Post-processing per chunk (clean and merge)

### 1) Normalize parameters & units
- Keep both `original_value` and `normalized_value`.
- Standardize units to SI where possible (`min`, `m`, `mm`, `m²`, `°C`).
- Add a `unit_system: "original|SI"`, and conversions (e.g., `1.2 m`).

### 2) Deterministic IDs everywhere
- `norm_id = sha1(f"{section_id}|{normalize(norm.text)}")`
- `param_id = sha1(f"{norm_id}|{name}|{normalized_value}|{unit}")`
- This makes re-runs stable and simplifies diffing.

### 3) Attach metadata
- Norm: `parent_section_id`, `path`, `page_from/to`, `char_from/to` (from anchor best guess), `highlights` (quads), `confidence`, `source_pass` (“exact|normalized|fuzzy|section_fallback”).
- Section: `tags` (union: ToC path tags + lx tags), `application_statement`, `exemption_statement`, `summary`.

### 4) Merge adjacent sentence norms
- If lx emits multiple norms that obviously belong to one legal clause (same subject + shared parameters/conditions + contiguous sentences), merge and keep a `parts:[ids]` array and a `merged:true` flag.

---

## Global post-processing (across all chunks)

### 1) Build Node Tree
- Tree: Sections (ToC order) → child Sections → Norms (sorted by first highlight page & char).
- Never reparent across ToC boundaries. Validate each Norm’s page lies in the Section interval.

### 2) Quality gates
- Report:
  - # norms extracted / section
  - anchoring success rates (exact/normalized/fuzzy/fallback)
  - parameter normalization coverage (% with parsed value+unit)
  - list of **ambiguous anchors** to review
  - list of **table-only references** (to plan future table extraction if needed)

### 3) Low-confidence queue
- Any norm with `confidence < 0.6` or `anchoring = fallback` goes to a **review bucket** with jump links to the page/section.

### 4) Caching & re-runs
- Cache per Section: normalized sentences, lx outputs, anchoring results keyed by `section_id` + document hash.
- On re-run after hierarchy fixes, only reprocess affected Sections.

---

## What to add (high impact, low effort)

- **Tag enrichment from path**: auto-tag `["SI3", "Evacuación", "Puertas"]` from the ToC path; lx tags are additive.
- **Cross-reference resolver**: simple regex to detect “ver sección …/tabla …” and store as structured `references` with best-effort links (by matching the cited label to a Section/Table title).
- **Version stamp**: store `document_hash`, `toc_revision`, `script_version` in outputs for reproducibility.

---

## Tiny pseudocode snippets you can use

**Anchoring (page-scoped)**
```python
def anchor_norm_to_pdf(norm_text, section_pages, page_corpus):
    for page in section_pages:
        exact = find_exact(page_corpus[page], norm_text)
        if exact: return build_quads(exact, page)
        normed = find_normalized(page_corpus[page], norm_text)
        if normed: return build_quads(normed, page)
        fuzzy = find_fuzzy_confident(page_corpus[page], norm_text, min_score=0.90)
        if fuzzy: return build_quads(fuzzy, page, source="fuzzy")
    return {"locator": {"pages": section_pages, "reason":"fallback"}}
```

**Deterministic IDs**
```python
def make_id(*parts):
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
```
