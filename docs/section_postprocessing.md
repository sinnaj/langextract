# Section Post-Processing

This document describes the post-processing mechanisms added to the section evaluation system for handling complex section hierarchies and duplicate section names.

## Overview

The post-processing system applies additional rules after the initial section evaluation to:

1. **Drop children of dropped sections** - Any section marked for dropping will also have all its descendant sections dropped
2. **Handle repeating section names** - Implements specific rules for sections with identical names based on their processing types

## Usage

### Command Line

```bash
# Without post-processing (backward compatible)
python chunk_evaluator.py document.md

# With post-processing (new functionality)
python chunk_evaluator.py document.md --postprocess
```

### Programmatic Usage

```python
from section_chunker import create_section_chunks
from chunk_evaluator import evaluate_and_postprocess_chunks

# Create chunks from markdown
chunks = create_section_chunks(markdown_text)

# Evaluate with post-processing
processed_evaluations = evaluate_and_postprocess_chunks(chunks)
```

## Post-Processing Rules

### Rule 1: Drop Children of Dropped Sections

When a section is marked for dropping (e.g., Table of Contents), all its child and descendant sections are automatically dropped as well.

**Example:**
```markdown
## Table of Contents
1. Chapter 1 ..................... 5
2. Chapter 2 ..................... 10

### Child of TOC
This section will be dropped

#### Grandchild of TOC  
This section will also be dropped
```

**Result:** All three sections are dropped.

### Rule 2: Handle Repeating Section Names

When multiple sections have the same name, the system applies different rules based on their processing types:

#### Rule 2.a: All Manual Processing Sections

If all sections with the same name are marked for manual processing, they are merged into one section:
- The highest level (lowest level number) section is kept
- All other sections are removed
- Children of removed sections are reassigned to the kept section

**Example:**
```markdown
## Manual Section     (level 2, kept)
### Subsection 1

## Manual Section     (level 2, removed)  
### Child Section     (reassigned to first Manual Section)
```

#### Rule 2.b: Mixed Manual and Extraction Sections

If some sections are marked for manual processing and others for extraction:
- All manual processing sections are dropped
- The highest level extraction section is kept
- Children of dropped manual sections are reassigned to the kept extraction section

**Example:**
```markdown
## Mixed Section      (extraction, kept)
Content for extraction.

## Mixed Section      (manual, dropped)
### Child Section     (reassigned to extraction section)
```

#### Rule 2.c: All Extraction Sections

If all sections with the same name are marked for extraction:
- Only the highest level (lowest level number) section is kept
- All other sections are dropped
- Children of dropped sections are reassigned to the kept section

**Example:**
```markdown
## Extract Section    (level 2, kept)
Content here.

## Extract Section    (level 2, dropped)
### Child Section     (reassigned to first section)
```

## Processing Type Determination

The system evaluates sections based on their content:

- **"extract"**: Sections with substantial content suitable for extraction
- **"manual"**: Sections with only headlines and minimal content  
- **"drop"**: Sections identified as Table of Contents or similar structural elements

## Output Format

When using `--postprocess`, the output includes additional information:

```json
{
  "postprocessing": {
    "enabled": true,
    "total_sections_before": 15,
    "total_sections_after": 10,
    "dropped_sections": ["section_006", "section_007"],
    "merged_sections": [["section_002", ["section_005"]]],
    "processing_log": [
      "Dropped section section_006 (Table of Contents) - marked for dropping",
      "Merged manual sections 'Manual Section': kept section_002, merged ['section_005']"
    ]
  }
}
```

## Implementation Details

The post-processing is implemented in `section_postprocessor.py` and integrated into `chunk_evaluator.py`. The main functions are:

- `post_process_section_evaluations()`: Main entry point for post-processing
- `drop_children_of_dropped_sections()`: Implements Rule 1  
- `handle_repeating_sections()`: Implements Rules 2.a, 2.b, and 2.c
- `identify_repeating_section_names()`: Helper to find duplicate section names

## Testing

Comprehensive tests are available in `test_section_postprocessor.py` covering all rules and edge cases.

```bash
python -m unittest test_section_postprocessor.py
```