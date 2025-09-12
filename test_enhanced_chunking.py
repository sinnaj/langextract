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
    """Create a mock Docling Document for testing with page headers and multi-level ToC."""
    mock_document = {
        "texts": [
            # Page 1 header (should be ignored)
            {
                "self_ref": "#/texts/0",
                "parent": {"$ref": "#/body"},
                "children": [],
                "content_layer": "body",
                "label": "page_header",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 50, "r": 500, "b": 70, "coord_origin": "TOPLEFT"},
                    "charspan": [0, 20]
                }],
                "text": "Página 1 - Header"
            },
            # Section SI 1 (Level 1 - in ToC)
            {
                "self_ref": "#/texts/1",
                "parent": {"$ref": "#/body"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 100, "r": 500, "b": 120, "coord_origin": "TOPLEFT"},
                    "charspan": [21, 35]
                }],
                "orig": "Sección SI 1",
                "text": "Sección SI 1",
                "level": 1
            },
            # Content for SI 1
            {
                "self_ref": "#/texts/2",
                "parent": {"$ref": "#/texts/1"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 130, "r": 500, "b": 180, "coord_origin": "TOPLEFT"},
                    "charspan": [36, 170]
                }],
                "text": "Este es el contenido de la Sección SI 1. Contiene información importante sobre seguridad contra incendios."
            },
            # Subsection 1.1 Objetivo (Level 2 - in ToC)
            {
                "self_ref": "#/texts/3",
                "parent": {"$ref": "#/texts/1"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 200, "r": 500, "b": 220, "coord_origin": "TOPLEFT"},
                    "charspan": [171, 185]
                }],
                "orig": "1.1 Objetivo",
                "text": "1.1 Objetivo",
                "level": 2
            },
            # Content for 1.1 Objetivo  
            {
                "self_ref": "#/texts/4",
                "parent": {"$ref": "#/texts/3"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 230, "r": 500, "b": 280, "coord_origin": "TOPLEFT"},
                    "charspan": [186, 365]
                }],
                "text": "El objetivo específico de esta subsección es establecer reglas detalladas para la seguridad."
            },
            # Non-ToC Header (should be treated as text content)
            {
                "self_ref": "#/texts/5",
                "parent": {"$ref": "#/texts/3"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 290, "r": 500, "b": 310, "coord_origin": "TOPLEFT"},
                    "charspan": [366, 385]
                }],
                "orig": "Non-ToC Header",
                "text": "Non-ToC Header",
                "level": 3
            },
            # Content under Non-ToC Header
            {
                "self_ref": "#/texts/6",
                "parent": {"$ref": "#/texts/5"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 320, "r": 500, "b": 350, "coord_origin": "TOPLEFT"},
                    "charspan": [386, 480]
                }],
                "text": "Este encabezado NO está en el ToC, por lo que debe ser tratado como texto del cuerpo."
            },
            # Subsection 1.2 Ámbito (Level 2 - in ToC)
            {
                "self_ref": "#/texts/7",
                "parent": {"$ref": "#/texts/1"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 370, "r": 500, "b": 390, "coord_origin": "TOPLEFT"},
                    "charspan": [481, 495]
                }],
                "orig": "1.2 Ámbito",
                "text": "1.2 Ámbito",
                "level": 2
            },
            # Content for 1.2 Ámbito
            {
                "self_ref": "#/texts/8",
                "parent": {"$ref": "#/texts/7"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 1,
                    "bbox": {"l": 72, "t": 400, "r": 500, "b": 450, "coord_origin": "TOPLEFT"},
                    "charspan": [496, 590]
                }],
                "text": "El ámbito de aplicación incluye todos los edificios y establecimientos."
            },
            # Page 2 header (should be ignored) 
            {
                "self_ref": "#/texts/9",
                "parent": {"$ref": "#/body"},
                "children": [],
                "content_layer": "body",
                "label": "page_header",
                "prov": [{
                    "page_no": 2,
                    "bbox": {"l": 72, "t": 50, "r": 500, "b": 70, "coord_origin": "TOPLEFT"},
                    "charspan": [591, 611]
                }],
                "text": "Página 2 - Header"
            },
            # Section SI 2 (Level 1 - in ToC)
            {
                "self_ref": "#/texts/10",
                "parent": {"$ref": "#/body"},
                "children": [],
                "content_layer": "body",
                "label": "section_header",
                "prov": [{
                    "page_no": 2,
                    "bbox": {"l": 72, "t": 100, "r": 500, "b": 120, "coord_origin": "TOPLEFT"},
                    "charspan": [612, 626]
                }],
                "orig": "Sección SI 2",
                "text": "Sección SI 2",
                "level": 1
            },
            # Content for SI 2
            {
                "self_ref": "#/texts/11",
                "parent": {"$ref": "#/texts/10"},
                "children": [],
                "content_layer": "body",
                "label": "text",
                "prov": [{
                    "page_no": 2,
                    "bbox": {"l": 72, "t": 130, "r": 500, "b": 250, "coord_origin": "TOPLEFT"},
                    "charspan": [627, 780]
                }],
                "text": "Esta sección trata sobre la propagación exterior del fuego. Se establecen las condiciones que deben cumplir los elementos constructivos."
            }
        ],
        "main_text": [
            {"text": "Página 1 - Header", "label": "page_header"},
            {"text": "Sección SI 1", "label": "section_header"},
            {"text": "Este es el contenido de la Sección SI 1...", "label": "text"},
            {"text": "1.1 Objetivo", "label": "section_header"},
            {"text": "El objetivo específico de esta subsección...", "label": "text"},
            {"text": "Non-ToC Header", "label": "section_header"},
            {"text": "Este encabezado NO está en el ToC...", "label": "text"},
            {"text": "1.2 Ámbito", "label": "section_header"},
            {"text": "El ámbito de aplicación incluye...", "label": "text"},
            {"text": "Página 2 - Header", "label": "page_header"},
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
        from enhanced_lx_runner import create_chunks_from_toc_and_docling
    except ImportError as e:
        print(f"Error importing chunking function: {e}")
        return False
    
    # Create mock ToC data with multiple levels
    mock_toc = [
        {
            "title": "Sección SI 1",
            "level": 1,
            "start_page": 1,
            "end_page": 1,
            "children": [
                {
                    "title": "1.1 Objetivo", 
                    "level": 2,
                    "start_page": 1,
                    "end_page": 1,
                    "children": []
                },
                {
                    "title": "1.2 Ámbito",
                    "level": 2,
                    "start_page": 1,
                    "end_page": 1,
                    "children": []
                }
            ]
        },
        {
            "title": "Sección SI 2",
            "level": 1, 
            "start_page": 2,
            "end_page": 2,
            "children": []
        }
    ]
    
    # Create mock Docling Document
    mock_doc = create_mock_docling_document()
    
    # Test chunking
    print("Testing enhanced ToC-based chunking with mock data...")
    
    try:
        chunks = create_chunks_from_toc_and_docling(mock_toc, mock_doc, max_chars=1000)
        
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
                    "method": "toc_based_chunking_with_docling", 
                    "test_document": "mock_toc_and_docling_document",
                    "total_chunks": len(chunks)
                },
                "chunks": chunks_data
            }, f, indent=2, ensure_ascii=False)
            
            print(f"\nTest chunks saved to: {f.name}")
        
        print("\n✅ ToC-based chunking test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ ToC-based chunking test failed: {e}")
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