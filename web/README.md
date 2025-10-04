# Arqio Extraction Workshop Web Runner

Lightweight Flask web UI to launch Arqio Extraction runs, stream logs live, and preview outputs (JSON, Markdown, logs, etc.).

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r web/requirements.txt
$env:PYTHONPATH = (Get-Location)
python web/app.py
```

Open `http://127.0.0.1:5000/`. The app stores outputs under `output_runs/` at repo root.

Tailwind CSS is loaded at runtime; there is no separate build step.

## Database Configuration (Required for Sandbox)

**Important**: The Sandbox feature now requires a PostgreSQL database. There is no fallback to file-based data.

### Setup Steps

1. **Install dependencies** (if not already done):
```bash
pip install -r web/requirements.txt
```

This installs Flask, SQLAlchemy, and psycopg (PostgreSQL driver).

2. **Create the database**:
```bash
createdb mydb
```

3. **Run the schema**:
```bash
psql -d mydb -f db/schema.sql
```

4. **Set the DATABASE_URL** environment variable:

```bash
# Linux/Mac
export DATABASE_URL="postgresql://localhost:5432/mydb"

# Windows PowerShell
$env:DATABASE_URL = "postgresql://localhost:5432/mydb"
```

Or add it to a `.env` file in the repository root:
```
DATABASE_URL=postgresql://localhost:5432/mydb
```

5. **Ingest norms** (optional - to have data to view):
```bash
python -m ingest.ingest \
  --dsn postgresql://localhost:5432/mydb \
  --json ./sample_norms.json \
  --document-title "My Document"
```

### Troubleshooting

If you see errors like "Database not available" or "SQLAlchemy not installed":

1. Make sure you've installed the requirements: `pip install -r web/requirements.txt`
2. Verify the DATABASE_URL is set: `echo $DATABASE_URL` (Linux/Mac) or `$env:DATABASE_URL` (PowerShell)
3. Check that PostgreSQL is running: `psql -d mydb -c "SELECT 1"`
4. Verify the schema is loaded: `psql -d mydb -c "\dt"`

The Sandbox will show HTTP 503 errors if the database is not properly configured.

## Features
- Start/cancel runs with a simple form. Recent `MODEL_ID`s appear as quick badges.
- Live console via SSE with word-wrap toggle and max-line setting.
- Stats auto-refresh while the run is active.
- File browser badges for each run’s outputs; click to preview inline or download when binary/large.
- Preview panel supports:
	- JSON: collapsible tree rendering (fully expanded by default) and syntax highlighting
	- JSONL/NDJSON: renders first lines as individual collapsible JSON blocks
	- Markdown: rendered via Markdown parser with GitHub-like styling and highlighted code blocks
	- Plain text/logs and common text formats
- Multi-panel preview: hide the left input panel to switch to 1/2/3 side-by-side preview columns.
	- Panels 2 and 3 are display-only (no collapse/folder controls) and follow panel 1’s selected run.
- Search within each panel with inline highlight of matches.
- Single-instance lock and graceful shutdown; active runs are canceled on exit.

## Using the UI
1) Pick or type a `MODEL_ID` (recent ones appear as badges).
2) Adjust `MODEL_TEMPERATURE`, `MAX_NORMS_PER_5K`, buffer/passes as needed.
3) Choose input files from the dropdowns (populated from `input_*`); leave as `None` to skip.
4) Optionally upload an input document (stored under `output_runs/<RUN_ID>/input/`).
5) Click `Start Run` to begin. Logs stream live; stats update periodically.
6) When finished, click file badges to preview results on the right. Use the folder icon in the first panel to load previous runs (this selection syncs to other panels).
7) Use the search icon in a panel to highlight text matches.

## Offline/No-CDN Environments

Some environments block external CDNs. The UI references a few JS/CSS libraries (Tailwind CDN runtime, Highlight.js, Marked, DOMPurify, JSON Formatter, GitHub Markdown CSS). To remain functional offline or with blocked CDNs:

- On startup, the Flask app attempts to download and cache local copies of these assets into `web/static/vendor/` (best-effort; startup never fails on download errors).
- The HTML uses robust fallbacks:
	- `onerror` attributes switch `<script>`/`<link>` to local paths if the CDN fails.
	- A runtime check verifies globals (`hljs`, `marked`, `DOMPurify`, `JSONFormatter`) and swaps to local copies if needed. It also swaps Highlight.js CSS to local versions if stylesheets are blocked.

Cached paths:

- `/static/vendor/tailwindcss.js`
- `/static/vendor/highlightjs/common.min.js`
- `/static/vendor/highlightjs/github.min.css`
- `/static/vendor/highlightjs/github-dark.min.css`
- `/static/vendor/marked/marked.min.js`
- `/static/vendor/dompurify/purify.min.js`
- `/static/vendor/json-formatter/json-formatter.umd.js`
- `/static/vendor/json-formatter/json-formatter.css`
- `/static/vendor/github-markdown.min.css`

If your environment is fully offline, you can pre-populate these files manually in the same locations before running the server. The app will use local versions automatically.

## Notes & Internals
- The app writes a small lock file to `output_runs/.web_app.lock` and refuses to start if another instance is already serving on the same port (`127.0.0.1:5000`). Stale locks are auto-removed when the port is not in use.
- The server provides endpoints to list runs, stream logs via SSE, check status, enumerate files, and fetch preview/downloads. For large text, a preview mode returns a truncated chunk to keep the UI responsive.
- Outputs are stored under `output_runs/<RUN_ID>/` including `run_input.json`, logs, and generated artifacts.
