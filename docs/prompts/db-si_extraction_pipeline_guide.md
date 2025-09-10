# DB-SI Extraction Pipeline — Practical Guide & Review

Awesome project. Your plan is solid, and you already solved the hardest bit (getting a reliable, ToC-driven hierarchy). Below is a pragmatic critique with focused improvements to make the pipeline simpler, more reliable, and easier to maintain—plus a few must-adds to support PDF highlights and good downstream UX.

## TL;DR recommendations
- **Chunk by ToC intervals only** (no arbitrary fixed sizes) and attach a **stable path-based ID** to every Section and Norm.
- **Pre-filter for normative sentences** (Spanish “debe/deberá/queda prohibido/no se permite/como mínimo…”) to cut LLM cost and noise.
- Use a **two-stage extraction**: (1) cheap pattern/rule pass to flag likely Norms, (2) **lx** to structure them (Norm + Parameters + Conditions + Exceptions).
- Implement robust **text anchoring back to PDF** with a deterministic, page-scoped matcher: exact → normalized → fuzzy (with tight bounds), and emit **highlight quads** from Docling line prov.
- Keep a clean **data model** (Section, Norm, Parameter, Reference, Tag), with **deterministic IDs** and **confidence** for review.
- Add **consistency checks** across chunks (no cross-section parenting, no orphan Norms, page/char spans inside Section bounds).
- Provide **review surfaces** (low-confidence queue, extraction coverage metrics, unmatched Tables/References list).

---

## Pre-processing (keep it simple & robust)

### 1) ToC → Sections with intervals
- You already compute `[start_page, end_page]` per ToC node. Use that as the **sole source** for chunk boundaries.
- Assign each Section a **stable ID**:  
  `section_id = sha1(f"{toc_path}|{start_page}|{title_normalized}")`
- Persist the **path** (e.g., `["Sección SI 3", "4 Dimensionado", "4.1 Criterios"]`) for tagging and context.

### 2) Docling alignment sanity checks
- After headline fixes, verify:
  - Every `section_header` page ∈ its ToC interval.
  - No Section under “Índice”.
  - Keep **Anejo** and **Sección** families isolated (you already do this—good).

### 3) Chunking strategy
- **One chunk per ToC Section**. If a section is very large (token-heavy), split **by page windows** *inside the Section interval* with **5–10% sentence overlap** to avoid boundary cuts.
- Add a **context header** to each chunk (Section path + title + short blurb).

---

## Preparing text for lx (high signal, low cost)

### 4) Sentence segmentation tuned for Spanish & lists
- Split on “.”, “;”, and list bullets like “a) ”, “1) ”, “— ”, while **keeping the bullet marker** (it carries structure).
- Never drop footnote markers like “(1)”—treat them as part of the sentence text (matching should tolerate them, not strip them).

### 5) Pre-filter normative candidates (cheap rule pass)
- Keep the full chunk, but **flag** candidate sentences for lx using a small ruleset:
  - **Obligation/Prohibition**: `debe|deberá|deberán|deben|será obligatorio|se exigirá|queda prohibido|no se permite`
  - **Thresholds**: `al menos|como mínimo|no inferior a|≥|≤|mm|cm|m|min|minutos|m²|kW|°C`
  - **Scoping**: `cuando|si|en caso de|salvo|excepto|no aplicable|no será de aplicación`
- Send **all sentences** to lx **with a flag** for “likely_norm: true/false”. lx can skip/cheaply group the non-likely ones.

### 6) Prompt/schema for lx
Ask lx to emit a **structured schema** per sentence (or merged across adjacent sentences when they belong together):

```json
{
  "norms": [
    {
      "id": "<filled by post-process>",
      "text": "<verbatim sentence(s)>",
      "type": "obligation|prohibition|limit|exception|scope",
      "subject": "puerta|escalera|fachada|sector de incendio|... (noun phrase)",
      "action": "debe disponer|no se permite|debe resistir ...",
      "conditions": ["cuando altura de evacuación > 28 m", "..."],
      "parameters": [
        {"name":"resistencia al fuego", "value":90, "unit":"min"},
        {"name":"ancho libre","value":1.20,"unit":"m"}
      ],
      "references": ["Tabla C.2.3.1", "Sección SI 3 4.2"],
      "exceptions": ["excepto en ..."],
      "applicability": ["uso hospitalario", "aparcamientos"],
      "confidence": 0.0-1.0
    }
  ],
  "section_summary": "…",
  "application_statement": "…",
  "exemption_statement": "…",
  "tags": ["Evacuación", "Puertas", "SI3"]
}
```

