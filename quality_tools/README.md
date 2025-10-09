# Quality Assessment Tools

Standalone Python scripts for analyzing extraction quality and generating comprehensive reports.

## Overview

These tools analyze `enhanced_extraction_results.json` files (from langextract extraction pipeline) and generate detailed quality reports. They are designed to be **standalone** and **isolated** from the main langextract project - they only require the JSON output files as input.

## Tools

### 1. Isolation Report Generator

**File**: `generate_isolation_report.py`

Identifies "isolated" norms that cannot be meaningfully clustered with other norms. Isolated norms require individual human review, which is costly at scale.

**Features**:
- Computes isolation scores based on feature sharing and tag coverage
- Diagnoses why norms are isolated (unique features, missing tags, etc.)
- Categorizes isolation reasons
- Provides recommendations for improvement

**Usage**:
```bash
# Basic usage
python generate_isolation_report.py \
    --input enhanced_extraction_results.json \
    --output isolation_report.txt

# Custom threshold (default 0.7)
python generate_isolation_report.py \
    --input data.json \
    --output report.txt \
    --threshold 0.6

# JSON output
python generate_isolation_report.py \
    --input data.json \
    --output report.json \
    --format json
```

**Example Output**:
```
======================================================================
ISOLATION ANALYSIS REPORT
======================================================================

SUMMARY STATISTICS
----------------------------------------------------------------------
Total Norms:           1,247
Isolated Norms:        87 (7.0%)
Average Isolation:     0.45
Threshold Used:        0.70

ISOLATION BREAKDOWN BY REASON
----------------------------------------------------------------------
   42 ( 48.3%) - Unique feature combinations
   23 ( 26.4%) - Poor tag coverage
   15 ( 17.2%) - Semantic outliers
    7 (  8.0%) - Section-specific

TOP 20 MOST ISOLATED NORMS
----------------------------------------------------------------------

1. [0.95] norm_helipad_001
   Statement: Buildings with helipads on roofs require lightning protection
   Reason: Unique features: BUILDING.HAS_HELIPAD
   Features: BUILDING.HAS_HELIPAD
   Tags: None

...
```

---

### 2. Quality Report Generator

**File**: `generate_quality_report.py`

Comprehensive quality assessment across five dimensions:
- **Completeness**: All required fields present
- **Consistency**: No contradictions, valid DSL syntax
- **Atomicity**: Single obligation per norm
- **Clustering Potential**: Feature and tag coverage
- **Traceability**: Source references present

**Features**:
- Assigns overall quality grade (A-F)
- Identifies specific issues per dimension
- Provides actionable recommendations
- Tracks feature/tag coverage

**Usage**:
```bash
# Basic usage
python generate_quality_report.py \
    --input enhanced_extraction_results.json \
    --output quality_report.txt

# JSON output
python generate_quality_report.py \
    --input data.json \
    --output quality_report.json \
    --format json
```

**Example Output**:
```
======================================================================
DATA QUALITY REPORT
======================================================================

OVERALL QUALITY SCORE: B (Good)
Score: 84.2%
----------------------------------------------------------------------

DIMENSION SCORES
----------------------------------------------------------------------
Completeness   :  95.3% ✓ Excellent
Consistency    :  88.1% ✓ Good
Atomicity      :  92.4% ✓ Excellent
Clustering     :  87.0% ✓ Good
Traceability   :  79.8% ○ Fair

DETAILED FINDINGS
----------------------------------------------------------------------

Completeness (95.3%):
  Top issues (showing 5):
    - norm_123: No relevant tags
    - norm_456: Unconditional norm (applies_if == TRUE)
    ...

...
```

---

## Installation

These scripts have minimal dependencies:

```bash
# No installation needed - just Python 3.7+
python3 --version

# The scripts only use standard library modules:
# - argparse
# - json
# - re
# - sys
# - pathlib
# - collections
# - typing
```

## Input Format

Both tools accept `enhanced_extraction_results.json` files with this structure:

