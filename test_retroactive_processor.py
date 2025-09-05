#!/usr/bin/env python3
"""Tests for the retroactive section processor."""

import unittest
import tempfile
import json
import os
from pathlib import Path
from retroactive_section_processor import process_combined_extractions


class TestRetroactiveSectionProcessor(unittest.TestCase):
    """Test cases for retroactive section processor."""
    
    def setUp(self):
        """Set up test cases."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up temp files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_process_simple_file(self):
        """Test processing a simple combined extractions file."""
        # Create test data
        test_data = {
            "document_metadata": {
                "source_file": "test.md",
                "total_processed_sections": 4
            },
            "evaluation_statistics": {
                "total_chunks": 4,
                "extract_count": 2,
                "manual_count": 2,
                "drop_count": 0
            },
            "sections": [
                {
                    "section_id": "section_001",
                    "section_name": "Main Section",
                    "section_level": 1,
                    "section_index": 0,
                    "parent_section": None,
                    "sub_sections": ["section_002"],
                    "processing_type": "manual",
                    "evaluation_reason": "headline only"
                },
                {
                    "section_id": "section_002",
                    "section_name": "Sub Section",
                    "section_level": 2,
                    "section_index": 1,
                    "parent_section": "section_001",
                    "sub_sections": [],
                    "processing_type": "extract",
                    "evaluation_reason": "substantial content"
                },
                {
                    "section_id": "section_003",
                    "section_name": "Duplicate Section",
                    "section_level": 1,
                    "section_index": 2,
                    "parent_section": None,
                    "sub_sections": [],
                    "processing_type": "manual",
                    "evaluation_reason": "headline only"
                },
                {
                    "section_id": "section_004",
                    "section_name": "Duplicate Section",
                    "section_level": 1,
                    "section_index": 3,
                    "parent_section": None,
                    "sub_sections": [],
                    "processing_type": "manual",
                    "evaluation_reason": "headline only"
                }
            ]
        }
        
        # Write test file
        input_file = Path(self.temp_dir) / "test_input.json"
        output_file = Path(self.temp_dir) / "test_output.json"
        
        with open(input_file, 'w') as f:
            json.dump(test_data, f)
        
        # Process the file
        process_combined_extractions(input_file, output_file)
        
        # Verify output file exists
        self.assertTrue(output_file.exists())
        
        # Load and verify output
        with open(output_file, 'r') as f:
            result = json.load(f)
        
        # Check that postprocessing info was added
        self.assertIn("postprocessing", result)
        self.assertTrue(result["postprocessing"]["enabled"])
        
        # Should have fewer sections due to merging duplicates
        original_count = len(test_data["sections"])
        processed_count = len(result["sections"])
        self.assertLessEqual(processed_count, original_count)
        
        # Check that evaluation statistics were updated
        self.assertEqual(result["evaluation_statistics"]["total_chunks"], processed_count)
    
    def test_empty_sections(self):
        """Test handling of empty sections list."""
        test_data = {
            "document_metadata": {"source_file": "test.md"},
            "sections": []
        }
        
        input_file = Path(self.temp_dir) / "empty_test.json"
        with open(input_file, 'w') as f:
            json.dump(test_data, f)
        
        # Should handle gracefully without errors
        process_combined_extractions(input_file)
    
    def test_missing_sections(self):
        """Test handling of missing sections key."""
        test_data = {
            "document_metadata": {"source_file": "test.md"}
        }
        
        input_file = Path(self.temp_dir) / "missing_sections_test.json"
        with open(input_file, 'w') as f:
            json.dump(test_data, f)
        
        # Should handle gracefully without errors
        process_combined_extractions(input_file)


if __name__ == "__main__":
    unittest.main()