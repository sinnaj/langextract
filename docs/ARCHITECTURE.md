# LangExtract architecture overview

This document summarizes the main components in this repository, what each script/module does, and how they work together during an extraction run. Use it as a quick reference when making changes.

## High-level flow

- Web UI (browser) submits a run request with model settings and file choices
- Flask app (`web/app.py`) persists the request in `output_runs/<run_id>/run_input.json` and spawns a worker
- Runner (`web/runner.py`) launches `web/runner_worker.py` with a JSON payload and streams logs back over Server-Sent Events (SSE)
- Worker imports and calls `makeRun` from `lxRunnerExtraction.py`
- `makeRun` orchestrates model invocation via the `langextract` library, validates/coerces outputs, enriches, and writes results to `output_runs/<run_id>`
- Web UI polls status and lists/preview files in the run folder

## Web application (workshop runner)

- `web/app.py` (Flask)
  - Endpoints
    - `GET /` serves the form UI (templates/index.html)
    - `GET /choices` lists available prompt/examples/etc. files for dropdowns
    - `POST /run` starts a run, writes `run_input.json`, spawns the worker
    - `GET /runs/<run_id>/logs` streams live logs via SSE (with keepalive and a 1h safety timeout)
    - `GET /runs/<run_id>/status` provides current process status and last known stats
    - `GET /runs/<run_id>/files` enumerates files in the specific run directory
    - `GET /runs/<run_id>/file?path=...` downloads or previews files (includes Windows-locked file handling: returns HTTP 423 with Retry-After when locked)
  - Single-instance protection: a lock file in `output_runs/.web_app.lock` prevents accidental double-starts
  - Robustness:
    - SSE: tolerate disconnects, send keepalives, emit final complete/error payloads
    - Preview: truncation and UTF-8 replacement for large/binary-ish files; proactive readability checks avoid hangs on locked files

- `web/templates/index.html`
  - Form fields for: `MODEL_ID`, `MODEL_TEMPERATURE`, `MAX_NORMS_PER_5K`
  - Also exposes extraction knobs: `MAX_CHAR_BUFFER` (internal chunk size) and `EXTRACTION_PASSES`
  - Selects for prompt/glossary/examples/semantics/teach files and an optional uploaded document
  - Right-hand preview area renders JSON/text/markdown and supports quick file switching

- `web/static/app.js`
  - Manages form persistence (localStorage) and submits form via `FormData`
  - Connects to SSE logs, updates a console pane, polls status endpoint until completion
  - Loads file list after completion and renders an inline preview for text/JSON/markdown files

- `web/runner.py`
  - `Runner` launches a subprocess for the worker and streams its combined stdout/stderr to both disk (`run.log`) and an in-memory ring buffer (sent to clients via SSE)
  - Keeps last `MAX_BUFFER_LINES` lines in memory; tracks lines dropped for clients connecting late
  - Parses `STATS: { ... }` lines to surface structured stats on `/status`
  - `build_worker_cmd(...)` prepares the worker invocation and environment

- `web/runner_worker.py`
  - Receives a JSON payload (run_id + settings)
  - Imports `lxRunnerExtraction.py` dynamically and calls `makeRun(...)` with arguments mapped from the payload
  - If missing, runs a dummy simulation so the UI experience stays intact

## Extraction runner (orchestrator)

- `lxRunnerExtraction.py`
  - Entry: `makeRun(RUN_ID, MODEL_ID, MODEL_TEMPERATURE, MAX_NORMS_PER_5K, MAX_CHAR_BUFFER, EXTRACTION_PASSES, INPUT_PROMPTFILE, INPUT_GLOSSARYFILE, INPUT_EXAMPLESFILE, INPUT_SEMANTCSFILE, INPUT_TEACHFILE)`
  - Loads environment (keys) and providers; prints a provider list for diagnostics
  - Selects the input text file from `output_runs/<run_id>/input` (or uses `LE_INPUT_FILE` env var)
  - Reads the prompt description and optionally appends teaching/semantics content when `LX_TEACH_MODE=1`
  - Loads few-shot examples from a Python module exporting `EXAMPLES` (either the selected examples file or `input_examplefiles/default.py`)
  - Builds a `factory.ModelConfig` for the language model
    - Default route is OpenRouter using the OpenAI-compatible provider (`OpenAILanguageModel`)
    - Respects `MODEL_TEMPERATURE`
  - Defines `extract_kwargs` for `langextract.extract(...)`
    - Uses knobs from the UI: `max_char_buffer`, `extraction_passes`
    - Turns off fences and strict schema constraints for this path
    - Configures the resolver: JSON format, suppressed parse errors by default, and alignment targeted only to `extraction_text` of `Norm`, `Tag`, and `Parameter`
  - Invokes `langextract.extract(...)` with the input text
    - On failure: logs a warning, synthesizes a minimal rich-schema object, and continues (never aborts a run)
    - On success: consumes `annotated.extractions` (legacy/classed items) and synthesizes a single rich-schema object
      - Accumulates/deduplicates across legacy lists by id
      - Writes a per-chunk raw JSON snapshot into `output_runs/<run_id>/chunks/`
  - Validation and enrichment
    - Validates the synthesized object with `postprocessing/output_schema_validation.py` and adds errors into `quality`
    - Optional enrichment (when `LX_TEACH_MODE=1`): parameter enrichment, duplicate-tag merging, relationship inference
    - Builds a DSL glossary stub from keys observed in the output
  - Outputs
    - `output_runs/<run_id>/output.json` (root `{ "extractions": [ ... ] }` shape)
    - `output_runs/<run_id>/glossary.json` (DSL keys → empty strings)
    - `output_runs/<run_id>/chunks/chunk_single.json` (raw per-chunk snapshot)
    - `output_runs/<run_id>/run.log` (from the process/stdout)
    - Optional `visualization.html` when `LX_WRITE_VIS=1`
  - Metadata/window config
    - `window_config` reflects: `input_chars`, `max_norms_per_5k_tokens`, `max_char_buffer`, `extraction_passes`, `extracted_norm_count`