```json
{
  "pipeline_info": {
    "version": "...",
    "total_extractions": 1247
  },
  "extractions": [
    {
      "extraction_class": "NORM",
      "extraction_text": "...",
      "attributes": {
        "id": "norm_001",
        "applies_if": "AREA.USAGE == 'PARKING' AND AREA.SIZE > 100",
        "satisfied_if": "HAS(FIRE.EXTINGUISHER)",
        "obligation_type": "MANDATORY",
        "relevant_tags": ["Fire Safety", "Parking"],
        "source": {
          "page": 15,
          "span_char_start": 1234,
          "span_char_end": 1456
        }
      }
    }
  ]
}
```

## Output Formats

Both tools support two output formats:

### Text Format (default)
Human-readable report with sections, statistics, and recommendations.

### JSON Format
Machine-readable structured data for further processing or integration.

```bash
# Text format
python generate_isolation_report.py --input data.json --output report.txt

# JSON format
python generate_isolation_report.py --input data.json --output report.json --format json
```

## Integration with Extraction Pipeline

These tools are designed to run **after** the extraction pipeline:

```bash
# 1. Run extraction
python enhanced_lx_runner.py --input document.pdf --output output_runs/run_001/

# 2. Generate quality reports
python quality_tools/generate_quality_report.py \
    --input output_runs/run_001/enhanced_output/enhanced_extraction_results.json \
    --output output_runs/run_001/quality_report.txt

python quality_tools/generate_isolation_report.py \
    --input output_runs/run_001/enhanced_output/enhanced_extraction_results.json \
    --output output_runs/run_001/isolation_report.txt
```

## Understanding the Metrics

### Isolation Score (0.0 - 1.0)

- **0.0**: Norm is well-connected to many other norms (shares features/tags)
- **0.5**: Moderately isolated
- **1.0**: Completely isolated (no shared features or tags)

**Threshold**: Default 0.7 means norms with scores ≥0.7 are flagged as isolated.

### Quality Dimensions

1. **Completeness (0-100%)**: Percentage of required fields present
2. **Consistency (0-100%)**: Absence of syntax errors and contradictions
3. **Atomicity (0-100%)**: Degree to which norms represent single obligations
4. **Clustering (0-100%)**: Feature and tag coverage for clustering potential
5. **Traceability (0-100%)**: Presence of source references (pages, spans)

### Quality Grades

- **A (90-100%)**: Excellent - Ready for production
- **B (80-89%)**: Good - Acceptable with minor issues
- **C (70-79%)**: Fair - Significant issues, needs review
- **D (60-69%)**: Poor - Major issues, requires rework
- **F (<60%)**: Failing - Not usable, re-extraction needed

## Troubleshooting

### "Input file not found"
Ensure the path to `enhanced_extraction_results.json` is correct and the file exists.

### "Invalid JSON"
Check that the input file is valid JSON. Use `python -m json.tool < file.json` to validate.

### No norms found
Ensure the JSON has an `extractions` array with items where `extraction_class == "NORM"`.

## Examples

### Batch Processing Multiple Files

```bash
#!/bin/bash
# Process all extraction results in output_runs

for dir in output_runs/*/enhanced_output; do
    if [ -f "$dir/enhanced_extraction_results.json" ]; then
        echo "Processing $dir..."
        
        python quality_tools/generate_quality_report.py \
            --input "$dir/enhanced_extraction_results.json" \
            --output "$dir/quality_report.txt"
        
        python quality_tools/generate_isolation_report.py \
            --input "$dir/enhanced_extraction_results.json" \
            --output "$dir/isolation_report.txt"
    fi
done
```

### Comparing Quality Across Runs

```bash
# Generate JSON reports for comparison
python quality_tools/generate_quality_report.py \
    --input output_runs/run_001/enhanced_output/enhanced_extraction_results.json \
    --output run_001_quality.json \
    --format json

python quality_tools/generate_quality_report.py \
    --input output_runs/run_002/enhanced_output/enhanced_extraction_results.json \
    --output run_002_quality.json \
    --format json

# Compare overall scores with jq
jq '.overall_score' run_001_quality.json run_002_quality.json
```

## Contributing

These tools are designed to be standalone and easy to extend. To add new quality checks:

1. Add your check function to the appropriate generator script
2. Integrate it into the `compute_*_metrics()` function
3. Update the report formatting function
4. Test with sample data

## License

Same as parent langextract project (Apache 2.0)

---

For questions or issues with these tools, please refer to the main langextract documentation or open an issue in the repository.
