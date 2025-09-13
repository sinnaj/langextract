"""Enhanced section-based chunking for the extraction pipeline.

This module provides ToC-interval-based chunking with stable path-based section IDs
and integration with PDF ToC extraction and headline fixes.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from .data_models import EnhancedSection, make_deterministic_id, normalize_text_for_id


def convert_table_to_markdown(table_data: Dict[str, Any]) -> str:
    """Convert Docling table data to markdown format.
    
    Args:
        table_data: Table data from DoclingDocument with 'table_cells' structure
        
    Returns:
        Markdown representation of the table
    """
    table_cells = table_data.get('table_cells', [])
    if not table_cells:
        return ""
    
    # Group cells by row and column indices
    rows = {}
    max_col = 0
    max_row = 0
    
    for cell in table_cells:
        row_start = cell.get('start_row_offset_idx', 0)
        col_start = cell.get('start_col_offset_idx', 0)
        text = cell.get('text', '').strip()
        
        if row_start not in rows:
            rows[row_start] = {}
        
        rows[row_start][col_start] = text
        max_col = max(max_col, col_start)
        max_row = max(max_row, row_start)
    
    # Build markdown table
    markdown_lines = []
    
    for row_idx in range(max_row + 1):
        if row_idx not in rows:
            continue
            
        row_cells = []
        for col_idx in range(max_col + 1):
            cell_text = rows[row_idx].get(col_idx, '')
            # Clean up cell text and escape markdown special characters
            cell_text = cell_text.replace('|', '\\|').replace('\n', ' ')
            row_cells.append(cell_text)
        
        # Create markdown table row
        markdown_lines.append('| ' + ' | '.join(row_cells) + ' |')
        
        # Add header separator after first row
        if row_idx == 0:
            separator = '| ' + ' | '.join(['---'] * (max_col + 1)) + ' |'
            markdown_lines.append(separator)
    
    return '\n'.join(markdown_lines)


def create_enhanced_sections_from_toc(
    toc_data: List[Dict[str, Any]],
    docling_document: Dict[str, Any]
) -> List[EnhancedSection]:
    """Create enhanced sections from ToC data with deterministic IDs.
    
    Args:
        toc_data: ToC extracted from PDF with page intervals
        docling_document: Docling document with corrected headlines
        
    Returns:
        List of EnhancedSection objects
    """
    sections = []
    section_index = 0
    
    def process_toc_node(
        node: Dict[str, Any],
        parent_path: List[str],
        parent_section_id: Optional[str] = None
    ) -> None:
        nonlocal section_index
        
        title = node.get('title', '')
        level = node.get('level', 1)
        start_page = node.get('start_page')
        end_page = node.get('end_page')
        
        # Skip sections under "Índice" and "Document Info"
        full_path = parent_path + [title]
        if any('índice' in part.lower() or 'document info' in part.lower() 
               for part in full_path):
            return
        
        # Create enhanced section with deterministic ID
        title_normalized = normalize_text_for_id(title)
        section = EnhancedSection.create_with_id(
            toc_path=full_path,
            start_page=start_page,
            title_normalized=title_normalized,
            section_name=title,
            section_level=level,
            section_index=section_index,
            parent_section_id=parent_section_id,
            end_page=end_page
        )
        
        sections.append(section)
        section_index += 1
        
        # Process child nodes
        children = node.get('children', [])
        for child in children:
            process_toc_node(child, full_path, section.section_id)
            
        # Update parent's sub_section_ids
        child_ids = []
        for child in children:
            child_title_normalized = normalize_text_for_id(child.get('title', ''))
            child_path = full_path + [child.get('title', '')]
            child_id = make_deterministic_id(
                "|".join(child_path),
                str(child.get('start_page', 0)),
                child_title_normalized
            )
            child_ids.append(child_id)
        section.sub_section_ids = child_ids
    
    # Process root ToC nodes
    for root_node in toc_data:
        process_toc_node(root_node, [])
    
    return sections


def extract_section_content(
    section: EnhancedSection,
    docling_document: Dict[str, Any]
) -> str:
    """Extract content for a section from Docling document.
    
    Args:
        section: Enhanced section with page boundaries
        docling_document: Docling document with structured content
        
    Returns:
        Section content as markdown text including tables converted to markdown
    """
    if not section.start_page or not section.end_page:
        return ""
    
    content_parts = []
    
    # Extract content from pages in section interval
    pages = docling_document.get('pages', [])
    for page_data in pages:
        page_num = page_data.get('page', 1)
        
        if page_num < section.start_page or page_num > section.end_page:
            continue
            
        # Extract text elements from this page
        elements = page_data.get('elements', [])
        for element in elements:
            element_type = element.get('type', '')
            element_text = element.get('text', '')
            
            if element_text.strip():
                content_parts.append(element_text)
    
    # Extract tables that fall within the section's page range
    tables = docling_document.get('tables', [])
    for table in tables:
        # Check if table falls within section page range
        table_page = None
        prov_data = table.get('prov', [])
        if prov_data:
            table_page = prov_data[0].get('page_no')
        
        if (table_page and 
            table_page >= section.start_page and 
            table_page <= section.end_page):
            
            # Convert table to markdown
            table_data = table.get('data', {})
            if table_data:
                table_markdown = convert_table_to_markdown(table_data)
                if table_markdown:
                    content_parts.append(f"\n{table_markdown}\n")
    
    return '\n'.join(content_parts)


def create_section_chunks_with_context(
    sections: List[EnhancedSection],
    docling_document: Dict[str, Any],
    max_chars: int = 5000
) -> List[Tuple[str, EnhancedSection]]:
    """Create chunks from sections with context headers.
    
    If a section is very large, split by page windows inside the section interval
    with 5-10% sentence overlap.
    
    Args:
        sections: List of enhanced sections
        docling_document: Docling document with content
        max_chars: Maximum characters per chunk
        
    Returns:
        List of (chunk_text, section) tuples
    """
    chunks = []
    
    for section in sections:
        content = extract_section_content(section, docling_document)
        
        if not content.strip():
            continue
        
        # Create context header
        context_header = create_context_header(section)
        
        if len(content) <= max_chars:
            # Single chunk
            chunk_text = f"{context_header}\n\n{content}"
            chunks.append((chunk_text, section))
        else:
            # Split into page windows with overlap
            page_chunks = split_section_by_pages(
                section, content, docling_document, max_chars
            )
            
            for i, page_content in enumerate(page_chunks):
                chunk_header = f"{context_header} (Part {i+1}/{len(page_chunks)})"
                chunk_text = f"{chunk_header}\n\n{page_content}"
                chunks.append((chunk_text, section))
    
    return chunks


def create_context_header(section: EnhancedSection) -> str:
    """Create context header for section chunk.
    
    Args:
        section: Enhanced section
        
    Returns:
        Context header string
    """
    path_str = " → ".join(section.toc_path)
    header = f"# Section: {section.section_name}\n"
    header += f"**Path:** {path_str}\n"
    header += f"**Level:** {section.section_level}\n"
    
    if section.tags:
        header += f"**Tags:** {', '.join(section.tags)}\n"
    
    if section.start_page and section.end_page:
        header += f"**Pages:** {section.start_page}-{section.end_page}\n"
    
    return header


def split_section_by_pages(
    section: EnhancedSection,
    content: str,
    docling_document: Dict[str, Any],
    max_chars: int
) -> List[str]:
    """Split large section content by page windows with sentence overlap.
    
    Args:
        section: Enhanced section
        content: Section content
        docling_document: Docling document
        max_chars: Maximum characters per window
        
    Returns:
        List of content chunks
    """
    if not section.start_page or not section.end_page:
        return [content]
    
    # Split content into sentences for overlap calculation
    sentences = split_into_sentences(content)
    if not sentences:
        return [content]
    
    chunks = []
    current_chunk = []
    current_length = 0
    overlap_size = max(1, len(sentences) // 20)  # 5% overlap
    
    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        
        if current_length + len(sentence) <= max_chars:
            current_chunk.append(sentence)
            current_length += len(sentence)
            i += 1
        else:
            if current_chunk:
                # Finish current chunk
                chunks.append(' '.join(current_chunk))
                
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - overlap_size)
                current_chunk = current_chunk[overlap_start:]
                current_length = sum(len(s) for s in current_chunk)
            else:
                # Sentence is too long, split it
                current_chunk.append(sentence[:max_chars])
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_length = 0
                i += 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences for overlap calculation.
    
    Args:
        text: Text to split
        
    Returns:
        List of sentences
    """
    # Simple sentence splitting - can be enhanced with proper NLP
    sentences = re.split(r'[.!?]+\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def validate_section_alignment(
    sections: List[EnhancedSection],
    docling_document: Dict[str, Any]
) -> List[str]:
    """Validate section alignment with Docling document after headline fixes.
    
    Args:
        sections: List of enhanced sections
        docling_document: Docling document with corrected headlines
        
    Returns:
        List of validation warnings
    """
    warnings = []
    
    # Extract section headers from Docling document
    docling_headers = extract_headers_from_docling(docling_document)
    
    for section in sections:
        if not section.start_page or not section.end_page:
            warnings.append(f"Section '{section.section_name}' has no page range")
            continue
        
        # Check if section header page is within its ToC interval
        header_found = False
        for header in docling_headers:
            if (header['text'].strip().lower() == section.section_name.strip().lower() and
                section.start_page <= header['page'] <= section.end_page):
                header_found = True
                break
        
        if not header_found:
            warnings.append(
                f"Section '{section.section_name}' header not found within "
                f"pages {section.start_page}-{section.end_page}"
            )
    
    return warnings


