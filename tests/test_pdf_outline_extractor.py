#!/usr/bin/env python3
"""
Test script for PDF Outline Extractor

This script tests the PDF outline extractor functionality with mock data
to validate the core logic without requiring external dependencies.
"""

import sys
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

# Add scripts directory to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class TestPDFOutlineExtractor(unittest.TestCase):
    """Test cases for the PDF outline extractor."""

    def test_determine_heading_level(self):
        """Test heading level determination logic."""
        from pdf_outline_extractor import determine_heading_level
        
        # Mock text item
        mock_item = Mock()
        
        # Test H1 patterns
        self.assertEqual(determine_heading_level("1. Introduction", mock_item), "H1")
        self.assertEqual(determine_heading_level("Chapter 1", mock_item), "H1")
        self.assertEqual(determine_heading_level("Abstract", mock_item), "H1")
        
        # Test H2 patterns
        self.assertEqual(determine_heading_level("1.1 Overview", mock_item), "H2")
        self.assertEqual(determine_heading_level("2.1 Background", mock_item), "H2")
        
        # Test H3 patterns
        self.assertEqual(determine_heading_level("1.1.1 Details", mock_item), "H3")
        self.assertEqual(determine_heading_level("Some Section", mock_item), "H2")  # fallback

    def test_is_likely_heading(self):
        """Test heading detection logic."""
        from pdf_outline_extractor import is_likely_heading
        
        # Should be headings
        self.assertTrue(is_likely_heading("1. Introduction"))
        self.assertTrue(is_likely_heading("Abstract"))
        self.assertTrue(is_likely_heading("CHAPTER ONE"))
        self.assertTrue(is_likely_heading("1.1 Background"))
        
        # Should not be headings
        self.assertFalse(is_likely_heading("This is a long paragraph with multiple sentences. It contains detailed information."))
        self.assertFalse(is_likely_heading(""))
        self.assertFalse(is_likely_heading("   "))
        
        # Edge cases
        self.assertFalse(is_likely_heading("Fig. 1. This is a figure caption with detailed description."))

    def test_extract_page_number(self):
        """Test page number extraction."""
        from pdf_outline_extractor import extract_page_number
        
        # Mock item with page info
        mock_item = Mock()
        mock_item.page = 2
        mock_item.prov = []
        self.assertEqual(extract_page_number(mock_item, default_page=1), 3)  # 0-based to 1-based
        
        # Mock item with provenance
        mock_prov = Mock()
        mock_prov.page = 4
        mock_item_prov = Mock()
        mock_item_prov.prov = [mock_prov]
        mock_item_prov.page = None
        self.assertEqual(extract_page_number(mock_item_prov, default_page=1), 5)
        
        # Mock item without page info
        mock_item_no_page = Mock()
        mock_item_no_page.page = None
        mock_item_no_page.prov = []
        self.assertEqual(extract_page_number(mock_item_no_page, default_page=3), 3)

    def test_extract_title_from_document(self):
        """Test title extraction from document."""
        from pdf_outline_extractor import extract_title_from_document
        
        # Mock document with title in description
        mock_doc = Mock()
        mock_doc.description = {"title": "Test Document Title"}
        mock_doc.texts = []
        
        title = extract_title_from_document(mock_doc)
        self.assertEqual(title, "Test Document Title")
        
        # Mock document without description but with first text item
        mock_doc2 = Mock()
        mock_doc2.description = None
        mock_text_item = Mock()
        mock_text_item.text = "Document from Text Item"
        mock_doc2.texts = [mock_text_item]
        
        # Test fallback to first text item
        title2 = extract_title_from_document(mock_doc2)
        self.assertEqual(title2, "Document from Text Item")

    @patch('pdf_outline_extractor.convert_pdf_to_docling')
    def test_extract_pdf_outline_structure(self, mock_convert):
        """Test the overall structure of PDF outline extraction."""
        from pdf_outline_extractor import extract_pdf_outline
        
        # Mock the DoclingDocument
        mock_doc = Mock()
        mock_doc.description = {"title": "Test PDF Document"}
        mock_doc.texts = []
        
        mock_convert.return_value = mock_doc
        
        result = extract_pdf_outline("test.pdf")
        
        # Check structure
        self.assertIn("title", result)
        self.assertIn("outline", result)
        self.assertEqual(result["title"], "Test PDF Document")
        self.assertIsInstance(result["outline"], list)

    def test_save_outline_stdout(self):
        """Test saving outline to stdout."""
        from pdf_outline_extractor import save_outline
        import json
        from io import StringIO
        
        test_data = {
            "title": "Test Document",
            "outline": [
                {"level": "H1", "text": "Introduction", "page": 1},
                {"level": "H2", "text": "Background", "page": 2}
            ]
        }
        
        # Capture stdout
        captured_output = StringIO()
        
        with patch('sys.stdout', captured_output):
            save_outline(test_data, output_path=None)
        
        # Parse the captured JSON (remove the extra newline)
        output_text = captured_output.getvalue().strip()
        parsed_data = json.loads(output_text)
        
        self.assertEqual(parsed_data["title"], "Test Document")
        self.assertEqual(len(parsed_data["outline"]), 2)


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests()