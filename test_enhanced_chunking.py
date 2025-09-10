#!/usr/bin/env python3
"""
Test script for the enhanced chunking functionality.

This script creates a mock Docling Document and tests the chunking pipeline
to verify that the implementation works as expected.
"""

import json
import tempfile
from pathlib import Path
import sys

def create_mock_docling_document():
    """Create a mock Docling Document for testing."""
    mock_document = {
        "texts": [
            {
                "self_ref": "#/texts/0",
                "parent": {"$ref": "#/body"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 100, "r": 500, "b": 120, "coord_origin": "TOPLEFT"},
                    "charspan": [0, 15]
                }],
                "orig": "Sección SI 1",
                "text": "Sección SI 1",
                "level": 1
            },
            {
                "self_ref": "#/texts/1",
                "parent": {"$ref": "#/texts/0"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 130, "r": 500, "b": 180, "coord_origin": "TOPLEFT"},
                    "charspan": [16, 150]
                }],
                "text": "Este es el contenido de la Sección SI 1. Contiene información importante sobre seguridad contra incendios y evacuación de edificios."
            },
            {
                "self_ref": "#/texts/2",
                "parent": {"$ref": "#/texts/0"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 200, "r": 500, "b": 220, "coord_origin": "TOPLEFT"},
                    "charspan": [151, 170]
                }],
                "orig": "1.1 Objetivo",
                "text": "1.1 Objetivo",
                "level": 2
            },
            {
                "self_ref": "#/texts/3",
                "parent": {"$ref": "#/texts/2"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 230, "r": 500, "b": 280, "coord_origin": "TOPLEFT"},
                    "charspan": [171, 350]
                }],
                "text": "El objetivo de esta sección es establecer las reglas y procedimientos para garantizar la seguridad de las personas en caso de incendio."
            },
            {
                "self_ref": "#/texts/4",
                "parent": {"$ref": "#/body"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 2,
                    "bbox": {"l": 72, "t": 100, "r": 500, "b": 120, "coord_origin": "TOPLEFT"},
                    "charspan": [351, 365]
                }],
                "orig": "Sección SI 2",
                "text": "Sección SI 2",
                "level": 1
            },
            {
                "self_ref": "#/texts/5",
                "parent": {"$ref": "#/texts/4"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 2,
                    "bbox": {"l": 72, "t": 130, "r": 500, "b": 250, "coord_origin": "TOPLEFT"},
                    "charspan": [366, 600]
                }],
                "text": "Esta sección trata sobre la propagación exterior del fuego. Se establecen las condiciones que deben cumplir los elementos constructivos para limitar el riesgo de propagación del incendio por el exterior del edificio."
            }
        ],
        "main_text": [
            {"text": "Sección SI 1", "label": "section_header"},
            {"text": "Este es el contenido de la Sección SI 1...", "label": "text"},
            {"text": "1.1 Objetivo", "label": "section_header"},
            {"text": "El objetivo de esta sección...", "label": "text"},
            {"text": "Sección SI 2", "label": "section_header"},
            {"text": "Esta sección trata sobre la propagación exterior del fuego...", "label": "text"}
        ],
        "document": {
            "name": "test_document.pdf"
        }
    }
    return mock_document

def test_chunking():
    """Test the enhanced chunking functionality."""
    
    # Add the current directory to Python path for imports
    sys.path.insert(0, str(Path(__file__).parent))
    
    try:
        from enhanced_lx_runner import create_chunks_from_docling_document
    except ImportError as e:
        print(f"Error importing chunking function: {e}")
        return False
    
    # Create mock Docling Document
    mock_doc = create_mock_docling_document()
    
    # Test chunking
    print("Testing enhanced chunking with mock Docling Document...")
    
    try:
        chunks = create_chunks_from_docling_document(mock_doc, max_chars=1000)
        
        print(f"\nChunking successful! Generated {len(chunks)} chunks:")
        
        for i, (chunk_text, section_info) in enumerate(chunks):
            print(f"\n--- Chunk {i+1} ---")
            print(f"Section: {section_info['section_name']}")
            print(f"Level: {section_info['section_level']}")
            print(f"Page: {section_info['start_page']}")
            print(f"Length: {len(chunk_text)} characters")
            print(f"Preview: {chunk_text[:200]}...")
        
        # Test JSON serialization
        chunks_data = []
        for i, (chunk_text, section_info) in enumerate(chunks):
            chunk_data = {
                "chunk_id": i + 1,
                "section_name": section_info.get("section_name", f"Section {i+1}"),
                "section_path": section_info.get("toc_path", []),
                "start_page": section_info.get("start_page"),
                "end_page": section_info.get("end_page"), 
                "section_level": section_info.get("section_level", 1),
                "chunk_text": chunk_text,
                "char_count": len(chunk_text)
            }
            chunks_data.append(chunk_data)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "pipeline_info": {
                    "version": "1.0",
                    "method": "docling_toc_based_chunking", 
                    "test_document": "mock_docling_document",
                    "total_chunks": len(chunks)
                },
                "chunks": chunks_data
            }, f, indent=2, ensure_ascii=False)
            
            print(f"\nTest chunks saved to: {f.name}")
        
        print("\n✅ Chunking test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Chunking test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Enhanced Chunking Test")
    print("=" * 50)
    
    success = test_chunking()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)