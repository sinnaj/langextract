#!/usr/bin/env python3
"""
Tests for add_section_application_metadata.py
"""

import json
import tempfile
from pathlib import Path
import sys
import os

# Add postprocessing directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'postprocessing'))

from add_section_application_metadata import add_metadata_to_sections, process_file


def test_add_metadata_basic():
    """Test basic metadata addition to sections."""
    test_data = {
        "sections": [
            {
                "section_id": "section_001",
                "section_name": "Test Section",
                "section_level": 1
            },
            {
                "section_id": "section_002",
                "section_name": "Another Section",
                "section_level": 2
            }
        ],
        "extractions": [
            {
                "extraction_class": "CHUNK_METADATA",
                "attributes": {
                    "parent_section_id": "section_001",
                    "meta_applies_if": "TRUE",
                    "meta_exempt_if": "BUILDING.USAGE == 'INDUSTRIAL'"
                }
            },
            {
                "extraction_class": "CHUNK_METADATA",
                "attributes": {
                    "parent_section_id": "section_002",
                    "meta_applies_if": "BUILDING.TYPE == 'RESIDENTIAL'",
                    "meta_exempt_if": "FALSE"
                }
            }
        ]
    }
    
    result = add_metadata_to_sections(test_data)
    
    # Check that metadata was added to sections
    assert result["sections"][0]["meta_applies_if"] == "TRUE"
    assert result["sections"][0]["meta_exempt_if"] == "BUILDING.USAGE == 'INDUSTRIAL'"
    
    assert result["sections"][1]["meta_applies_if"] == "BUILDING.TYPE == 'RESIDENTIAL'"
    assert result["sections"][1]["meta_exempt_if"] == "FALSE"
    
    # Check processing stats
    assert "processing_stats" in result
    assert "section_metadata_enriched" in result["processing_stats"]
    
    print("✓ test_add_metadata_basic passed")


def test_missing_parent_section():
    """Test handling of CHUNK_METADATA with missing parent section."""
    test_data = {
        "sections": [
            {
                "section_id": "section_001",
                "section_name": "Test Section",
                "section_level": 1
            }
        ],
        "extractions": [
            {
                "extraction_class": "CHUNK_METADATA",
                "attributes": {
                    "parent_section_id": "nonexistent_section",
                    "meta_applies_if": "TRUE",
                    "meta_exempt_if": "FALSE"
                }
            }
        ]
    }
    
    result = add_metadata_to_sections(test_data)
    
    # Section should not have metadata since parent_section_id doesn't exist
    assert "meta_applies_if" not in result["sections"][0]
    assert "meta_exempt_if" not in result["sections"][0]
    
    print("✓ test_missing_parent_section passed")


def test_non_chunk_metadata_ignored():
    """Test that non-CHUNK_METADATA extractions are ignored."""
    test_data = {
        "sections": [
            {
                "section_id": "section_001",
                "section_name": "Test Section",
                "section_level": 1
            }
        ],
        "extractions": [
            {
                "extraction_class": "NORM",
                "attributes": {
                    "parent_section_id": "section_001",
                    "meta_applies_if": "TRUE"
                }
            }
        ]
    }
    
    result = add_metadata_to_sections(test_data)
    
    # Section should not have metadata since extraction is not CHUNK_METADATA
    assert "meta_applies_if" not in result["sections"][0]
    
    print("✓ test_non_chunk_metadata_ignored passed")


def test_partial_metadata():
    """Test handling of CHUNK_METADATA with only one metadata field."""
    test_data = {
        "sections": [
            {
                "section_id": "section_001",
                "section_name": "Test Section",
                "section_level": 1
            }
        ],
        "extractions": [
            {
                "extraction_class": "CHUNK_METADATA",
                "attributes": {
                    "parent_section_id": "section_001",
                    "meta_applies_if": "TRUE"
                }
            }
        ]
    }
    
    result = add_metadata_to_sections(test_data)
    
    # Only meta_applies_if should be added
    assert result["sections"][0]["meta_applies_if"] == "TRUE"
    assert "meta_exempt_if" not in result["sections"][0]
    
    print("✓ test_partial_metadata passed")


def test_file_processing():
    """Test processing a file."""
    test_data = {
        "sections": [
            {
                "section_id": "section_001",
                "section_name": "Test Section",
                "section_level": 1
            }
        ],
        "extractions": [
            {
                "extraction_class": "CHUNK_METADATA",
                "attributes": {
                    "parent_section_id": "section_001",
                    "meta_applies_if": "TRUE",
                    "meta_exempt_if": "BUILDING.USAGE == 'INDUSTRIAL'"
                }
            }
        ]
    }
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_data, f)
        temp_path = Path(f.name)
    
    try:
        # Process the file
        process_file(temp_path)
        
        # Read the result
        with open(temp_path, 'r') as f:
            result = json.load(f)
        
        # Check that metadata was added
        assert result["sections"][0]["meta_applies_if"] == "TRUE"
        assert result["sections"][0]["meta_exempt_if"] == "BUILDING.USAGE == 'INDUSTRIAL'"
        
        print("✓ test_file_processing passed")
    finally:
        # Clean up
        temp_path.unlink()


def run_all_tests():
    """Run all tests."""
    print("Running tests for add_section_application_metadata.py...")
    print()
    
    test_add_metadata_basic()
    test_missing_parent_section()
    test_non_chunk_metadata_ignored()
    test_partial_metadata()
    test_file_processing()
    
    print()
    print("All tests passed! ✓")


if __name__ == "__main__":
    run_all_tests()
