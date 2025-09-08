#!/usr/bin/env python3
"""
Integration test for PDF Outline Extractor

This test validates the PDF outline extractor with a mock PDF scenario,
testing the complete pipeline without requiring actual PDF dependencies.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add scripts directory to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


class TestPDFOutlineExtractorIntegration(unittest.TestCase):
    """Integration tests for the PDF outline extractor."""

    @patch('pdf_outline_extractor.convert_pdf_to_docling')
    def test_full_pipeline_with_mock_pdf(self, mock_convert):
        """Test the complete pipeline with a mock PDF document."""
        from pdf_outline_extractor import extract_pdf_outline
        
        # Create a comprehensive mock DoclingDocument
        mock_doc = Mock()
        mock_doc.description = {"title": "Advanced Machine Learning Techniques"}
        
        # Create mock text items representing a typical academic paper structure
        mock_items = []
        
        # Helper function to create properly configured mock items
        def create_mock_item(text, page=0):
            item = Mock()
            item.text = text
            item.page = page
            item.prov = []
            # Add hasattr behavior for common attributes
            item.__dict__.update({'text': text, 'page': page, 'prov': []})
            return item
        
        # Title item (should be skipped in outline)
        title_item = create_mock_item("Advanced Machine Learning Techniques")
        mock_items.append(title_item)
        
        # Abstract section
        abstract_item = create_mock_item("Abstract", 0)
        mock_items.append(abstract_item)
        
        # Introduction section
        intro_item = create_mock_item("1. Introduction", 0)
        mock_items.append(intro_item)
        
        # Subsection
        background_item = create_mock_item("1.1 Background", 1)
        mock_items.append(background_item)
        
        # Methods section
        methods_item = create_mock_item("2. Methodology", 2)
        mock_items.append(methods_item)
        
        # Deep subsection
        data_item = create_mock_item("2.1.1 Data Collection", 3)
        mock_items.append(data_item)
        
        # Results section
        results_item = create_mock_item("3. Results", 4)
        mock_items.append(results_item)
        
        # Conclusion
        conclusion_item = create_mock_item("Conclusion", 5)
        mock_items.append(conclusion_item)
        
        mock_doc.texts = mock_items
        mock_convert.return_value = mock_doc
        
        # Extract outline
        result = extract_pdf_outline("test_paper.pdf")
        
        # Validate structure
        self.assertEqual(result["title"], "Advanced Machine Learning Techniques")
        self.assertIn("outline", result)
        
        outline = result["outline"]
        self.assertGreater(len(outline), 0, "Should extract at least some outline items")
        
        # Validate outline structure
        expected_texts = ["Abstract", "1. Introduction", "1.1 Background", 
                         "2. Methodology", "2.1.1 Data Collection", "3. Results", "Conclusion"]
        
        extracted_texts = [item["text"] for item in outline]
        
        # Check that key sections are captured
        self.assertIn("Abstract", extracted_texts)
        self.assertIn("1. Introduction", extracted_texts)
        self.assertIn("2. Methodology", extracted_texts)
        
        # Validate that each outline item has required fields
        for item in outline:
            self.assertIn("level", item)
            self.assertIn("text", item)
            self.assertIn("page", item)
            self.assertIn(item["level"], ["H1", "H2", "H3", "H4"])
            self.assertIsInstance(item["text"], str)
            self.assertIsInstance(item["page"], int)
            self.assertGreater(item["page"], 0)  # 1-based page numbers

    def test_output_json_format_compatibility(self):
        """Test that the output JSON format is compatible with PDF-Outline-Extractor."""
        from pdf_outline_extractor import save_outline
        
        # Create test data matching the expected format
        test_data = {
            "title": "Sample Document Title",
            "outline": [
                {"level": "H1", "text": "Introduction", "page": 1},
                {"level": "H2", "text": "Background", "page": 2},
                {"level": "H2", "text": "Related Work", "page": 3},
                {"level": "H1", "text": "Methodology", "page": 4},
                {"level": "H3", "text": "Data Processing", "page": 5},
                {"level": "H1", "text": "Results", "page": 6},
                {"level": "H4", "text": "Statistical Analysis", "page": 7},
                {"level": "H1", "text": "Conclusion", "page": 8}
            ]
        }
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            save_outline(test_data, temp_path)
            
            # Read back and validate
            with open(temp_path, 'r') as f:
                loaded_data = json.load(f)
            
            # Validate structure matches PDF-Outline-Extractor format
            self.assertEqual(loaded_data["title"], "Sample Document Title")
            self.assertIn("outline", loaded_data)
            
            outline = loaded_data["outline"]
            self.assertEqual(len(outline), 8)
            
            # Validate each outline item
            for item in outline:
                self.assertIn("level", item)
                self.assertIn("text", item)
                self.assertIn("page", item)
                
                # Validate level values
                self.assertIn(item["level"], ["H1", "H2", "H3", "H4"])
                
                # Validate page numbers are positive integers
                self.assertIsInstance(item["page"], int)
                self.assertGreater(item["page"], 0)
                
                # Validate text is non-empty string
                self.assertIsInstance(item["text"], str)
                self.assertGreater(len(item["text"]), 0)
            
            # Test hierarchical levels are present
            levels = set(item["level"] for item in outline)
            self.assertIn("H1", levels)  # Should have H1 sections
            
        finally:
            # Clean up
            Path(temp_path).unlink(missing_ok=True)

    @patch('pdf_outline_extractor.convert_pdf_to_docling')
    def test_edge_cases(self, mock_convert):
        """Test edge cases and error conditions."""
        from pdf_outline_extractor import extract_pdf_outline
        
        # Test empty document
        mock_empty_doc = Mock()
        mock_empty_doc.description = None
        mock_empty_doc.texts = []
        mock_convert.return_value = mock_empty_doc
        
        result = extract_pdf_outline("empty.pdf")
        self.assertEqual(result["title"], "")
        self.assertEqual(result["outline"], [])
        
        # Test document with only non-heading text
        mock_text_doc = Mock()
        mock_text_doc.description = {"title": "Text Only Document"}
        
        # Helper function for creating mock items
        def create_mock_item(text, page=0):
            item = Mock()
            item.text = text
            item.page = page
            item.prov = []
            item.__dict__.update({'text': text, 'page': page, 'prov': []})
            return item
        
        # Create text items that shouldn't be headings
        text_item1 = create_mock_item("This is a long paragraph of text that should not be considered a heading because it contains multiple sentences and is too long.", 0)
        text_item2 = create_mock_item("Another paragraph with detailed information that spans multiple lines and contains various punctuation marks, making it unsuitable as a heading.", 0)
        
        mock_text_doc.texts = [text_item1, text_item2]
        mock_convert.return_value = mock_text_doc
        
        result = extract_pdf_outline("text_only.pdf")
        self.assertEqual(result["title"], "Text Only Document")
        self.assertEqual(len(result["outline"]), 0)  # No headings should be detected

    def test_command_line_interface(self):
        """Test the command-line interface structure."""
        from pdf_outline_extractor import main
        import argparse
        
        # This test validates that the argument parser is set up correctly
        # We can't easily test the full CLI without mocking sys.argv
        # But we can test the help functionality
        
        with patch('sys.argv', ['pdf_outline_extractor.py', '--help']):
            with patch('argparse.ArgumentParser.print_help') as mock_help:
                with self.assertRaises(SystemExit):
                    main()
                mock_help.assert_called_once()


def run_integration_tests():
    """Run all integration tests."""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_integration_tests()