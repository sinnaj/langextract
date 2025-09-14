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
    """Convert Docling table data to markdown format with optimized performance.
    
    Args:
        table_data: Table data from DoclingDocument with 'table_cells' structure
        
    Returns:
        Markdown representation of the table
    """
    table_cells = table_data.get('table_cells', [])
    if not table_cells:
        return ""
    
    # Pre-compute dimensions and optimize cell processing
    max_col = max((cell.get('start_col_offset_idx', 0) for cell in table_cells), default=0)
    max_row = max((cell.get('start_row_offset_idx', 0) for cell in table_cells), default=0)
    
    # Initialize grid with empty strings for better performance
    grid = [[''] * (max_col + 1) for _ in range(max_row + 1)]
    
    # Batch process all cells in single pass
    for cell in table_cells:
        row_idx = cell.get('start_row_offset_idx', 0)
        col_idx = cell.get('start_col_offset_idx', 0)
        text = cell.get('text', '').strip()
        
        # Optimize text cleaning - combine operations
        text = text.replace('|', '\\|').replace('\n', ' ')
        grid[row_idx][col_idx] = text
    
    # Build markdown table with pre-allocated list
    markdown_lines = []
    
    # Generate header separator once
    separator = '| ' + ' | '.join(['---'] * (max_col + 1)) + ' |'
    
    for row_idx in range(max_row + 1):
        # Use join directly on the row for better performance
        markdown_lines.append('| ' + ' | '.join(grid[row_idx]) + ' |')
        
        # Add header separator after first row
        if row_idx == 0:
            markdown_lines.append(separator)
    
    return '\n'.join(markdown_lines)


def collect_positioning_data_for_section(
    section: EnhancedSection,
    docling_document: Dict[str, Any],
    max_elements: int = 5
) -> List[Dict[str, Any]]:
    """Collect positioning data for a section from docling document.
    
    Args:
        section: Enhanced section to collect positioning for
        docling_document: Docling document with text elements
        max_elements: Maximum number of positioning elements to collect
        
    Returns:
        List of positioning data dictionaries
    """
    texts = docling_document.get('texts', [])
    positioning_data = []
    
    # Find text elements within this section's page range
    for text_item in texts:
        if len(positioning_data) >= max_elements:
            break
            
        # Skip page headers
        if text_item.get('label') == 'page_header':
            continue
        
        text_content = text_item.get('text', '').strip()
        if not text_content:
            continue
            
        # Get page from provenance
        page_no = None
        charspan = [0, 0]
        bbox = {}
        
        prov_data = text_item.get('prov', [])
        if prov_data and isinstance(prov_data, list) and len(prov_data) > 0:
            first_prov = prov_data[0]
            if isinstance(first_prov, dict):
                page_no = first_prov.get('page_no')
                charspan = first_prov.get('charspan', [0, 0])
                bbox = first_prov.get('bbox', {})
        
        # Check if this element is within the section's page range
        if page_no and section.start_page and section.end_page:
            if section.start_page <= page_no <= section.end_page:
                positioning_data.append({
                    'page_no': page_no,
                    'charspan': charspan,
                    'bbox': bbox,
                    'text': text_content[:100]  # First 100 chars for reference
                })
    
    return positioning_data


