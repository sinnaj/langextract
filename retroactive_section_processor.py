#!/usr/bin/env python3
"""Retroactive section processor for already processed output files.

This script applies section processing logic (dropping and merging sections)
to already processed output files that lacked these post-processing steps
prior to extraction.

The script takes a combined_extractions.json file and applies the same
post-processing logic that is normally applied during the evaluation phase
by chunk_evaluator.py and section_postprocessor.py.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from section_chunker import SectionChunk, SectionMetadata
from chunk_evaluator import ChunkEvaluation
from section_postprocessor import post_process_section_evaluations


def load_combined_extractions(file_path: Path) -> Dict[str, Any]:
    """Load the combined extractions JSON file.
    
    Args:
        file_path: Path to the combined_extractions.json file
        
    Returns:
        Parsed JSON data
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def convert_section_to_chunk_evaluation(section: Dict[str, Any]) -> Tuple[SectionChunk, ChunkEvaluation]:
    """Convert a section from JSON format to SectionChunk and ChunkEvaluation.
    
    Args:
        section: Section data from the JSON file
        
    Returns:
        Tuple of (SectionChunk, ChunkEvaluation)
    """
    # Create SectionMetadata
    metadata = SectionMetadata(
        section_id=section["section_id"],
        section_name=section["section_name"],
        section_level=section["section_level"],
        section_index=section["section_index"],
        parent_section_id=section["parent_section"]
    )
    
    # Create a minimal SectionChunk (we don't have the original text)
    chunk = SectionChunk(
        chunk_text="",  # Empty since we're working with processed data
        section_metadata=metadata,
        char_start=0,  # Placeholder values since we don't have original text
        char_end=0
    )
    
    # Create ChunkEvaluation from the section data
    evaluation = ChunkEvaluation(
        should_extract=(section["processing_type"] == "extract"),
        reason=section.get("evaluation_reason", ""),
        processing_type=section["processing_type"],
        metadata=section.get("metadata", {})
    )
    
    return chunk, evaluation


def convert_sections_to_evaluations(sections: List[Dict[str, Any]]) -> List[Tuple[SectionChunk, ChunkEvaluation]]:
    """Convert all sections from JSON to the evaluation format.
    
    Args:
        sections: List of section dictionaries from JSON
        
    Returns:
        List of (SectionChunk, ChunkEvaluation) tuples
    """
    evaluations = []
    for section in sections:
        chunk, evaluation = convert_section_to_chunk_evaluation(section)
        evaluations.append((chunk, evaluation))
    
    return evaluations


