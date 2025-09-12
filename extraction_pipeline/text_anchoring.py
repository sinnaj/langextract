"""PDF text anchoring implementation for the extraction pipeline.

This module provides deterministic 3-stage text matching (exact → normalized → fuzzy)
with page-scoped character span matching and highlight quad generation.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Union
from fuzzywuzzy import fuzz
from .data_models import (
    TextAnchor, HighlightQuad, PageLocator, AnchoringSource
)


def normalize_text_for_matching(text: str) -> str:
    """Normalize text for matching (case-fold, collapse whitespace, canonicalize punctuation).
    
    Keeps parentheses and numbers as specified in the pipeline guide.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text suitable for matching
    """
    # Case-fold and collapse whitespace
    normalized = " ".join(text.strip().lower().split())
    
    # Canonicalize punctuation but keep parentheses and numbers
    # Replace common punctuation variations with standard forms
    normalized = re.sub(r'["""]', '"', normalized)
    normalized = re.sub(r"[''']", "'", normalized)
    normalized = re.sub(r'[–—]', '-', normalized)
    
    return normalized


def find_exact_match(page_text: str, norm_text: str) -> Optional[Tuple[int, int]]:
    """Find exact substring match (identity, case sensitive).
    
    If multiple exact hits, prefer the one whose surrounding 20–40 chars 
    best match the norm's context.
    
    Args:
        page_text: Text of the PDF page
        norm_text: Text to search for
        
    Returns:
        Tuple of (start, end) positions if found, None otherwise
    """
    matches = []
    start = 0
    
    while True:
        pos = page_text.find(norm_text, start)
        if pos == -1:
            break
        matches.append((pos, pos + len(norm_text)))
        start = pos + 1
    
    if not matches:
        return None
    
    if len(matches) == 1:
        return matches[0]
    
    # Multiple matches - use context to disambiguate
    # For now, return the first match
    # TODO: Implement context-based disambiguation
    return matches[0]


def find_normalized_match(page_text: str, norm_text: str) -> Optional[Tuple[int, int]]:
    """Find normalized match (case-fold, collapse whitespace, canonicalize punctuation).
    
    Args:
        page_text: Text of the PDF page
        norm_text: Text to search for
        
    Returns:
        Tuple of (start, end) positions in original page_text if found, None otherwise
    """
    normalized_page = normalize_text_for_matching(page_text)
    normalized_norm = normalize_text_for_matching(norm_text)
    
    pos = normalized_page.find(normalized_norm)
    if pos == -1:
        return None
    
    # Map back to original text positions
    # Simple approach: scan through original text to find matching portion
    words_norm = normalized_norm.split()
    if not words_norm:
        return None
    
    # Find the best matching sequence in original text
    page_words = page_text.lower().split()
    for i in range(len(page_words) - len(words_norm) + 1):
        # Check if this sequence matches
        page_sequence = page_words[i:i + len(words_norm)]
        if page_sequence == words_norm:
            # Found match, calculate character positions
            chars_before = len(' '.join(page_words[:i]))
            if chars_before > 0:
                chars_before += 1  # Add space before
            chars_match = len(' '.join(words_norm))
            return (chars_before, chars_before + chars_match)
    
    return None