def create_enhanced_sections_from_toc(
    toc_data: List[Dict[str, Any]],
    docling_document: Dict[str, Any]
) -> List[EnhancedSection]:
    """Create enhanced sections from ToC data with deterministic IDs.
    
    Args:
        toc_data: ToC extracted from PDF with page intervals
        docling_document: Docling document with corrected headlines
        
    Returns:
        List of EnhancedSection objects including both ToC sections and table sections
    """
    sections = []
    section_index = 0
    
    def process_toc_node(
        node: Dict[str, Any],
        parent_path: List[str],
        parent_section_id: Optional[str] = None
    ) -> Optional[str]:
        nonlocal section_index
        
        title = node.get('title', '')
        level = node.get('level', 1)
        start_page = node.get('start_page')
        end_page = node.get('end_page')
        
        # Skip sections under "Índice" and "Document Info"
        full_path = parent_path + [title]
        if any('índice' in part.lower() or 'document info' in part.lower() 
               for part in full_path):
            # Still process children but with current parent context
            children = node.get('children', [])
            for child in children:
                process_toc_node(child, parent_path, parent_section_id)
            return None
        
        # Check if this section should be filtered (page headers, invalid ranges)
        title_lower = title.lower()
        should_skip_section = (
            title_lower.startswith('documento básico') or 
            title_lower.startswith('página') or 
            title_lower.startswith('page ') or
            'header' in title_lower or
            # Skip sections with very broad page ranges that look like page headers
            (start_page and end_page and end_page - start_page > 100)
        )
        
        if should_skip_section:
            print(f"[DEBUG] Skipping potential page header section: '{title}' (pages {start_page}-{end_page})")
            # Still process children but with current parent context, adjusting their level
            children = node.get('children', [])
            for child in children:
                # Promote child level since we're skipping the parent
                child_copy = dict(child)
                if 'level' in child_copy and child_copy['level'] > 1:
                    child_copy['level'] -= 1
                process_toc_node(child_copy, parent_path, parent_section_id)
            return None
        
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
            end_page=end_page,
            section_type="Headline"
        )
        
        # Collect positioning data for the section
        section.positioning_data = collect_positioning_data_for_section(section, docling_document)
        
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
        
        return section.section_id
    
    # Process root ToC nodes
    for root_node in toc_data:
        process_toc_node(root_node, [])
    
    # Add table sections
    table_sections = create_table_sections_from_docling(docling_document, sections, section_index)
    sections.extend(table_sections)
    
    return sections


def extract_section_content(
    section: EnhancedSection,
    docling_document: Dict[str, Any],
    _cached_pages: Dict[int, List[Dict[str, Any]]] = None
) -> str:
    """Extract content for a section from Docling document with caching optimization.
    
    Args:
        section: Enhanced section with page boundaries
        docling_document: Docling document with structured content
        _cached_pages: Optional pre-computed page elements cache for performance
        
    Returns:
        Section content as markdown text. For table sections, returns only the table 
        markdown. For regular sections, returns text content excluding tables 
        (since tables now have their own sections).
    """
    if not section.start_page or not section.end_page:
        return ""
    
    # Handle table sections specially - return only the table content
    if section.section_type == "Table":
        return extract_table_content_for_section(section, docling_document)
    
    content_parts = []
    
    # For real docling documents, content is in 'texts' array with provenance data
    texts = docling_document.get('texts', [])
    
    if texts:
        # Extract content from texts with page-based filtering
        for text_item in texts:
            # Get page number from provenance data
            prov_data = text_item.get('prov', [])
            if prov_data and isinstance(prov_data, list):
                text_page = prov_data[0].get('page_no')
                if text_page and section.start_page <= text_page <= section.end_page:
                    text_content = text_item.get('text', '').strip()
                    if text_content:
                        content_parts.append(text_content)
    else:
        # Fallback: Use cached page elements if available (for test/mock documents)
        if _cached_pages is None:
            pages_data = docling_document.get('pages', {})
            page_elements_cache = {}
            
            # Handle both list format (test/mock) and dict format (real docling document)
            if isinstance(pages_data, list):
                # List format: [{"page": 1, "elements": [...]}, ...]
                for page_data in pages_data:
                    page_num = page_data.get('page', 1)
                    page_elements_cache[page_num] = page_data.get('elements', [])
            else:
                # Dict format: {"1": {"elements": [...]}, "2": {"elements": [...]}, ...}
                for page_key, page_data in pages_data.items():
                    page_num = int(page_key) if isinstance(page_key, str) and page_key.isdigit() else 1
                    page_elements_cache[page_num] = page_data.get('elements', [])
        else:
            page_elements_cache = _cached_pages
        
        # Extract content from pages in section interval
        for page_num in range(section.start_page, section.end_page + 1):
            if page_num not in page_elements_cache:
                continue
                
            # Process elements from cached page data
            for element in page_elements_cache[page_num]:
                element_text = element.get('text', '').strip()
                if element_text:
                    content_parts.append(element_text)
    
    # For regular sections, we no longer include tables since they have their own sections
    # This is a change from the previous behavior where tables were included in regular sections
    
    return '\n'.join(content_parts)


