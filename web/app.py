from __future__ import annotations
from pathlib import Path
import json
import mimetypes
import time
from typing import Dict, Any
from flask import Flask, render_template, jsonify, request, Response, send_file, abort  # type: ignore

from runner import Runner, build_worker_cmd

app = Flask(__name__, static_folder="static", template_folder="templates")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "output_runs"
OUTPUT_ROOT.mkdir(exist_ok=True)

RUNNERS: Dict[str, Runner] = {}

INPUT_DIRS = {
    "input_promptfiles": REPO_ROOT / "input_promptfiles",
    "input_glossaryfiles": REPO_ROOT / "input_glossaryfiles",
    "input_examplefiles": REPO_ROOT / "input_examplefiles",
    "input_semanticsfiles": REPO_ROOT / "input_semanticsfiles",
    "input_teachfiles": REPO_ROOT / "input_teachfiles",
}

PAST_MODELS_FILE = REPO_ROOT / "web" / "pastmodels.json"

# Ensure input dirs exist
for _k, _p in INPUT_DIRS.items():
    _p.mkdir(parents=True, exist_ok=True)

def _list_rel_files(dir_key: str):
    p = INPUT_DIRS[dir_key]
    if not p.exists() or not p.is_dir():
        return []
    items = []
    for child in sorted(p.iterdir()):
        if child.is_file():
            rel = Path(dir_key) / child.name
            items.append(str(rel).replace("\\", "/"))
    return items

def _load_past_models():
    if PAST_MODELS_FILE.exists():
        try:
            return json.loads(PAST_MODELS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _update_past_models(model_id: str):
    if not model_id:
        return
    models = _load_past_models()
    new_list = [model_id] + [m for m in models if m != model_id]
    new_list = new_list[:10]
    PAST_MODELS_FILE.write_text(json.dumps(new_list, indent=2), encoding="utf-8")

@app.get("/runs")
def list_runs():
    runs = []
    if OUTPUT_ROOT.exists():
        for d in OUTPUT_ROOT.iterdir():
            if d.is_dir():
                try:
                    rid = d.name
                    meta = {}
                    meta_path = d / "run_input.json"
                    if meta_path.exists():
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    ts = d.stat().st_mtime
                    runs.append({"run_id": rid, "mtime": ts, "meta": meta})
                except Exception:
                    continue
    runs.sort(key=lambda x: x["mtime"], reverse=True)
    return jsonify(runs)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/choices")
def choices():
    return jsonify({
        "input_promptfiles": _list_rel_files("input_promptfiles"),
        "input_glossaryfiles": _list_rel_files("input_glossaryfiles"),
        "input_examplefiles": _list_rel_files("input_examplefiles"),
        "input_semanticsfiles": _list_rel_files("input_semanticsfiles"),
        "input_teachfiles": _list_rel_files("input_teachfiles"),
        "pastmodels": _load_past_models(),
    })

@app.post("/run")
def start_run():
    form = request.form
    files = request.files

    # Required/basic fields
    model_id = form.get("MODEL_ID", "").strip()
    model_temperature = form.get("MODEL_TEMPERATURE", "0.15").strip()
    max_norms = form.get("MAX_NORMS_PER_5K", "10").strip()
    input_prompt = form.get("INPUT_PROMPTFILE") or ""
    input_glossary = form.get("INPUT_GLOSSARYFILE") or ""
    input_examples = form.get("INPUT_EXAMPLESFILE") or ""
    input_semantics = form.get("INPUT_SEMANTCSFILE") or ""
    input_teach = form.get("INPUT_TEACHFILE") or ""

    # Convert empty to None in worker payload; keep strings for run_input.json
    payload = {
        "MODEL_ID": model_id,
        "MODEL_TEMPERATURE": float(model_temperature) if model_temperature else 0.15,
        "MAX_NORMS_PER_5K": int(max_norms) if max_norms else 10,
        "INPUT_PROMPTFILE": input_prompt or None,
        "INPUT_GLOSSARYFILE": input_glossary or None,
        "INPUT_EXAMPLESFILE": input_examples or None,
        "INPUT_SEMANTCSFILE": input_semantics or None,
        "INPUT_TEACHFILE": input_teach or None,
    }

    run_id = str(int(time.time()))
    run_dir = OUTPUT_ROOT / run_id
    (run_dir / "input").mkdir(parents=True, exist_ok=True)

    # Save uploaded input_document if present
    up = files.get("input_document")
    if up and up.filename:
        dest = run_dir / "input" / up.filename
        up.save(dest)

    # Persist run_input.json (recording explicit values including RUN_ID)
    run_input = {
        "RUN_ID": run_id,
        "MODEL_ID": model_id,
        "MODEL_TEMPERATURE": model_temperature,
        "MAX_NORMS_PER_5K": max_norms,
        "INPUT_PROMPTFILE": input_prompt,
        "INPUT_GLOSSARYFILE": input_glossary,
        "INPUT_EXAMPLESFILE": input_examples,
        "INPUT_SEMANTCSFILE": input_semantics,
        "INPUT_TEACHFILE": input_teach,
    }
    (run_dir / "run_input.json").write_text(json.dumps(run_input, indent=2), encoding="utf-8")

    # Update past models badges
    _update_past_models(model_id)

    # Launch runner worker
    args, env = build_worker_cmd(run_id, payload, run_dir)
    r = Runner(run_id, env, args, run_dir)
    RUNNERS[run_id] = r
    r.start()

    return jsonify({"run_id": run_id})

@app.get("/runs/<run_id>/logs")
def stream_logs(run_id: str):
    r = RUNNERS.get(run_id)
    if not r:
        return abort(404)

    def generate():
        idx = 0
        # Send any buffered lines first
        while True:
            buf = r.state.buffer
            while idx < len(buf):
                line = buf[idx]
                idx += 1
                yield f"data: {json.dumps({'line': line, 'run_id': run_id, 'ts': time.time()})}\n\n"
            if r.state.status in ("finished", "error"):
                payload = {"event": "complete", "run_id": run_id, "status": r.state.status}
                # exit_code added if Runner stores it
                exit_code = getattr(r.state, 'exit_code', None)
                if exit_code is not None:
                    payload["code"] = exit_code
                yield f"data: {json.dumps(payload)}\n\n"
                break
            time.sleep(0.2)
    return Response(generate(), mimetype="text/event-stream")

@app.get("/runs/<run_id>/status")
def run_status(run_id: str):
    r = RUNNERS.get(run_id)
    if not r:
        return abort(404)
    return jsonify({
        "status": r.state.status,
        "started_at": r.state.started_at,
        "ended_at": r.state.ended_at,
        "stats": r.state.stats,
    })

@app.get("/runs/<run_id>/files")
def run_files(run_id: str):
    run_dir = OUTPUT_ROOT / run_id
    if not run_dir.exists():
        return abort(404)
    files: list[dict[str, Any]] = []
    for p in run_dir.rglob("*"):
        if p.is_file():
            rel = p.relative_to(run_dir)
            try:
                sz = p.stat().st_size
            except OSError:
                sz = 0
            files.append({"path": str(rel).replace("\\", "/"), "size": sz})
    files.sort(key=lambda x: str(x["path"]))  # type: ignore[call-overload]
    return jsonify(files)

@app.get("/runs/<run_id>/file")
def run_file(run_id: str):
    rel_path = request.args.get("path", "")
    run_dir = OUTPUT_ROOT / run_id
    if not rel_path:
        return abort(400)
    # Normalize and prevent traversal
    abs_path = (run_dir / rel_path).resolve()
    try:
        run_dir_res = run_dir.resolve()
    except Exception:
        return abort(404)
    if not str(abs_path).startswith(str(run_dir_res)) or not abs_path.exists() or not abs_path.is_file():
        return abort(404)
    mime, _ = mimetypes.guess_type(str(abs_path))
    size = abs_path.stat().st_size
    is_text_or_json = False
    if mime:
        is_text_or_json = mime.startswith("text/") or "application/json" in mime
    as_attachment = True
    if is_text_or_json and size <= 1_000_000:  # 1MB inline limit
        as_attachment = False
    return send_file(str(abs_path), mimetype=mime or "application/octet-stream", as_attachment=as_attachment)

if __name__ == "__main__":
    # Simple dev server
    app.run(host="127.0.0.1", port=5000, debug=True)
