<p align="center">
  <a href="https://github.com/google/langextract">
    <img src="https://raw.githubusercontent.com/google/langextract/main/docs/_static/logo.svg" alt="LangExtract Logo" width="128" />
  </a>
</p>

# LangExtract

[![PyPI version](https://img.shields.io/pypi/v/langextract.svg)](https://pypi.org/project/langextract/)
[![GitHub stars](https://img.shields.io/github/stars/google/langextract.svg?style=social&label=Star)](https://github.com/google/langextract)
![Tests](https://github.com/google/langextract/actions/workflows/ci.yaml/badge.svg)

## Table of Contents

- [Introduction](#introduction)
- [Why LangExtract?](#why-langextract)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [API Key Setup for Cloud Models](#api-key-setup-for-cloud-models)
- [Adding Custom Model Providers](#adding-custom-model-providers)
- [Using OpenAI Models](#using-openai-models)
- [Using Local LLMs with Ollama](#using-local-llms-with-ollama)
- [More Examples](#more-examples)
  - [*Romeo and Juliet* Full Text Extraction](#romeo-and-juliet-full-text-extraction)
  - [Medication Extraction](#medication-extraction)
  - [Radiology Report Structuring: RadExtract](#radiology-report-structuring-radextract)
- [Community Providers](#community-providers)
- [Contributing](#contributing)
- [Testing](#testing)
- [Disclaimer](#disclaimer)

## Introduction

LangExtract is a Python library that uses LLMs to extract structured information from unstructured text documents based on user-defined instructions. It processes materials such as clinical notes or reports, identifying and organizing key details while ensuring the extracted data corresponds to the source text.

## Why LangExtract?

1.  **Precise Source Grounding:** Maps every extraction to its exact location in the source text, enabling visual highlighting for easy traceability and verification.
2.  **Reliable Structured Outputs:** Enforces a consistent output schema based on your few-shot examples, leveraging controlled generation in supported models like Gemini to guarantee robust, structured results.
3.  **Optimized for Long Documents:** Overcomes the "needle-in-a-haystack" challenge of large document extraction by using an optimized strategy of text chunking, parallel processing, and multiple passes for higher recall.
4.  **Interactive Visualization:** Instantly generates a self-contained, interactive HTML file to visualize and review thousands of extracted entities in their original context.
5.  **Flexible LLM Support:** Supports your preferred models, from cloud-based LLMs like the Google Gemini family to local open-source models via the built-in Ollama interface.
6.  **Adaptable to Any Domain:** Define extraction tasks for any domain using just a few examples. LangExtract adapts to your needs without requiring any model fine-tuning.
7.  **Leverages LLM World Knowledge:** Utilize precise prompt wording and few-shot examples to influence how the extraction task may utilize LLM knowledge. The accuracy of any inferred information and its adherence to the task specification are contingent upon the selected LLM, the complexity of the task, the clarity of the prompt instructions, and the nature of the prompt examples.

## Quick Start

> **Note:** Using cloud-hosted models like Gemini requires an API key. See the [API Key Setup](#api-key-setup-for-cloud-models) section for instructions on how to get and configure your key.

Extract structured information with just a few lines of code.

### 1. Define Your Extraction Task

First, create a prompt that clearly describes what you want to extract. Then, provide a high-quality example to guide the model.

```python
import langextract as lx
import textwrap

# 1. Define the prompt and extraction rules
prompt = textwrap.dedent("""\
    Extract characters, emotions, and relationships in order of appearance.
    Use exact text for extractions. Do not paraphrase or overlap entities.
    Provide meaningful attributes for each entity to add context.""")

# 2. Provide a high-quality example to guide the model
examples = [
    lx.data.ExampleData(
        text="ROMEO. But soft! What light through yonder window breaks? It is the east, and Juliet is the sun.",
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="ROMEO",
                attributes={"emotional_state": "wonder"}
            ),
            lx.data.Extraction(
                extraction_class="emotion",
                extraction_text="But soft!",
                attributes={"feeling": "gentle awe"}
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Juliet is the sun",
                attributes={"type": "metaphor"}
            ),
        ]
    )
]
```

### 2. Run the Extraction

Provide your input text and the prompt materials to the `lx.extract` function.

```python
# The input text to be processed
input_text = "Lady Juliet gazed longingly at the stars, her heart aching for Romeo"

# Run the extraction
result = lx.extract(
    text_or_documents=input_text,
    prompt_description=prompt,
    examples=examples,
    model_id="gemini-2.5-flash",
)
```

> **Model Selection**: `gemini-2.5-flash` is the recommended default, offering an excellent balance of speed, cost, and quality. For highly complex tasks requiring deeper reasoning, `gemini-2.5-pro` may provide superior results. For large-scale or production use, a Tier 2 Gemini quota is suggested to increase throughput and avoid rate limits. See the [rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits#tier-2) for details.
>
> **Model Lifecycle**: Note that Gemini models have a lifecycle with defined retirement dates. Users should consult the [official model version documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions) to stay informed about the latest stable and legacy versions.

### 3. Visualize the Results

The extractions can be saved to a `.jsonl` file, a popular format for working with language model data. LangExtract can then generate an interactive HTML visualization from this file to review the entities in context.

```python
# Save the results to a JSONL file
lx.io.save_annotated_documents([result], output_name="extraction_results.jsonl", output_dir=".")

# Generate the visualization from the file
html_content = lx.visualize("extraction_results.jsonl")
with open("visualization.html", "w") as f:
    if hasattr(html_content, 'data'):
        f.write(html_content.data)  # For Jupyter/Colab
    else:
        f.write(html_content)
```

This creates an animated and interactive HTML file:

![Romeo and Juliet Basic Visualization ](https://raw.githubusercontent.com/google/langextract/main/docs/_static/romeo_juliet_basic.gif)

> **Note on LLM Knowledge Utilization:** This example demonstrates extractions that stay close to the text evidence - extracting "longing" for Lady Juliet's emotional state and identifying "yearning" from "gazed longingly at the stars." The task could be modified to generate attributes that draw more heavily from the LLM's world knowledge (e.g., adding `"identity": "Capulet family daughter"` or `"literary_context": "tragic heroine"`). The balance between text-evidence and knowledge-inference is controlled by your prompt instructions and example attributes.

### Scaling to Longer Documents

For larger texts, you can process entire documents directly from URLs with parallel processing and enhanced sensitivity:

```python
# Process Romeo & Juliet directly from Project Gutenberg
result = lx.extract(
    text_or_documents="https://www.gutenberg.org/files/1513/1513-0.txt",
    prompt_description=prompt,
    examples=examples,
    model_id="gemini-2.5-flash",
    extraction_passes=3,    # Improves recall through multiple passes
    max_workers=20,         # Parallel processing for speed
    max_char_buffer=1000    # Smaller contexts for better accuracy
)
```

This approach can extract hundreds of entities from full novels while maintaining high accuracy. The interactive visualization seamlessly handles large result sets, making it easy to explore hundreds of entities from the output JSONL file. **[See the full *Romeo and Juliet* extraction example →](https://github.com/google/langextract/blob/main/docs/examples/longer_text_example.md)** for detailed results and performance insights.

## Installation

### From PyPI

```bash
pip install langextract
```

*Recommended for most users. For isolated environments, consider using a virtual environment:*

```bash
python -m venv langextract_env
source langextract_env/bin/activate  # On Windows: langextract_env\Scripts\activate
pip install langextract
```

### From Source

LangExtract uses modern Python packaging with `pyproject.toml` for dependency management:

*Installing with `-e` puts the package in development mode, allowing you to modify the code without reinstalling.*


```bash
git clone https://github.com/google/langextract.git
cd langextract

# For basic installation:
pip install -e .

# For development (includes linting tools):
pip install -e ".[dev]"


# For testing (includes pytest):
pip install -e ".[test]"
```

### Docker

```bash
docker build -t langextract .
docker run --rm -e LANGEXTRACT_API_KEY="your-api-key" langextract python your_script.py
```

## API Key Setup for Cloud Models

When using LangExtract with cloud-hosted models (like Gemini or OpenAI), you'll need to
set up an API key. On-device models don't require an API key. For developers
using local LLMs, LangExtract offers built-in support for Ollama and can be
extended to other third-party APIs by updating the inference endpoints.

### API Key Sources

Get API keys from:

*   [AI Studio](https://aistudio.google.com/app/apikey) for Gemini models
*   [Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview) for enterprise use
*   [OpenAI Platform](https://platform.openai.com/api-keys) for OpenAI models

### Setting up API key in your environment

**Option 1: Environment Variable**

```bash
export LANGEXTRACT_API_KEY="your-api-key-here"
```

**Option 2: .env File (Recommended)**

Add your API key to a `.env` file:

```bash
# Add API key to .env file
cat >> .env << 'EOF'
LANGEXTRACT_API_KEY=your-api-key-here
EOF

# Keep your API key secure
echo '.env' >> .gitignore
```

In your Python code:
```python
import langextract as lx

result = lx.extract(
    text_or_documents=input_text,
    prompt_description="Extract information...",
    examples=[...],
    model_id="gemini-2.5-flash"
)
```

**Option 3: Direct API Key (Not Recommended for Production)**

You can also provide the API key directly in your code, though this is not recommended for production use:

```python
result = lx.extract(
    text_or_documents=input_text,
    prompt_description="Extract information...",
    examples=[...],
    model_id="gemini-2.5-flash",
    api_key="your-api-key-here"  # Only use this for testing/development
)
```

<<<<<<< HEAD
=======
**Option 4: Vertex AI (Service Accounts)**

Use [Vertex AI](https://cloud.google.com/vertex-ai/docs/start/introduction-unified-platform) for authentication with service accounts:

```python
result = lx.extract(
    text_or_documents=input_text,
    prompt_description="Extract information...",
    examples=[...],
    model_id="gemini-2.5-flash",
    language_model_params={
        "vertexai": True,
        "project": "your-project-id",
        "location": "global"  # or regional endpoint
    }
)
```

>>>>>>> upstream/main
## Adding Custom Model Providers

LangExtract supports custom LLM providers via a lightweight plugin system. You can add support for new models without changing core code.

- Add new model support independently of the core library
- Distribute your provider as a separate Python package
- Keep custom dependencies isolated
- Override or extend built-in providers via priority-based resolution

See the detailed guide in [Provider System Documentation](langextract/providers/README.md) to learn how to:

- Register a provider with `@registry.register(...)`
- Publish an entry point for discovery
- Optionally provide a schema with `get_schema_class()` for structured output
- Integrate with the factory via `create_model(...)`

## Using OpenAI Models

LangExtract supports OpenAI models (requires optional dependency: `pip install langextract[openai]`):

```python
import langextract as lx

result = lx.extract(
    text_or_documents=input_text,
    prompt_description=prompt,
    examples=examples,
    model_id="gpt-4o",  # Automatically selects OpenAI provider
    api_key=os.environ.get('OPENAI_API_KEY'),
    fence_output=True,
    use_schema_constraints=False
)
```

Note: OpenAI models require `fence_output=True` and `use_schema_constraints=False` because LangExtract doesn't implement schema constraints for OpenAI yet.

## Using Local LLMs with Ollama
LangExtract supports local inference using Ollama, allowing you to run models without API keys:

```python
import langextract as lx

result = lx.extract(
    text_or_documents=input_text,
    prompt_description=prompt,
    examples=examples,
    model_id="gemma2:2b",  # Automatically selects Ollama provider
    model_url="http://localhost:11434",
    fence_output=False,
    use_schema_constraints=False
)
```

**Quick setup:** Install Ollama from [ollama.com](https://ollama.com/), run `ollama pull gemma2:2b`, then `ollama serve`.

For detailed installation, Docker setup, and examples, see [`examples/ollama/`](examples/ollama/).

## More Examples

Additional examples of LangExtract in action:

### *Romeo and Juliet* Full Text Extraction

LangExtract can process complete documents directly from URLs. This example demonstrates extraction from the full text of *Romeo and Juliet* from Project Gutenberg (147,843 characters), showing parallel processing, sequential extraction passes, and performance optimization for long document processing.

**[View *Romeo and Juliet* Full Text Example →](https://github.com/google/langextract/blob/main/docs/examples/longer_text_example.md)**

### Medication Extraction

> **Disclaimer:** This demonstration is for illustrative purposes of LangExtract's baseline capability only. It does not represent a finished or approved product, is not intended to diagnose or suggest treatment of any disease or condition, and should not be used for medical advice.

LangExtract excels at extracting structured medical information from clinical text. These examples demonstrate both basic entity recognition (medication names, dosages, routes) and relationship extraction (connecting medications to their attributes), showing LangExtract's effectiveness for healthcare applications.

**[View Medication Examples →](https://github.com/google/langextract/blob/main/docs/examples/medication_examples.md)**

### Radiology Report Structuring: RadExtract

Explore RadExtract, a live interactive demo on HuggingFace Spaces that shows how LangExtract can automatically structure radiology reports. Try it directly in your browser with no setup required.

**[View RadExtract Demo →](https://huggingface.co/spaces/google/radextract)**

## Community Providers

Extend LangExtract with custom model providers! Check out our [Community Provider Plugins](COMMUNITY_PROVIDERS.md) registry to discover providers created by the community or add your own.

For detailed instructions on creating a provider plugin, see the [Custom Provider Plugin Example](examples/custom_provider_plugin/).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](https://github.com/google/langextract/blob/main/CONTRIBUTING.md) to get started
with development, testing, and pull requests. You must sign a
[Contributor License Agreement](https://cla.developers.google.com/about)
before submitting patches.



## Testing

To run tests locally from the source:

```bash
# Clone the repository
git clone https://github.com/google/langextract.git
cd langextract

# Install with test dependencies
pip install -e ".[test]"

# Run all tests
pytest tests
```

Or reproduce the full CI matrix locally with tox:

```bash
tox  # runs pylint + pytest on Python 3.10 and 3.11
```

### Ollama Integration Testing

If you have Ollama installed locally, you can run integration tests:

```bash
# Test Ollama integration (requires Ollama running with gemma2:2b model)
tox -e ollama-integration
```

This test will automatically detect if Ollama is available and run real inference tests.

## Development

### Code Formatting

This project uses automated formatting tools to maintain consistent code style:

```bash
# Auto-format all code
./autoformat.sh

# Or run formatters separately
isort langextract tests --profile google --line-length 80
pyink langextract tests --config pyproject.toml
```

### Pre-commit Hooks

For automatic formatting checks:
```bash
pre-commit install  # One-time setup
pre-commit run --all-files  # Manual run
```

### Linting

Run linting before submitting PRs:

```bash
pylint --rcfile=.pylintrc langextract tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development guidelines.

## Disclaimer

This is not an officially supported Google product. If you use
LangExtract in production or publications, please cite accordingly and
acknowledge usage. Use is subject to the [Apache 2.0 License](https://github.com/google/langextract/blob/main/LICENSE).
For health-related applications, use of LangExtract is also subject to the
[Health AI Developer Foundations Terms of Use](https://developers.google.com/health-ai-developer-foundations/terms).

---

**Happy Extracting!**
<<<<<<< HEAD

# lxRunnerExtraction: Rich Schema Extraction Runner

This document walks through `lxRunnerExtraction.py` step by step. It explains the purpose, configuration, input discovery, model invocation, normalization, enrichment, and outputs. Use it as a companion while reading the code.

## What this runner is

A development harness that:
- Invokes the model (OpenRouter OpenAI-compatible by default) with a single authoritative prompt file and optional few-shot examples.
- Normalizes legacy classed extractions into a single "rich schema" JSON object.
- Deduplicates by content, validates structure, optionally enriches relationships in teach mode, and saves outputs under `output_runs/<RUN_ID>/`.

It’s designed for iterative work and tracing. For batch/production pipelines (chunked PDFs, ID registries, dedup across runs), build specialized scripts on top.

## High-level flow

1) Load environment and provider registry.
2) Resolve which provider to use (OpenRouter vs direct Gemini) and set the model config.
3) Load the prompt, examples, and input text.
4) Optionally inject teaching appendices and known field paths.
5) Call `lx.extract(...)` with strict JSON preference and resolver options.
6) Convert any legacy classed results to a single rich-schema object with de-dup.
7) Validate and optionally enrich.
8) Persist outputs (root JSON and glossary) and print a concise summary.

## Configuration inputs

The sole entry point is the function `makeRun(...)`:

- `RUN_ID`: Output folder name under `output_runs/`.
- `MODEL_ID`: Requested model id (overridden internally; see note below).
- `MODEL_TEMPERATURE`: Requested temperature (overridden internally; see note below).
- `MAX_NORMS_PER_5K`: Soft cap marker stored in metadata (not enforced client-side here).
- `MAX_CHAR_BUFFER`: Governs internal library chunking of the input text.
- `EXTRACTION_PASSES`: Number of passes to improve recall.
- `INPUT_PROMPTFILE`: Path to the primary prompt file (required).
- `INPUT_GLOSSARYFILE`: Output path for the DSL glossary stub (or default under run dir).
- `INPUT_EXAMPLESFILE`: Python file exporting `EXAMPLES` list for few-shot.
- `INPUT_SEMANTCSFILE`: Reserved for future use (accepted, not currently consumed).
- `INPUT_TEACHFILE`: Reserved for future use (accepted, not currently consumed).

Environment variables:
- `USE_OPENROUTER` (default "1"): if truthy, uses OpenRouter OpenAI-compatible route; else direct Gemini.
- `OPENAI_API_KEY`: used as OpenRouter API key when `USE_OPENROUTER=1`.
- `GOOGLE_API_KEY`: used for direct Gemini path when `USE_OPENROUTER=0`.
- `OPENROUTER_REFERER`, `OPENROUTER_TITLE`: optional attribution headers for OpenRouter.
- `LE_INPUT_FILE`: absolute/relative path to the input `.txt`/`.md` file; if not set, runner searches `output_runs/<RUN_ID>/input/`.
- `LX_TEACH_MODE=1`: appends teaching appendices and enables relationship inference in enrichment.
- `LX_WRITE_VIS=1`: writes a simple HTML visualization for the annotated document.

Notes on overrides:
- The runner currently overrides `MODEL_ID` and `MODEL_TEMPERATURE` internally:
  - `MODEL_ID` -> `google/gemini-2.5-flash` when using OpenRouter; `gemini-2.5-flash` when direct.
  - `MODEL_TEMPERATURE` -> `0.15`.
  This is intentional for stable runs. Feel free to relax these in the code if you want to honor the function arguments.

## Where files go

- Outputs: `output_runs/<RUN_ID>/output.json` and `output_runs/<RUN_ID>/glossary.json`.
- Optional per-chunk traces: `output_runs/<RUN_ID>/chunks/chunk_*.json`.
- Optional visualization (when `LX_WRITE_VIS=1`): `output_runs/<RUN_ID>/visualization.html`.
- Inputs: if `LE_INPUT_FILE` is not set, the runner searches `output_runs/<RUN_ID>/input/` for text-like files (`.txt`, `.md`), skipping known generated artifacts.

## Step-by-step through the code

### 0) Environment and provider setup
- Loads `.env` via `dotenv`.
- Initializes provider registry: `providers.load_builtins_once()` and `providers.load_plugins_once()` then logs available providers.
- Determines routing:
  - If `USE_OPENROUTER` is truthy, uses the OpenAI-compatible provider against `https://openrouter.ai/api/v1`.
  - Otherwise, calls direct Gemini with `GOOGLE_API_KEY`.

### 1) Resolve paths and inputs
- `PROMPT_FILE` must exist or the run is aborted.
- Determines `run_dir = output_runs/<RUN_ID>` and `chunks_dir` under it.
- Glossary path defaults to `run_dir/glossary.json` when not provided.
- Input file resolution:
  - If `LE_INPUT_FILE` is set, use it.
  - Else, search `run_dir/input/` for suitable files (prefer `.txt`/`.md`).
- Teach-mode appendix files are under `prompts/` and appended when `LX_TEACH_MODE=1`.

### 2) Examples loading
- If `INPUT_EXAMPLESFILE` is provided, the runner imports it dynamically (expects `EXAMPLES`).
- Else it tries `input_examplefiles/default.py`.
- On failure or missing `EXAMPLES`, it proceeds with an empty list and logs a warning.

### 3) Prompt composition and teaching augmentation
- Reads `INPUT_PROMPTFILE` as the base description.
- If `LX_TEACH_MODE=1`, appends `prompts/prompt_appendix_teaching.md` and `prompts/prompt_appendix_entity_semantics.md` when present.
- If a prior glossary file exists, injects the discovered DSL paths between `KNOWN_FIELD_PATHS_START/END` markers to guide the model.

### 4) Model configuration and extract kwargs
- Builds `factory.ModelConfig(...)` with the provider `OpenAILanguageModel` for OpenRouter.
- Provider kwargs include the API key, base URL, temperature, and `FormatType.JSON`.
- Builds `extract_kwargs`:
  - `text_or_documents`: the selected input text
  - `prompt_description`: composed prompt
  - `examples`: the few-shot list
  - `config`: the model config above
  - `fence_output=False`, `use_schema_constraints=False`: rely on JSON mode and a tolerant resolver
  - `max_char_buffer`: for library-managed chunking
  - `extraction_passes`: number of passes
  - `resolver_params`: JSON format preference and alignment limited to classes ["Norm", "Tag", "Parameter"].

### 5) Calling the model and capturing results
- `_call_and_capture(text, idx)`:
  - Invokes `lx.extract(**extract_kwargs)`.
  - On exception: logs a redacted message, synthesizes a minimal rich object, and saves a chunk trace so the run completes.
  - On success: reads the legacy `annotated.extractions` list and converts it into a single rich-schema object.

### 6) Normalization and de-duplication
- For each classed list (`norms`, `tags`, `locations`, `questions`, `consequences`, `parameters`):
  - Compute content-based signatures (e.g., norm identity uses statement/applies/satisfied/exempt/obligation/relevant_tags).
  - Drop duplicates by signature.
- Populate `window_config.debug_counts` with pre/post numbers for traceability.
- Persist per-chunk JSON under `chunks/`.
- Optional visualization (`LX_WRITE_VIS=1`) by calling `lx.visualize(annotated)`.

### 7) Validation, enrichment, and persistence
- Assembles the root: `{"extractions": [ rich_object ]}`.
- Validates structure via `pp_schema.is_rich_schema()` and `pp_schema.validate_rich()`; collects errors/warnings under `quality`.
- Updates `window_config` counts.
- If `LX_TEACH_MODE=1`: runs enrichment steps (`enrich_parameters`, `merge_duplicate_tags`, `autophrase_questions`, and `infer_relationships`).
- Writes `output.json` and a DSL `glossary.json` draft (all discovered DSL keys set to empty strings as placeholders).
- Prints a one-line summary with counts of each entity type plus errors/warnings.

## Things to know and adjust

- The runner forces a specific model and temperature for stability. If you need full external control, remove those overrides.
- The cap `MAX_NORMS_PER_5K` is tracked in metadata but not enforced; add a cap step if you want hard limits.
- Output JSON is a single rich object per run. If you want multiple windows/segments, call `_call_and_capture` repeatedly and aggregate.
- The resolver currently aligns extraction_text only for classes `["Norm", "Tag", "Parameter"]`. Expand if needed.

## How to run it

Interactive example (PowerShell):

```powershell
$runId = [string][int][double]::Parse((Get-Date -UFormat %s))
$env:USE_OPENROUTER = "1"
$env:OPENAI_API_KEY = "<your_openrouter_key>"
$env:LE_INPUT_FILE = "path\to\your\input.txt"

python - << 'PY'
import time
from pathlib import Path
from lxRunnerExtraction import makeRun

RUN_ID = str(int(time.time()))
makeRun(
    RUN_ID=RUN_ID,
    MODEL_ID="ignored-by-runner",
    MODEL_TEMPERATURE=0.0,
    MAX_NORMS_PER_5K=10,
    MAX_CHAR_BUFFER=5000,
    EXTRACTION_PASSES=2,
    INPUT_PROMPTFILE=str(Path("prompts/extraction_prompt.md")),
    INPUT_GLOSSARYFILE="",              # let runner default to output_runs/<RUN_ID>/glossary.json
    INPUT_EXAMPLESFILE=str(Path("input_examplefiles/examples_enhanced_updated_V2.py")),
    INPUT_SEMANTCSFILE="",              # reserved
    INPUT_TEACHFILE="",                 # reserved
)
PY
```

Outputs will land in `output_runs/<RUN_ID>/`.

## FAQ

- Can I use direct Gemini? Set `USE_OPENROUTER=0` and provide `GOOGLE_API_KEY`.
- How do I change the model? Remove the internal overrides (`MODEL_ID`, `MODEL_TEMPERATURE`) and pass your choices to `makeRun`.
- Why do I see synthesized outputs? Errors are trapped so a run always produces a well-formed root. Check `quality.errors` and per-chunk JSON under `chunks/`.
=======
>>>>>>> upstream/main
