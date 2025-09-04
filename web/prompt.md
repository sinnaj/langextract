READ THE PLAN IN ITS ENTIRETY AND DRAW YOUR NEXT ACTIONS FROM IT. WHENEVER YOU FINISH A TASK, REPORT BACK, UPDATE THE TASKLIST OF THIS PLAN AND SEQUENTIALLY MOVE ON TO THE NEXT TASK/TOPIC:

Tasklist (single-use workshop build)
1) Scaffold files: `web/app.py`, `web/templates/index.html` (Tailwind via CDN), `web/static/app.js`, `web/requirements.txt`, `web/runner.py`, `web/README.md`
2) Implement endpoints: `GET /`, `GET /choices`, `POST /run` (multipart with `input_document`), SSE `GET /runs/<run_id>/logs`, `GET /runs/<run_id>/status`, `GET /runs/<run_id>/files`, `GET /runs/<run_id>/file`
3) Implement form UI with structured fields and badges; wire Tailwind; submit as multipart; show live logs, stats, files, and preview
4) Read dropdown options from input folders; manage model badges via `web/pastmodels.json` (create/update, dedupe, keep last 10)
5) On submit: generate `RUN_ID`, write `run_input.json`, save optional `input_document` to `output_runs/<run_id>/input/`, start run, stream logs
6) Call `extractionExperiment.makeRun(...)` with typed params; set `LE_RUN_DIR`; capture `STATS:` line or `stats.json`
7) Produce `web/README.md` with Windows PowerShell steps; quick smoke test

Build a tiny, single-page workshop web app in `/web/` that launches a Python run with a given config, streams live logs, and shows outputs and statistics after completion. Keep it simple and pragmatic for a one-time internal workshop.

The web app must call `extractionExperiment.py` function `makeRun(...)` with the following exact signature and typed parameters:

```
makeRun(
		RUN_ID: str,
		MODEL_ID: str,
		MODEL_TEMPERATURE: float,
		MAX_NORMS_PER_5K: int,
		INPUT_PROMPTFILE: str,
		INPUT_GLOSSARYFILE: str,
		INPUT_EXAMPLESFILE: str,
		INPUT_SEMANTCSFILE: str,
		INPUT_TEACHFILE: str,
)
```
 Serve one page that lets a user submit a configuration via structured fields and start a run.
 On submit, generate a run-id (UNIX timestamp), persist the submitted config as `/output_runs/{run-id}/run_input.json` (the JSON reflects the above `makeRun` parameters), and execute `makeRun(...)` with those values.
 Use Server-Sent Events (SSE) for live log streaming; avoid WebSockets to keep it simple. Use Tailwind CSS via CDN (`https://cdn.tailwindcss.com`) for styling; no CSS build step.
 The run function is `makeRun(...)` as defined above and lives in `extractionExperiment.py` at repo root. The app should import and call it directly. If `extractionExperiment.py` is not present, provide a fallback dummy runner so the web app remains demoable.
 Client script (`web/static/app.js`): handles form submit (multipart), SSE logs, status/files fetching, preview rendering, and model badge interactions.
 Config input: structured fields mapped 1:1 to `makeRun` parameters (see UI below). Validate types client-side and server-side.
