# Norm and Tag Quality Evaluators

Two evaluation scripts have been created to assess the quality of extractions from the LangExtract system:

## Files Created

1. **`norm_evaluator.py`** - Evaluates NORM extractions
2. **`tag_evaluator.py`** - Evaluates TAG extractions  
3. **`test_evaluators.py`** - Test suite for validation
4. **`docs/evaluators_readme.md`** - Comprehensive documentation

## Quick Start

1. **Set up API key** (choose one):
   ```bash
   export OPENROUTER_API_KEY="your_key_here"  # Recommended
   # OR
   export GEMINI_API_KEY="your_key_here"      # Fallback
   ```

2. **Run evaluations**:
   ```bash
   # Evaluate norms
   python norm_evaluator.py combined_extractions.json --output norm_report.json
   
   # Evaluate tags
   python tag_evaluator.py combined_extractions.json --output tag_report.json
   ```

3. **Test without API**:
   ```bash
   python test_evaluators.py  # Validates structure and functionality
   ```

## Key Features

### Norm Evaluator
- **Atomicity**: Evaluates how well norms can be interpreted/implemented without additional context
- **Applicability & Satisfied Structure**: Assesses meaningfulness and actionability of conditions
- Reports lowest quality norms first for prioritized improvement

### Tag Evaluator
- **Uniqueness**: Detects similar tags with essentially the same content
- **Entity Structure**: Identifies cases where main entities appear in the middle of tag strings
- Provides structural analysis and duplicate detection

## Sample Output

Both evaluators generate comprehensive reports with:
- Meta statistics (averages, distributions, counts)
- Individual quality scores with reasoning
- Prioritized improvement recommendations
- Sorted results (lowest quality first)

## API Requirements

- **OpenRouter**: Uses `google/gemini-2.5-flash` model via OpenAI-compatible API
- **Gemini**: Direct access to `gemini-2.5-flash` model
- Robust error handling for API failures

The evaluators are production-ready and follow the repository's coding standards.