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

# Database connection for Sandbox
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/langextract")
_db_engine = None

def get_db_engine():
    """Get or create database engine for Sandbox."""
    global _db_engine
    if _db_engine is None:
        try:
            from sqlalchemy import create_engine
            _db_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        except Exception as e:
            print(f"[WARNING] Failed to create database engine: {e}")
            print(f"[WARNING] Sandbox will fall back to file-based data")
            _db_engine = False  # Mark as unavailable
    return _db_engine if _db_engine is not False else None

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

# Cache for parsed norm ASTs (per run_id)
_NORM_AST_CACHE: Dict[str, Dict[str, Any]] = {}

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
    return render_template("mode_selection.html")

@app.get("/runner")
def runner():
    mode = request.args.get("mode", "new")
    if mode == "existing":
        return render_template("runner.html", mode="existing")
    else:
        return render_template("runner.html", mode="new")

@app.get("/debug")
def debug():
    """Debug page for testing TreeCommentsUI."""
    return send_file("debug_comments.html")

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
    
    files: list[dict[str, Any]] = []
    
    # Check for enhanced output first
    enhanced_output_dir = run_dir / "enhanced_output"
    if enhanced_output_dir.exists():
        for p in enhanced_output_dir.rglob("*"):
            if p.is_file():
                filename = p.name
                
                # Filter out chunks folder files as requested
                # Skip any files inside the chunks subfolder
                rel = p.relative_to(run_dir)
                rel_str = str(rel).replace("\\", "/")
                if "/chunks/" in rel_str or rel_str.startswith("enhanced_output/chunks/"):
                    continue  # Skip chunk files
                
                try:
                    sz = p.stat().st_size
                except OSError:
                    sz = 0
                files.append({"path": rel_str, "size": sz})
    
    # Fallback: check legacy 'lx output' folder for backward compatibility
    lx_output_dir = run_dir / "lx output"
    if lx_output_dir.exists() and not enhanced_output_dir.exists():
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
    """Get comments for a specific file and optionally tree item."""
    file_path = request.args.get("file_path", "")
    tree_item = request.args.get("tree_item", "")
    run_id = request.args.get("run_id", "")
    
    if not file_path:
        return jsonify({"error": "file_path parameter is required"}), 400
    
    try:
        run_id_param = run_id if run_id else None
        if tree_item:
            comments = comments_db.get_comments_for_tree_item(file_path, tree_item, run_id_param)
        else:
            comments = comments_db.get_comments_for_file(file_path, run_id_param)
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
        required_fields = ["file_path", "author_name", "text_body", "tree_item"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400
        
        # Create comment object
        comment = Comment(
            file_path=data["file_path"],
            tree_item=data["tree_item"],
            author_name=data["author_name"],
            text_body=data["text_body"],
            parent_comment_id=data.get("parent_comment_id"),
            run_id=data.get("run_id")  # Optional run_id for scoping
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
            tree_item=parent_comment.tree_item,  # Inherit tree_item from parent
            author_name=data["author_name"],
            text_body=data["text_body"],
            parent_comment_id=comment_id,
            run_id=parent_comment.run_id  # Inherit run_id from parent
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


# PDF Viewer API endpoints

@app.get("/api/runs/<run_id>/pdf")
def serve_pdf(run_id: str):
    """Serve the PDF file for a specific run."""
    run_dir = OUTPUT_ROOT / run_id
    if not run_dir.exists():
        return abort(404, "Run not found")
    
    # Look for PDF file in the input directory
    input_dir = run_dir / "input"
    if not input_dir.exists():
        return abort(404, "No input directory found")
    
    # Find the first PDF file in the input directory
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        return abort(404, "No PDF file found for this run")
    
    pdf_path = pdf_files[0]  # Use the first PDF found
    
    try:
        return send_file(pdf_path, as_attachment=False, mimetype='application/pdf')
    except Exception as e:
        return abort(500, f"Error serving PDF: {str(e)}")


@app.get("/api/runs/<run_id>/positioning")
def get_positioning_data(run_id: str):
    """Get positioning data for PDF highlighting."""
    run_dir = OUTPUT_ROOT / run_id
    if not run_dir.exists():
        return abort(404, "Run not found")
    
    # Look for enhanced output directory
    enhanced_output_dir = run_dir / "enhanced_output"
    if not enhanced_output_dir.exists():
        # Fallback to legacy output location
        output_dir = run_dir / "lx output"
        if not output_dir.exists():
            return jsonify({"sections": []})  # Return empty if no output yet
        enhanced_output_dir = output_dir
    
    # Look for the enhanced extraction results and docling document
    extraction_results_file = enhanced_output_dir / "enhanced_extraction_results.json"
    docling_document_file = enhanced_output_dir / "headline_fixed_doclingdocument.json"
    
    if not extraction_results_file.exists() or not docling_document_file.exists():
        # Fallback to old method for compatibility
        enhanced_output_file = None
        for pattern in ["enhanced_output.json", "*enhanced*.json", "output*.json"]:
            files = list(enhanced_output_dir.glob(pattern))
            if files:
                enhanced_output_file = files[0]
                break
        
        if enhanced_output_file:
            try:
                with open(enhanced_output_file, 'r', encoding='utf-8') as f:
                    output_data = json.load(f)
                positioning_data = extract_positioning_from_output(output_data)
                return jsonify(positioning_data)
            except Exception as e:
                print(f"Error loading legacy positioning data: {e}")
        
        return jsonify({"sections": []})
    
    try:
        # Load extraction results
        with open(extraction_results_file, 'r', encoding='utf-8') as f:
            extraction_data = json.load(f)
        
        # Load docling document
        with open(docling_document_file, 'r', encoding='utf-8') as f:
            docling_data = json.load(f)
        
        # Extract positioning data from the enhanced output and docling document
        positioning_data = extract_positioning_from_docling(extraction_data, docling_data)
        return jsonify(positioning_data)
        
    except Exception as e:
        print(f"Error loading positioning data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"sections": []})


def extract_positioning_from_docling(extraction_data, docling_data):
    """Extract positioning data from enhanced_lx_runner output and docling document."""
    positioning_data = {"sections": []}
    
    # Get extractions from extraction data
    extractions = extraction_data.get("extractions", [])
    sections = extraction_data.get("sections", [])
    
    # Get text elements from docling document  
    texts = docling_data.get("texts", [])
    
    # Create a mapping from text content to positioning data
    text_to_position = {}
    for text_elem in texts:
        text_content = text_elem.get("text", "").strip()
        prov = text_elem.get("prov", [])
        if text_content and prov:
            # Use the first provenance entry
            first_prov = prov[0]
            text_to_position[text_content] = {
                "page_no": first_prov.get("page_no"),
                "bbox": first_prov.get("bbox"),
                "charspan": first_prov.get("charspan")
            }
    
    # Create a section mapping from the sections array (the source of truth)
    section_id_to_info = {}
    for section in sections:
        section_id = section.get("section_id")
        if section_id:
            section_id_to_info[section_id] = section
    
    print(f"Found {len(section_id_to_info)} sections: {list(section_id_to_info.keys())}")
    
    # Initialize sections_map with all sections first
    sections_map = {}
    for section_id, section_info in section_id_to_info.items():
        sections_map[section_id] = {
            "section_id": section_id,
            "section_name": section_info.get("section_name", section_id),
            "extraction_text": "",  # Will be populated if CHUNK_METADATA exists
            "norms": []
        }
    
    # Map CHUNK_METADATA to sections and add metadata
    chunk_to_section = {}
    
    for extraction in extractions:
        extraction_class = extraction.get("extraction_class")
        extraction_text = extraction.get("extraction_text", "").strip()
        attributes = extraction.get("attributes", {})
        
        if extraction_class == "CHUNK_METADATA":
            # This is a section metadata - map it to actual section
            chunk_id = attributes.get("id")
            section_title = None
            
            # Extract section title from extraction text (e.g., "Section: 6 Puertas...")
            for line in extraction_text.split('\n'):
                if line.startswith('Section:'):
                    section_title = line.replace('Section:', '').strip()
                    break
            
            if chunk_id and section_title:
                # Find matching section by title
                matching_section_id = None
                for section_id, section_info in section_id_to_info.items():
                    if section_info.get("section_name", "").strip() == section_title:
                        matching_section_id = section_id
                        break
                
                if matching_section_id and matching_section_id in sections_map:
                    print(f"Mapped CHUNK_METADATA {chunk_id} to section {matching_section_id}")
                    chunk_to_section[chunk_id] = matching_section_id
                    # Update with metadata
                    sections_map[matching_section_id]["extraction_text"] = extraction_text
                else:
                    print(f"Could not find matching section for title: {section_title}")
    
    # Now process norms using the real section IDs
    for extraction in extractions:
        extraction_class = extraction.get("extraction_class")
        extraction_text = extraction.get("extraction_text", "").strip()
        attributes = extraction.get("attributes", {})
        
        if extraction_class == "NORM":
            # This is a norm within a section
            parent_section_id = attributes.get("parent_section_id")
            norm_id = attributes.get("id")
            
            print(f"Processing norm {norm_id} with parent {parent_section_id}")
            if parent_section_id and parent_section_id in sections_map:
                norm_data = {
                    "norm_id": norm_id,
                    "extraction_text": extraction_text,
                    "attributes": attributes
                }
                sections_map[parent_section_id]["norms"].append(norm_data)
                print(f"Added norm {norm_id} to section {parent_section_id}")
            else:
                print(f"Parent section {parent_section_id} not found for norm {norm_id}. Available sections: {list(sections_map.keys())}")
    
    print(f"Mapped {len(sections_map)} sections with {len(text_to_position)} text elements")
    print(f"Sample docling text elements: {list(text_to_position.keys())[:5]}")
    if len(text_to_position) > 5:
        print(f"... and {len(text_to_position) - 5} more elements")
    
    # Now map texts to positions using fuzzy matching
    for section_id, section_data in sections_map.items():
        print(f"Processing section {section_id} for positioning...")
        
        # For sections, try to find section headers or content
        section_text = section_data["extraction_text"]
        section_name = section_data["section_name"]
        
        # If no CHUNK_METADATA extraction text, use section name
        if not section_text and section_name:
            section_text = section_name
        
        if section_text:
            # Extract actual section title from extraction text (skip metadata)
            section_title = None
            if section_text.startswith("Section:"):
                section_lines = section_text.split('\n')
                for line in section_lines:
                    if line.startswith('Section:'):
                        section_title = line.replace('Section:', '').strip()
                        break
            else:
                # Use the section name directly
                section_title = section_name
            
            if section_title:
                section_positioning = find_text_position(section_title, text_to_position)
                if section_positioning:
                    section_data["positioning"] = section_positioning
                    print(f"Found positioning for section {section_id}: {section_title[:50]}...")
                else:
                    print(f"No positioning found for section {section_id}: {section_title[:50]}...")
        else:
            print(f"No text available for section {section_id} positioning")
        
        # Process norms in this section
        for norm_data in section_data["norms"]:
            norm_text = norm_data["extraction_text"]
            norm_id = norm_data["norm_id"]
            print(f"Trying to find positioning for norm {norm_id} with text: {norm_text[:100]}...")
            
            if norm_text:
                norm_positioning = find_text_position(norm_text, text_to_position)
                if norm_positioning:
                    norm_data["positioning"] = norm_positioning
                    print(f"Found positioning for norm {norm_id}: {norm_text[:50]}...")
                else:
                    print(f"No positioning found for norm {norm_id}")
            else:
                print(f"No text available for norm {norm_id}")
        
        positioning_data["sections"].append(section_data)
    
    # Final validation and fallback for missing positioning
    total_norms_processed = 0
    norms_with_positioning = 0
    
    for section_data in positioning_data["sections"]:
        for norm_data in section_data.get("norms", []):
            total_norms_processed += 1
            if "positioning" in norm_data:
                norms_with_positioning += 1
            else:
                # Try fallback: use section positioning if available
                if "positioning" in section_data:
                    norm_data["positioning"] = section_data["positioning"].copy()
                    norm_data["positioning"]["fallback"] = "section_level"
                    norms_with_positioning += 1
                    print(f"Applied section-level positioning fallback for norm {norm_data.get('norm_id', 'Unknown')}")
    
    positioning_success_rate = norms_with_positioning / total_norms_processed if total_norms_processed > 0 else 0
    print(f"Final positioning success rate: {norms_with_positioning}/{total_norms_processed} ({positioning_success_rate:.1%})")
    
    return positioning_data


def find_text_position(target_text, text_to_position):
    """Find the best matching position for target text in the docling document."""
    target_text = target_text.strip()
    
    if not target_text:
        return None
    
    # First try exact match
    if target_text in text_to_position:
        print(f"Exact match found for: {target_text[:50]}...")
        return text_to_position[target_text]
    
    # Try substring matching (both ways)
    best_match = None
    best_score = 0
    best_match_text = ""
    
    for docling_text, position in text_to_position.items():
        docling_text_clean = docling_text.strip()
        
        # Skip very short texts as they may lead to false positives
        if len(docling_text_clean) < 3:
            continue
        
        # Check for substring matches
        if len(target_text) >= 10 and len(docling_text_clean) >= 10:
            # Check if one is a substring of the other
            if docling_text_clean in target_text:
                score = len(docling_text_clean) / len(target_text)
                if score > best_score and score > 0.3:
                    best_score = score
                    best_match = position
                    best_match_text = docling_text_clean
                    continue
            
            if target_text in docling_text_clean:
                score = len(target_text) / len(docling_text_clean)
                if score > best_score and score > 0.3:
                    best_score = score
                    best_match = position
                    best_match_text = docling_text_clean
                    continue
        
        # Check if target text starts with or contains this docling text
        if (len(docling_text_clean) >= 20 and 
            (docling_text_clean.startswith(target_text[:50]) or 
             target_text.startswith(docling_text_clean[:50]))):
            # Simple scoring based on length match
            score = min(len(docling_text_clean), len(target_text)) / max(len(docling_text_clean), len(target_text))
            if score > best_score and score > 0.2:
                best_score = score
                best_match = position
                best_match_text = docling_text_clean
        
        # Also check word-based similarity for shorter texts
        elif len(target_text) >= 20:
            target_words = set(target_text.lower().split())
            docling_words = set(docling_text_clean.lower().split())
            
            if target_words and docling_words:
                overlap = len(target_words & docling_words)
                union = len(target_words | docling_words)
                jaccard_score = overlap / union if union > 0 else 0
                
                if jaccard_score > best_score and jaccard_score > 0.3:
                    best_score = jaccard_score
                    best_match = position
                    best_match_text = docling_text_clean
    
    # Only return match if it's reasonably good
    if best_match and best_score > 0.2:
        print(f"Found match (score: {best_score:.2f}) for target: {target_text[:50]}... -> docling: {best_match_text[:50]}...")
        return best_match
    else:
        print(f"No good match found for: {target_text[:50]}... (best score: {best_score:.2f})")
    
    return None


def extract_positioning_from_output(output_data):
    """Extract positioning data from enhanced_lx_runner output (legacy method)."""
    positioning_data = {"sections": []}
    
    if not isinstance(output_data, dict):
        return positioning_data
    
    sections = output_data.get("sections", [])
    for section in sections:
        section_data = {
            "section_id": section.get("section_id"),
            "section_name": section.get("section_name"),
            "norms": []
        }
        
        # Add section-level positioning if available
        if section.get("start_page") or section.get("end_page"):
            section_data["positioning"] = {
                "page_no": section.get("start_page", 1),
                "start_page": section.get("start_page"),
                "end_page": section.get("end_page")
            }
        
        # Process norms within the section
        norms = section.get("norms", [])
        for norm in norms:
            norm_data = {
                "norm_id": norm.get("norm_id"),
                "text": norm.get("text")
            }
            
            # For now, use section positioning for norms
            # In the future, enhanced_lx_runner should provide individual norm positioning
            if section.get("start_page"):
                norm_data["positioning"] = {
                    "page_no": section.get("start_page"),
                    # These would come from actual Docling positioning data
                    "bbox": {
                        "l": 50,   # Default positioning - should be replaced with real data
                        "t": 700,
                        "r": 500,
                        "b": 650,
                        "coord_origin": "BOTTOMLEFT"
                    }
                }
            
            section_data["norms"].append(norm_data)
        
        positioning_data["sections"].append(section_data)
    
    return positioning_data


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


# Sandbox API endpoints

@app.get("/sandbox")
def sandbox():
    """Sandbox page for interactive norm filtering."""
    return render_template("sandbox.html")


@app.get("/api/sandbox/outputs")
def list_sandbox_outputs():
    """List available documents from database, or return 'All Norms' if no documents."""
    engine = get_db_engine()
    if not engine:
        return jsonify({"error": "Database not available. Please configure DATABASE_URL."}), 503
    
    try:
        from sqlalchemy import select, func
    except ImportError:
        return jsonify({"error": "SQLAlchemy not installed. Please install: pip install sqlalchemy psycopg"}), 503
    
    try:
        # Add ingest directory to path if not already there
        ingest_path = str(REPO_ROOT / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)
        from sql import documents, norms
        
        with engine.connect() as conn:
            # Try to get documents first
            docs_query = select(
                documents.c.id,
                documents.c.title,
                documents.c.jurisdiction,
                documents.c.language,
                documents.c.created_at
            ).order_by(documents.c.created_at.desc())
            
            doc_results = conn.execute(docs_query).fetchall()
            
            outputs = []
            
            # If documents exist, return them
            if doc_results:
                for doc in doc_results:
                    doc_id = str(doc[0])
                    title = doc[1] or f"Document {doc_id[:8]}"
                    jurisdiction = doc[2]
                    language = doc[3]
                    timestamp = doc[4].timestamp() if doc[4] else time.time()
                    
                    outputs.append({
                        "doc_id": doc_id,
                        "title": title,
                        "jurisdiction": jurisdiction,
                        "language": language,
                        "timestamp": timestamp
                    })
            else:
                # No documents, return "All Norms" option
                # Count total norms in database
                count_query = select(func.count(norms.c.id))
                total_norms = conn.execute(count_query).scalar()
                
                outputs.append({
                    "doc_id": "all",
                    "title": f"All Norms ({total_norms} total)",
                    "jurisdiction": None,
                    "language": None,
                    "timestamp": time.time()
                })
            
            return jsonify({"outputs": outputs, "total": len(outputs)})
    except Exception as e:
        import traceback
        return jsonify({
            "error": f"Failed to fetch documents: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500


@app.get("/api/sandbox/norms/<doc_id>")
def get_sandbox_norms(doc_id: str):
    """Get all norms from database for a specific document or all norms if doc_id is 'all'."""
    engine = get_db_engine()
    if not engine:
        return jsonify({"error": "Database not available. Please configure DATABASE_URL."}), 503
    
    try:
        from sqlalchemy import select, text
    except ImportError:
        return jsonify({"error": "SQLAlchemy not installed. Please install: pip install sqlalchemy psycopg"}), 503
    
    try:
        # Add ingest directory to path if not already there
        ingest_path = str(REPO_ROOT / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)
        from sql import norms, topics, norm_topics, documents
        
        with engine.connect() as conn:
            # Build norms query based on doc_id
            if doc_id == "all":
                # Get all norms regardless of document
                norms_query = select(
                    norms.c.id,
                    norms.c.extraction_class,
                    norms.c.extraction_text,
                    norms.c.obligation,
                    norms.c.norm_statement,
                    norms.c.applies_if_text,
                    norms.c.satisfied_if_text,
                    norms.c.exempt_if_text,
                    norms.c.section_id
                )
            else:
                # Get norms for specific document
                norms_query = select(
                    norms.c.id,
                    norms.c.extraction_class,
                    norms.c.extraction_text,
                    norms.c.obligation,
                    norms.c.norm_statement,
                    norms.c.applies_if_text,
                    norms.c.satisfied_if_text,
                    norms.c.exempt_if_text,
                    norms.c.section_id
                ).where(norms.c.document_id == text(f"'{doc_id}'::uuid"))
            
            norm_results = conn.execute(norms_query).fetchall()
            
            # Convert to JSON format
            norms_list = []
            for norm_row in norm_results:
                norm_id = str(norm_row[0])
                
                # Get topics for this norm
                topics_query = select(topics.c.code).select_from(
                    norm_topics.join(topics, norm_topics.c.topic_id == topics.c.id)
                ).where(norm_topics.c.norm_id == norm_row[0])
                
                topic_results = conn.execute(topics_query).fetchall()
                topic_codes = [t[0] for t in topic_results]
                
                norm_dict = {
                    "id": norm_id,
                    "extraction_class": norm_row[1],
                    "extraction_text": norm_row[2],
                    "obligation": norm_row[3],
                    "norm_statement": norm_row[4],
                    "applies_if": norm_row[5] or "TRUE",
                    "satisfied_if": norm_row[6],
                    "exempt_if": norm_row[7],
                    "section_id": norm_row[8],
                    "topics": topic_codes
                }
                norms_list.append(norm_dict)
            
            return jsonify({"norms": norms_list, "total": len(norms_list)})
    except Exception as e:
        import traceback
        return jsonify({
            "error": f"Error loading norms: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500


@app.get("/api/sandbox/features")
def get_sandbox_features():
    """Get feature definitions (questions) from database ordered by usage count."""
    engine = get_db_engine()
    if not engine:
        return jsonify({"error": "Database not available. Please configure DATABASE_URL."}), 503
    
    try:
        from sqlalchemy import select, func
    except ImportError:
        return jsonify({"error": "SQLAlchemy not installed. Please install: pip install sqlalchemy psycopg"}), 503
    
    try:
        # Add ingest directory to path if not already there
        ingest_path = str(REPO_ROOT / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)
        from sql import questions, norm_requirements
        
        with engine.connect() as conn:
            # Get all questions with their usage statistics
            # Order by occurrence count in norm_requirements table
            usage_query = select(
                questions.c.id,
                questions.c.key,
                questions.c.value_hint,
                questions.c.allowed_enum,
                func.count(norm_requirements.c.id).label('usage_count')
            ).select_from(
                questions.outerjoin(
                    norm_requirements,
                    questions.c.id == norm_requirements.c.question_id
                )
            ).group_by(
                questions.c.id,
                questions.c.key,
                questions.c.value_hint,
                questions.c.allowed_enum
            ).order_by(func.count(norm_requirements.c.id).desc())
            
            question_results = conn.execute(usage_query).fetchall()
            
            features = []
            for row in question_results:
                question_id = row[0]
                question_key = row[1]
                value_hint = row[2]  # value_type enum
                allowed_enum = row[3]  # array of allowed values
                usage_count = row[4]
                
                # Skip questions with zero usage
                if usage_count == 0:
                    continue
                
                # Determine feature type and values
                feature_type = 'categorical'
                values = []
                
                if value_hint:
                    if value_hint == 'BOOLEAN':
                        feature_type = 'categorical'
                        values = ['TRUE', 'FALSE']
                    elif value_hint in ['INTEGER', 'NUMERIC']:
                        if allowed_enum and len(allowed_enum) > 0:
                            # Enum with numeric values
                            feature_type = 'categorical'
                            values = allowed_enum
                        else:
                            # Numeric input
                            feature_type = 'int'
                            values = []
                    elif value_hint == 'STRING':
                        if allowed_enum and len(allowed_enum) > 0:
                            feature_type = 'categorical'
                            values = allowed_enum
                        else:
                            feature_type = 'categorical'
                            values = []
                    elif value_hint == 'ARRAY':
                        if allowed_enum and len(allowed_enum) > 0:
                            feature_type = 'categorical'
                            values = allowed_enum
                        else:
                            feature_type = 'categorical'
                            values = []
                    elif value_hint == 'ENUM':
                        feature_type = 'categorical'
                        values = allowed_enum if allowed_enum else []
                    else:
                        feature_type = 'categorical'
                        values = []
                
                # Format display name with usage count
                display_name = f"{question_key} ({usage_count})"
                
                features.append({
                    'id': question_id,
                    'name': question_key,
                    'display_name': display_name,
                    'type': feature_type,
                    'values': values,
                    'usage_count': usage_count,
                    'numeric': value_hint in ['INTEGER', 'NUMERIC'] if value_hint else False
                })
            
            return jsonify({"features": features, "total": len(features)})
    except Exception as e:
        import traceback
        return jsonify({
            "error": f"Error loading features: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500


@app.post("/api/sandbox/filter")
def filter_sandbox_norms():
    """Filter norms based on current filter selections using SQL-based filtering."""
    engine = get_db_engine()
    if not engine:
        return jsonify({"error": "Database not available. Please configure DATABASE_URL."}), 503
    
    try:
        from sqlalchemy import select, and_, or_, text, func
    except ImportError:
        return jsonify({"error": "SQLAlchemy not installed. Please install: pip install sqlalchemy psycopg"}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON data is required"}), 400
        
        doc_id = data.get('doc_id')
        filters = data.get('filters', {})  # {question_id: value}
        
        if not doc_id:
            return jsonify({"error": "doc_id is required"}), 400
        
        # Add ingest directory to path if not already there
        ingest_path = str(REPO_ROOT / "ingest")
        if ingest_path not in sys.path:
            sys.path.insert(0, ingest_path)
        from sql import norms, norm_requirements, norm_clause_groups, questions, topics, norm_topics
        
        with engine.connect() as conn:
            # If no filters, return all norms for the document (or all norms if doc_id is "all")
            if not filters:
                # Simple query for all norms
                if doc_id == "all":
                    norms_query = select(
                        norms.c.id,
                        norms.c.extraction_class,
                        norms.c.extraction_text,
                        norms.c.obligation,
                        norms.c.norm_statement,
                        norms.c.applies_if_text,
                        norms.c.satisfied_if_text,
                        norms.c.exempt_if_text,
                        norms.c.section_id
                    )
                else:
                    norms_query = select(
                        norms.c.id,
                        norms.c.extraction_class,
                        norms.c.extraction_text,
                        norms.c.obligation,
                        norms.c.norm_statement,
                        norms.c.applies_if_text,
                        norms.c.satisfied_if_text,
                        norms.c.exempt_if_text,
                        norms.c.section_id
                    ).where(norms.c.document_id == text(f"'{doc_id}'::uuid"))
                
                norm_results = conn.execute(norms_query).fetchall()
                
                norms_list = []
                for norm_row in norm_results:
                    norm_id = str(norm_row[0])
                    
                    # Get topics
                    topics_query = select(topics.c.code).select_from(
                        norm_topics.join(topics, norm_topics.c.topic_id == topics.c.id)
                    ).where(norm_topics.c.norm_id == norm_row[0])
                    topic_results = conn.execute(topics_query).fetchall()
                    topic_codes = [t[0] for t in topic_results]
                    
                    norms_list.append({
                        "id": norm_id,
                        "extraction_class": norm_row[1],
                        "extraction_text": norm_row[2],
                        "obligation": norm_row[3],
                        "norm_statement": norm_row[4],
                        "applies_if": norm_row[5] or "TRUE",
                        "satisfied_if": norm_row[6],
                        "exempt_if": norm_row[7],
                        "section_id": norm_row[8],
                        "topics": topic_codes
                    })
                
                return jsonify({
                    "norms": norms_list,
                    "total": len(norms_list),
                    "filtered": False
                })
            
            # With filters: Find norms that satisfy at least one disjunct
            # For each norm, check if any of its clause groups (disjuncts) satisfy all filters
            
            # Step 1: Get all norms for the document (or all norms if doc_id is "all")
            if doc_id == "all":
                all_norms_query = select(
                    norms.c.id,
                    norms.c.extraction_class,
                    norms.c.extraction_text,
                    norms.c.obligation,
                    norms.c.norm_statement,
                    norms.c.applies_if_text,
                    norms.c.satisfied_if_text,
                    norms.c.exempt_if_text,
                    norms.c.section_id
                )
            else:
                all_norms_query = select(
                    norms.c.id,
                    norms.c.extraction_class,
                    norms.c.extraction_text,
                    norms.c.obligation,
                    norms.c.norm_statement,
                    norms.c.applies_if_text,
                    norms.c.satisfied_if_text,
                    norms.c.exempt_if_text,
                    norms.c.section_id
                ).where(norms.c.document_id == text(f"'{doc_id}'::uuid"))
            
            all_norm_results = conn.execute(all_norms_query).fetchall()
            
            filtered_norms = []
            
            for norm_row in all_norm_results:
                norm_id_uuid = norm_row[0]
                norm_id = str(norm_id_uuid)
                
                # Get all APPLIES_IF clause groups for this norm
                groups_query = select(
                    norm_clause_groups.c.id
                ).where(
                    and_(
                        norm_clause_groups.c.norm_id == norm_id_uuid,
                        norm_clause_groups.c.clause == 'APPLIES_IF'
                    )
                )
                group_results = conn.execute(groups_query).fetchall()
                group_ids = [g[0] for g in group_results]
                
                # If no clause groups, norm always applies (trivial TRUE)
                if not group_ids:
                    norm_matches = True
                else:
                    # Check if any clause group satisfies all filters
                    norm_matches = False
                    
                    for group_id in group_ids:
                        # Get all requirements for this group
                        reqs_query = select(
                            norm_requirements.c.question_id,
                            norm_requirements.c.operator,
                            norm_requirements.c.expected_value
                        ).where(norm_requirements.c.group_id == group_id)
                        
                        req_results = conn.execute(reqs_query).fetchall()
                        
                        # Check if this group satisfies all filters
                        group_satisfies = True
                        
                        for req_row in req_results:
                            req_question_id = req_row[0]
                            req_operator = req_row[1]
                            req_expected = req_row[2]
                            
                            # Check if this requirement is in the filters
                            if req_question_id in filters:
                                filter_value = filters[req_question_id]
                                
                                # Compare based on operator
                                if req_operator == 'EQ':
                                    # Extract value from JSONB (it's stored as JSON string)
                                    expected_val = req_expected
                                    if isinstance(expected_val, str):
                                        expected_val = expected_val.strip('"')
                                    
                                    if str(filter_value) != str(expected_val):
                                        group_satisfies = False
                                        break
                                # Add more operator support as needed
                                else:
                                    # For now, only support EQ
                                    pass
                        
                        if group_satisfies:
                            norm_matches = True
                            break
                
                if norm_matches:
                    # Get topics
                    topics_query = select(topics.c.code).select_from(
                        norm_topics.join(topics, norm_topics.c.topic_id == topics.c.id)
                    ).where(norm_topics.c.norm_id == norm_id_uuid)
                    topic_results = conn.execute(topics_query).fetchall()
                    topic_codes = [t[0] for t in topic_results]
                    
                    filtered_norms.append({
                        "id": norm_id,
                        "extraction_class": norm_row[1],
                        "extraction_text": norm_row[2],
                        "obligation": norm_row[3],
                        "norm_statement": norm_row[4],
                        "applies_if": norm_row[5] or "TRUE",
                        "satisfied_if": norm_row[6],
                        "exempt_if": norm_row[7],
                        "section_id": norm_row[8],
                        "topics": topic_codes
                    })
            
            return jsonify({
                "norms": filtered_norms,
                "total": len(filtered_norms),
                "original_total": len(all_norm_results),
                "filtered": True
            })
        
    except Exception as e:
        import traceback
        return jsonify({
            "error": f"Error filtering norms: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500


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
