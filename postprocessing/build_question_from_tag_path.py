from postprocessing.humanize_segment import humanize_segment
from testExtraction_3_norms_min_copy import QUESTION_VERB_MAP


def build_question_from_tag_path(tag_path: str) -> str:
    parts = tag_path.split('.') if tag_path else []
    leaf = parts[-1] if parts else ''
    if leaf in QUESTION_VERB_MAP:
        return QUESTION_VERB_MAP[leaf]
    # Generic fallback
    base = humanize_segment(leaf or 'valor')
    return f"¿Cuál es el {base}?" if not base.endswith('?') else base