- Keep **verbatim** text to improve anchoring.
- lx can also return **per-norm confidence** and any **spans** it sees; but don’t rely on spans from lx—do anchoring locally.

---

## Anchoring & highlights (critical for UX)

### 7) Deterministic anchoring back to PDF
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

### 8) Normalize parameters & units
- Keep both `original_value` and `normalized_value`.
- Standardize units to SI where possible (`min`, `m`, `mm`, `m²`, `°C`).
- Add a `unit_system: "original|SI"`, and conversions (e.g., `1.2 m`).

### 9) Deterministic IDs everywhere
- `norm_id = sha1(f"{section_id}|{normalize(norm.text)}")`
- `param_id = sha1(f"{norm_id}|{name}|{normalized_value}|{unit}")`
- This makes re-runs stable and simplifies diffing.

### 10) Attach metadata
- Norm: `parent_section_id`, `path`, `page_from/to`, `char_from/to` (from anchor best guess), `highlights` (quads), `confidence`, `source_pass` (“exact|normalized|fuzzy|section_fallback”).
- Section: `tags` (union: ToC path tags + lx tags), `application_statement`, `exemption_statement`, `summary`.

### 11) Merge adjacent sentence norms
- If lx emits multiple norms that obviously belong to one legal clause (same subject + shared parameters/conditions + contiguous sentences), merge and keep a `parts:[ids]` array and a `merged:true` flag.

---

## Global post-processing (across all chunks)

### 12) Build Node Tree
- Tree: Sections (ToC order) → child Sections → Norms (sorted by first highlight page & char).
- Never reparent across ToC boundaries. Validate each Norm’s page lies in the Section interval.

### 13) Quality gates
- Report:
  - % sentences flagged as normative
  - # norms extracted / section
  - anchoring success rates (exact/normalized/fuzzy/fallback)
  - parameter normalization coverage (% with parsed value+unit)
  - list of **ambiguous anchors** to review
  - list of **table-only references** (to plan future table extraction if needed)

### 14) Low-confidence queue
- Any norm with `confidence < 0.6` or `anchoring = fallback` goes to a **review bucket** with jump links to the page/section.

### 15) Caching & re-runs
- Cache per Section: normalized sentences, lx outputs, anchoring results keyed by `section_id` + document hash.
- On re-run after hierarchy fixes, only reprocess affected Sections.

---

## How to simplify (if you want a lean MVP)

- **Skip sentence merging** in v1. Keep one norm per triggering sentence.
- **Skip conversions**; store only original units in v1.
- **Skip table parsing**; just capture “see Tabla X” as a reference string.
- Use only **exact + normalized** anchoring (no fuzzy) and fall back to Section highlight for misses.
- Defer **exemption/application** extraction and accept a Section summary only.

This still delivers: stable tree, clickable highlights for most norms, and structured parameters for a good chunk of cases.

---

## What to add (high impact, low effort)

- **Tag enrichment from path**: auto-tag `["SI3", "Evacuación", "Puertas"]` from the ToC path; lx tags are additive.
- **Cross-reference resolver**: simple regex to detect “ver sección …/tabla …” and store as structured `references` with best-effort links (by matching the cited label to a Section/Table title).
- **Version stamp**: store `document_hash`, `toc_revision`, `script_version` in outputs for reproducibility.

---

## Tiny pseudocode snippets you’ll likely want

**Chunking by ToC intervals**
```python
def iter_section_chunks(docling, toc_intervals, max_tokens=6000):
    for sec in toc_intervals:
        lines = collect_lines(docling, sec.start_page, sec.end_page)
        # split by pages if too long (token estimate)
        for sub in split_by_token_budget(lines, max_tokens, overlap_sentences=2):
            yield {
                "section_id": sec.id,
                "path": sec.path,
                "title": sec.title,
                "text": sub.text,
                "pages": sub.pages,
            }
```

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
