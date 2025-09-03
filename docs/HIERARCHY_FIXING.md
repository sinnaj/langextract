# Hierarchy Fixing for LangExtract Output

This module provides postprocessing functionality to fix hierarchical document structure and merge duplicate sections in langextract output.

## Problem Addressed

LangExtract processes documents in chunks, which can lead to:
1. **Incomplete hierarchies**: Parent-child relationships between sections may be broken or missing
2. **Duplicate sections**: Sections may appear multiple times (e.g., first in table of contents, then as actual content)

## Solution

The `fix_hierarchy.py` module provides functions to:
- Detect and merge duplicate sections based on title and content similarity
- Fix orphaned sections by finding appropriate parent sections
- Validate the final hierarchical structure

## Usage

### Programmatic Usage

```python
from postprocessing.fix_hierarchy import fix_hierarchy_and_merge_duplicates

# Load your langextract output
data = {"extractions": [...]}

# Apply fixes
fix_hierarchy_and_merge_duplicates(data)

# The data is now modified with fixed hierarchy and merged duplicates
# Quality warnings are added to data["quality"]["warnings"]
```

### Command Line Usage

Use the standalone script to process JSON files:

```bash
# Process a file (creates input_file_fixed.json)
python fix_hierarchy_script.py path/to/output.json

# Specify output file
python fix_hierarchy_script.py input.json output_fixed.json

# Validate only (no changes)
python fix_hierarchy_script.py input.json --validate-only

# Verbose output
python fix_hierarchy_script.py input.json --verbose
```

### Example Output

```
2025-09-03 12:45:52 - INFO - === BEFORE Statistics ===
2025-09-03 12:45:52 - INFO - Total extractions: 420
2025-09-03 12:45:52 - INFO - Sections: 73
2025-09-03 12:45:52 - INFO - Applying hierarchy fixes...
2025-09-03 12:45:52 - INFO - Merged 1 duplicate sections
2025-09-03 12:45:52 - INFO - Fixed 6 orphaned sections
2025-09-03 12:45:52 - INFO - === AFTER Statistics ===
2025-09-03 12:45:52 - INFO - Sections: 72
2025-09-03 12:45:52 - INFO - Quality warnings: 2
2025-09-03 12:45:52 - INFO -   - DUPLICATE_SECTIONS_MERGED:1
2025-09-03 12:45:52 - INFO -   - ORPHANED_SECTIONS_FIXED:6
```

## Technical Details

### Duplicate Detection
- **Exact title matching**: Sections with identical `section_title` are considered duplicates
- **Content similarity**: Uses Jaccard similarity (70% threshold) on extraction text
- **Merge strategy**: Prefers sections that appear later in the document (higher `extraction_index`)

### Hierarchy Fixing
- **Orphan detection**: Finds sections with `parent_id` references that don't exist
- **Parent selection**: Uses section level hierarchy and title similarity to find appropriate parents
- **Fallback**: Links orphaned sections to document root if no suitable parent found

### Data Preservation
- **Non-destructive**: Original data structure is preserved
- **Metadata tracking**: Merge and fix operations are recorded in section attributes
- **Quality reporting**: All changes are logged in `quality.warnings`

## Quality Warnings

The following warnings may be added to indicate changes made:

- `DUPLICATE_SECTIONS_MERGED:N` - N duplicate sections were merged
- `ORPHANED_SECTIONS_FIXED:N` - N sections had their parent_id fixed

## Validation

The `validate_hierarchy()` function checks for:
- Circular parent-child references
- Invalid parent_id references
- Structural consistency

## Testing

Run the test suite:
```bash
python -m pytest arqio_tests/test_fix_hierarchy.py
```

The tests cover:
- Text similarity calculation
- Duplicate section detection and merging
- Orphaned section detection and fixing
- Integration scenarios
- Edge cases (empty inputs, invalid data)