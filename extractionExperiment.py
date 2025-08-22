"""Comprehensive extraction runner aligned with `prompts/extraction_prompt.md`.

Imperative Goal:
  Exercise the full rich schema (Norms, Tags, Locations, Questions, Consequences, Parameters)
  specified in `extraction_prompt.md`, provide diverse few-shot guidance, invoke the model,
  validate & normalize output, and persist structured JSON for downstream ingestion.

Key Features:
  * Loads authoritative prompt from file (single source of truth).
  * Few-shot examples for each extraction class (Norm, Tag, Location, Question, Consequence, Parameter) using the specified DSL grammar (UPPERCASE.DOTCASE, IN[], ; OR separation, geo operators, HAS()).
  * Post-run validation: required top-level keys, ID reference integrity, DSL surface heuristics.
  * Legacy fallback wrapper (if model returns only classic `extractions` list) → upgrade into rich schema skeleton.
  * Optional heuristic enrichment (priority scoring, parameter derivation) if missing.
  * Glossary creation for discovered DSL field paths.

NOTE: This is an iterative development harness. For production scaling (multi-chunk PDF ingestion,
ontology merging across runs, persistent ID registry, and deduplication) implement specialized
pipelines beyond this script.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from datetime import datetime

from dotenv import load_dotenv
import langextract as lx


USE_OPENROUTER = os.getenv("USE_OPENROUTER", "1").lower() in {"1","true","yes"}
OPENROUTER_KEY = os.environ.get("OPENAI_API_KEY")  # repurposed for OpenRouter
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if USE_OPENROUTER:
    if not OPENROUTER_KEY:
        print("WARNING: OPENROUTER (OPENAI_API_KEY) key not set – OpenRouter call will fail.", file=sys.stderr)
else:
    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set – direct Gemini call will likely fail.", file=sys.stderr)

PROMPT_FILE = Path("prompts/extraction_prompt.md")
OUTPUT_FILE = Path("rich_norms_full.json")
GLOSSARY_FILE = Path("dsl_glossary.json")
MAX_NORMS_PER_5K = 10  # matches spec guidance
MODEL_ID = "google/gemini-2.5-flash" if USE_OPENROUTER else "gemini-2.5-flash"
MODEL_TEMPERATURE = 0.15



def getConfig(
  PROMPT_FILE: str,
  OUTPUT_FILE: str,
  GLOSSARY_FILE: str,
  MAX_NORMS_PER_5K: int,
  MODEL_ID: str,
  MODEL_TEMPERATURE: float,
  TEACH_FILE: Optional[str],
) -> Dict[str, Any]:
  """Set module-level config variables from provided values and return a config dict.

  Note: uses globals() to avoid 'global' conflicts with parameter names.
  Coerces types to expected module-level types (Path/int/float/str).
  """
  pf = Path(PROMPT_FILE) if not isinstance(PROMPT_FILE, Path) else PROMPT_FILE
  of = Path(OUTPUT_FILE) if not isinstance(OUTPUT_FILE, Path) else OUTPUT_FILE
  gf = Path(GLOSSARY_FILE) if not isinstance(GLOSSARY_FILE, Path) else GLOSSARY_FILE
  tf = PATH(TEACH_FILE) if TEACH_FILE and not isinstance(TEACH_FILE, Path) else TEACH_FILE
  max_norms = int(MAX_NORMS_PER_5K)
  model_id = str(MODEL_ID)
  model_temp = float(MODEL_TEMPERATURE)

  # Assign to module-level variables
  g = globals()
  g["PROMPT_FILE"] = pf
  g["OUTPUT_FILE"] = of
  g["GLOSSARY_FILE"] = gf
  g["MAX_NORMS_PER_5K"] = max_norms
  g["MODEL_ID"] = model_id
  g["MODEL_TEMPERATURE"] = model_temp
  g["TEACH_FILE"] = TEACH_FILE
  return {
    "PROMPT_FILE": pf,
    "OUTPUT_FILE": of,
    "GLOSSARY_FILE": gf,
    "MAX_NORMS_PER_5K": max_norms,
    "MODEL_ID": model_id,
    "MODEL_TEMPERATURE": model_temp,
  }

if not PROMPT_FILE.exists():
    print(f"FATAL: Prompt file missing at {PROMPT_FILE}", file=sys.stderr)
    sys.exit(1)

PROMPT_DESCRIPTION = PROMPT_FILE.read_text(encoding="utf-8")