def extract_table_content_for_section(
    table_section: EnhancedSection,
    docling_document: Dict[str, Any]
) -> str:
    """Extract table content for a table section.
    
    Args:
        table_section: Table section
        docling_document: Docling document with table data
        
    Returns:
        Markdown representation of the table
    """
    tables = docling_document.get('tables', [])
    
    # Check if we have stored table index
    if hasattr(table_section, 'table_index'):
        table_index = table_section.table_index
        if 0 <= table_index < len(tables):
            table = tables[table_index]
            table_data = table.get('data', {})
            if table_data:
                return convert_table_to_markdown(table_data)
    
    # Fallback: Find table by matching page and table number
    # Extract table number from section name (e.g., "Table 1" -> 1)
    import re
    match = re.search(r'Table (\d+)', table_section.section_name)
    if not match:
        return ""
    
    target_table_number = int(match.group(1))
    
    # Count tables to match the section name
    table_counter = 1
    for table in tables:
        table_page = None
        prov_data = table.get('prov', [])
        if prov_data:
            table_page = prov_data[0].get('page_no')
        
        if table_counter == target_table_number:
            table_data = table.get('data', {})
            if table_data:
                return convert_table_to_markdown(table_data)
        table_counter += 1
    
    return ""


def create_table_sections_from_docling(
    docling_document: Dict[str, Any], 
    existing_sections: List[EnhancedSection],
    starting_section_index: int
) -> List[EnhancedSection]:
    """Create table sections from Docling document tables.
    
    Args:
        docling_document: Docling document with table data
        existing_sections: List of existing sections to find parents
        starting_section_index: Starting index for new table sections
        
    Returns:
        List of table EnhancedSection objects
    """
    table_sections = []
    tables = docling_document.get('tables', [])
    section_index = starting_section_index
    table_counter = 1
    
    # Create a mapping of page to section for finding parent sections
    # We want the most specific (deepest level) section that contains each page
    # In hierarchical structures: Level 1 = parent, Level 2 = child, etc.
    # So we want the section with the HIGHEST level number (most specific)
    page_to_section = {}
    
    # First pass: find reasonable page bounds by analyzing all sections
    max_reasonable_page = 1
    for section in existing_sections:
        if section.start_page and section.start_page > 0:
            max_reasonable_page = max(max_reasonable_page, section.start_page + 20)  # Allow 20 pages per section as reasonable
    
    # Cap at reasonable document size (most PDFs are under 100 pages)
    max_reasonable_page = min(max_reasonable_page, 100)
    
    for section in existing_sections:
        # Skip sections with invalid page ranges
        if not section.start_page or not section.end_page or section.start_page < 1:
            continue
        
        # Detect unrealistic page ranges (sections claiming > 50 pages or end_page > 500)
        effective_end_page = section.end_page
        if section.end_page - section.start_page > 50 or section.end_page > max_reasonable_page:
            # For overly broad sections, limit their scope to reasonable bounds
            effective_end_page = min(section.start_page + 20, max_reasonable_page)
            print(f"[DEBUG] Section '{section.section_name}' has unrealistic page range {section.start_page}-{section.end_page}, limiting to {section.start_page}-{effective_end_page}")
            
        for page in range(section.start_page, effective_end_page + 1):
            if page not in page_to_section or section.section_level > page_to_section[page].section_level:
                page_to_section[page] = section
    
    for table_index, table in enumerate(tables):
        # Get table page from provenance data
        table_page = None
        prov_data = table.get('prov', [])
        if prov_data:
            table_page = prov_data[0].get('page_no')
        
        if not table_page:
            continue
            
        # Find parent section for this table
        parent_section = page_to_section.get(table_page)
        if not parent_section:
            continue
        
        # Create table section name using the global table counter
        table_name = f"Table {table_counter}"
        
        # Create ToC path by extending parent's path
        table_toc_path = parent_section.toc_path + [table_name]
        
        # Create table section with deterministic ID
        title_normalized = normalize_text_for_id(table_name)
        table_section = EnhancedSection.create_with_id(
            toc_path=table_toc_path,
            start_page=table_page,
            title_normalized=title_normalized,
            section_name=table_name,
            section_level=parent_section.section_level + 1,  # One level deeper than parent
            section_index=section_index,
            parent_section_id=parent_section.section_id,
            end_page=table_page,  # Tables are typically on single pages
            section_type="Table"
        )
        
        # Store the table index for content extraction
        table_section.table_index = table_index
        
        # Collect positioning data for the table from provenance data
        table_positioning = []
        for prov_item in prov_data:
            if isinstance(prov_item, dict) and 'page_no' in prov_item:
                # Extract positioning information from provenance data
                prov_positioning = {
                    'page_no': prov_item.get('page_no'),
                    'charspan': prov_item.get('charspan', [0, 0]),
                    'bbox': prov_item.get('bbox', {}),
                    'text': table_name  # Use table name as reference
                }
                table_positioning.append(prov_positioning)
        
        # Store positioning data for the table section
        table_section.positioning_data = table_positioning
        
        # Add table section to parent's sub_section_ids
        if table_section.section_id not in parent_section.sub_section_ids:
            parent_section.sub_section_ids.append(table_section.section_id)
        
        table_sections.append(table_section)
        section_index += 1
        table_counter += 1
    
    return table_sections


