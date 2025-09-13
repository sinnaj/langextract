#!/usr/bin/env python3
"""Debug script to analyze positioning data issues in the enhanced extraction pipeline."""

import json
import sys
from pathlib import Path

def analyze_positioning_data(extraction_file, docling_file):
    """Analyze the positioning data from extraction results and docling document."""
    
    # Load extraction data
    with open(extraction_file, 'r', encoding='utf-8') as f:
        extraction_data = json.load(f)
    
    # Load docling document
    with open(docling_file, 'r', encoding='utf-8') as f:
        docling_data = json.load(f)
    
    print("=== EXTRACTION DATA ANALYSIS ===")
    print(f"Total extractions: {len(extraction_data.get('extractions', []))}")
    print(f"Total sections: {len(extraction_data.get('sections', []))}")
    
    # Analyze extractions by type
    extraction_types = {}
    norms_count = 0
    chunk_metadata_count = 0
    
    for extraction in extraction_data.get('extractions', []):
        ext_type = extraction.get('extraction_class', 'Unknown')
        extraction_types[ext_type] = extraction_types.get(ext_type, 0) + 1
        
        if ext_type == 'NORM':
            norms_count += 1
        elif ext_type == 'CHUNK_METADATA':
            chunk_metadata_count += 1
    
    print(f"Extraction types: {extraction_types}")
    print(f"NORM extractions: {norms_count}")
    print(f"CHUNK_METADATA extractions: {chunk_metadata_count}")
    
    print("\n=== DOCLING DOCUMENT ANALYSIS ===")
    texts = docling_data.get('texts', [])
    print(f"Total text elements: {len(texts)}")
    
    # Count elements with positioning data
    elements_with_positioning = 0
    pages_found = set()
    
    for text_elem in texts:
        prov = text_elem.get('prov', [])
        if prov:
            elements_with_positioning += 1
            for p in prov:
                pages_found.add(p.get('page_no', 0))
    
    print(f"Text elements with positioning: {elements_with_positioning}")
    print(f"Pages with text: {sorted(list(pages_found))}")
    
    # Sample a few text elements to see their structure
    print("\n=== SAMPLE TEXT ELEMENTS ===")
    for i, text_elem in enumerate(texts[:3]):
        print(f"Text {i+1}:")
        print(f"  Text: {text_elem.get('text', '')[:100]}...")
        print(f"  Has positioning: {bool(text_elem.get('prov', []))}")
        if text_elem.get('prov'):
            first_prov = text_elem['prov'][0]
            print(f"  Page: {first_prov.get('page_no')}")
            print(f"  BBox: {first_prov.get('bbox')}")
    
    print("\n=== POSITIONING MAPPING ANALYSIS ===")
    
    # Test the actual mapping logic from app.py
    sys.path.append(str(Path(__file__).parent / 'web'))
    from app import extract_positioning_from_docling
    
    positioning_result = extract_positioning_from_docling(extraction_data, docling_data)
    
    print(f"Mapped sections: {len(positioning_result.get('sections', []))}")
    
    sections_with_positioning = 0
    norms_with_positioning = 0
    
    for section in positioning_result.get('sections', []):
        if 'positioning' in section:
            sections_with_positioning += 1
        
        for norm in section.get('norms', []):
            if 'positioning' in norm:
                norms_with_positioning += 1
    
    print(f"Sections with positioning: {sections_with_positioning}")
    print(f"Norms with positioning: {norms_with_positioning}")
    
    # Show detailed analysis for first few sections
    print("\n=== DETAILED SECTION ANALYSIS ===")
    for i, section in enumerate(positioning_result.get('sections', [])[:2]):
        print(f"\nSection {i+1}: {section.get('section_id', 'Unknown')}")
        print(f"  Has positioning: {'positioning' in section}")
        print(f"  Number of norms: {len(section.get('norms', []))}")
        
        # Check norm positioning details
        for j, norm in enumerate(section.get('norms', [])[:2]):
            print(f"  Norm {j+1} ({norm.get('norm_id', 'Unknown')}):")
            print(f"    Has positioning: {'positioning' in norm}")
            print(f"    Text length: {len(norm.get('extraction_text', ''))}")
            print(f"    Text sample: {norm.get('extraction_text', '')[:100]}...")
            
            if 'positioning' in norm:
                pos = norm['positioning']
                print(f"    Page: {pos.get('page_no')}")
                print(f"    BBox: {pos.get('bbox')}")

if __name__ == "__main__":
    # Use the test data we found
    extraction_file = "/home/runner/work/langextract/langextract/output_runs/1757671460/enhanced_output/enhanced_extraction_results.json"
    docling_file = "/home/runner/work/langextract/langextract/output_runs/1757671460/enhanced_output/headline_fixed_doclingdocument.json"
    
    analyze_positioning_data(extraction_file, docling_file)