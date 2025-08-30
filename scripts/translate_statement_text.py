from __future__ import annotations

"""
Translate all "statement_text" fields in a JSON file from Spanish to English.

Usage (PowerShell):
  python scripts/translate_statement_text.py <input.json> [<output.json>]

If <output.json> is not provided, the script writes a sibling file named
"output_en.json" next to the input file.

Notes:
- This is an offline, deterministic translator based on simple phrase and word
  mappings. It preserves JSON structure and only touches values under the key
  "statement_text".
- Extend PHRASES and WORDS below to improve translation quality as needed.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


# Ordered phrase replacements (match on lowercase text; longest first)
PHRASES: List[Tuple[str, str]] = [
    # Domain-specific long forms first
    (
        "este documento básico (db) tiene por objeto establecer reglas y procedimientos que permiten cumplir las exigencias básicas de seguridad en caso de incendio",
        "This Basic Document (DB) aims to establish rules and procedures that make it possible to meet the basic fire safety requirements",
    ),
    (
        "las secciones de este db se corresponden con las exigencias básicas si 1 a si 6",
        "The sections of this DB correspond to the basic requirements SI 1 to SI 6",
    ),
    (
        "la correcta aplicación de cada sección supone el cumplimiento de la exigencia básica correspondiente",
        "Proper application of each section implies compliance with the corresponding basic requirement",
    ),
    # Common legal/technical connectors
    ("tiene por objeto", "aims to"),
    ("tiene por finalidad", "is intended to"),
    ("con el objeto de", "in order to"),
    ("con el fin de", "in order to"),
    ("de acuerdo con", "in accordance with"),
    ("de acuerdo a", "according to"),
    ("en caso de incendio", "in case of fire"),
    ("en todo caso", "in any case"),
    ("debe cumplirse", "must be complied with"),
    ("debe cumplir", "must comply with"),
    ("debe aplicarse", "must be applied"),
    ("aplicación de", "application of"),
    ("cumplimiento de", "compliance with"),
    ("se considerará", "will be considered"),
    ("se considera", "is considered"),
    ("la aplicación correcta", "the proper application"),
]

# Word-level dictionary (lowercase; accents included when common)
WORDS: Dict[str, str] = {
    # articles and function words
    "el": "the",
    "la": "the",
    "los": "the",
    "las": "the",
    "un": "a",
    "una": "a",
    "y": "and",
    "o": "or",
    "de": "of",
    "del": "of",
    "al": "to",
    "en": "in",
    "con": "with",
    "sin": "without",
    "por": "by",
    "para": "for",
    "según": "according to",
    "segun": "according to",
    "si": "if",
    "cuando": "when",
    "donde": "where",
    "que": "that",

    # common verbs/nouns
    "debe": "must",
    "deben": "must",
    "podrá": "may",
    "podran": "may",
    "permiten": "allow",
    "permite": "allows",
    "permitirá": "will allow",
    "cumplir": "comply with",
    "cumplimiento": "compliance",
    "cumplen": "meet",
    "cumpla": "meets",
    "cumplan": "meet",
    "establecer": "establish",
    "establece": "establishes",
    "establezcan": "establish",
    "aplicación": "application",
    "aplicar": "apply",
    "aplicarse": "be applied",
    "exigencias": "requirements",
    "exigencia": "requirement",
    "seguridad": "safety",
    "incendio": "fire",
    "incendios": "fires",
    "documento": "document",
    "básico": "basic",
    "básica": "basic",
    "básicas": "basic",
    "requisito": "requirement",
    "requisitos": "requirements",
    "conjunto": "set",
    "satisface": "satisfies",
    "sección": "section",
    "secciones": "sections",
    "correcta": "proper",
    "correspondiente": "corresponding",
    "implica": "implies",
    "supone": "entails",
    "norma": "rule",
    "general": "general",
    "tabla": "table",
    "ocupación": "occupancy",
    "ocupacion": "occupancy",
    "edificio": "building",
    "edificios": "buildings",
    # acronyms (kept uppercase by post step too)
    "db": "DB",
    "si": "SI",
}

TOKEN_RE = re.compile(r"(\w+|\s+|[^\w\s])", re.UNICODE)

# Optional OCR/typo fixes before translation
OCR_FIXES: Tuple[Tuple[str, str], ...] = (
    ("secaciones", "secciones"),
)


def _apply_ocr_fixes(s: str) -> str:
    out = s
    for a, b in OCR_FIXES:
        out = out.replace(a, b)
    return out


def _post_cleanup(result: str) -> str:
    # Grammar/phrasing polish (very light)
    fixes: Tuple[Tuple[str, str], ...] = (
        ("document basic", "Basic Document"),
        ("allow comply with", "allow compliance with"),
        ("allow to comply with", "allow compliance with"),
        (
            "aims to establish rules and procedures that allow compliance with",
            "aims to establish rules and procedures that make it possible to meet",
        ),
        ("requirements basic", "basic requirements"),
        ("requirement basic", "basic requirement"),
        ("correct application", "proper application"),
    )
    out = result
    for a, b in fixes:
        out = out.replace(a, b)
    # Keep DB and SI capitalization
    out = re.sub(r"\bdb\b", "DB", out)
    out = re.sub(r"\bsi\b", "SI", out)
    return out


def translate_text(text: str) -> str:
    # Lowercase working copy for phrase/word matching
    lower = _apply_ocr_fixes(text).lower()
    # phrase replacements (longest first)
    for es, en in sorted(PHRASES, key=lambda p: len(p[0]), reverse=True):
        lower = lower.replace(es, en)
    # token-wise replacements to preserve punctuation/spacing
    tokens = TOKEN_RE.findall(lower)
    out_tokens: List[str] = []
    for t in tokens:
        if not t.strip():
            out_tokens.append(t)
            continue
        if t.isalpha():
            out_tokens.append(WORDS.get(t, t))
        else:
            out_tokens.append(t)
    result = "".join(out_tokens)
    result = _post_cleanup(result)
    # Capitalize sentence start if original started with uppercase
    if text[:1].isupper() and result:
        result = result[:1].upper() + result[1:]
    return result


def transform(obj: Any, keys: Tuple[str, ...], counts: Dict[str, int]) -> Any:
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k in keys and isinstance(v, str):
                new_obj[k] = translate_text(v)
                counts[k] = counts.get(k, 0) + 1
            else:
                new_obj[k] = transform(v, keys, counts)
        return new_obj
    if isinstance(obj, list):
        return [transform(v, keys, counts) for v in obj]
    return obj


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: translate_statement_text.py <input.json> [<output.json>] [--also-notes]")
        return 2
    inp = Path(argv[1])
    if not inp.exists():
        print(f"Input not found: {inp}")
        return 2
    # parse optional args
    outp_arg = None
    also_notes = False
    # permit either: script.py in out [--also-notes]  OR script.py in [--also-notes]
    for a in argv[2:]:
        if a == "--also-notes":
            also_notes = True
        elif outp_arg is None and not a.startswith("--"):
            outp_arg = a

    outp = Path(outp_arg) if outp_arg else inp.with_name("output_en.json")
    try:
        data = json.loads(inp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        return 1
    keys: Tuple[str, ...] = ("statement_text",) + (("notes",) if also_notes else tuple())
    counts: Dict[str, int] = {}
    new_data = transform(data, keys, counts)
    outp.write_text(json.dumps(new_data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(counts.values())
    keys_str = ", ".join([f"{k}={counts.get(k,0)}" for k in keys])
    print(f"Updated JSON written to: {outp}")
    print(f"Translated fields: {total} ({keys_str})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
