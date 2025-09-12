"""Content chunking utilities for enhanced extraction pipeline.

This module provides intelligent content splitting and chunking strategies
for processing large documents efficiently while maintaining context.
"""

import re
from typing import List, Dict, Any


def split_large_content(content: str, max_chars: int) -> List[str]:
    """Basic content splitting by character count.
    
    Args:
        content: Text content to split
        max_chars: Maximum characters per chunk
        
    Returns:
        List of content chunks
    """
    if len(content) <= max_chars:
        return [content]
        
    chunks = []
    start = 0
    
    while start < len(content):
        end = start + max_chars
        if end >= len(content):
            chunks.append(content[start:])
            break
            
        # Try to break at a reasonable boundary
        chunk = content[start:end]
        
        # Look for paragraph break
        last_paragraph = chunk.rfind('\n\n')
        if last_paragraph > max_chars // 2:
            chunks.append(content[start:start + last_paragraph])
            start += last_paragraph + 2
            continue
            
        # Look for sentence break
        last_sentence = max(chunk.rfind('. '), chunk.rfind('.\n'))
        if last_sentence > max_chars // 2:
            chunks.append(content[start:start + last_sentence + 1])
            start += last_sentence + 2
            continue
            
        # Fallback to word boundary
        last_space = chunk.rfind(' ')
        if last_space > max_chars // 2:
            chunks.append(content[start:start + last_space])
            start += last_space + 1
        else:
            # Force split at max_chars
            chunks.append(chunk)
            start = end
            
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def split_large_content_safe(content: str, max_chars: int, section_title: str = "") -> List[str]:
    """Safe content splitting with context preservation.
    
    This function tries multiple strategies to split content intelligently:
    1. Preserve complete paragraphs when possible
    2. Maintain sentence boundaries
    3. Keep word boundaries intact
    4. Add context headers for multi-part splits
    
    Args:
        content: Text content to split
        max_chars: Maximum characters per chunk
        section_title: Section title for context headers
        
    Returns:
        List of content chunks with preserved context
    """
    if len(content) <= max_chars:
        return [content]
    
    print(f"[INFO] Splitting large content ({len(content)} chars) for section: {section_title}")
    
    chunks = []
    
    # First, try to split by major structural elements
    major_splits = _split_by_major_elements(content, max_chars)
    
    for i, section in enumerate(major_splits):
        if len(section) <= max_chars:
            # Add context header for multi-part sections
            if len(major_splits) > 1:
                header = f"=== {section_title} (Part {i+1}/{len(major_splits)}) ===\n\n"
                chunks.append(header + section)
            else:
                chunks.append(section)
        else:
            # Further split large sections
            sub_chunks = _emergency_split_with_context(section, max_chars, section_title, i+1, len(major_splits))
            chunks.extend(sub_chunks)
    
    return chunks


def _split_by_major_elements(content: str, max_chars: int) -> List[str]:
    """Split content by major structural elements like headings and paragraphs.
    
    Args:
        content: Text content to split
        max_chars: Target maximum characters per section
        
    Returns:
        List of content sections
    """
    # Try to split by headings first
    heading_pattern = r'\n(#{1,6}\s+.+|[A-Z][^.\n]{10,100})\n'
    sections = re.split(heading_pattern, content)
    
    if len(sections) > 3:  # If we found meaningful splits
        result = []
        current_section = ""
        
        for section in sections:
            if not section or section.isspace():
                continue
                
            # Check if adding this section would exceed limit
            if current_section and len(current_section + section) > max_chars:
                if current_section.strip():
                    result.append(current_section.strip())
                current_section = section
            else:
                current_section += section
                
        if current_section.strip():
            result.append(current_section.strip())
            
        return result if result else [content]
    
    # Fallback: split by paragraphs
    paragraphs = content.split('\n\n')
    if len(paragraphs) > 1:
        result = []
        current_section = ""
        
        for para in paragraphs:
            if not para.strip():
                continue
                
            if current_section and len(current_section + '\n\n' + para) > max_chars:
                if current_section.strip():
                    result.append(current_section.strip())
                current_section = para
            else:
                current_section += '\n\n' + para if current_section else para
                
        if current_section.strip():
            result.append(current_section.strip())
            
        return result if result else [content]
    
    return [content]


def _emergency_split_with_context(content: str, max_chars: int, section_title: str, part_num: int, total_parts: int) -> List[str]:
    """Emergency content splitting when other methods fail.
    
    Args:
        content: Content to split
        max_chars: Maximum characters per chunk
        section_title: Original section title
        part_num: Current part number
        total_parts: Total number of parts
        
    Returns:
        List of content chunks with context headers
    """
    basic_chunks = split_large_content(content, max_chars)
    
    result = []
    for i, chunk in enumerate(basic_chunks):
        if len(basic_chunks) > 1:
            header = f"=== {section_title} (Part {part_num}.{i+1}/{total_parts}.{len(basic_chunks)}) ===\n\n"
            result.append(header + chunk)
        else:
            result.append(chunk)
            
    return result


def emergency_chunk_content(content: str, max_chars: int) -> List[str]:
    """Last resort content chunking when all else fails.
    
    This function performs aggressive splitting to ensure content fits
    within memory constraints, even if it breaks semantic boundaries.
    
    Args:
        content: Content to chunk
        max_chars: Maximum characters per chunk
        
    Returns:
        List of content chunks
    """
    if len(content) <= max_chars:
        return [content]
    
    chunks = []
    sentences = content.split('. ')
    current_chunk = ""
    
    for sentence in sentences:
        # Handle very long sentences
        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # Split long sentence
            sentence_chunks = emergency_split_sentence(sentence, max_chars)
            chunks.extend(sentence_chunks)
        else:
            # Check if adding this sentence exceeds limit
            test_chunk = current_chunk + '. ' + sentence if current_chunk else sentence
            if len(test_chunk) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = test_chunk
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


def emergency_split_sentence(sentence: str, max_chars: int) -> List[str]:
    """Split a very long sentence at word boundaries.
    
    Args:
        sentence: Sentence to split
        max_chars: Maximum characters per chunk
        
    Returns:
        List of sentence chunks
    """
    if len(sentence) <= max_chars:
        return [sentence]
    
    words = sentence.split(' ')
    chunks = []
    current_chunk = ""
    
    for word in words:
        if len(word) > max_chars:
            # Handle extremely long words (rare)
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            # Split long word at character boundaries
            for i in range(0, len(word), max_chars):
                chunks.append(word[i:i + max_chars])
        else:
            test_chunk = current_chunk + ' ' + word if current_chunk else word
            if len(test_chunk) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk = test_chunk
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks