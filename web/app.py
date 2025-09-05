from __future__ import annotations
from pathlib import Path
import json
import mimetypes
import time
from typing import Dict, Any
import os
import sys
import atexit
import signal
import socket
from flask import Flask, render_template, jsonify, request, Response, send_file, abort  # type: ignore
from urllib.request import urlopen  # stdlib, avoid extra deps
from urllib.error import URLError, HTTPError

from runner import Runner, build_worker_cmd
from comments_db import CommentsDB, Comment

app = Flask(__name__, static_folder="static", template_folder="templates")

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "output_runs"
OUTPUT_ROOT.mkdir(exist_ok=True)

# Local cache for CDN assets
STATIC_ROOT = Path(__file__).resolve().parent / "static"
VENDOR_ROOT = STATIC_ROOT / "vendor"
VENDOR_ROOT.mkdir(parents=True, exist_ok=True)

# Map of local vendor paths -> source CDN URLs (prefer unpinned or maintained versions)
VENDOR_ASSETS: dict[str, str] = {
    # Tailwind CDN runtime (generates CSS in browser). Using canonical URL for latest.
    str(VENDOR_ROOT / "tailwindcss.js"): "https://cdn.tailwindcss.com",
    # Highlight.js core (common languages) + themes for light/dark
    str(VENDOR_ROOT / "highlightjs" / "common.min.js"): "https://cdn.jsdelivr.net/npm/highlight.js@11/lib/common.min.js",
    str(VENDOR_ROOT / "highlightjs" / "github.min.css"): "https://cdn.jsdelivr.net/npm/highlight.js@11/styles/github.min.css",
    str(VENDOR_ROOT / "highlightjs" / "github-dark.min.css"): "https://cdn.jsdelivr.net/npm/highlight.js@11/styles/github-dark.min.css",
    # Markdown and sanitization
    str(VENDOR_ROOT / "marked" / "marked.min.js"): "https://cdn.jsdelivr.net/npm/marked/marked.min.js",
    str(VENDOR_ROOT / "dompurify" / "purify.min.js"): "https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js",
    # JSON viewer (collapsible tree) + CSS
    str(VENDOR_ROOT / "json-formatter" / "json-formatter.umd.js"): "https://cdn.jsdelivr.net/npm/json-formatter-js@2/dist/json-formatter.umd.js",
    str(VENDOR_ROOT / "json-formatter" / "json-formatter.css"): "https://cdn.jsdelivr.net/npm/json-formatter-js@2/dist/json-formatter.css",
    # GitHub Markdown CSS for nicer MD rendering
    str(VENDOR_ROOT / "github-markdown.min.css"): "https://cdn.jsdelivr.net/npm/github-markdown-css/github-markdown.min.css",
}


