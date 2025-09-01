# LangExtract Workshop Web Runner

Quick internal tool to launch `extractionExperiment.makeRun(...)`, stream logs, and view outputs.

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r web/requirements.txt
$env:PYTHONPATH = (Get-Location)
python web/app.py
```

Open http://127.0.0.1:5000/ and ensure `output_runs/` exists at repo root.

Tailwind CSS is loaded via CDN; no build step needed.

## Offline/No-CDN Environments

Some environments block external CDNs. The UI references a few JS/CSS libraries (Tailwind CDN runtime, Highlight.js, Marked, DOMPurify). To remain functional offline or with blocked CDNs:

- On startup, the Flask app attempts to download and cache local copies of these assets into `web/static/vendor/`.
- The HTML uses robust fallbacks:
	- `onerror` attributes switch `<script>`/`<link>` to local paths if the CDN fails to load.
	- A small runtime check verifies globals (`hljs`, `marked`, `DOMPurify`) and loads local scripts if needed. It also swaps Highlight.js CSS to local copies if the stylesheet is blocked.

Cached paths:

- `/static/vendor/tailwindcss.js`
- `/static/vendor/highlightjs/common.min.js`
- `/static/vendor/highlightjs/github.min.css`
- `/static/vendor/highlightjs/github-dark.min.css`
- `/static/vendor/marked/marked.min.js`
- `/static/vendor/dompurify/purify.min.js`

If your environment is fully offline, you can pre-populate these files manually in the same locations before running the server. The app will use local versions automatically.

## Try it
- Pick or type a `MODEL_ID` (badges show last used models).
- Adjust `MODEL_TEMPERATURE` and `MAX_NORMS_PER_5K` if needed.
- Choose input files from the dropdowns (populated from `input_*` folders). Leave as `None` to skip.
- Optionally upload an `input_document` (saved to `output_runs/<RUN_ID>/input/`).
- Click `Start Run` to begin. Live logs stream in the console; stats appear automatically. When the run finishes, the right side lists all files for quick preview/download.

Notes:
- If `extractionExperiment.makeRun(...)` is not available, the runner uses a small dummy simulation and still writes `stats.json`. To wire your actual function, implement `makeRun(RUN_ID, MODEL_ID, MODEL_TEMPERATURE, MAX_NORMS_PER_5K, INPUT_PROMPTFILE, INPUT_GLOSSARYFILE, INPUT_EXAMPLESFILE, INPUT_SEMANTCSFILE, INPUT_TEACHFILE)` in `extractionExperiment.py`.
- The app persists `run_input.json`, `run.log`, `stats.json` (if provided), and any outputs under `output_runs/<RUN_ID>/`.
