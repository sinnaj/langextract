# LangExtract Development Guide

This codebase builds on the LangExtract library (Google's structured text extraction tool) with custom extraction runners, web interfaces, and domain-specific prompt engineering.

## Architecture Overview

### Core Components

- **`langextract/` package**: The main LangExtract library providing `lx.extract()`, providers, schema system, and visualization
- **`lxRunnerExtraction.py`**: Custom extraction orchestrator for regulatory document processing with rich schema normalization
- **`web/`**: Flask workshop app for interactive extraction runs with live logs and file management
- **`input_*files/`**: Domain-specific prompts, examples, glossaries, and teaching materials for Spanish regulatory compliance

### Key Data Flow

1. **Extraction Pipeline**: `lx.extract()` → Provider (OpenRouter/Gemini/Ollama) → Resolver → AnnotatedDocument → Post-processing
2. **Rich Schema**: Legacy extractions normalized to single JSON with `norms[]`, `tags[]`, `parameters[]`, `locations[]`, `questions[]`, `consequences[]`
3. **Output Structure**: `output_runs/<run_id>/` containing `output.json`, chunks, logs, and optional visualization

## Essential Patterns

### Provider System
```python
# Provider auto-selection by model_id pattern
lx.extract(model_id="gemini-2.5-flash")  # → GeminiLanguageModel
lx.extract(model_id="gpt-4o")            # → OpenAILanguageModel
lx.extract(model_id="llama3:8b")         # → OllamaLanguageModel

# Explicit provider control
config = lx.factory.ModelConfig(
    model_id="google/gemini-2.5-flash",
    provider="OpenAILanguageModel",  # Force OpenRouter route
    provider_kwargs={"base_url": "https://openrouter.ai/api/v1"}
)
```

### Environment Configuration
```bash
# Provider routing
USE_OPENROUTER=1              # Use OpenRouter (default)
OPENAI_API_KEY=<key>         # OpenRouter API key
GOOGLE_API_KEY=<key>         # Direct Gemini access

# Input discovery
LE_INPUT_FILE=path/to/input.txt  # Override input file location

# Feature flags
LX_TEACH_MODE=1              # Enable relationship inference
LX_WRITE_VIS=1              # Generate HTML visualization
```

### Custom Extraction Runner Pattern
The `lxRunnerExtraction.py` demonstrates the canonical pattern:
- Environment setup with provider registry
- Input discovery (`LE_INPUT_FILE` or search `output_runs/<id>/input/`)
- Model configuration with resolver params (`fence_output=False`, JSON format)
- Error-resilient execution (always produces valid output)
- Rich schema normalization with deduplication
- Optional enrichment in teach mode

## Development Workflows

### Python Environment Setup
**CRITICAL**: Always use the `.venv` virtual environment - it contains all required dependencies:

```powershell
# Windows PowerShell - Use .venv Python for all operations
.venv\Scripts\python.exe your_script.py
.venv\Scripts\Activate.ps1  # Activate environment (optional)

# Linux/Mac
.venv/bin/python your_script.py
source .venv/bin/activate   # Activate environment (optional)
```

### Running Extractions
```powershell
# Via web interface (ALWAYS use .venv)
.venv\Scripts\python.exe web/app.py  # → http://127.0.0.1:5000

# Direct runner (ALWAYS use .venv)
$env:LE_INPUT_FILE="path/to/input.txt"
.venv\Scripts\python.exe -c "import lxRunnerExtraction; lxRunnerExtraction.makeRun(...)"

# Example from terminal history
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); import lxRunnerExtraction; lxRunnerExtraction.makeRun('1756231677','google/gemini-2.5-flash',0.15,15,5000,1,'input_promptfiles/extraction_prompt_V5.md','input_glossaryfiles/dsl_glossary.json','input_examplefiles/examples_V5.py','input_semanticsfiles/prompt_appendix_entity_semantics.md','input_teachfiles/prompt_appendix_teaching.md')"

# Using tasks (configured in .vscode/tasks.json)
# Tasks automatically use .venv: "Run Flask dev server", "Run makeRun", "Run runner_worker"
```

### Testing Strategy
```bash
# Full test suite (uses .venv automatically via tox)
tox                           # Python 3.10-3.12 + lint
pytest tests/ -m "not live_api"  # Direct pytest (ensure .venv activated)

# Provider-specific tests
tox -e ollama-integration     # Requires Ollama running
tox -e live-api              # Requires API keys
tox -e plugin-integration    # Provider plugin E2E tests

# Code formatting (uses .venv)
./autoformat.sh             # isort + pyink (Google style)
tox -e format               # Check formatting

# Manual pytest (if not using tox)
.venv\Scripts\python.exe -m pytest tests/ -m "not live_api"  # Windows
.venv/bin/python -m pytest tests/ -m "not live_api"         # Linux/Mac
```

### Provider Development
Use the generator script for new providers:
```bash
# Always use .venv for script execution
.venv\Scripts\python.exe scripts/create_provider_plugin.py MyProvider --with-schema  # Windows
.venv/bin/python scripts/create_provider_plugin.py MyProvider --with-schema         # Linux/Mac
```

Creates complete plugin structure with entry points, tests, and documentation.

## Code Conventions

### Import Organization
```python
# Standard library
import os
from pathlib import Path

# Third-party
import langextract as lx
from absl.testing import absltest

# Local modules
from langextract.core import data
from langextract.providers import registry
```

### Error Handling
- **Never abort extraction runs**: Always synthesize minimal valid outputs on errors
- **Sanitize logs**: Redact API keys with regex patterns
- **Graceful degradation**: Use fallback providers, empty examples, default configurations

### Schema Patterns
```python
# Rich schema structure (post lxRunnerExtraction normalization)
{
  "extractions": [{
    "schema_version": "1.0.0",
    "norms": [...],           # Regulatory requirements
    "tags": [...],           # Hierarchical categorization
    "parameters": [...],     # Extracted thresholds/values
    "locations": [...],      # Geographic scope
    "questions": [...],      # Clarification needs
    "consequences": [...],   # Compliance implications
    "quality": {"errors": [], "warnings": []}
  }]
}
```

## Integration Points

### Web Runner
- **SSE streaming**: Live logs via `GET /runs/<id>/logs`
- **File management**: Preview/download via `GET /runs/<id>/file`
- **Multipart uploads**: Input documents to `output_runs/<id>/input/`

### DSL Grammar
Regulatory extraction uses UPPERCASE.DOTCASE paths:
```
DOOR.TYPE == 'AUTOMATIC'
PROJECT.HEIGHT >= 50 AND PROJECT.HEIGHT <= 100
LOCATION IN ['MADRID','BARCELONA']
HAS(SAFETY.FIRE)  # Ontology existence check
```

### Visualization
```python
# Generate interactive HTML from JSONL
html = lx.visualize("extraction_results.jsonl")
# Highlights extractions in source text with entity filtering
```

## Debugging Approaches

- **Per-chunk traces**: Check `output_runs/<id>/chunks/` for raw resolver output
- **Emergency saves**: `lx output/` contains pre-processing document snapshots
- **Quality metrics**: `quality.errors` and `quality.warnings` in final output
- **Verbose logging**: LangExtract uses absl logging with alignment details

When extraction fails, check the resolver's parsing path: strict JSON → YAML → sanitized JSON fallback.