def _ensure_parent_dirs(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _download_url_to_file(url: str, dest_path: Path, timeout: float = 10.0) -> bool:
    """Best-effort download of a URL to a local file. Returns True on success.
    Non-fatal on failures (returns False). Uses stdlib urllib to avoid extra deps.
    """
    try:
        _ensure_parent_dirs(dest_path)
        with urlopen(url, timeout=timeout) as resp:  # nosec - fetching public static assets
            data = resp.read()
        dest_path.write_bytes(data)
        return True
    except (URLError, HTTPError, TimeoutError, OSError):
        return False
    except Exception:
        return False


def ensure_vendor_assets() -> None:
    """Ensure local cached copies of critical CDN assets exist.
    We only download if the file is missing to keep startup fast and offline-friendly.
    """
    for local_str, url in VENDOR_ASSETS.items():
        local_path = Path(local_str)
        try:
            if not local_path.exists() or local_path.stat().st_size == 0:
                _download_url_to_file(url, local_path)
        except Exception:
            # Never fail startup for vendor caching
            pass

# Single-instance lock file in output_runs
LOCK_FILE_PATH = OUTPUT_ROOT / ".web_app.lock"

# Track shutdown to avoid duplicate attempts
_SHUTTING_DOWN = False

RUNNERS: Dict[str, Runner] = {}

INPUT_DIRS = {
    "input_promptfiles": REPO_ROOT / "input_promptfiles",
    "input_glossaryfiles": REPO_ROOT / "input_glossaryfiles",
    "input_examplefiles": REPO_ROOT / "input_examplefiles",
    "input_semanticsfiles": REPO_ROOT / "input_semanticsfiles",
    "input_teachfiles": REPO_ROOT / "input_teachfiles",
}

PAST_MODELS_FILE = REPO_ROOT / "web" / "pastmodels.json"

# Initialize comments database
COMMENTS_DB_PATH = REPO_ROOT / "web" / "comments.db"
comments_db = CommentsDB(COMMENTS_DB_PATH)

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


@app.get("/test-comments")
def test_comments():
    return render_template("test_comments.html")

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
    max_char_buffer = form.get("MAX_CHAR_BUFFER", "5000").strip()
    extraction_passes = form.get("EXTRACTION_PASSES", "2").strip()
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
        "MAX_CHAR_BUFFER": int(max_char_buffer) if max_char_buffer else 5000,
        "EXTRACTION_PASSES": int(extraction_passes) if extraction_passes else 2,
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
        "MAX_CHAR_BUFFER": max_char_buffer,
        "EXTRACTION_PASSES": extraction_passes,
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
        # Absolute line index accounting for truncation
        idx = 0
        last_emit = time.time()
        start_time = last_emit
        max_stream_seconds = 60 * 60  # 1 hour safety cutoff
        # Initial comment to open SSE stream promptly
        try:
            yield ": connected\n\n"
        except Exception:
            return
        # Send any buffered lines first
        while True:
            try:
                buf = r.state.buffer
                offset = getattr(r.state, "buffer_offset", 0)
                # Skip ahead if the buffer was truncated
                if idx < offset:
                    idx = offset
                while idx - offset < len(buf):
                    line = buf[idx - offset]
                    idx += 1
                    yield f"data: {json.dumps({'line': line, 'run_id': run_id, 'ts': time.time()})}\n\n"
                    last_emit = time.time()
                if r.state.status in ("finished", "error", "canceled"):
                    payload = {"event": "complete", "run_id": run_id, "status": r.state.status}
                    # exit_code added if Runner stores it
                    exit_code = getattr(r.state, 'exit_code', None)
                    if exit_code is not None:
                        payload["code"] = exit_code
                    yield f"data: {json.dumps(payload)}\n\n"
                    break
                # Periodic keepalive to prevent proxy timeouts
                now = time.time()
                if now - last_emit > 10:
                    yield ": keepalive\n\n"
                    last_emit = now
                # Safety cutoff to avoid run-away streams
                if now - start_time > max_stream_seconds:
                    yield f"data: {json.dumps({'event':'timeout','run_id': run_id})}\n\n"
                    break
                time.sleep(0.2)
            except (GeneratorExit, ConnectionResetError, BrokenPipeError):
                # Client disconnected; stop streaming
                break
            except Exception:
                # On unexpected errors, try to emit a final message and close
                try:
                    yield f"data: {json.dumps({'event':'error','run_id': run_id})}\n\n"
                except Exception:
                    pass
                break
    resp = Response(generate(), mimetype="text/event-stream")
    # Prevent buffering by proxies and encourage streaming
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp

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

@app.post("/runs/<run_id>/cancel")
def cancel_run(run_id: str):
    r = RUNNERS.get(run_id)
    if not r:
        return abort(404)
    ok = r.cancel()
    return jsonify({"ok": ok, "status": r.state.status})

@app.get("/runs/<run_id>/files")
def run_files(run_id: str):
    run_dir = OUTPUT_ROOT / run_id
    if not run_dir.exists():
        return abort(404)
    
    # Only show files from the 'lx output' folder for processed results
    # This prevents showing intermediate processing files from chunks folder
    lx_output_dir = run_dir / "lx output"
    files: list[dict[str, Any]] = []
    
    if lx_output_dir.exists():
        for p in lx_output_dir.rglob("*"):
            if p.is_file():
                filename = p.name
                
                # Filter out intermediate processing files that should be in chunks folder
                # These are legacy files from older runs before the file reorganization
                skip_patterns = [
                    "raw_annotated_document_",
                    "raw_resolver_output_", 
                    "annotated_extractions_",
                    "raw_extraction.json"
                ]
                
                if any(filename.startswith(pattern) for pattern in skip_patterns):
                    continue  # Skip intermediate files that should be in chunks folder
                
                # Make path relative to run directory for consistency
                rel = p.relative_to(run_dir)
                try:
                    sz = p.stat().st_size
                except OSError:
                    sz = 0
                files.append({"path": str(rel).replace("\\", "/"), "size": sz})
    
    # Also include run_input.json if it exists at the root level
    run_input_file = run_dir / "run_input.json"
    if run_input_file.exists():
        try:
            sz = run_input_file.stat().st_size
        except OSError:
            sz = 0
        files.append({"path": "run_input.json", "size": sz})
    
    files.sort(key=lambda x: str(x["path"]))  # type: ignore[call-overload]
    return jsonify(files)

@app.get("/runs/<run_id>/file")
def run_file(run_id: str):
    rel_path = request.args.get("path", "")
    # Optional query params:
    #  - preview=1 returns a truncated text preview for large files
    #  - maxBytes sets preview byte cap (default 1MB)
    #  - inline=1 forces inline delivery even if file exceeds inline limits
    preview_flag = request.args.get("preview", "0") == "1"
    inline_flag = request.args.get("inline", "0") == "1"
    try:
        max_bytes = int(request.args.get("maxBytes", "1000000"))
    except Exception:
        max_bytes = 1_000_000
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
    # Enhance detection: common text-like extensions
    ext = abs_path.suffix.lower()
    text_exts = {".txt", ".md", ".json", ".py", ".log", ".csv", ".tsv", ".yml", ".yaml"}
    if not mime:
        if ext == ".json":
            mime = "application/json"
        elif ext in text_exts:
            mime = "text/plain"
    is_text_or_json = False
    if mime:
        is_text_or_json = mime.startswith("text/") or "application/json" in mime
    # If mime is still inconclusive, sniff small files for utf-8 decodability
    if not is_text_or_json and size <= 1_000_000:  # only sniff small files
        try:
            with open(abs_path, "rb") as fh:
                chunk = fh.read(65536)
            chunk.decode("utf-8")
            is_text_or_json = True
            if not mime:
                mime = "text/plain"
        except Exception:
            is_text_or_json = False
    # If preview requested, return a truncated text view regardless of original type
    if preview_flag:
        try:
            # Read up to max_bytes for preview
            with open(abs_path, "rb") as fh:
                chunk = fh.read(max_bytes)
            truncated = size > len(chunk)
            # Attempt UTF-8 decode with replacement to avoid failures
            text = chunk.decode("utf-8", errors="replace")
            if truncated:
                text += f"\n\n--- TRUNCATED PREVIEW ({len(chunk)} of {size} bytes) ---\n"
            resp = Response(text, mimetype="text/plain; charset=utf-8")
            # Always serve preview inline
            resp.headers["Content-Disposition"] = "inline"
            resp.headers["X-Preview"] = "1"
            resp.headers["X-Preview-Truncated"] = "1" if truncated else "0"
            resp.headers["X-File-Size"] = str(size)
            resp.headers["X-Preview-Max-Bytes"] = str(max_bytes)
            return resp
        except PermissionError:
            # Likely locked by writer (Windows sharing). Advise client to retry.
            msg = "File is temporarily locked; please retry shortly."
            resp = Response(msg, status=423, mimetype="text/plain; charset=utf-8")
            resp.headers["Retry-After"] = "1"
            return resp
        except OSError as oe:
            if getattr(oe, 'errno', None) in (13, 32):  # Permission denied / sharing violation
                msg = "File is temporarily unavailable; please retry shortly."
                resp = Response(msg, status=423, mimetype="text/plain; charset=utf-8")
                resp.headers["Retry-After"] = "1"
                return resp
            return abort(404)

    # Decide inline vs download: allow larger inline for text-like files
    inline_limit = 1_000_000  # default 1MB
    if ext in {".log", ".txt", ".md", ".csv", ".tsv", ".py", ".json"}:
        inline_limit = 10_000_000  # 10MB for common text files (incl. logs)

    # Determine Content-Disposition
    as_attachment = True
    if inline_flag:
        as_attachment = False
    elif is_text_or_json and size <= inline_limit:
        as_attachment = False

    # Proactively test readability to avoid server hangs on locked files
    try:
        with open(abs_path, "rb"):
            pass
    except PermissionError:
        resp = Response("File is temporarily locked; please retry shortly.", status=423, mimetype="text/plain; charset=utf-8")
        resp.headers["Retry-After"] = "1"
        return resp
    except OSError as oe:
        if getattr(oe, 'errno', None) in (13, 32):
            resp = Response("File is temporarily unavailable; please retry shortly.", status=423, mimetype="text/plain; charset=utf-8")
            resp.headers["Retry-After"] = "1"
            return resp
    return send_file(
        str(abs_path),
        mimetype=mime or "application/octet-stream",
        as_attachment=as_attachment,
    )

# Comments API endpoints

@app.get("/api/comments")
def get_comments():
    """Get comments for a specific file."""
    file_path = request.args.get("file_path", "")
    if not file_path:
        return jsonify({"error": "file_path parameter is required"}), 400
    
    try:
        comments = comments_db.get_comments_for_file(file_path)
        return jsonify({"comments": comments})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/comments")
def create_comment():
    """Create a new comment."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON data is required"}), 400
        
        # Validate required fields
        required_fields = ["file_path", "author_name", "text_body"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400
        
        # Create comment object
        comment = Comment(
            file_path=data["file_path"],
            position_data=data.get("position_data", {}),
            author_name=data["author_name"],
            text_body=data["text_body"],
            parent_comment_id=data.get("parent_comment_id")
        )
        
        # Validate parent comment exists if specified
        if comment.parent_comment_id:
            parent = comments_db.get_comment(comment.parent_comment_id)
            if not parent:
                return jsonify({"error": "Parent comment not found"}), 404
            
            # Ensure we're not creating nested replies (depth > 1)
            if parent.parent_comment_id is not None:
                return jsonify({"error": "Cannot reply to a reply (max depth is 1)"}), 400
        
        # Create the comment
        created_comment = comments_db.create_comment(comment)
        return jsonify({"comment": created_comment.to_dict()}), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.put("/api/comments/<int:comment_id>")
def update_comment(comment_id: int):
    """Update an existing comment."""
    try:
        data = request.get_json()
        if not data or not data.get("text_body"):
            return jsonify({"error": "text_body is required"}), 400
        
        # Check if comment exists
        comment = comments_db.get_comment(comment_id)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404
        
        # Update the comment
        success = comments_db.update_comment(comment_id, data["text_body"])
        if success:
            updated_comment = comments_db.get_comment(comment_id)
            return jsonify({"comment": updated_comment.to_dict()})
        else:
            return jsonify({"error": "Failed to update comment"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.delete("/api/comments/<int:comment_id>")
def delete_comment(comment_id: int):
    """Delete a comment and its replies."""
    try:
        # Check if comment exists
        comment = comments_db.get_comment(comment_id)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404
        
        # Delete the comment (cascades to replies)
        success = comments_db.delete_comment(comment_id)
        if success:
            return jsonify({"message": "Comment deleted successfully"})
        else:
            return jsonify({"error": "Failed to delete comment"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/comments/<int:comment_id>/reply")
def reply_to_comment(comment_id: int):
    """Create a reply to a comment."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON data is required"}), 400
        
        # Validate required fields
        required_fields = ["author_name", "text_body"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400
        
        # Check if parent comment exists
        parent_comment = comments_db.get_comment(comment_id)
        if not parent_comment:
            return jsonify({"error": "Parent comment not found"}), 404
        
        # Ensure we're not replying to a reply (depth > 1)
        if parent_comment.parent_comment_id is not None:
            return jsonify({"error": "Cannot reply to a reply (max depth is 1)"}), 400
        
        # Create reply comment
        reply_comment = Comment(
            file_path=parent_comment.file_path,
            position_data=parent_comment.position_data,  # Inherit position from parent
            author_name=data["author_name"],
            text_body=data["text_body"],
            parent_comment_id=comment_id
        )
        
        # Create the reply
        created_reply = comments_db.create_comment(reply_comment)
        return jsonify({"comment": created_reply.to_dict()}), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/comments/<int:comment_id>")
def get_comment_details(comment_id: int):
    """Get details of a specific comment."""
    try:
        comment = comments_db.get_comment(comment_id)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404
        
        # Get reply count
        reply_count = comments_db.get_reply_count(comment_id)
        
        comment_dict = comment.to_dict()
        comment_dict["reply_count"] = reply_count
        
        return jsonify({"comment": comment_dict})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _is_port_in_use(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex((host, port)) == 0
    except Exception:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass


def _acquire_single_instance_lock(host: str, port: int) -> None:
    """Create an exclusive lock file; if an active server seems to hold it, exit.
    If stale lock is detected and port is free, remove it and continue.
    """
    if LOCK_FILE_PATH.exists():
        # If port is in use, assume another instance is running and exit
        if _is_port_in_use(host, port):
            msg = f"Another web app instance appears to be running on {host}:{port}."
            print(msg, file=sys.stderr)
            sys.exit(1)
        # Port is free -> stale lock, attempt to remove
        try:
            LOCK_FILE_PATH.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            # Can't remove -> bail to avoid double spawn
            print("Could not remove stale lock file; aborting start.", file=sys.stderr)
            sys.exit(1)
    try:
        LOCK_FILE_PATH.write_text(json.dumps({
            "pid": os.getpid(),
            "ts": time.time(),
        }), encoding="utf-8")
    except Exception as e:
        print(f"Failed to create lock file: {e}", file=sys.stderr)
        sys.exit(1)


def _release_single_instance_lock() -> None:
    try:
        if LOCK_FILE_PATH.exists():
            LOCK_FILE_PATH.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass


def _cancel_all_runs():
    # Attempt to cancel all active runs and give them a moment to exit
    for rid, r in list(RUNNERS.items()):
        try:
            r.cancel()
        except Exception:
            pass
    # Best-effort brief wait
    time.sleep(0.25)


def _graceful_shutdown(signum: int | None = None, _frame: Any | None = None):
    global _SHUTTING_DOWN
    if _SHUTTING_DOWN:
        return
    _SHUTTING_DOWN = True
    try:
        # Write a small note so SSE consumers see a final line if possible
        for rid, r in list(RUNNERS.items()):
            try:
                if r.state.log_path:
                    with open(r.state.log_path, "a", encoding="utf-8", buffering=1) as lf:
                        lf.write("[app] Shutting down web app; canceling run\n")
                r.state.buffer.append("[app] Shutting down web app; canceling run")
            except Exception:
                pass
    finally:
        try:
            _cancel_all_runs()
        finally:
            _release_single_instance_lock()


def _install_signal_handlers():
    # Handle Ctrl+C / TERM / BREAK (Windows) to cleanly shutdown and kill workers
    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                signal.signal(sig, _graceful_shutdown)  # type: ignore[arg-type]
            except Exception:
                pass
    # Windows specific Ctrl+Break
    if hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, _graceful_shutdown)  # type: ignore[arg-type]
        except Exception:
            pass


if __name__ == "__main__":
    # Ensure single instance and graceful shutdown
    host = "127.0.0.1"
    port = 5000
    # Try to cache vendor assets locally for CDN fallbacks
    ensure_vendor_assets()
    _acquire_single_instance_lock(host, port)
    atexit.register(_graceful_shutdown)
    _install_signal_handlers()

    # Simple dev server: disable reloader to avoid double-spawn
    use_reloader = False
    try:
        # Enable threading so SSE and other requests don't block each other
        app.run(host=host, port=port, debug=True, use_reloader=use_reloader, threaded=True)
    finally:
        _graceful_shutdown()
