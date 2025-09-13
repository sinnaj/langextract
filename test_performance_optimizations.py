#!/usr/bin/env python3
"""Test script to verify performance optimizations in chunk processing alignment."""

import json
import time
from typing import Dict, Any, List
from extraction_pipeline.enhanced_chunking import (
    convert_table_to_markdown,
    build_document_caches,
    extract_section_content,
    validate_section_alignment,
    create_section_chunks_with_context_optimized,
    EnhancedSection
)

def create_test_docling_document() -> Dict[str, Any]:
    """Create a test Docling document with pages, tables, and headers."""
    return {
        'pages': [
            {
                'page': 1,
                'elements': [
                    {'type': 'heading1', 'text': 'Introduction', 'level': 1},
                    {'type': 'text', 'text': 'This is the introduction section with some content.'},
                    {'type': 'text', 'text': 'More content in the introduction.'}
                ]
            },
            {
                'page': 2,
                'elements': [
                    {'type': 'heading2', 'text': 'Methods', 'level': 2},
                    {'type': 'text', 'text': 'This section describes the methods used.'},
                    {'type': 'text', 'text': 'Additional methodological details.'}
                ]
            },
            {
                'page': 3,
                'elements': [
                    {'type': 'heading2', 'text': 'Results', 'level': 2},
                    {'type': 'text', 'text': 'The results are presented here.'}
                ]
            }
        ],
        'tables': [
            {
                'prov': [{'page_no': 2}],
                'data': {
                    'table_cells': [
                        {'start_row_offset_idx': 0, 'start_col_offset_idx': 0, 'text': 'Header 1'},
                        {'start_row_offset_idx': 0, 'start_col_offset_idx': 1, 'text': 'Header 2'},
                        {'start_row_offset_idx': 1, 'start_col_offset_idx': 0, 'text': 'Row 1 Col 1'},
                        {'start_row_offset_idx': 1, 'start_col_offset_idx': 1, 'text': 'Row 1 Col 2'},
                        {'start_row_offset_idx': 2, 'start_col_offset_idx': 0, 'text': 'Row 2 Col 1'},
                        {'start_row_offset_idx': 2, 'start_col_offset_idx': 1, 'text': 'Row 2 Col 2'}
                    ]
                }
            }
        ]
    }

def create_test_section() -> EnhancedSection:
    """Create a test enhanced section."""
    return EnhancedSection(
        section_id="test_section_1",
        section_name="Methods",
        section_level=2,
        section_index=1,
        start_page=2,
        end_page=2,
        toc_path=["Methods"],
        sub_section_ids=[],
        parent_section_id=None,
        tags=[]
    )

def test_table_conversion_performance():
    """Test the optimized table conversion."""
    print("Testing table conversion performance...")
    
    # Create a large table for performance testing
    large_table_data = {
        'table_cells': []
    }
    
    # Create a 100x10 table
    for row in range(100):
        for col in range(10):
            large_table_data['table_cells'].append({
                'start_row_offset_idx': row,
                'start_col_offset_idx': col,
                'text': f'Cell_{row}_{col}'
            })
    
    # Time the conversion
    start_time = time.time()
    result = convert_table_to_markdown(large_table_data)
    end_time = time.time()
    
    print(f"Table conversion took {end_time - start_time:.4f} seconds")
    print(f"Generated markdown has {len(result)} characters")
    
    # Verify the result contains expected content
    assert '| Cell_0_0 | Cell_0_1 |' in result
    assert '| --- | --- |' in result
    assert 'Cell_99_9' in result
    print("✓ Table conversion test passed")

def test_document_caches():
    """Test the document cache building."""
    print("Testing document cache building...")
    
    docling_doc = create_test_docling_document()
    
    start_time = time.time()
    page_cache, header_cache, sorted_headers = build_document_caches(docling_doc)
    end_time = time.time()
    
    print(f"Cache building took {end_time - start_time:.4f} seconds")
    print(f"Built caches: {len(page_cache)} pages, {len(header_cache)} headers")
    
    # Verify caches are built correctly
    assert len(page_cache) == 3  # 3 pages
    assert 'introduction' in header_cache
    assert 'methods' in header_cache
    assert 'results' in header_cache
    
    print("✓ Document cache test passed")

def test_optimized_content_extraction():
    """Test the optimized content extraction."""
    print("Testing optimized content extraction...")
    
    docling_doc = create_test_docling_document()
    section = create_test_section()
    
    # Test with and without cache
    page_cache, _, _ = build_document_caches(docling_doc)
    
    start_time = time.time()
    content_with_cache = extract_section_content(section, docling_doc, page_cache)
    cache_time = time.time() - start_time
    
    start_time = time.time()
    content_without_cache = extract_section_content(section, docling_doc, None)
    no_cache_time = time.time() - start_time
    
    print(f"Content extraction with cache: {cache_time:.4f} seconds")
    print(f"Content extraction without cache: {no_cache_time:.4f} seconds")
    
    # Content should be the same
    assert content_with_cache == content_without_cache
    print("✓ Optimized content extraction test passed")

def test_alignment_validation():
    """Test the optimized alignment validation."""
    print("Testing alignment validation...")
    
    docling_doc = create_test_docling_document()
    sections = [create_test_section()]
    
    start_time = time.time()
    warnings = validate_section_alignment(sections, docling_doc)
    end_time = time.time()
    
    print(f"Alignment validation took {end_time - start_time:.4f} seconds")
    print(f"Found {len(warnings)} warnings")
    
    # Should find the Methods section correctly
    assert len(warnings) == 0, f"Unexpected warnings: {warnings}"
    print("✓ Alignment validation test passed")

def main():
    """Run all performance optimization tests."""
    print("Running performance optimization tests...")
    print("=" * 50)
    
    test_table_conversion_performance()
    print()
    
    test_document_caches()
    print()
    
    test_optimized_content_extraction()
    print()
    
    test_alignment_validation()
    print()
    
    print("=" * 50)
    print("All performance optimization tests passed! ✓")

if __name__ == "__main__":
    main()