# Postprocessing Scripts

This directory contains postprocessing scripts for LangExtract extraction results.

## Available Scripts

### add_section_application_metadata.py

Propagates `meta_applies_if` and `meta_exempt_if` attributes from CHUNK_METADATA extractions to their parent sections.

**Usage:**
```bash
# Basic usage - overwrites the input file
python postprocessing/add_section_application_metadata.py <input_file.json>

# Save to a different output file
python postprocessing/add_section_application_metadata.py <input_file.json> <output_file.json>
```

**Example:**
```bash
python postprocessing/add_section_application_metadata.py \
  output_runs/1757864159/enhanced_output/enhanced_extraction_results.json
```

**What it does:**
1. Reads enhanced_extraction_results.json
2. Finds all CHUNK_METADATA extractions
3. Extracts meta_applies_if and meta_exempt_if from CHUNK_METADATA attributes
4. Adds these fields to the parent section (identified by parent_section_id)
5. Saves the enriched JSON with processing statistics

### extract_params.py

Extracts parameter objects from norm extractions.

### extract_tags.py

Extracts tag objects from norm extractions.

### enrich_outputdata.py

General enrichment utilities for output data including parameter derivation and tag merging.

### relationship_inference.py

Infers relationships between extracted entities.

### output_schema_validation.py

Validates output data against expected schemas.

## Running Tests

Tests are located in the `/tests` directory:

```bash
# Run specific test
python tests/test_add_section_application_metadata.py

# Run all tests with pytest
pytest tests/
```