def find_fuzzy_match(
    page_text: str, 
    norm_text: str, 
    min_score: float = 0.90
) -> Optional[Tuple[int, int, float]]:
    """Find fuzzy match with token-set ratio ≥ min_score.
    
    Guardrails:
    - Only accept if matched window length is ≥ 80% of norm text length
    - If >1 candidate within 2% score, mark as ambiguous
    
    Args:
        page_text: Text of the PDF page
        norm_text: Text to search for
        min_score: Minimum fuzzy match score (0.0 to 1.0)
        
    Returns:
        Tuple of (start, end, score) if found, None otherwise
    """
    norm_len = len(norm_text)
    min_window_len = int(norm_len * 0.8)  # 80% of norm text length
    max_window_len = min(len(page_text), norm_len * 2)
    
    candidates = []
    
    # Slide a window across the page text
    step_size = max(1, norm_len // 10)  # Step by 10% of norm length for efficiency
    
    for window_size in range(min_window_len, max_window_len + 1, step_size):
        for i in range(0, len(page_text) - window_size + 1, step_size):
            window = page_text[i:i + window_size]
            try:
                score = fuzz.token_set_ratio(norm_text, window) / 100.0
                
                if score >= min_score:
                    candidates.append((i, i + window_size, score))
            except Exception:
                # Skip on any fuzzy matching errors
                continue
    
    if not candidates:
        return None
    
    # Sort by score descending
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    # Check for ambiguity (multiple candidates within 2% score)
    best_score = candidates[0][2]
    similar_candidates = [c for c in candidates if abs(c[2] - best_score) <= 0.02]
    
    if len(similar_candidates) > 1:
        # Ambiguous - return None to indicate fallback needed
        return None
    
    return candidates[0]


def anchor_norm_to_pdf(
    norm_text: str,
    section_pages: List[int],
    page_corpus: Dict[int, Dict[str, Any]]
) -> Union[List[TextAnchor], PageLocator]:
    """Anchor norm text to PDF using deterministic 3-stage matching.
    
    Args:
        norm_text: The norm text to anchor
        section_pages: List of pages in the section interval
        page_corpus: Dict mapping page numbers to page data with 'text' and 'lines'
        
    Returns:
        List of TextAnchor objects if successful, PageLocator if fallback needed
    """
    anchors = []
    
    for page in section_pages:
        if page not in page_corpus:
            continue
            
        page_data = page_corpus[page]
        page_text = page_data.get('text', '')
        page_lines = page_data.get('lines', [])
        
        if not page_text:
            continue
        
        # Stage 1: Exact match
        exact_match = find_exact_match(page_text, norm_text)
        if exact_match:
            start, end = exact_match
            quads = build_quads_from_char_span(start, end, page_lines, page_text)
            anchor = TextAnchor(
                page=page,
                quads=quads,
                source=AnchoringSource.EXACT,
                confidence=1.0,
                char_span=(start, end)
            )
            anchors.append(anchor)
            continue
        
        # Stage 2: Normalized match
        normalized_match = find_normalized_match(page_text, norm_text)
        if normalized_match:
            start, end = normalized_match
            quads = build_quads_from_char_span(start, end, page_lines, page_text)
            anchor = TextAnchor(
                page=page,
                quads=quads,
                source=AnchoringSource.NORMALIZED,
                confidence=0.9,
                char_span=(start, end)
            )
            anchors.append(anchor)
            continue
        
        # Stage 3: Fuzzy match
        fuzzy_result = find_fuzzy_match(page_text, norm_text)
        if fuzzy_result:
            start, end, score = fuzzy_result
            quads = build_quads_from_char_span(start, end, page_lines, page_text)
            anchor = TextAnchor(
                page=page,
                quads=quads,
                source=AnchoringSource.FUZZY,
                confidence=score,
                char_span=(start, end)
            )
            anchors.append(anchor)
    
    if anchors:
        return anchors
    
    # Fallback to section-level locator
    return PageLocator(
        page_range=(min(section_pages), max(section_pages)),
        reason="not_found"
    )


def build_quads_from_char_span(
    start: int,
    end: int,
    page_lines: List[Dict[str, Any]],
    page_text: str
) -> List[HighlightQuad]:
    """Build highlight quads from character span using Docling line data.
    
    Args:
        start: Starting character position in page text
        end: Ending character position in page text
        page_lines: List of line data with 'text', 'charspan', and 'bbox'
        page_text: Full page text
        
    Returns:
        List of HighlightQuad objects
    """
    quads = []
    
    # Find lines that overlap with the character span
    for line_data in page_lines:
        line_text = line_data.get('text', '')
        line_charspan = line_data.get('charspan', {})
        line_bbox = line_data.get('bbox', {})
        
        if not line_charspan or not line_bbox:
            continue
            
        line_start = line_charspan.get('start', 0)
        line_end = line_charspan.get('end', 0)
        
        # Check if this line overlaps with our target span
        if line_end <= start or line_start >= end:
            continue  # No overlap
        
        # Calculate the portion of the line that overlaps
        overlap_start = max(start, line_start)
        overlap_end = min(end, line_end)
        
        # Calculate the sub-bbox for the overlapping portion
        if line_start < line_end and line_text:
            # Proportion of the line that's highlighted
            line_len = line_end - line_start
            start_ratio = (overlap_start - line_start) / line_len if line_len > 0 else 0
            end_ratio = (overlap_end - line_start) / line_len if line_len > 0 else 1
            
            # Get bbox coordinates
            x1 = line_bbox.get('x', 0)
            y1 = line_bbox.get('y', 0)
            x2 = x1 + line_bbox.get('width', 0)
            y2 = y1 + line_bbox.get('height', 0)
            
            # Calculate sub-bbox (approximate horizontally by character proportion)
            width = x2 - x1
            sub_x1 = x1 + (width * start_ratio)
            sub_x2 = x1 + (width * end_ratio)
            
            # Create quad (rectangle in this case)
            quad = HighlightQuad(
                x1=sub_x1, y1=y1,
                x2=sub_x2, y2=y1,
                x3=sub_x2, y3=y2,
                x4=sub_x1, y4=y2
            )
            quads.append(quad)
    
    return quads


def create_page_corpus_from_docling(docling_document: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """Create page corpus from Docling document for anchoring.
    
    Args:
        docling_document: Parsed Docling document
        
    Returns:
        Dict mapping page numbers to page data with 'text' and 'lines'
    """
    corpus = {}
    
    # Extract pages from Docling document structure
    # This is a simplified implementation - actual structure may vary
    pages = docling_document.get('pages', [])
    
    for page_data in pages:
        page_num = page_data.get('page', 1)
        
        # Combine text from all elements on the page
        page_text = ""
        page_lines = []
        char_offset = 0
        
        elements = page_data.get('elements', [])
        for element in elements:
            element_text = element.get('text', '')
            if element_text:
                # Add character span info
                element_start = char_offset
                element_end = char_offset + len(element_text)
                
                # Store line info for quad generation
                bbox = element.get('bbox', {})
                line_info = {
                    'text': element_text,
                    'charspan': {'start': element_start, 'end': element_end},
                    'bbox': bbox
                }
                page_lines.append(line_info)
                
                page_text += element_text + " "
                char_offset += len(element_text) + 1
        
        corpus[page_num] = {
            'text': page_text.strip(),
            'lines': page_lines
        }
    
    return corpus