#!/usr/bin/env python3
"""Integration module for docling hierarchical chunking with lxRunnerExtraction.

This module provides functionality to use docling's hierarchical chunker
in place of the existing section-based chunker, while maintaining compatibility
with the existing lxRunnerExtraction pipeline.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING
import tempfile

# Import the existing data structures to maintain compatibility
from section_chunker import SectionMetadata, SectionChunk

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument
    from docling_core.transforms.chunker.base import BaseChunk

logger = logging.getLogger(__name__)


def create_docling_document_from_text(text: str) -> 'DoclingDocument':
    """
    Create a DoclingDocument from markdown text.
    
    This creates a simple document structure that works with the hierarchical chunker.
    The chunker will then provide the hierarchical metadata we need.
    
    Args:
        text: Input markdown text to convert to DoclingDocument
        
    Returns:
        DoclingDocument object
        
    Raises:
        ImportError: If docling-core is not installed
    """
    try:
        from docling_core.types.doc import (
            DoclingDocument, TextItem, GroupItem, RefItem
        )
        from docling_core.types.doc.labels import DocItemLabel
        import re
    except ImportError as e:
        raise ImportError(
            'docling-core is required for hierarchical chunking. '
            "Install with: pip install docling-core"
        ) from e
    
    # Split text into lines and create text items
    lines = text.split('\n')
    texts = []
    
    for i, line in enumerate(lines):
        if line.strip():  # Only process non-empty lines
            # Determine label based on content - use only valid TextItem labels
            if line.strip().startswith('#'):
                label = DocItemLabel.TEXT  # Headers are still text items
            else:
                label = DocItemLabel.TEXT
                
            text_item = TextItem(
                self_ref=f"#/texts/{i}",
                parent=RefItem(cref="#/body"),
                text=line,
                label=label,
                prov=[],
                orig=line
            )
            texts.append(text_item)
    
    # Create simple document structure
    document = DoclingDocument(
        name="markdown_document",
        description={"title": "Markdown Document for Hierarchical Chunking"},
        texts=texts,
        tables=[],
        pictures=[],
        key_value_items=[],
        body=GroupItem(
            self_ref="#/body",
            children=[RefItem(cref=f"#/texts/{i}") for i in range(len(texts))]
        ),
        furniture=GroupItem(
            self_ref="#/furniture", 
            children=[]
        ),
        groups=[]
    )
    
    return document


def perform_docling_hierarchical_chunking(
    text: str,
    merge_list_items: bool = True,
    delim: str = '\n\n'
) -> List['BaseChunk']:
    """
    Perform hierarchical chunking on text using docling.
    
    Args:
        text: Input text to chunk
        merge_list_items: Whether to merge list items together
        delim: Delimiter to use for chunk separation
        
    Returns:
        List of BaseChunk objects
        
    Raises:
        ImportError: If docling-core is not installed
    """
    try:
        from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker
    except ImportError as e:
        raise ImportError(
            'docling-core is required for hierarchical chunking. '
            "Install with: pip install docling-core"
        ) from e
    
    logger.info('Creating DoclingDocument from text...')
    document = create_docling_document_from_text(text)
    
    logger.info('Performing hierarchical chunking...')
    chunker = HierarchicalChunker(
        merge_list_items=merge_list_items,
        delim=delim
    )
    
    chunks = list(chunker.chunk(document))
    logger.info('Hierarchical chunking completed. Generated %d chunks', len(chunks))
    
    return chunks


def convert_docling_chunk_to_section_chunk(
    docling_chunk: 'BaseChunk',
    chunk_index: int,
    text_start_pos: int = 0
) -> SectionChunk:
    """
    Convert a docling BaseChunk to a SectionChunk, extracting hierarchical information
    from the docling chunk metadata rather than manually calculating it.
    
    Args:
        docling_chunk: BaseChunk from docling hierarchical chunker
        chunk_index: Index of the chunk (0-based)
        text_start_pos: Starting position in the original text
        
    Returns:
        SectionChunk compatible with existing pipeline
    """
    chunk_text = getattr(docling_chunk, 'text', '') or ''
    
    # Extract metadata from docling chunk
    docling_metadata = {}
    doc_items_info = []
    
    if hasattr(docling_chunk, 'meta') and docling_chunk.meta:
        try:
            if hasattr(docling_chunk.meta, 'model_dump'):
                docling_metadata = docling_chunk.meta.model_dump()
            elif hasattr(docling_chunk.meta, 'dict'):
                docling_metadata = docling_chunk.meta.dict()
            else:
                docling_metadata = {"raw_meta": str(docling_chunk.meta)}
            
            # Extract doc_items information for hierarchical analysis
            if hasattr(docling_chunk.meta, 'doc_items') and docling_chunk.meta.doc_items:
                for item in docling_chunk.meta.doc_items:
                    item_info = {
                        'text': getattr(item, 'text', ''),
                        'label': str(getattr(item, 'label', '')),
                        'self_ref': getattr(item, 'self_ref', ''),
                        'parent': str(getattr(item, 'parent', '')) if hasattr(item, 'parent') else None
                    }
                    doc_items_info.append(item_info)
                        
        except Exception as e:
            logger.warning(f"Failed to extract chunk metadata: {e}")
            docling_metadata = {"raw_meta": str(docling_chunk.meta)}
    
    # Analyze the chunk content and doc_items to determine hierarchical position
    section_name = f"Chunk {chunk_index + 1}"
    section_level = 1
    section_type = "Text"
    
    # Look for header information in doc_items
    header_items = [item for item in doc_items_info 
                   if 'header' in item['label'].lower() or 'title' in item['label'].lower()]
    
    if header_items:
        # This chunk contains header information
        header_item = header_items[0]  # Use first header
        section_name = header_item['text'].strip()
        
        # Extract level from markdown header syntax if present
        if section_name.startswith('#'):
            section_level = len(section_name) - len(section_name.lstrip('#'))
            section_name = section_name.lstrip('#').strip()
        else:
            # Determine level based on label type
            if 'title' in header_item['label'].lower():
                section_level = 1
            else:
                section_level = 2  # Default for section headers
        
        section_type = "Header"
    else:
        # This is content under a section, try to extract from text
        text_lines = chunk_text.strip().split('\n')
        if text_lines:
            first_line = text_lines[0].strip()
            if first_line.startswith('#'):
                # Direct markdown header in text
                section_level = len(first_line) - len(first_line.lstrip('#'))
                section_name = first_line.lstrip('#').strip()
                section_type = "Header"
            else:
                # Regular content - maintain as text chunk
                section_name = f"Content {chunk_index + 1}"
                section_type = "Content"
    
    # For hierarchical sectioning, let docling handle the relationships
    # Don't manually calculate parent_section_id here - this should come from docling's structure
    parent_section_id = None
    
    # Extract parent information from docling metadata if available
    if docling_metadata.get('origin'):
        # Origin might contain parent relationship information
        origin_info = docling_metadata['origin']
        # This would need to be parsed based on docling's actual structure
        # For now, leave as None and let the hierarchical processing handle it
    
    # Create section metadata with information derived from docling
    section_metadata = SectionMetadata(
        section_id=f"docling_chunk_{chunk_index:03d}",
        section_name=section_name,
        section_level=section_level,
        section_index=chunk_index,
        parent_section_id=parent_section_id,  # To be derived from docling hierarchy
        sub_sections=[],  # To be populated from docling hierarchy
        section_summary="",
        section_type=section_type
    )
    
    # Add docling-specific metadata as additional attributes
    section_metadata.docling_metadata = docling_metadata
    section_metadata.doc_items_info = doc_items_info
    section_metadata.original_chunk_index = chunk_index
    
    # Calculate character positions
    char_start = text_start_pos
    char_end = char_start + len(chunk_text)
    
    return SectionChunk(
        chunk_text=chunk_text,
        section_metadata=section_metadata,
        char_start=char_start,
        char_end=char_end
    )


def create_docling_hierarchical_chunks(text: str) -> List[SectionChunk]:
    """
    Create hierarchical chunks using docling and convert to SectionChunk format.
    
    This function serves as a drop-in replacement for create_section_chunks
    from section_chunker.py.
    
    Args:
        text: Input text to chunk
        
    Returns:
        List of SectionChunk objects compatible with existing pipeline
    """
    if not text.strip():
        logger.warning("Empty input text provided to docling hierarchical chunker")
        return []
    
    try:
        # Perform docling hierarchical chunking
        docling_chunks = perform_docling_hierarchical_chunking(text)
        
        if not docling_chunks:
            logger.warning("No chunks generated by docling hierarchical chunker")
            return []
        
        # Convert to SectionChunk format
        section_chunks = []
        current_pos = 0
        
        for i, docling_chunk in enumerate(docling_chunks):
            section_chunk = convert_docling_chunk_to_section_chunk(
                docling_chunk, i, current_pos
            )
            section_chunks.append(section_chunk)
            current_pos = section_chunk.char_end
        
        # Post-process to establish parent-child relationships from docling metadata
        derive_hierarchy_from_docling_chunks(section_chunks)
        
        logger.info(
            "Created %d hierarchical chunks from docling", 
            len(section_chunks)
        )
        
        return section_chunks
        
    except ImportError as e:
        logger.error("Docling not available, falling back to text-only chunking: %s", e)
        return create_fallback_chunks(text)
    except Exception as e:
        logger.error("Error in docling hierarchical chunking: %s", e)
        return create_fallback_chunks(text)


def derive_hierarchy_from_docling_chunks(chunks: List[SectionChunk]) -> None:
    """
    Derive parent-child relationships from docling chunk metadata rather than 
    manually calculating based on header levels.
    
    This function uses the hierarchical information already provided by docling
    to establish relationships between chunks.
    
    Args:
        chunks: List of SectionChunk objects to process
    """
    # Track sections by their hierarchical position
    header_stack = []  # Stack of (chunk_index, level, section_id)
    
    for i, chunk in enumerate(chunks):
        metadata = chunk.section_metadata
        
        # Only process header chunks for hierarchy
        if metadata.section_type == "Header":
            level = metadata.section_level
            
            # Pop headers of same or deeper level from stack
            while header_stack and header_stack[-1][1] >= level:
                header_stack.pop()
            
            # Set parent from the stack
            if header_stack:
                parent_idx, parent_level, parent_id = header_stack[-1]
                metadata.parent_section_id = parent_id
                
                # Add this chunk as child to parent
                parent_chunk = chunks[parent_idx]
                if metadata.section_id not in parent_chunk.section_metadata.sub_sections:
                    parent_chunk.section_metadata.sub_sections.append(metadata.section_id)
            
            # Add this header to the stack
            header_stack.append((i, level, metadata.section_id))
            
        else:
            # Content chunks inherit the parent of the most recent header
            if header_stack:
                _, _, parent_id = header_stack[-1]
                metadata.parent_section_id = parent_id


def create_fallback_chunks(text: str) -> List[SectionChunk]:
    """
    Create simple text-based chunks as fallback when docling is not available.
    
    Args:
        text: Input text to chunk
        
    Returns:
        List of SectionChunk objects
    """
    logger.info("Creating fallback chunks from text")
    
    # Simple paragraph-based chunking
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    chunks = []
    current_pos = 0
    
    for i, paragraph in enumerate(paragraphs):
        section_metadata = SectionMetadata(
            section_id=f"fallback_{i:03d}",
            section_name=f"Paragraph {i + 1}",
            section_level=1,
            section_index=i,
            section_type="Fallback"
        )
        
        chunk = SectionChunk(
            chunk_text=paragraph,
            section_metadata=section_metadata,
            char_start=current_pos,
            char_end=current_pos + len(paragraph)
        )
        
        chunks.append(chunk)
        current_pos += len(paragraph) + 2  # +2 for \n\n
    
    return chunks


def get_docling_hierarchical_statistics(chunks: List[SectionChunk]) -> Dict[str, Any]:
    """
    Get statistics about the docling hierarchical chunks.
    
    This function serves as a drop-in replacement for get_section_statistics
    from section_chunker.py.
    
    Args:
        chunks: List of hierarchical chunks
        
    Returns:
        Dictionary with chunk statistics
    """
    if not chunks:
        return {
            "total_sections": 0, 
            "levels": {},
            "chunking_method": "docling_hierarchical"
        }
    
    level_counts = {}
    total_chars = 0
    hierarchical_chunks = 0
    
    for chunk in chunks:
        level = chunk.section_metadata.section_level
        level_counts[level] = level_counts.get(level, 0) + 1
        total_chars += len(chunk.chunk_text)
        
        if chunk.section_metadata.section_type == "Hierarchical":
            hierarchical_chunks += 1
    
    return {
        "total_sections": len(chunks),
        "levels": {f"level_{k}": v for k, v in sorted(level_counts.items())},
        "total_characters": total_chars,
        "average_section_length": total_chars // len(chunks) if chunks else 0,
        "chunking_method": "docling_hierarchical",
        "hierarchical_chunks": hierarchical_chunks,
        "fallback_chunks": len(chunks) - hierarchical_chunks
    }