## Endpoints
 `GET /choices` -> returns dropdown options gathered from the input folders (see below) and `web/pastmodels.json` (created if missing).
 `POST /run` -> accepts `multipart/form-data` with the structured fields below and an optional file input named `input_document`:
	```json
	{
		"MODEL_ID": "string",
		"MODEL_TEMPERATURE": 0.15,
		"MAX_NORMS_PER_5K": 10,
		"INPUT_PROMPTFILE": "" | "filename.ext",
		"INPUT_GLOSSARYFILE": "" | "filename.ext",
		"INPUT_EXAMPLESFILE": "" | "filename.ext",
		"INPUT_SEMANTCSFILE": "" | "filename.ext",
		"INPUT_TEACHFILE": "" | "filename.ext"
	}
	```
	- Server generates `RUN_ID` (UNIX timestamp), creates run folder, writes `run_input.json` with all parameters including `RUN_ID`, saves the uploaded file (if provided) to `/output_runs/{run_id}/input/{original_filename}`, calls `runner.py` to launch a worker that calls `makeRun(...)`, and returns `{ run_id }`.

 `GET /runs/<run_id>/logs` -> SSE stream of log lines. Each event is a JSON payload: `{ line: string, run_id, ts }`. Send a final event `{ event: 'complete', status, code }` when the run ends.
 `GET /runs/<run_id>/status` -> JSON `{ status, started_at, ended_at?, stats? }`.
 `GET /runs/<run_id>/files` -> JSON array of files under the run folder with relative paths and sizes.
 `GET /runs/<run_id>/file?path=<relative>` -> serves the file for preview/download. For preview, if MIME type is text or JSON and size < 1MB, return inline; otherwise, force download.
 `GET /runs` -> optional list of recent runs based on folder names in `output_runs`.

 - Form fields and defaults:
	 - `MODEL_ID` (text input) with clickable badges rendered from `web/pastmodels.json` (most recent first) to prefill the input on click. On successful run, the chosen model id is appended/updated in `web/pastmodels.json` (dedupe; keep up to 10).
	- `MODEL_TEMPERATURE` (number input) default `0.15`.
	- `MAX_NORMS_PER_5K` (number input) default `10`.
	- `INPUT_PROMPTFILE` (dropdown) options: `None` plus all filenames discovered in `/input_promptfiles`.
	- `INPUT_GLOSSARYFILE` (dropdown) options: `None` plus all filenames in `/input_glossaryfiles`.
	- `INPUT_EXAMPLESFILE` (dropdown) options: `None` plus all filenames in `/input_examplefiles`.
	- `INPUT_SEMANTCSFILE` (dropdown) options: `None` plus all filenames in `/input_semanticsfiles`.
	- `INPUT_TEACHFILE` (dropdown) options: `None` plus all filenames in `/input_teachfiles`.
	- For each dropdown, selecting `None` maps to empty string `""` in the payload.
	- On submit: call `POST /run` with the structured payload; receive `run_id`, then:
 - `web/static/app.js`: Client logic for form submit, SSE log streaming, fetching status/files, and preview rendering.
 - Invalid types or out-of-range values -> return 400 with message; show inline near fields.
- `web/runner.py`: Subprocess wrapper that launches the target run and bridges stdout to the web app, extracts stats, and ensures outputs go to `/output_runs/{run-id}/`.
- `web/requirements.txt`: `flask` plus anything else required (keep minimal).
 Create an empty `output_runs` folder if missing. Ensure the following input folders exist at repo root (case-sensitive as shown):
 - `input_promptfiles/`
 - `input_glossaryfiles/`
 - `input_examplefiles/`
 - `input_semanticsfiles/`
 - `input_teachfiles/`
- `web/README.md`: How to set up and run on Windows PowerShell.
 Runner must pass the run folder path to the target via an environment variable `LE_RUN_DIR` so the target can write outputs there. It must call `makeRun` with the typed parameters in the order shown above.

## Architecture (minimal)
- Root paths:
	- Determine repo root as `Path(__file__).resolve().parents[1]`.
	- `OUTPUT_ROOT = repo_root / 'output_runs'`.
- Run-id: `str(int(time.time()))`.
- Config input: structured fields (no JSON textarea). Validate types client-side and server-side.
- When a run starts:
	1. Create folder `OUTPUT_ROOT / run_id`.
	2. Write `run_input.json` there with the submitted JSON config.
	3. If a file was uploaded via `input_document`, create subfolder `input/` and save the file as `OUTPUT_ROOT / run_id / input / {original_filename}`.
	4. Start the run via `runner.py` which imports `extractionExperiment.makeRun` and calls it with the typed parameters.
	5. Keep a per-run state in memory: status (`running|finished|error`), start/end times, path to log file, last N lines ring buffer, and optional `stats` dict once available.

### Runner details (`web/runner.py`)
- Responsibility: invoke the target script so that:
	- All stdout/stderr lines are immediately flushed (use `-u` for unbuffered Python) and can be streamed by the Flask app.
	- Outputs are written to `OUTPUT_ROOT / run_id`.
	- Statistics are communicated back to the web app.
- Invocation model:
	- Import `extractionExperiment` from repo root, resolve `makeRun` and call it with the parameters in order (`RUN_ID`, `MODEL_ID`, `MODEL_TEMPERATURE`, `MAX_NORMS_PER_5K`, `INPUT_PROMPTFILE`, `INPUT_GLOSSARYFILE`, `INPUT_EXAMPLESFILE`, `INPUT_SEMANTCSFILE`, `INPUT_TEACHFILE`).
	- Ensure `PYTHONPATH` includes repo root; set env var `LE_RUN_DIR` to the run folder. Set current working directory to repo root or run folder as appropriate.
	- Fallback if import fails: simulate a short run that prints logs, writes `stats.json`, and creates files.
