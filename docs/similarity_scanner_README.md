# Similarity Scanner Documentation

## Overview

The `similarity_scanner.py` script analyzes `enhanced_extraction_results.json` files from LangExtract to identify similarly named tags and parameters that might indicate inconsistent naming conventions.

## Problem Statement

In large extraction datasets, similar concepts may be tagged with slightly different naming conventions:
- `FIRE.EXIT` vs `FIRE_EXIT`
- `DOOR.WIDTH` vs `DOOR_WIDTH` 
- `BUILDING.HEIGHT` vs `BUILDING.EVACUATION.HEIGHT`

This inconsistency can lead to:
- Reduced data quality
- Difficult analysis and aggregation
- Missed relationships between similar concepts

## Features

### Similarity Detection
- **Normalization**: Converts different separator styles (`.`, `_`, `-`, spaces) to a common format
- **Fuzzy Matching**: Uses sequence similarity and substring matching to identify related names
- **Configurable Threshold**: Adjustable similarity threshold (0.0-1.0) to control detection sensitivity

### Analysis Coverage
- **Tags**: Analyzes the `tag` field from tag objects in the JSON
- **Parameters**: Analyzes the `applies_for_tag` field from parameter objects in the JSON
- **Comprehensive Output**: Shows both original and normalized names for clarity

## Usage

### Basic Usage
```bash
python similarity_scanner.py path/to/enhanced_extraction_results.json
```

### With Custom Threshold
```bash
python similarity_scanner.py path/to/enhanced_extraction_results.json --threshold 0.9
```

### Example with Real Data
```bash
python similarity_scanner.py output_runs/1757868964/enhanced_output/enhanced_extraction_results.json
```

## Command Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `file_path` | Required | - | Path to the enhanced_extraction_results.json file |
| `--threshold` | Float | 0.8 | Similarity threshold (0.0-1.0) |
| `--help` | Flag | - | Show help message and usage examples |

## Output Format

### Sample Output
```
🔍 Similarity Analysis for: output_runs/1757868964/enhanced_output/enhanced_extraction_results.json
📊 Total Tags: 1357, Total Parameters: 233

🏷️  Found 230 pairs of similar tags:
================================================================================
  1.000 - 'FIRE.EXIT' ≈ 'FIRE_EXIT'
          (normalized: 'FIRE_EXIT' ≈ 'FIRE_EXIT')
  0.950 - 'DOOR.WIDTH' ≈ 'DOOR_WIDTH'
          (normalized: 'DOOR_WIDTH' ≈ 'DOOR_WIDTH')

⚙️  Found 167 pairs of similar parameters:
================================================================================
  1.000 - 'BUILDING.HEIGHT' ≈ 'BUILDING_HEIGHT'
          (normalized: 'BUILDING_HEIGHT' ≈ 'BUILDING_HEIGHT')

⚠️  Summary: Found 397 potential naming inconsistencies
   - 230 tag similarity issues
   - 167 parameter similarity issues
```

### Output Elements

1. **Header**: Shows file path and total counts
2. **Similar Tags Section**: Lists tag pairs with similarity scores
3. **Similar Parameters Section**: Lists parameter pairs with similarity scores
4. **Normalized Names**: Shows how names are normalized for comparison
5. **Summary Statistics**: Total issues found by category

## Similarity Algorithm

### Normalization Process
1. Convert to uppercase
2. Replace separators (`.`, `-`, spaces) with underscores `_`
3. Remove consecutive underscores
4. Trim leading/trailing underscores

### Similarity Calculation
1. **Exact Match**: Returns 1.0 if names are identical after normalization
2. **Sequence Similarity**: Uses Python's `difflib.SequenceMatcher`
3. **Substring Boost**: Adds bonus for substring containment
4. **Threshold Filtering**: Only reports pairs above the threshold

### Example Normalizations
| Original | Normalized |
|----------|------------|
| `FIRE.EXIT` | `FIRE_EXIT` |
| `FIRE-EXIT` | `FIRE_EXIT` |
| `fire exit` | `FIRE_EXIT` |
| `BUILDING.EVACUATION.HEIGHT` | `BUILDING_EVACUATION_HEIGHT` |

## Interpreting Results

### High Similarity (>= 0.95)
Likely indicates:
- Different separator conventions
- Exact duplicates with formatting differences
- Should be consolidated to single naming convention

### Medium Similarity (0.8-0.94)
May indicate:
- Related but distinct concepts
- Hierarchical relationships
- Requires manual review for consolidation

### Threshold Recommendations
- **0.99**: Only exact matches (after normalization)
- **0.90**: High confidence similar names
- **0.80**: Default - balance of precision and recall
- **0.70**: More aggressive detection (may include false positives)

## Integration with Existing Tools

### Relationship to Other Scripts
- Complements `tag_evaluator.py` by focusing on naming consistency
- Can be used with `enhanced_lx_runner.py` output files
- Supports analysis of files from `output_runs/` directories

### Workflow Integration
1. Run extraction with `enhanced_lx_runner.py`
2. Analyze naming consistency with `similarity_scanner.py`
3. Evaluate tag quality with `tag_evaluator.py`
4. Apply corrections and re-run if needed

## Technical Implementation

### Key Classes
- `SimilarityScanner`: Main analysis class with configurable threshold
- Methods for normalization, similarity calculation, and result formatting

### Dependencies
- Standard library only (no external dependencies)
- Compatible with Python 3.7+

### Performance Characteristics
- O(n²) complexity for similarity comparison
- Memory usage proportional to number of unique tags/parameters
- Typical processing time: < 1 second for 1000+ items

## Examples and Use Cases

### Quality Assurance
Use during extraction pipeline validation:
```bash
# Check for naming inconsistencies in latest run
python similarity_scanner.py output_runs/latest/enhanced_output/enhanced_extraction_results.json
```

### Threshold Tuning
Find optimal threshold for your dataset:
```bash
# Start conservative
python similarity_scanner.py file.json --threshold 0.99

# Gradually lower to find sweet spot
python similarity_scanner.py file.json --threshold 0.90
```

### Batch Processing
Analyze multiple extraction runs:
```bash
for dir in output_runs/*/enhanced_output/; do
    echo "Analyzing $dir"
    python similarity_scanner.py "$dir/enhanced_extraction_results.json"
done
```

## Troubleshooting

### Common Issues

#### File Not Found
```
❌ Error: File not found: path/to/file.json
```
**Solution**: Verify the file path exists and is accessible

#### Invalid JSON
```
❌ Error: Failed to load file: Expecting ',' delimiter
```
**Solution**: Check that the JSON file is valid and not corrupted

#### No Similarities Found
```
✅ No overly similar tags found.
✅ No overly similar parameters found.
```
**Possible reasons**:
- Threshold too high - try lowering it
- Good naming consistency (ideal case)
- Limited dataset size

### Performance Considerations
- Large datasets (>5000 items) may take longer to process
- Consider using higher thresholds for initial analysis
- Memory usage scales with dataset size

## Future Enhancements

### Potential Improvements
- **Semantic Similarity**: Use word embeddings for concept similarity
- **Batch Processing**: Built-in support for multiple files
- **Export Formats**: JSON/CSV output for programmatic use
- **Interactive Mode**: Guided consolidation recommendations
- **Configuration Files**: Save/load similarity settings

### Integration Opportunities
- **CI/CD Integration**: Automated quality checks in pipelines
- **Web Interface**: Visual similarity analysis dashboard
- **API Integration**: Expose functionality as REST endpoints