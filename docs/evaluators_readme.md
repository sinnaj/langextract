# LangExtract Quality Evaluators

This directory contains two evaluation scripts for assessing the quality of extractions produced by the LangExtract system.

## Overview

- **`norm_evaluator.py`**: Evaluates the quality of NORM extractions
- **`tag_evaluator.py`**: Evaluates the quality of TAG extractions

Both evaluators use Large Language Models (LLM) to assess quality based on specific criteria and generate comprehensive reports.

## Requirements

### Dependencies
The evaluators require the LangExtract package and its dependencies, which should already be installed if you're working in this repository.

### API Keys
You need **one** of the following API keys:

1. **OpenRouter API Key** (recommended):
   - Get from: https://openrouter.ai/keys
   - Set as environment variable: `OPENROUTER_API_KEY`
   - Uses Gemini 2.5 Flash via OpenRouter's API

2. **Gemini API Key** (fallback):
   - Get from: https://ai.google.dev/gemini-api/docs/api-key
   - Set as environment variable: `GEMINI_API_KEY`
   - Uses Gemini 2.5 Flash directly

## Norm Evaluator

### Purpose
Evaluates NORM extractions based on two key criteria:

1. **Atomicity** (1-10): How well is this norm interpretable/implementable without additional context?
2. **Applicability & Satisfied Structure** (1-10): How meaningful & actionable are the application and satisfaction criteria?

### Usage

```bash
# Basic usage
python norm_evaluator.py combined_extractions.json

# Save output to file
python norm_evaluator.py input.json --output norm_evaluation_report.json

# Quiet mode (no progress output)
python norm_evaluator.py input.json --quiet
```

### Output

The norm evaluator provides:

1. **Meta Report**: Statistics about the evaluation including:
   - Total norms evaluated
   - Average quality scores for each dimension
   - Quality distribution (excellent/good/fair/poor)

2. **Detailed Evaluations**: For each norm:
   - Atomicity score and reasoning
   - Applicability structure score and reasoning
   - Overall quality score
   - Key issues identified
   - Improvement suggestions

3. **Sorted Results**: Norms sorted by quality (lowest first) to prioritize improvements

## Tag Evaluator

### Purpose
Evaluates TAG extractions based on two key criteria:

1. **Uniqueness** (1-10): Are there similar tags with essentially the same content?
2. **Tag Entity Structure** (1-10): Are main entities showing up in the middle of tag strings?

### Usage

```bash
# Basic usage
python tag_evaluator.py combined_extractions.json

# Save output to file  
python tag_evaluator.py input.json --output tag_evaluation_report.json

# Quiet mode (no progress output)
python tag_evaluator.py input.json --quiet
```

### Output

The tag evaluator provides:

1. **Meta Report**: Statistics including:
   - Total tags evaluated
   - Average quality scores for each dimension
   - Structural analysis (tag depth, prefixes, duplicates)
   - Potential duplicate detection

2. **Detailed Evaluations**: For each tag:
   - Uniqueness score and reasoning
   - Entity structure score and reasoning
   - Overall quality score
   - Similar tags identified
   - Structural issues
   - Improvement suggestions

3. **Sorted Results**: Tags sorted by quality (lowest first)
4. **Usage Analysis**: Most frequently used tags

## Example Output

### Norm Evaluation Report Summary
```
============================================================
NORM QUALITY EVALUATION REPORT
============================================================
Total norms evaluated: 89
Average overall quality: 6.8/10
Average atomicity: 6.5/10
Average applicability structure: 7.1/10
Quality range: 3.2-9.1

Quality Distribution:
  Excellent (8-10): 23
  Good (6-8):       41
  Fair (4-6):       20
  Poor (<4):        5

Lowest Quality Norms (showing top 5):
  1. ID: norm_042 | Quality: 3.2/10
     Statement: Door width requirements for emergency egress...
     Issues: Unclear measurement criteria, Missing context
```

### Tag Evaluation Report Summary
```
============================================================
TAG QUALITY EVALUATION REPORT
============================================================
Total tags evaluated: 156
Average overall quality: 7.2/10
Average uniqueness: 7.8/10
Average entity structure: 6.6/10
Quality range: 2.1-9.4

Structural Analysis:
  Average tag depth: 2.8
  Single-level tags: 23
  Deep tags (>4 levels): 12
  Unique prefixes: 18

Duplicate Analysis:
  Potential duplicates found: 8
  Examples:
    'DOOR.WIDTH' ~ 'DOOR.DIMENSIONS.WIDTH'
    'FIRE.SAFETY' ~ 'SAFETY.FIRE'
```

## Testing

Run the test suite to verify the evaluators work correctly:

```bash
python test_evaluators.py
```

This will test the data loading, prompt generation, and output formatting without requiring API keys.

## Error Handling

The evaluators include robust error handling:

- **API Failures**: Individual evaluation failures are logged but don't stop the process
- **Invalid Data**: Malformed extractions are skipped with warnings
- **Missing Fields**: Required fields are validated before evaluation

## Performance Considerations

- **API Costs**: Each norm/tag requires one LLM API call
- **Rate Limits**: The evaluators process items sequentially to respect API limits
- **Large Files**: For files with hundreds of extractions, expect several minutes of processing time

## Integration

The evaluators are designed to work with the standard LangExtract pipeline:

1. Run extraction: `lxRunnerExtraction.py`
2. Generate `combined_extractions.json`
3. Evaluate quality: `norm_evaluator.py` and `tag_evaluator.py`
4. Review lowest-quality items for improvement

## Troubleshooting

### Common Issues

1. **"No NORM/Tag extractions found"**
   - Check that your input file contains the correct extraction classes
   - Verify the JSON structure matches expected format

2. **"API key required"**
   - Set either `OPENROUTER_API_KEY` or `GEMINI_API_KEY` environment variable
   - Verify the key is valid and has sufficient credits

3. **"Evaluation failed"**
   - Check network connectivity
   - Verify API service status
   - Review individual error messages in the output

### File Format Requirements

The input file must be a valid `combined_extractions.json` with structure:
```json
{
  "extractions": [
    {
      "extraction_class": "NORM",
      "attributes": {
        "id": "...",
        "norm_statement": "...",
        "applies_if": "...",
        "satisfied_if": "..."
      }
    }
  ]
}
```