- Statistics contract:
	- Primary: the target prints a single line prefixed with `STATS:` followed by a JSON object (e.g., `STATS: {"duration": 5.2, ...}`). Runner captures and forwards this to the app.
	- Fallback: if no prefixed line is seen, the runner looks for `stats.json` in the run folder when the process ends.

## Front-end behavior (`index.html` + `app.js`)
 - Layout: left main area for form and live console; right sidebar for files/preview and stats. Use Tailwind utility classes for spacing and typography.
 - Form fields and defaults:
 	- `MODEL_ID` (text input) with clickable badges rendered from `pastmodels.json` (most recent first) to prefill the input on click. On successful run, the chosen model id is appended/updated in `pastmodels.json` (dedupe; keep up to 10).
 	- `MODEL_TEMPERATURE` (number input) default `0.15`.
 	- `MAX_NORMS_PER_5K` (number input) default `10`.
 	- `INPUT_PROMPTFILE`, `INPUT_GLOSSARYFILE`, `INPUT_EXAMPLESFILE`, `INPUT_SEMANTCSFILE`, `INPUT_TEACHFILE` (dropdowns). Options: `None` + filenames from their folders. `None` -> empty string in payload.
	- `input_document` (file input) optional; accept any file type (likely md/txt/pdf). The server will store it under `/output_runs/{run_id}/input/{filename}`.
 	- On submit: call `POST /run`, receive `run_id`, then open SSE `/runs/<run_id>/logs`, poll `/runs/<run_id>/status` until finished, then fetch `/runs/<run_id>/files` and render clickable list. Clicking previews via `/runs/<run_id>/file?path=...`.
 - Preview:
 	- If content-type is `text/*` or `application/json` and size < 1MB, render text in a pre block (pretty-print JSON where applicable). Otherwise show a download link.

## Error Handling (simple for workshop)
 - Invalid types or out-of-range values -> return 400 with message; show inline near fields.
 - Target script missing or crashes -> mark run status `error`, stream stderr lines; surface non-zero exit code in UI.
 - Large outputs -> write logs to `output_runs/<run_id>/run.log`; no replay buffer.

## Notes on Scope
 - One-time internal workshop tool. Skip authentication and advanced security/architecture. Focus on a working single page and live logs.

## Implementation Notes
 - Use `subprocess.Popen([...], stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)` and ensure unbuffered Python via `-u` when invoking Python targets for immediate stdout flush.
 - Use a background thread per run to read lines and stream via SSE; also append to `run.log` in the run folder. Persist a minimal `run_meta.json`.

## Acceptance Criteria
- Starting a run creates `output_runs/<run_id>/run_input.json` with the submitted JSON and starts the target.
- If a file is uploaded in `input_document`, it is saved to `output_runs/<run_id>/input/{original_filename}` before the run starts.
- While running, the UI shows new console output within <= 1s of emission.
- When the run ends, the UI shows status and statistics (from `STATS:` line or `stats.json`).
- The sidebar lists all files present in `output_runs/<run_id>/` and clicking shows a preview for text/JSON files; binaries download.
- Works on Windows PowerShell and POSIX shells; paths handled via `pathlib`.

## —

## Setup and Run (Windows PowerShell)
Add these run instructions to `web/README.md` and ensure they work locally:

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r web/requirements.txt
$env:PYTHONPATH = (Get-Location)
python web/app.py
```

Then open `http://127.0.0.1:5000/` in the browser. For development, ensure `output_runs/` exists at the repository root; if not, create it.
 Tailwind is loaded via CDN in the HTML template; no additional CSS build step is needed.

## Configuring the Target Script
- Default target is `extractionExperiment.py` at repo root.
- If you implement the optional demo, allow overriding via env var `LE_TARGET=web/dummy_target.py` or a config in `app.py`.
- Runner should pass the run folder path to the target via an environment variable `LE_RUN_DIR` and/or arguments `--run-dir` so the target can write outputs there.

## Testing
- Include a dummy run path (if enabled) that completes within ~5–10 seconds, writes a `stats.json` like `{ "ok": true, "items": 3 }`, and creates two small text files to showcase preview.
- Manual smoke test steps should be documented in `web/README.md`.

## Out of Scope
- Authentication, multi-user separation, and SSL termination are not required.
- No JavaScript frameworks; keep plain JS to minimize dependencies.

Implement the above in the specified files and ensure the app runs end-to-end with live logs, stats, and file previews.
