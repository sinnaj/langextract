# Retroactive Section Processing

This document describes the `retroactive_section_processor.py` script, which applies section processing logic to already processed output files that lacked post-processing steps prior to extraction.

## Overview

The retroactive section processor allows you to apply the same section post-processing logic (dropping and merging sections) that is normally performed during the evaluation phase by `chunk_evaluator.py` and `section_postprocessor.py` to already processed `combined_extractions.json` files.

This is useful when you have existing extraction results that were processed without the post-processing features enabled, and you want to apply these optimizations retroactively.

## Usage

### Command Line

```bash
# Basic usage - creates a new file with _processed suffix
python retroactive_section_processor.py path/to/combined_extractions.json

# Specify output file
python retroactive_section_processor.py input.json output.json

# Example with the provided test file
python retroactive_section_processor.py "output_runs/1757020697/lx output/combined_extractions.json"
```

### What the Script Does

1. **Loads the existing JSON file**: Parses the `combined_extractions.json` file and extracts section information
2. **Converts to internal format**: Transforms section data into the format used by the post-processing functions
3. **Applies post-processing rules**: Executes the same logic from `section_postprocessor.py`:
   - Drops children of dropped sections
   - Handles repeating section names according to the established rules
4. **Updates the data**: Modifies section relationships, counts, and statistics
5. **Saves the result**: Writes an updated JSON file with post-processing information

## Post-Processing Rules Applied

The script applies the same rules as the standard post-processing pipeline:

### Rule 1: Drop Children of Dropped Sections
Any section marked for dropping will also have all its descendant sections dropped.

### Rule 2: Handle Repeating Section Names
When multiple sections have the same name:

- **2.a All Manual Sections**: Merge into one section (highest level kept)
- **2.b Mixed Manual/Extraction**: Drop manual sections, keep extraction sections
- **2.c All Extraction Sections**: Keep only the highest level section

## Output Changes

The processed file will have:

### Updated Section Count
- Fewer total sections due to merging/dropping
- Updated subsection references
- Corrected parent-child relationships

### Added Post-Processing Information
```json
{
  "postprocessing": {
    "enabled": true,
    "total_sections_before": 228,
    "total_sections_after": 187,
    "dropped_sections": [],
    "merged_sections": [["section_009", ["section_039", "section_041"]]],
    "processing_log": [
      "Merged manual sections 'Example': kept section_009, merged ['section_039']"
    ]
  }
}
```

### Updated Statistics
```json
{
  "evaluation_statistics": {
    "total_chunks": 187,
    "extract_count": 146,
    "manual_count": 41,
    "drop_count": 0,
    "extract_percentage": 78.1,
    "manual_percentage": 21.9,
    "drop_percentage": 0.0
  }
}
```

## Example Results

Using the provided test file `output_runs/1757020697/lx output/combined_extractions.json`:

```
Processing 228 sections...
Processed file saved to: output_runs/1757020697/lx output/combined_extractions_processed.json
Sections before processing: 228
Sections after processing: 187
Dropped sections: 0
Merged sections: 2
```

The processing reduced 228 sections to 187 sections by merging duplicate manual sections and handling mixed section types according to the established rules.

## Limitations

- **No Original Text**: Since the script works with already processed data, it doesn't have access to the original markdown text, so some evaluation metadata may be limited
- **Preserves Existing Evaluations**: The script doesn't re-evaluate sections; it only applies post-processing rules to existing evaluations
- **JSON Format Dependency**: The script expects the specific JSON format used by the LangExtract pipeline

## Error Handling

The script includes robust error handling:
- Validates input file existence
- Handles missing or empty sections gracefully
- Provides meaningful error messages
- Maintains data integrity during processing

## Testing

Run the test suite to verify functionality:

```bash
python -m unittest test_retroactive_processor.py -v
```

The tests cover:
- Basic processing functionality
- Empty sections handling
- Missing sections key handling
- Data integrity verification