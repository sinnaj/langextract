# Docling Heading Hierarchy Post-processor

This document describes the Docling heading hierarchy post-processor module that infers true heading levels (H1/H2/H3/…) from DoclingDocument objects.

## Overview

The Docling heading hierarchy post-processor addresses a common issue where DoclingDocument objects mark many headers as `label="section_header"` with `level=1` only, regardless of their true hierarchical relationship in the document structure.

The post-processor uses a combination of heuristics to infer the proper heading levels:

1. **Anchor patterns**: Recognizes common document section markers (Spanish + generic)
2. **Numbering depth**: Uses numbering patterns like "1.2.3" to determine relative levels
3. **Typography/layout**: Falls back to font size and spacing when other methods don't apply
4. **Legal outline enforcement**: Ensures no level jumps greater than 1

## Installation

The post-processor is included in the langextract package:

```bash
pip install langextract
```

## Usage

### Python API

```python
from langextract.postprocess.headings import (
    infer_outline,
    infer_outline_from_json,
    to_markdown,
    OutlineHeading
)

# From DoclingDocument object
outline = infer_outline(docling_document)

# From JSON dictionary
outline = infer_outline_from_json(json_data)

# Convert to Markdown
markdown_text = to_markdown(outline)
```

### Command Line Interface

```bash
# Basic usage
python -m langextract.postprocess.headings input.json output.json

# With Markdown output
python -m langextract.postprocess.headings input.json output.json --md output.md

# With custom configuration
python -m langextract.postprocess.headings input.json output.json --config config.yaml
```

## Output Format

The `OutlineHeading` dataclass contains:

```python
@dataclass
class OutlineHeading:
    level: int                  # 1 = top level
    text: str                   # Heading text
    ref: str | None             # JSON pointer like "#/texts/236" 
    page_no: int | None         # Page number
    bbox: tuple[float,float,float,float] | None  # (l, t, r, b)
    signals: dict               # Debug information
```

### Signals Dictionary

The `signals` field contains debug information about how the level was determined:

- `anchor`: Boolean indicating if this matches an anchor pattern
- `num_level`: Integer level from numbering pattern (if applicable)
- `size_rank`: Rank based on font size (1 = largest)
- `gap_to_next`: Vertical spacing to next heading
- `word_count`: Number of words in heading text
- `proposed_level`: Initial level before legal outline enforcement
- `final_level`: Final level after enforcement
- `clamped`: Whether the level was reduced due to legal outline rules

## Heuristic Rules

### Anchor Patterns (Level 1)

These patterns are recognized as top-level sections:

- `Sección SI 2` (Spanish section with SI prefix)
- `Sección 3` (Spanish section)
- `Capítulo IV` or `Capítulo 1` (Spanish chapter)
- `Título A` or `Título 1` (Spanish title)
- `Anexo A` or `Anexo 1` (Spanish appendix)
- `Apéndice B` or `Apéndice 2` (Spanish appendix)

### Numbering Patterns

- `1.2.3` → Level 4 (count dots + 2)
- `1.2` → Level 3
- `1` → Level 2
- `A.` → Level 2
- `I.` → Level 2 (Roman numerals)

### Typography Fallbacks

When anchor and numbering patterns don't apply:

1. Headers are ranked by font size (bbox height)
2. Largest size → Level 2, second largest → Level 3, etc.
3. Short headings (≤10 words) get boosted to Level 3
4. Large vertical gaps (>18pt) boost to Level 3

### Legal Outline Enforcement

- No level can jump by more than +1 relative to the previous heading
- Example: If previous heading is Level 2, next can be at most Level 3

## Configuration

Create a YAML or JSON configuration file to customize patterns:

```yaml
# config.yaml
GAP_THRESHOLD: 25.0
ANCHOR_PATTERNS:
  - '^\s*Section\s+\d+\b'
  - '^\s*Chapter\s+([IVXLCDM]+|\d+)\b'
NUM_DEPTHS:
  - pattern: '^\s*(\d+(?:\.\d+)+)\b'
    level_func: 'count_dots_plus_2'
  - pattern: '^\s*(\d+)\b'
    level_func: 'level_2'
```

## Examples

### Basic Example

```python
import json
from langextract.postprocess.headings import infer_outline_from_json, to_markdown

# Sample DoclingDocument JSON
doc_json = {
    "body": {
        "children": [{"cref": "#/texts/0"}, {"cref": "#/texts/1"}]
    },
    "texts": [
        {
            "self_ref": "#/texts/0",
            "text": "Sección SI 2 Propagación exterior",
            "label": "section_header",
            "prov": [{"page_no": 1, "bbox": {"l": 10, "t": 100, "r": 200, "b": 75}}]
        },
        {
            "self_ref": "#/texts/1", 
            "text": "1 Medianerías y fachadas",
            "label": "section_header",
            "prov": [{"page_no": 1, "bbox": {"l": 10, "t": 150, "r": 200, "b": 135}}]
        }
    ]
}

# Infer outline
outline = infer_outline_from_json(doc_json)

# Results:
# outline[0].level == 1  (anchor pattern matched)
# outline[1].level == 2  (numbering pattern "1")

# Convert to Markdown
markdown = to_markdown(outline)
# Output:
# # Sección SI 2 Propagación exterior
# ## 1 Medianerías y fachadas
```

### Acceptance Criteria Validation

The implementation satisfies the specified acceptance criteria:

- ✅ "Sección SI 2 Propagación exterior" → Level 1 (anchor pattern)
- ✅ "1 Medianerías y fachadas" → Level 2 (numbering pattern)  
- ✅ Signals include `anchor=True` for first heading, `num_level=2` for second
- ✅ Legal outline enforcement prevents level jumps > 1
- ✅ CLI supports JSON input/output and optional Markdown

## Testing

Run the test suite:

```bash
python -m pytest tests/test_headings.py -v
```

The test suite includes:
- Anchor pattern matching tests
- Numbering level detection tests
- Bbox height calculation tests
- Vertical gap calculation tests
- End-to-end outline inference tests
- CLI functionality tests
- Configuration loading tests

## Performance Considerations

- The post-processor operates on section headers only (not full document text)
- Processing time scales linearly with number of headers
- Memory usage is minimal (stores only header metadata)
- No external dependencies beyond standard library

## Troubleshooting

### Common Issues

1. **No headers detected**: Ensure input document has items with `label="section_header"`
2. **Wrong levels assigned**: Check if text matches expected patterns or adjust configuration
3. **Missing bbox information**: Post-processor handles missing bbox gracefully
4. **Level jumps**: Legal outline enforcement may clamp levels - check `signals.clamped`

### Debug Information

Use the `signals` field in each `OutlineHeading` to understand how levels were determined:

```python
for heading in outline:
    print(f"'{heading.text}' -> Level {heading.level}")
    print(f"  Signals: {heading.signals}")
```

---

> **Note**: This post-processor is designed specifically for legal and regulatory documents with Spanish section markers, but can be easily configured for other document types and languages.