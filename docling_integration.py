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
    Create a DoclingDocument from plain text.
    
    This is a simplified version that creates a basic document structure
    from plain text input, which can then be processed by the hierarchical chunker.
    
    Args:
        text: Input text to convert to DoclingDocument
        
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
    except ImportError as e:
        raise ImportError(
            'docling-core is required for hierarchical chunking. '
            "Install with: pip install docling-core"
        ) from e
    
    # Split text into lines and process markdown structure
    lines = text.split('\n')
    texts = []
    
    for i, line in enumerate(lines):
        if line.strip():  # Only process non-empty lines
            text_item = TextItem(
                self_ref=f"#/texts/{i}",
                parent=RefItem(cref="#/body"),
                text=line,
                label=DocItemLabel.TEXT,
                prov=[],
                orig=line
            )
            texts.append(text_item)
    
    # Create document structure
    document = DoclingDocument(
        name="text_document",
        description={"title": "Text Document for Hierarchical Chunking"},
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
    Convert a docling BaseChunk to a SectionChunk for compatibility.
    
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
    headings = []
    
    if hasattr(docling_chunk, 'meta') and docling_chunk.meta:
        try:
            if hasattr(docling_chunk.meta, 'model_dump'):
                docling_metadata = docling_chunk.meta.model_dump()
            elif hasattr(docling_chunk.meta, 'dict'):
                docling_metadata = docling_chunk.meta.dict()
            else:
                docling_metadata = {"raw_meta": str(docling_chunk.meta)}
            
            # Extract headings from metadata
            if hasattr(docling_chunk.meta, 'headings') and docling_chunk.meta.headings:
                headings = list(docling_chunk.meta.headings)
            
            # Also check doc_items for hierarchical information
            if hasattr(docling_chunk.meta, 'doc_items') and docling_chunk.meta.doc_items:
                doc_items = docling_chunk.meta.doc_items
                # Extract any title or header information from doc_items
                for item in doc_items:
                    if hasattr(item, 'label') and item.label:
                        # Convert enum to string for comparison
                        label_str = str(item.label).lower()
                        if 'title' in label_str or 'header' in label_str:
                            if hasattr(item, 'text') and item.text:
                                if item.text not in headings:
                                    headings.append(item.text)
                        
        except Exception as e:
            logger.warning(f"Failed to extract chunk metadata: {e}")
            docling_metadata = {"raw_meta": str(docling_chunk.meta)}
    
    # Determine section name and level from chunk content and headings
    section_name = f"Chunk {chunk_index + 1}"
    section_level = 1
    
    # Try to extract section name from the chunk text itself
    text_lines = chunk_text.strip().split('\n')
    if text_lines:
        first_line = text_lines[0].strip()
        # Check if first line is a markdown header
        if first_line.startswith('#'):
            # Extract header text and level
            header_match = first_line.lstrip('#').strip()
            if header_match:
                section_name = header_match
                section_level = len(first_line) - len(first_line.lstrip('#'))
                if section_name not in headings:
                    headings.append(section_name)
    
    # Use headings if available and no header found in text
    if headings and section_name.startswith('Chunk'):
        section_name = headings[-1] if headings[-1] else section_name
        section_level = len(headings)
    
    # Determine parent section based on section level
    parent_section_id = None
    if section_level > 1:
        # Parent would be a section with level - 1
        parent_section_id = f"section_{max(0, chunk_index-1):03d}"
    
    # Create section metadata
    section_metadata = SectionMetadata(
        section_id=f"section_{chunk_index:03d}",
        section_name=section_name,
        section_level=section_level,
        section_index=chunk_index,
        parent_section_id=parent_section_id,
        sub_sections=[],  # Will be populated later when processing all chunks
        section_summary="",
        section_type="Hierarchical"
    )
    
    # Add docling-specific metadata as additional attributes
    section_metadata.docling_metadata = docling_metadata
    section_metadata.headings_context = headings
    
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
        
        # Post-process to establish parent-child relationships
        establish_parent_child_relationships(section_chunks)
        
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


def establish_parent_child_relationships(chunks: List[SectionChunk]) -> None:
    """
    Establish parent-child relationships between chunks based on their hierarchical levels.
    
    Args:
        chunks: List of SectionChunk objects to process
    """
    # Build parent-child relationships based on hierarchical levels
    for i, chunk in enumerate(chunks):
        metadata = chunk.section_metadata
        current_level = metadata.section_level
        
        # Find the most recent chunk with a lower level (parent)
        for j in range(i - 1, -1, -1):  # Go backwards from current position
            potential_parent = chunks[j]
            parent_metadata = potential_parent.section_metadata
            parent_level = parent_metadata.section_level
            
            # Check if this chunk is a potential parent (lower level)
            if parent_level < current_level:
                # This is the immediate parent
                metadata.parent_section_id = parent_metadata.section_id
                
                # Add this chunk as a child to the parent
                if metadata.section_id not in parent_metadata.sub_sections:
                    parent_metadata.sub_sections.append(metadata.section_id)
                
                break  # Found the immediate parent, stop searching
        
        # If no parent found and level > 1, it might be orphaned
        if metadata.parent_section_id is None and current_level > 1:
            logger.warning(
                f"Chunk {metadata.section_id} ({metadata.section_name}) "
                f"at level {current_level} has no parent"
            )


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