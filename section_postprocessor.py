#!/usr/bin/env python3
"""Post-processing utilities for section-based evaluation.

This module provides post-processing functionality for section chunks after
initial evaluation, implementing logic for:
1. Dropping children of dropped sections
2. Handling repeating section names according to specified rules
"""

from typing import Dict, Any, List, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass
from section_chunker import SectionChunk, SectionMetadata
from chunk_evaluator import ChunkEvaluation


@dataclass
class PostProcessingResult:
    """Result of post-processing operations."""
    processed_evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]
    dropped_sections: List[str]  # IDs of sections that were dropped
    merged_sections: List[Tuple[str, List[str]]]  # (target_id, merged_from_ids)
    processing_log: List[str]  # Log of operations performed


def drop_children_of_dropped_sections(
    evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]
) -> Tuple[List[Tuple[SectionChunk, ChunkEvaluation]], List[str], List[str]]:
    """Drop children of sections that are marked for dropping.
    
    Args:
        evaluations: List of (chunk, evaluation) tuples.
        
    Returns:
        Tuple of (filtered_evaluations, dropped_section_ids, processing_log)
    """
    # Find sections marked for dropping
    dropped_section_ids = set()
    for chunk, evaluation in evaluations:
        if evaluation.processing_type == "drop":
            dropped_section_ids.add(chunk.section_metadata.section_id)
    
    # Recursively find all children of dropped sections
    def find_all_children(section_id: str, evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]) -> Set[str]:
        children = set()
        for chunk, _ in evaluations:
            if chunk.section_metadata.parent_section_id == section_id:
                child_id = chunk.section_metadata.section_id
                children.add(child_id)
                # Recursively find grandchildren
                children.update(find_all_children(child_id, evaluations))
        return children
    
    # Find all descendants of dropped sections
    all_dropped = set(dropped_section_ids)
    for dropped_id in dropped_section_ids:
        all_dropped.update(find_all_children(dropped_id, evaluations))
    
    # Filter out dropped sections and their children
    filtered_evaluations = []
    processing_log = []
    
    for chunk, evaluation in evaluations:
        section_id = chunk.section_metadata.section_id
        if section_id in all_dropped:
            if section_id not in dropped_section_ids:
                # This was dropped because parent was dropped
                processing_log.append(f"Dropped section {section_id} ({chunk.section_metadata.section_name}) - child of dropped section")
            else:
                processing_log.append(f"Dropped section {section_id} ({chunk.section_metadata.section_name}) - marked for dropping")
        else:
            filtered_evaluations.append((chunk, evaluation))
    
    return filtered_evaluations, list(all_dropped), processing_log


def identify_repeating_section_names(
    evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]
) -> Dict[str, List[Tuple[SectionChunk, ChunkEvaluation]]]:
    """Identify sections with repeating names.
    
    Args:
        evaluations: List of (chunk, evaluation) tuples.
        
    Returns:
        Dictionary mapping section names to lists of (chunk, evaluation) tuples
        that share that name. Only includes names that appear more than once.
    """
    name_groups = defaultdict(list)
    
    for chunk, evaluation in evaluations:
        section_name = chunk.section_metadata.section_name
        name_groups[section_name].append((chunk, evaluation))
    
    # Only return groups with more than one section
    return {name: sections for name, sections in name_groups.items() if len(sections) > 1}