## Core library (langextract)

- Package root: `langextract/`
  - `extraction.py` and `inference.py` expose the main `extract(...)` path used by the runner
  - `resolver.py` parses, coerces, and aligns model outputs
    - Robust parsing: strict JSON → YAML → sanitized JSON
    - Coercion: normalizes various malformed/legacy shapes to `{ "extractions": [ { norms, tags, locations, questions, consequences, parameters, quality } ] }`
    - Alignment: only aligns `extraction_text` for `Norm`, `Tag`, and `Parameter` (attributes are not aligned); JSON-like texts are skipped to avoid mangling
  - `factory.py` builds model configs used by providers
  - `providers/` contains provider implementations and routing
    - `openai.py` (OpenAI-compatible client, used for OpenRouter)
    - `gemini.py` (direct Gemini access)
    - `ollama.py` (local inference)
    - `router.py` combines provider selection logic
  - `core/` contains the stable schema and types used across the library
    - `core/schema.py` defines `EXTRACTIONS_KEY`, base classes, and typed structures
  - `schema.py` at package root is a compatibility shim that re-exports items from `core.schema` (emits deprecation warnings)
  - Other notable modules: `chunking.py` (windowing), `tokenizer.py`, `prompting.py`, `visualization.py`, `progress.py`, `data.py`, `data_lib.py`

## Configuration knobs and environment

- Form/UI
  - `MODEL_ID`, `MODEL_TEMPERATURE`
  - `MAX_NORMS_PER_5K` (cap used for summarization goals and metrics)
  - `MAX_CHAR_BUFFER` (approximate per-pass text size; enables internal chunking)
  - `EXTRACTION_PASSES` (number of model passes to improve recall)
  - `INPUT_PROMPTFILE`, `INPUT_GLOSSARYFILE`, `INPUT_EXAMPLESFILE`, `INPUT_SEMANTCSFILE`, `INPUT_TEACHFILE`
- Environment variables
  - `USE_OPENROUTER` (default true) toggles OpenRouter vs direct Gemini
  - `OPENAI_API_KEY` (used as OpenRouter key)
  - `GOOGLE_API_KEY` (for direct Gemini path)
  - `LE_INPUT_FILE` (optional path override for the input document)
  - `LX_TEACH_MODE` (append teaching/semantics prompt content; enables extra enrichments)
  - `LX_WRITE_VIS` (write visualization HTML)

## Output structure (summary)

- Root: `{ "extractions": [ <extraction_object>, ... ] }`
- Each extraction object (single in this runner) includes:
  - `norms[]`, `tags[]`, `locations[]`, `questions[]`, `consequences[]`, `parameters[]`
  - `quality: { errors[], warnings[], confidence_global, uncertainty_global }`
  - `window_config: { input_chars, max_norms_per_5k_tokens, max_char_buffer, extraction_passes, extracted_norm_count }`
  - Additional metadata (schema/ontology versions, disclaimers, document metadata)

## Error handling and resilience

- Runs never abort due to parse/shape issues; the runner synthesizes a minimal, valid rich object when needed
- Resolver tolerates common malformed outputs and JSON issues
- SSE logging avoids UI hangs and supports partial/late connections
- File preview/download guard against Windows sharing violations
- Logs redact obvious secrets and truncate very long lines

## Typical end-to-end sequence

1) User selects prompt/examples and uploads a document (optional)
2) Clicks Start Run → `/run` persists inputs, spawns worker
3) SSE console streams logs while the run proceeds
4) `makeRun` invokes the LLM via `langextract.extract(...)` and writes outputs
5) Status flips to finished; UI shows file badges and opens `output.json` preview

---

Tips:
- If you change `makeRun` parameters, update `web/runner_worker.py` and `web/app.py` to match.
- The alignment scope and parse tolerance live in `resolver_params` inside `lxRunnerExtraction.py` → adjust carefully.
- For bigger documents, increase `MAX_CHAR_BUFFER` or `EXTRACTION_PASSES` to trade latency for recall.
