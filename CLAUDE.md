# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

LangExtract is a Python library developed by Google for extracting structured information from unstructured text using Large Language Models (LLMs). It provides precise source grounding, reliable structured outputs, and is optimized for long documents.

## Development Commands

### Setup and Environment
```bash
# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install
```

### Testing
```bash
# Run all unit tests
pytest tests/

# Run tests with coverage
pytest tests/ --cov=langextract --cov-report=html

# Run specific test file
pytest tests/test_annotation.py

# Run only live API tests (requires API keys)
pytest tests/ -m live_api

# Run full test matrix (multiple Python versions + linting)
tox
```

### Code Quality
```bash
# Auto-format code
./autoformat.sh

# Or manually run formatters
isort langextract tests
pyink langextract tests

# Lint code
pylint --rcfile=.pylintrc langextract tests

# Type checking
pytype langextract
```

### Running Examples
```bash
# Set up API keys
export LANGEXTRACT_API_KEY="your-api-key-here"  # For Gemini
# Or
export LANGEXTRACT_OPENAI_API_KEY="your-openai-key"  # For OpenAI

# Run examples
python examples/medication_extraction.py
python examples/romeo_and_juliet.py
```

## Architecture Overview

### Key Components

1. **langextract/__init__.py**: Main API entry point with `extract()` function
2. **langextract/data.py**: Core data structures (`Extraction`, `Document`, `AnnotatedDocument`)
3. **langextract/inference.py**: LLM provider implementations (Gemini, OpenAI, Ollama)
4. **langextract/annotation.py**: Main `Annotator` class coordinating extraction pipeline
5. **langextract/schema.py**: Schema constraint generation for structured outputs
6. **langextract/chunking.py**: Document segmentation for long texts
7. **langextract/visualization.py**: Interactive HTML result visualization

### Processing Pipeline

1. **Text Chunking**: Documents are intelligently segmented into processable chunks
2. **Prompt Generation**: Templates with few-shot examples are created
3. **LLM Inference**: Parallel processing with configurable workers
4. **Output Resolution**: Structured data extraction from LLM responses
5. **Source Alignment**: Character-level grounding to original text
6. **Visualization**: Optional HTML generation for result analysis

### LLM Provider Support

- **Gemini** (Primary): Full support including schema constraints
- **OpenAI**: GPT-4 and other models
- **Ollama**: Local model support

## Important File Locations

- **Configuration**: `pyproject.toml`, `tox.ini`, `.pylintrc`
- **Documentation**: `README.md`, `CONTRIBUTING.md`, examples in `docs/`
- **CI/CD**: `.github/workflows/`, `kokoro/`
- **Docker**: `Dockerfile` for containerized deployment

## Development Guidelines

### Code Style
- Follows Google Python Style Guide
- Line length: 80 characters
- Formatter: pyink (Google's Black fork)
- Import sorting: isort with Google profile

### Testing Strategy
- All new features require unit tests
- Live API tests marked with `@pytest.mark.live_api`
- Test files named `{module}_test.py`
- Use pytest fixtures for common test data

### Commit Message Format
Follow conventional commits:
- feat: new features
- fix: bug fixes
- docs: documentation changes
- test: test additions/changes
- refactor: code refactoring
- chore: maintenance tasks

### API Design Principles
- Simple, intuitive API surface (`extract()` function)
- Flexible schema definitions using Pydantic models
- Provider-agnostic abstractions
- Comprehensive error handling with custom exceptions

## Key Dependencies

### Core Dependencies
- **google-genai>=0.1.0**: Gemini model integration
- **openai>=1.50.0**: OpenAI API client
- **pydantic>=1.8.0**: Data validation and schemas
- **pandas>=1.3.0**: Data manipulation
- **tqdm>=4.64.0**: Progress bars

### Development Dependencies
- **pytest>=7.4.0**: Testing framework
- **pyink~=24.3.0**: Code formatter
- **pylint>=3.0.0**: Linter
- **pytype>=2024.10.11**: Type checker

## Common Tasks

### Adding a New LLM Provider
1. Create new class inheriting from `BaseLanguageModel` in `inference.py`
2. Implement required methods: `generate_text()`, `count_tokens()`
3. Add provider-specific configuration handling
4. Update `__init__.py` to expose new provider
5. Add tests in `tests/test_inference.py`

### Modifying Extraction Pipeline
1. Core logic is in `annotation.py` (`Annotator` class)
2. Update `_process_chunk()` for chunk-level changes
3. Modify `_resolve_extractions()` for output processing
4. Ensure backward compatibility with existing API

### Working with Schema Constraints
1. Schema generation is in `schema.py`
2. Currently optimized for Gemini models
3. Uses Pydantic models for schema definition
4. See `generate_gemini_schema()` for implementation details

## Environment Variables

- **LANGEXTRACT_API_KEY**: Gemini API key
- **LANGEXTRACT_OPENAI_API_KEY**: OpenAI API key
- **LANGEXTRACT_OLLAMA_BASE_URL**: Ollama server URL (default: http://localhost:11434)

## Debugging Tips

1. Enable verbose logging: Set log level in your code
2. Use `visualization.py` to generate HTML outputs for debugging extractions
3. Check character alignments with `CharInterval` objects
4. Use pytest's `-s` flag to see print statements during tests

## Release Process

1. Update version in `pyproject.toml`
2. Create GitHub release with tag
3. GitHub Actions automatically publishes to PyPI
4. Docker images built and pushed automatically