#!/usr/bin/env python3
"""
Add section application metadata from CHUNK_METADATA extractions.

This script processes enhanced_extraction_results.json files and propagates
meta_applies_if and meta_exempt_if attributes from CHUNK_METADATA extractions
to their parent sections.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def add_metadata_to_sections(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add meta_applies_if and meta_exempt_if from CHUNK_METADATA to parent sections.
    
    Args:
        data: The parsed JSON data containing sections and extractions
        
    Returns:
        Modified data with updated section metadata
    """
    # Build a map of section_id -> section for quick lookup
    sections = data.get("sections", [])
    section_map: Dict[str, Dict[str, Any]] = {}
    for section in sections:
        section_id = section.get("section_id")
        if section_id:
            section_map[section_id] = section
    
    # Process CHUNK_METADATA extractions
    extractions = data.get("extractions", [])
    metadata_added = 0
    
    for extraction in extractions:
        if not isinstance(extraction, dict):
            continue
            
        extraction_class = extraction.get("extraction_class")
        if extraction_class != "CHUNK_METADATA":
            continue
        
        attributes = extraction.get("attributes", {})
        parent_section_id = attributes.get("parent_section_id")
        
        if not parent_section_id or parent_section_id not in section_map:
            continue
        
        # Get the metadata attributes from CHUNK_METADATA
        meta_applies_if = attributes.get("meta_applies_if")
        meta_exempt_if = attributes.get("meta_exempt_if")
        
        # Add to parent section if they exist
        parent_section = section_map[parent_section_id]
        
        if meta_applies_if is not None:
            parent_section["meta_applies_if"] = meta_applies_if
            metadata_added += 1
            
        if meta_exempt_if is not None:
            parent_section["meta_exempt_if"] = meta_exempt_if
            if meta_applies_if is None:  # Only count once per CHUNK_METADATA
                metadata_added += 1
    
    # Add processing info
    if metadata_added > 0:
        processing_stats = data.setdefault("processing_stats", {})
        processing_stats["section_metadata_enriched"] = metadata_added
    
    return data


def process_file(input_path: Path, output_path: Optional[Path] = None) -> None:
    """
    Process an enhanced_extraction_results.json file.
    
    Args:
        input_path: Path to the input JSON file
        output_path: Path to save the output (defaults to overwriting input)
    """
    if not input_path.exists():
        print(f"Error: File {input_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    # Read the input file
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Process the data
    updated_data = add_metadata_to_sections(data)
    
    # Determine output path
    if output_path is None:
        output_path = input_path
    
    # Write the output file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(updated_data, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully processed {input_path}")
    print(f"Output written to {output_path}")


def main():
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print("Usage: python add_section_application_metadata.py <input_file.json> [output_file.json]")
        print("\nExample:")
        print("  python add_section_application_metadata.py output_runs/1757864159/enhanced_output/enhanced_extraction_results.json")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    process_file(input_path, output_path)


if __name__ == "__main__":
    main()
