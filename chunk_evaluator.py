#!/usr/bin/env python3
"""Chunk evaluator for section-based processing.

This script evaluates section chunks and decides whether they should be passed to 
lx.extract or processed manually. It identifies Table of Contents sections and 
headline-only sections that don't need extraction.
"""

import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from section_chunker import SectionChunk, SectionMetadata


@dataclass
class ChunkEvaluation:
    """Result of chunk evaluation."""
    should_extract: bool
    reason: str
    processing_type: str  # "extract", "drop", "manual"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


def is_table_of_contents(chunk: SectionChunk) -> bool:
    """Check if a chunk appears to be a Table of Contents.
    
    Args:
        chunk: The section chunk to evaluate.
        
    Returns:
        True if the chunk appears to be a TOC, False otherwise.
    """
    text = chunk.chunk_text.lower()
    title = chunk.section_metadata.section_name.lower()
    
    # Check for common TOC indicators in title
    toc_titles = [
        "índice", "indice", "table of contents", "contents", "tabla de contenidos",
        "contenido", "contenidos", "sumario", "index"
    ]
    
    if any(toc_title in title for toc_title in toc_titles):
        return True
    
    # Check for TOC patterns in content
    lines = chunk.chunk_text.split('\n')
    content_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
    
    if len(content_lines) < 3:
        return False
    
    # Look for patterns like:
    # 1. Introduction .................. 5
    # 2.1 Overview .................... 12
    # Chapter 1: Getting Started ...... 15
    page_number_pattern = r'\.{3,}.*?\d+\s*$'
    numbered_list_pattern = r'^\d+(\.\d+)*\.?\s+'
    
    toc_indicators = 0
    
    for line in content_lines[:10]:  # Check first 10 content lines
        if re.search(page_number_pattern, line):
            toc_indicators += 1
        elif re.search(numbered_list_pattern, line):
            toc_indicators += 1
    
    # If more than 50% of lines look like TOC entries
    return toc_indicators > len(content_lines[:10]) * 0.5


def is_headline_only(chunk: SectionChunk) -> bool:
    """Check if a chunk contains only headlines with no substantial content.
    
    Args:
        chunk: The section chunk to evaluate.
        
    Returns:
        True if the chunk is headline-only, False otherwise.
    """
    lines = chunk.chunk_text.split('\n')
    
    # Count different types of lines
    header_lines = 0
    content_lines = 0
    empty_lines = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            empty_lines += 1
        elif line.startswith('#'):
            header_lines += 1
        elif len(line) > 20:  # Substantial content line
            content_lines += 1
        else:
            # Short lines that might be labels or minimal content
            if len(line) > 3:  # Not just punctuation
                content_lines += 0.5  # Count as half content
    
    # Consider it headline-only if:
    # 1. Has headers but very little content
    # 2. Content is less than 10% of the total meaningful lines
    total_meaningful = header_lines + content_lines
    
    if total_meaningful == 0:
        return True
    
    content_ratio = content_lines / total_meaningful
    
    # If less than 15% content and we have headers, it's probably headline-only
    return header_lines > 0 and content_ratio < 0.15


def evaluate_chunk(chunk: SectionChunk) -> ChunkEvaluation:
    """Evaluate a section chunk to determine processing approach.
    
    Args:
        chunk: The section chunk to evaluate.
        
    Returns:
        ChunkEvaluation with processing decision and reasoning.
    """
    # Check for Table of Contents
    if is_table_of_contents(chunk):
        return ChunkEvaluation(
            should_extract=False,
            reason="Identified as Table of Contents",
            processing_type="drop",
            metadata={"content_type": "table_of_contents"}
        )
    
    # Check for headline-only content
    if is_headline_only(chunk):
        return ChunkEvaluation(
            should_extract=False,
            reason="Contains only headlines with minimal content",
            processing_type="manual",
            metadata={
                "content_type": "headline_only",
                "section_structure": True,
                "add_to_final_json": True
            }
        )
    
    # Default: extract normally
    return ChunkEvaluation(
        should_extract=True,
        reason="Contains substantial content suitable for extraction",
        processing_type="extract",
        metadata={"content_type": "substantial_content"}
    )


def evaluate_chunks(chunks: List[SectionChunk]) -> List[Tuple[SectionChunk, ChunkEvaluation]]:
    """Evaluate a list of section chunks.
    
    Args:
        chunks: List of section chunks to evaluate.
        
    Returns:
        List of tuples (chunk, evaluation) for each input chunk.
    """
    results = []
    
    for chunk in chunks:
        evaluation = evaluate_chunk(chunk)
        results.append((chunk, evaluation))
    
    return results


def get_evaluation_statistics(evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]) -> Dict[str, Any]:
    """Get statistics about chunk evaluations.
    
    Args:
        evaluations: List of (chunk, evaluation) tuples.
        
    Returns:
        Dictionary with evaluation statistics.
    """
    total = len(evaluations)
    if total == 0:
        return {"total": 0}
    
    extract_count = sum(1 for _, eval in evaluations if eval.processing_type == "extract")
    drop_count = sum(1 for _, eval in evaluations if eval.processing_type == "drop")
    manual_count = sum(1 for _, eval in evaluations if eval.processing_type == "manual")
    
    return {
        "total_chunks": total,
        "extract_count": extract_count,
        "drop_count": drop_count,
        "manual_count": manual_count,
        "extract_percentage": round(extract_count / total * 100, 1),
        "drop_percentage": round(drop_count / total * 100, 1),
        "manual_percentage": round(manual_count / total * 100, 1),
    }


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    from section_chunker import create_section_chunks
    
    if len(sys.argv) != 2:
        print("Usage: python chunk_evaluator.py <input_file.md>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File {input_file} does not exist")
        sys.exit(1)
    
    # Read and chunk the input file
    text = input_file.read_text(encoding="utf-8")
    chunks = create_section_chunks(text)
    
    # Evaluate chunks
    evaluations = evaluate_chunks(chunks)
    stats = get_evaluation_statistics(evaluations)
    
    # Output results
    output = {
        "source_file": str(input_file),
        "evaluation_statistics": stats,
        "chunk_evaluations": []
    }
    
    for chunk, evaluation in evaluations:
        chunk_data = {
            "section_metadata": chunk.section_metadata.to_dict(),
            "chunk_length": len(chunk.chunk_text),
            "evaluation": {
                "should_extract": evaluation.should_extract,
                "reason": evaluation.reason,
                "processing_type": evaluation.processing_type,
                "metadata": evaluation.metadata
            }
        }
        output["chunk_evaluations"].append(chunk_data)
    
    print(json.dumps(output, ensure_ascii=False, indent=2))