def convert_evaluations_back_to_sections(
    evaluations: List[Tuple[SectionChunk, ChunkEvaluation]],
    original_sections: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Convert processed evaluations back to section format.
    
    Args:
        evaluations: Processed evaluations from post-processing
        original_sections: Original section data for preserving fields
        
    Returns:
        Updated sections list
    """
    # Create a mapping of section_id to original section data
    original_sections_map = {section["section_id"]: section for section in original_sections}
    
    updated_sections = []
    for chunk, evaluation in evaluations:
        section_id = chunk.section_metadata.section_id
        
        # Start with original section data
        if section_id in original_sections_map:
            updated_section = original_sections_map[section_id].copy()
        else:
            # This shouldn't happen in normal cases, but handle gracefully
            updated_section = {
                "section_id": section_id,
                "section_name": chunk.section_metadata.section_name,
                "section_level": chunk.section_metadata.section_level,
                "section_index": chunk.section_metadata.section_index,
                "parent_section": chunk.section_metadata.parent_section_id,
                "sub_sections": [],
                "section_summary": "",
                "has_extractions": False,
                "extraction_count": 0
            }
        
        # Update with processed evaluation data
        updated_section["processing_type"] = evaluation.processing_type
        updated_section["evaluation_reason"] = evaluation.reason
        
        # Update parent reference if it was changed during post-processing
        updated_section["parent_section"] = chunk.section_metadata.parent_section_id
        
        updated_sections.append(updated_section)
    
    return updated_sections


def update_subsection_references(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Update sub_sections lists based on current parent-child relationships.
    
    Args:
        sections: List of section dictionaries
        
    Returns:
        Updated sections with corrected sub_sections lists
    """
    # Create mapping of parent to children
    parent_to_children = {}
    for section in sections:
        parent_id = section["parent_section"]
        if parent_id:
            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = []
            parent_to_children[parent_id].append(section["section_id"])
    
    # Update sub_sections for each section
    for section in sections:
        section_id = section["section_id"]
        section["sub_sections"] = parent_to_children.get(section_id, [])
    
    return sections


def process_combined_extractions(input_file: Path, output_file: Path = None) -> None:
    """Process a combined extractions file with retroactive section processing.
    
    Args:
        input_file: Path to input combined_extractions.json file
        output_file: Path for output file (defaults to input_file with _processed suffix)
    """
    # Load the original data
    data = load_combined_extractions(input_file)
    
    # Extract sections
    sections = data.get("sections", [])
    if not sections:
        print("No sections found in the input file.")
        return
    
    print(f"Processing {len(sections)} sections...")
    
    # Convert to evaluation format
    evaluations = convert_sections_to_evaluations(sections)
    
    # Apply post-processing
    result = post_process_section_evaluations(evaluations)
    
    # Convert back to sections format
    updated_sections = convert_evaluations_back_to_sections(result.processed_evaluations, sections)
    
    # Update subsection references
    updated_sections = update_subsection_references(updated_sections)
    
    # Update the data
    data["sections"] = updated_sections
    
    # Add post-processing information
    postprocessing_info = {
        "enabled": True,
        "total_sections_before": len(sections),
        "total_sections_after": len(updated_sections),
        "dropped_sections": result.dropped_sections,
        "merged_sections": result.merged_sections,
        "processing_log": result.processing_log
    }
    
    # Update evaluation statistics if they exist
    if "evaluation_statistics" in data:
        # Recalculate statistics based on updated sections
        extract_count = sum(1 for s in updated_sections if s["processing_type"] == "extract")
        manual_count = sum(1 for s in updated_sections if s["processing_type"] == "manual")
        drop_count = sum(1 for s in updated_sections if s["processing_type"] == "drop")
        total = len(updated_sections)
        
        data["evaluation_statistics"].update({
            "total_chunks": total,
            "extract_count": extract_count,
            "manual_count": manual_count,
            "drop_count": drop_count,
            "extract_percentage": round((extract_count / total * 100), 1) if total > 0 else 0,
            "manual_percentage": round((manual_count / total * 100), 1) if total > 0 else 0,
            "drop_percentage": round((drop_count / total * 100), 1) if total > 0 else 0
        })
    
    # Add or update postprocessing info
    data["postprocessing"] = postprocessing_info
    
    # Update document metadata
    if "document_metadata" in data:
        data["document_metadata"]["total_processed_sections"] = len(updated_sections)
    
    # Determine output file path
    if output_file is None:
        output_file = input_file.parent / f"{input_file.stem}_processed{input_file.suffix}"
    
    # Write the updated data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Processed file saved to: {output_file}")
    print(f"Sections before processing: {len(sections)}")
    print(f"Sections after processing: {len(updated_sections)}")
    print(f"Dropped sections: {len(result.dropped_sections)}")
    print(f"Merged sections: {len(result.merged_sections)}")
    
    if result.processing_log:
        print("\nProcessing log:")
        for log_entry in result.processing_log:
            print(f"  {log_entry}")


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python retroactive_section_processor.py <input_file> [output_file]")
        print("Example: python retroactive_section_processor.py output_runs/1757020697/lx output/combined_extractions.json")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) == 3 else None
    
    if not input_file.exists():
        print(f"Error: Input file {input_file} does not exist")
        sys.exit(1)
    
    try:
        process_combined_extractions(input_file, output_file)
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()