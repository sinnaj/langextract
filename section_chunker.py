#!/usr/bin/env python3
"""Standalone section-based chunker for LangExtract.

This script provides functionality to parse markdown documents and create
chunks based on section boundaries (headers) rather than character count.
Each chunk corresponds to a document section and includes metadata about
the section hierarchy.

This is intended to be used as a pre-processing step before calling langextract.
"""

from collections.abc import Iterator
import dataclasses
import re
from typing import Optional, Dict, Any, List, Tuple


@dataclasses.dataclass
class SectionMetadata:
    """Metadata for a document section.
    
    Attributes:
        section_id: Unique identifier for the section.
        section_name: Name/title of the section.
        section_level: Header level (1 for #, 2 for ##, etc.).
        section_index: Sequential index of the section (0-based).
        parent_section_id: ID of the parent section (None for top-level).
        sub_sections: List of child section IDs.
        section_summary: Summary of the section content (to be filled by LangExtract).
    """
    section_id: str
    section_name: str
    section_level: int
    section_index: int
    parent_section_id: Optional[str] = None
    sub_sections: List[str] = dataclasses.field(default_factory=list)
    section_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "section_id": self.section_id,
            "section_name": self.section_name,
            "section_level": self.section_level,
            "section_index": self.section_index,
            "parent_section": self.parent_section_id,
            "sub_sections": self.sub_sections,
            "section_summary": self.section_summary,
        }


@dataclasses.dataclass
class SectionChunk:
    """A text chunk with section metadata.
    
    Represents a document section with its content and metadata.
    """
    chunk_text: str
    section_metadata: SectionMetadata
    char_start: int
    char_end: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "chunk_text": self.chunk_text,
            "section_metadata": self.section_metadata.to_dict(),
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


def parse_markdown_sections(text: str) -> List[Tuple[str, SectionMetadata, int, int]]:
    """Parse markdown text to identify sections and their boundaries.
    
    Args:
        text: The markdown text to parse.
        
    Returns:
        List of tuples (section_text, metadata, start_pos, end_pos) for each section.
    """
    lines = text.split('\n')
    sections = []
    current_section_lines = []
    current_metadata = None
    current_start_pos = 0
    section_stack = []  # Stack to track parent sections
    section_counter = 1
    
    for i, line in enumerate(lines):
        # Check if line is a header
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
        
        if header_match:
            # Save previous section if exists
            if current_metadata is not None and current_section_lines:
                section_text = '\n'.join(current_section_lines)
                end_pos = current_start_pos + len(section_text)
                sections.append((section_text, current_metadata, current_start_pos, end_pos))
                current_start_pos = end_pos + 1  # +1 for newline
            
            # Parse new header
            header_level = len(header_match.group(1))
            section_title = header_match.group(2).strip()
            section_id = f"section_{section_counter:03d}"
            
            # Update section stack for parent tracking
            # Remove sections at same or deeper level
            while section_stack and section_stack[-1][1] >= header_level:
                section_stack.pop()
            
            # Determine parent
            parent_id = section_stack[-1][0] if section_stack else None
            
            # Create metadata with proper 0-based indexing
            current_metadata = SectionMetadata(
                section_id=section_id,
                section_name=section_title,
                section_level=header_level,
                section_index=section_counter - 1,  # 0-based index
                parent_section_id=parent_id
            )
            
            section_counter += 1
            
            # Add to parent's sub_sections if applicable
            if parent_id:
                # Find parent in already processed sections and update its sub_sections
                for section_tuple in sections:
                    _, meta, _, _ = section_tuple
                    if meta.section_id == parent_id:
                        meta.sub_sections.append(section_id)
                        break
            
            # Add to stack
            section_stack.append((section_id, header_level))
            
            # Start new section with header line
            current_section_lines = [line]
        else:
            # Add line to current section
            if current_metadata is not None:
                current_section_lines.append(line)
            else:
                # Content before first header - create a default section
                if not sections and line.strip():
                    current_metadata = SectionMetadata(
                        section_id="section_000",
                        section_name="Introduction",
                        section_level=1,
                        section_index=0
                    )
                    current_section_lines = [line]
                elif current_section_lines:
                    current_section_lines.append(line)
    
    # Add final section
    if current_metadata is not None and current_section_lines:
        section_text = '\n'.join(current_section_lines)
        end_pos = current_start_pos + len(section_text)
        sections.append((section_text, current_metadata, current_start_pos, end_pos))
    
    return sections


def create_section_chunks(text: str) -> List[SectionChunk]:
    """Create section-based chunks from markdown text.
    
    Args:
        text: The markdown text to chunk.
        
    Returns:
        List of SectionChunk objects representing document sections.
    """
    sections = parse_markdown_sections(text)
    chunks = []
    
    for section_text, metadata, start_pos, end_pos in sections:
        chunk = SectionChunk(
            chunk_text=section_text,
            section_metadata=metadata,
            char_start=start_pos,
            char_end=end_pos
        )
        chunks.append(chunk)
    
    return chunks


def get_section_statistics(chunks: List[SectionChunk]) -> Dict[str, Any]:
    """Get statistics about the section chunks.
    
    Args:
        chunks: List of section chunks.
        
    Returns:
        Dictionary with section statistics.
    """
    if not chunks:
        return {"total_sections": 0, "levels": {}}
    
    level_counts = {}
    for chunk in chunks:
        level = chunk.section_metadata.section_level
        level_counts[level] = level_counts.get(level, 0) + 1
    
    return {
        "total_sections": len(chunks),
        "levels": {f"level_{k}": v for k, v in sorted(level_counts.items())},
        "total_characters": sum(len(chunk.chunk_text) for chunk in chunks),
        "average_section_length": sum(len(chunk.chunk_text) for chunk in chunks) // len(chunks),
    }


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    
    if len(sys.argv) != 2:
        print("Usage: python section_chunker.py <input_file.md>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File {input_file} does not exist")
        sys.exit(1)
    
    # Read the input file
    text = input_file.read_text(encoding="utf-8")
    
    # Create section chunks
    chunks = create_section_chunks(text)
    
    # Get statistics
    stats = get_section_statistics(chunks)
    
    # Output results
    output = {
        "chunks": [chunk.to_dict() for chunk in chunks],
        "statistics": stats,
        "source_file": str(input_file),
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))