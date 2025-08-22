from typing import List, Tuple


def chunk_text(text: str, max_chars: int = 4000, overlap: int = 350) -> List[Tuple[int,str]]:
    """Produce (offset, substring) pairs covering full text.
    Keeps mild overlap to avoid boundary loss. Offsets are absolute char positions in original text.
    """
    spans: List[Tuple[int,str]] = []
    i = 0
    n = len(text)
    while i < n:
        end = min(n, i + max_chars)
        spans.append((i, text[i:end]))
        if end >= n:
            break
        # step forward with overlap
        i = end - overlap
        if i < 0 or i >= n:
            break
    return spans