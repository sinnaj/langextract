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

## Try it
- Pick or type a `MODEL_ID` (badges show last used models).
- Adjust `MODEL_TEMPERATURE` and `MAX_NORMS_PER_5K` if needed.
- Choose input files from the dropdowns (populated from `input_*` folders). Leave as `None` to skip.
- Optionally upload an `input_document` (saved to `output_runs/<RUN_ID>/input/`).
- Click `Start Run` to begin. Live logs stream in the console; stats appear automatically. When the run finishes, the right side lists all files for quick preview/download.

Notes:
- If `extractionExperiment.makeRun(...)` is not available, the runner uses a small dummy simulation and still writes `stats.json`. To wire your actual function, implement `makeRun(RUN_ID, MODEL_ID, MODEL_TEMPERATURE, MAX_NORMS_PER_5K, INPUT_PROMPTFILE, INPUT_GLOSSARYFILE, INPUT_EXAMPLESFILE, INPUT_SEMANTCSFILE, INPUT_TEACHFILE)` in `extractionExperiment.py`.
- The app persists `run_input.json`, `run.log`, `stats.json` (if provided), and any outputs under `output_runs/<RUN_ID>/`.