def handle_repeating_sections(
    repeating_groups: Dict[str, List[Tuple[SectionChunk, ChunkEvaluation]]],
    all_evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]
) -> Tuple[List[Tuple[SectionChunk, ChunkEvaluation]], List[Tuple[str, List[str]]], List[str]]:
    """Handle repeating section names according to specified rules.
    
    Rules:
    2.a) If all tagged for manual processing, merge them together into one,
         adjust parent relationship of children to point towards resulting section
    2.b) If some are marked for manual and some for extraction, drop the manual ones
         and point their children to the highest level (lowest level number) section
    2.c) If all are marked for extraction, drop all but the highest level (lowest level number)
    
    Args:
        repeating_groups: Dictionary of section name -> list of (chunk, evaluation) tuples
        all_evaluations: All evaluations for context and child relationship updates
        
    Returns:
        Tuple of (updated_evaluations, merged_sections_info, processing_log)
    """
    updated_evaluations = list(all_evaluations)
    merged_sections = []
    processing_log = []
    sections_to_remove = set()
    
    for section_name, sections in repeating_groups.items():
        processing_types = [eval.processing_type for _, eval in sections]
        
        # Categorize sections by processing type
        manual_sections = [(chunk, eval) for chunk, eval in sections if eval.processing_type == "manual"]
        extract_sections = [(chunk, eval) for chunk, eval in sections if eval.processing_type == "extract"]
        drop_sections = [(chunk, eval) for chunk, eval in sections if eval.processing_type == "drop"]
        
        # Rule 2.a: All manual - merge into one
        if len(manual_sections) == len(sections):
            # Find the highest level (lowest level number) section
            target_section = min(manual_sections, key=lambda x: x[0].section_metadata.section_level)
            target_chunk, target_eval = target_section
            target_id = target_chunk.section_metadata.section_id
            
            # Sections to merge (all except target)
            sections_to_merge = [chunk.section_metadata.section_id for chunk, _ in manual_sections 
                               if chunk.section_metadata.section_id != target_id]
            
            if sections_to_merge:
                # Update children to point to target section
                _update_children_parent(target_id, sections_to_merge, updated_evaluations)
                
                # Remove merged sections from evaluations
                sections_to_remove.update(sections_to_merge)
                
                merged_sections.append((target_id, sections_to_merge))
                processing_log.append(f"Merged manual sections '{section_name}': kept {target_id}, merged {sections_to_merge}")
        
        # Rule 2.b: Mixed manual and extraction - drop manual, keep extraction
        elif manual_sections and extract_sections:
            # Find highest level extraction section
            target_section = min(extract_sections, key=lambda x: x[0].section_metadata.section_level)
            target_id = target_section[0].section_metadata.section_id
            
            # Drop all manual sections
            manual_ids = [chunk.section_metadata.section_id for chunk, _ in manual_sections]
            
            # Update children of manual sections to point to target extraction section
            _update_children_parent(target_id, manual_ids, updated_evaluations)
            
            sections_to_remove.update(manual_ids)
            processing_log.append(f"Mixed sections '{section_name}': dropped manual {manual_ids}, kept extraction {target_id}")
        
        # Rule 2.c: All extraction - keep only highest level
        elif len(extract_sections) == len(sections):
            # Find highest level (lowest level number) section
            target_section = min(extract_sections, key=lambda x: x[0].section_metadata.section_level)
            target_id = target_section[0].section_metadata.section_id
            
            # Drop all other extraction sections
            sections_to_drop = [chunk.section_metadata.section_id for chunk, _ in extract_sections 
                              if chunk.section_metadata.section_id != target_id]
            
            if sections_to_drop:
                # Update children to point to target section
                _update_children_parent(target_id, sections_to_drop, updated_evaluations)
                
                sections_to_remove.update(sections_to_drop)
                processing_log.append(f"All-extraction sections '{section_name}': kept {target_id}, dropped {sections_to_drop}")
    
    # Filter out removed sections
    final_evaluations = [(chunk, eval) for chunk, eval in updated_evaluations 
                        if chunk.section_metadata.section_id not in sections_to_remove]
    
    return final_evaluations, merged_sections, processing_log


def _update_children_parent(target_parent_id: str, old_parent_ids: List[str], 
                           evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]) -> None:
    """Update children's parent references from old parents to new target parent.
    
    Args:
        target_parent_id: ID of the section that should become the new parent
        old_parent_ids: List of old parent IDs whose children should be reassigned
        evaluations: List of all evaluations to search for children
    """
    for chunk, _ in evaluations:
        if chunk.section_metadata.parent_section_id in old_parent_ids:
            # Update the parent reference
            chunk.section_metadata.parent_section_id = target_parent_id


def post_process_section_evaluations(
    evaluations: List[Tuple[SectionChunk, ChunkEvaluation]]
) -> PostProcessingResult:
    """Apply all post-processing rules to section evaluations.
    
    Args:
        evaluations: List of (chunk, evaluation) tuples from initial evaluation.
        
    Returns:
        PostProcessingResult with processed evaluations and operation details.
    """
    processing_log = []
    
    # Step 1: Drop children of dropped sections
    filtered_evaluations, dropped_section_ids, drop_log = drop_children_of_dropped_sections(evaluations)
    processing_log.extend(drop_log)
    
    # Step 2: Handle repeating section names
    repeating_groups = identify_repeating_section_names(filtered_evaluations)
    
    if repeating_groups:
        final_evaluations, merged_sections, repeat_log = handle_repeating_sections(
            repeating_groups, filtered_evaluations
        )
        processing_log.extend(repeat_log)
    else:
        final_evaluations = filtered_evaluations
        merged_sections = []
        processing_log.append("No repeating section names found")
    
    return PostProcessingResult(
        processed_evaluations=final_evaluations,
        dropped_sections=dropped_section_ids,
        merged_sections=merged_sections,
        processing_log=processing_log
    )


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path
    from section_chunker import create_section_chunks
    from chunk_evaluator import evaluate_chunks
    
    if len(sys.argv) != 2:
        print("Usage: python section_postprocessor.py <input_file.md>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File {input_file} does not exist")
        sys.exit(1)
    
    # Read and process the input file
    text = input_file.read_text(encoding="utf-8")
    chunks = create_section_chunks(text)
    evaluations = evaluate_chunks(chunks)
    
    # Apply post-processing
    result = post_process_section_evaluations(evaluations)
    
    # Output results
    output = {
        "source_file": str(input_file),
        "post_processing_result": {
            "total_sections_before": len(evaluations),
            "total_sections_after": len(result.processed_evaluations),
            "dropped_sections": result.dropped_sections,
            "merged_sections": result.merged_sections,
            "processing_log": result.processing_log
        },
        "final_evaluations": [
            {
                "section_metadata": chunk.section_metadata.to_dict(),
                "chunk_length": len(chunk.chunk_text),
                "evaluation": {
                    "should_extract": evaluation.should_extract,
                    "reason": evaluation.reason,
                    "processing_type": evaluation.processing_type,
                    "metadata": evaluation.metadata
                }
            }
            for chunk, evaluation in result.processed_evaluations
        ]
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))