def extract_headers_from_docling(docling_document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract headers from Docling document.
    
    Args:
        docling_document: Docling document
        
    Returns:
        List of header data with 'text', 'page', and 'level'
    """
    headers = []
    
    pages = docling_document.get('pages', [])
    for page_data in pages:
        page_num = page_data.get('page', 1)
        elements = page_data.get('elements', [])
        
        for element in elements:
            element_type = element.get('type', '')
            if element_type.lower().startswith('heading') or 'header' in element_type.lower():
                headers.append({
                    'text': element.get('text', ''),
                    'page': page_num,
                    'level': element.get('level', 1),
                    'element_type': element_type
                })
    
    return headers


def load_toc_and_docling(
    pdf_path: Path,
    toc_output_path: Optional[Path] = None,
    docling_output_path: Optional[Path] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load ToC and Docling document, running extraction if needed.
    
    Args:
        pdf_path: Path to PDF file
        toc_output_path: Optional path to existing ToC JSON
        docling_output_path: Optional path to existing Docling JSON
        
    Returns:
        Tuple of (toc_data, docling_document)
    """
    import subprocess
    
    # Load or extract ToC
    if toc_output_path and toc_output_path.exists():
        with open(toc_output_path, 'r', encoding='utf-8') as f:
            toc_data = json.load(f)
    else:
        # Run ToC extraction
        print(f"Extracting ToC from {pdf_path}")
        result = subprocess.run([
            'python', 'scripts/pdf_toc_extractor.py',
            str(pdf_path), 
            str(docling_output_path) if docling_output_path else 'temp_docling.json'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"ToC extraction failed: {result.stderr}")
        
        # Load extracted ToC (assuming it's saved as toc.json)
        toc_path = pdf_path.parent / 'toc.json'
        if toc_path.exists():
            with open(toc_path, 'r', encoding='utf-8') as f:
                toc_data = json.load(f)
        else:
            toc_data = []
    
    # Load or extract Docling document
    if docling_output_path and docling_output_path.exists():
        with open(docling_output_path, 'r', encoding='utf-8') as f:
            docling_document = json.load(f)
    else:
        # Run Docling extraction
        print(f"Converting PDF to Docling format: {pdf_path}")
        docling_path = pdf_path.parent / 'docling_document.json'
        result = subprocess.run([
            'python', 'scripts/pdf_to_markdown.py',
            str(pdf_path),
            str(docling_path),
            '--format', 'docling'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Docling extraction failed: {result.stderr}")
            
        with open(docling_path, 'r', encoding='utf-8') as f:
            docling_document = json.load(f)
    
    return toc_data, docling_document