def build_document_caches(docling_document: Dict[str, Any]) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[str, int], List[Dict[str, Any]]]:
    """Build optimized caches for document processing to improve alignment performance.
    
    Args:
        docling_document: Docling document with structured content
        
    Returns:
        Tuple of (page_elements_cache, header_lookup_cache, sorted_headers_cache)
    """
    # Cache 1: Page elements indexed by page number
    pages_data = docling_document.get('pages', {})
    page_elements_cache = {}
    
    # Handle both list format (test/mock) and dict format (real docling document)
    if isinstance(pages_data, list):
        # List format: [{"page": 1, "elements": [...]}, ...]
        for page_data in pages_data:
            page_num = page_data.get('page', 1)
            page_elements_cache[page_num] = page_data.get('elements', [])
    else:
        # Dict format: {"1": {"elements": [...]}, "2": {"elements": [...]}, ...}
        # Real docling documents don't have elements in pages, so create empty cache
        for page_key, page_data in pages_data.items():
            page_num = int(page_key) if isinstance(page_key, str) and page_key.isdigit() else 1
            page_elements_cache[page_num] = page_data.get('elements', [])
    
    # Cache 2: Header title -> page number lookup for fast section alignment
    header_lookup_cache = {}
    sorted_headers_cache = []
    
    # For real docling documents, we don't have page elements with headers,
    # so we'll build a minimal cache or skip header processing
    if isinstance(pages_data, list):
        # Process page elements for test/mock documents
        for page_data in pages_data:
            page_num = page_data.get('page', 1)
            elements = page_data.get('elements', [])
            
            for element in elements:
                element_type = element.get('type', '')
                element_text = element.get('text', '').strip()
                
                if (element_type.lower().startswith('heading') or 'header' in element_type.lower()) and element_text:
                    header_key = element_text.lower()
                    # Store the first occurrence for faster lookups
                    if header_key not in header_lookup_cache:
                        header_lookup_cache[header_key] = page_num
                    
                    sorted_headers_cache.append({
                        'text': element_text,
                        'page': page_num,
                        'level': element.get('level', 1),
                        'element_type': element_type
                    })
    
    # Sort headers by page and level for efficient traversal
    sorted_headers_cache.sort(key=lambda x: (x['page'], x['level']))
    
    print(f"[DEBUG] Built document caches: {len(page_elements_cache)} pages, {len(header_lookup_cache)} headers")
    
    return page_elements_cache, header_lookup_cache, sorted_headers_cache


def create_section_chunks_with_context_optimized(
    sections: List[EnhancedSection],
    docling_document: Dict[str, Any],
    max_chars: int = 5000
) -> List[Tuple[str, EnhancedSection]]:
    """Create chunks from sections with context headers using optimized caching.
    
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
    
    # Build caches once for all sections to improve performance
    page_elements_cache, _, _ = build_document_caches(docling_document)
    
    for section in sections:
        content = extract_section_content(section, docling_document, page_elements_cache)
        
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
    """Validate section alignment with Docling document after headline fixes using optimized lookup.
    
    Args:
        sections: List of enhanced sections
        docling_document: Docling document with corrected headlines
        
    Returns:
        List of validation warnings
    """
    warnings = []
    
    # Build optimized header lookup cache once
    _, header_lookup_cache, sorted_headers = build_document_caches(docling_document)
    
    for section in sections:
        if not section.start_page or not section.end_page:
            warnings.append(f"Section '{section.section_name}' has no page range")
            continue
        
        # Fast lookup using pre-built cache
        section_name_lower = section.section_name.strip().lower()
        header_page = header_lookup_cache.get(section_name_lower)
        
        if header_page and section.start_page <= header_page <= section.end_page:
            # Header found within section page range - valid alignment
            continue
        
        # More detailed search if quick lookup failed
        header_found = False
        for header in sorted_headers:
            # Skip headers outside the section's page range for efficiency
            if header['page'] < section.start_page:
                continue
            if header['page'] > section.end_page:
                break
                
            if header['text'].strip().lower() == section_name_lower:
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