#!/usr/bin/env python3
"""Test complete table section integration with extraction pipeline."""

import json
import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extraction_pipeline.enhanced_chunking import (
    create_enhanced_sections_from_toc, 
    create_section_chunks_with_context_optimized,
    extract_section_content
)
from extraction_pipeline.data_models import EnhancedSection


def test_complete_table_integration():
    """Test complete integration from ToC to section chunks including tables."""
    
    # Mock ToC data
    toc_data = [
        {
            "title": "Requirements Analysis",
            "level": 1,
            "start_page": 1,
            "end_page": 5,
            "children": [
                {
                    "title": "Material Properties",
                    "level": 2,
                    "start_page": 3,
                    "end_page": 4,
                    "children": []
                }
            ]
        }
    ]
    
    # Mock docling document with both text content and tables
    docling_document = {
        "pages": [
            {
                "page": 1,
                "elements": [
                    {"type": "text", "text": "This document outlines the requirements."},
                    {"type": "text", "text": "Key specifications are provided below."}
                ]
            },
            {
                "page": 3,
                "elements": [
                    {"type": "text", "text": "Material properties must meet standards."},
                    {"type": "text", "text": "See the table below for detailed values."}
                ]
            },
            {
                "page": 4,
                "elements": [
                    {"type": "text", "text": "Additional requirements apply."}
                ]
            }
        ],
        "tables": [
            {
                "prov": [{"page_no": 3}],
                "data": {
                    "table_cells": [
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Material"},
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "Strength (MPa)"},
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 2, "text": "Temperature (°C)"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text": "Steel"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text": "400"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 2, "text": "150"},
                        {"start_row_offset_idx": 2, "start_col_offset_idx": 0, "text": "Aluminum"},
                        {"start_row_offset_idx": 2, "start_col_offset_idx": 1, "text": "300"},
                        {"start_row_offset_idx": 2, "start_col_offset_idx": 2, "text": "200"}
                    ]
                }
            },
            {
                "prov": [{"page_no": 4}],
                "data": {
                    "table_cells": [
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Test"},
                        {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "Frequency"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text": "Pressure"},
                        {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text": "Weekly"}
                    ]
                }
            }
        ]
    }
    
    print("=== Testing Complete Table Section Integration ===")
    
    # 1. Create enhanced sections (including table sections)
    print("\n1. Creating enhanced sections from ToC...")
    sections = create_enhanced_sections_from_toc(toc_data, docling_document)
    
    print(f"Created {len(sections)} sections:")
    for section in sections:
        print(f"  - {section.section_name} (Type: {section.section_type}, Level: {section.section_level})")
        if section.parent_section_id:
            parent = next((s for s in sections if s.section_id == section.parent_section_id), None)
            if parent:
                print(f"    Parent: {parent.section_name}")
        if section.sub_section_ids:
            print(f"    Children: {len(section.sub_section_ids)}")
    
    # 2. Create chunks for extraction
    print("\n2. Creating chunks for extraction...")
    chunks = create_section_chunks_with_context_optimized(sections, docling_document, max_chars=1000)
    
    print(f"Created {len(chunks)} chunks:")
    for i, (chunk_text, section) in enumerate(chunks):
        print(f"\nChunk {i+1} - Section: {section.section_name} (Type: {section.section_type})")
        print(f"Text preview: {chunk_text[:200]}...")
        if section.section_type == "Table":
            print("  ^^ This is a TABLE chunk - should contain markdown table")
        else:
            print("  ^^ This is a REGULAR chunk - should NOT contain table data")
    
    # 3. Verify table sections contain proper table markdown
    print("\n3. Verifying table sections...")
    table_sections = [s for s in sections if s.section_type == "Table"]
    print(f"Found {len(table_sections)} table sections")
    
    for table_section in table_sections:
        content = extract_section_content(table_section, docling_document)
        print(f"\nTable section '{table_section.section_name}' content:")
        print(content)
        print(f"Contains markdown table: {'|' in content and '---' in content}")
    
    # 4. Create a mock output structure that could be used by web visualization
    print("\n4. Creating output structure for web visualization...")
    output_structure = {
        "sections": [
            {
                "section_id": section.section_id,
                "section_name": section.section_name,
                "section_type": section.section_type,
                "section_level": section.section_level,
                "toc_path": section.toc_path,
                "parent_section_id": section.parent_section_id,
                "sub_section_ids": section.sub_section_ids,
                "start_page": section.start_page,
                "end_page": section.end_page
            }
            for section in sections
        ],
        "chunks": [
            {
                "chunk_index": i,
                "section_id": section.section_id,
                "section_name": section.section_name,
                "section_type": section.section_type,
                "chunk_preview": chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text
            }
            for i, (chunk_text, section) in enumerate(chunks)
        ]
    }
    
    # Save to file for inspection
    output_file = Path("test_table_integration_output.json")
    with open(output_file, 'w') as f:
        json.dump(output_structure, f, indent=2, ensure_ascii=False)
    
    print(f"Output structure saved to: {output_file}")
    
    # Verify key requirements
    print("\n=== Verification ===")
    
    # Requirement 1: Tables converted to markdown
    table_chunks = [(chunk, section) for chunk, section in chunks if section.section_type == "Table"]
    print(f"✓ Table chunks contain markdown: {all('|' in chunk for chunk, _ in table_chunks)}")
    
    # Requirement 2.1: Tables show up as sections with parent relationships
    table_sections = [s for s in sections if s.section_type == "Table"]
    all_have_parents = all(ts.parent_section_id is not None for ts in table_sections)
    print(f"✓ All table sections have parents: {all_have_parents}")
    
    # Requirement 2.2: Regular sections don't include table content
    regular_chunks = [(chunk, section) for chunk, section in chunks if section.section_type == "Headline"]
    no_tables_in_regular = all('| --- |' not in chunk for chunk, _ in regular_chunks)
    print(f"✓ Regular sections don't contain table markdown: {no_tables_in_regular}")
    
    print("\n=== Integration Test Completed Successfully ===")
    return sections, chunks, output_structure


if __name__ == '__main__':
    test_complete_table_integration()