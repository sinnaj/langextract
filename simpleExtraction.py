import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import importlib.util   
import langextract as lx
from dotenv import load_dotenv
from langextract import data_lib
from langextract import providers
import time
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from absl import logging as absl_logging
import requests
from langextract import factory
from langextract.resolver import ResolverParsingError
from langextract.core import data as core_data

# Load .env so OPENAI_API_KEY is available when running from terminal
load_dotenv()
absl_logging.set_verbosity(absl_logging.ERROR)

# Ensure provider registry is populated even when schema path is used
providers.load_builtins_once()
providers.load_plugins_once()

# --- Simple timestamped logger to both console and file ---
LOG_FILE = "simpleExtraction.log"

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(line + "\n")
    except Exception:
        pass

OPENROUTER_KEY = os.environ.get("OPENAI_API_KEY")
prompt = Path("input_promptfiles/extraction_prompt.md")
# Optional appendix that nudges the model to emit Tags/Questions consistently
semantics_appendix = Path("input_semanticsfiles/prompt_appendix_entity_semantics_min.md")
examples_path = Path("input_examplefiles/examples_enhanced.py")
# Use forward slashes or raw string to avoid escape sequences on Windows
model = "google/gemini-2.5-flash"

# Load examples list from the python module file
examples: List[Any] = []
if examples_path.exists():
    try:
        spec = importlib.util.spec_from_file_location("lx_examples", str(examples_path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            ex = getattr(module, "EXAMPLES", None)
            if isinstance(ex, list):
                examples = ex
    except Exception as e:
        print(f"[WARN] Failed to load EXAMPLES from {examples_path}: {e}")

# Ensure MODEL_TEMPERATURE, lx, and lm_params are defined before this block
if not OPENROUTER_KEY:
    log("[FATAL] OPENAI_API_KEY is not set. Add it to your .env or environment for OpenRouter usage.")
    raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env or environment for OpenRouter usage.")

# Read local file contents as input text (UTF-8 with fallback)
file_path = Path(r"C:\Projects\Arqio\LangExtract\langextract\docs\test_docs\small_test_norms.txt")
try:
    input_source = file_path.read_text(encoding="utf-8")
except UnicodeDecodeError:
    input_source = file_path.read_text(encoding="latin-1")
log(f"[INFO] Loaded local file {file_path} ({len(input_source)} chars)")

# Basic URL preflight to surface network/content-type issues early
def _is_url(s: str) -> bool:
    return isinstance(s, str) and (s.startswith("http://") or s.startswith("https://"))

if _is_url(input_source):
    try:
        log(f"[INFO] Preflight HEAD {input_source}")
        h = requests.head(input_source, allow_redirects=True, timeout=20)
        log(f"[INFO] HEAD status={h.status_code} content-type={h.headers.get('Content-Type','')} length={h.headers.get('Content-Length','?')}")
    except Exception as e:
        log(f"[WARN] HEAD request failed: {e}")

# Explicitly route to OpenAI-compatible provider via OpenRouter
cfg = factory.ModelConfig(
    model_id=model,
    provider="OpenAILanguageModel",  # Explicit provider class to route via OpenRouter's OpenAI-compatible API
    provider_kwargs={
        "api_key": OPENROUTER_KEY,
        "base_url": "https://openrouter.ai/api/v1",
        "temperature": 0.1,
        # Encourage strict JSON mode on providers that support it
        "format_type": core_data.FormatType.JSON,
        "max_workers": 20,
    },
)

# Build prompt description with optional semantics appendix to drive Tag emission
prompt_description = prompt.read_text(encoding="utf-8") if prompt.exists() else ""
if semantics_appendix.exists():
    try:
        prompt_description += "\n\n" + semantics_appendix.read_text(encoding="utf-8")
        log(f"[INFO] Appended semantics appendix: {semantics_appendix}")
    except Exception as e:
        log(f"[WARN] Failed to read semantics appendix {semantics_appendix}: {e}")

extract_kwargs = dict(
    text_or_documents=input_source,
    ## text_or_documents=document_path.read_text(encoding="utf-8") if document_path.exists() else "",
    prompt_description=prompt_description,
    examples=examples,
    config=cfg,
    # IMPORTANT: The compact spec forbids markdown fences; keep resolver/model non-fenced JSON
    fence_output=False,
    # Enable schema constraints so examples inform the provider when supported
    use_schema_constraints=True,
    extraction_passes=1,    # Improves recall through multiple passes
    max_workers=20,         # Parallel processing for speed
    max_char_buffer=5000,   # Smaller contexts for better accuracy
    ## debug=False             # Reduce absl DEBUG noise during normal runs
)

# Make resolver expectations explicit and consistent with non-fenced JSON
extract_kwargs["resolver_params"] = {
    "fence_output": False,
    "format_type": core_data.FormatType.JSON,
}

# Run the extraction with a heartbeat so terminal doesn't just go silent
log("[INFO] Invoking lx.extract...")
start = time.time()
def _do_extract():
    try:
        return lx.extract(**extract_kwargs)
    except ResolverParsingError:
        log("[WARN] Resolver failed to parse JSON; retrying with fenced YAML...")
        # Switch provider and extractor to YAML format and retain fences
        cfg_yaml = factory.ModelConfig(
            model_id=model,
            provider="OpenAILanguageModel",
            provider_kwargs={
                **cfg.provider_kwargs,
                "format_type": core_data.FormatType.YAML,
            },
        )
        ek = dict(extract_kwargs)
        ek["config"] = cfg_yaml
        ek["fence_output"] = True
        ek["use_schema_constraints"] = True
        ek["debug"] = extract_kwargs.get("debug", False)
        ek["format_type"] = core_data.FormatType.YAML
        ek["resolver_params"] = {"fence_output": True, "format_type": core_data.FormatType.YAML}
        return lx.extract(**ek)

result = None
with ThreadPoolExecutor(max_workers=1) as ex:
    fut = ex.submit(_do_extract)
    spinner = "|/-\\"
    i = 0
    while True:
        try:
            # Poll with a short timeout to allow heartbeat prints
            result = fut.result(timeout=5)
            break
        except TimeoutError:
            i = (i + 1) % len(spinner)
            elapsed = int(time.time() - start)
            log(f"[HEARTBEAT] extract running... {spinner[i]} elapsed={elapsed}s")
        except Exception as e:
            log(f"[ERROR] Extraction raised: {e}")
            tb = traceback.format_exc()
            log(tb)
            raise
log(f"[INFO] Extraction completed in {time.time()-start:.1f}s — saving artifacts...")

# Save the results to a JSONL file (force UTF-8, avoid locale cp1252 on Windows)
doc_dict = data_lib.annotated_document_to_dict(result)
with open("extraction_results.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps(doc_dict, ensure_ascii=False) + "\n")

# Generate the visualization directly from the AnnotatedDocument
html_content = lx.visualize(result)
with open("visualization.html", "w", encoding="utf-8") as f:
    if hasattr(html_content, 'data'):
        f.write(html_content.data)  # For Jupyter/Colab
    else:
        f.write(html_content)