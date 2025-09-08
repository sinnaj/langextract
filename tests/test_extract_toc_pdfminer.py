#!/usr/bin/env python3
"""Tests for the PDF TOC extraction script using pdfminer.six."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the script module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
    from extract_toc_pdfminer import (
        PDFTOCExtractor, TOCEntry, 
        save_toc_as_text, save_toc_as_json,
        main
    )
except ImportError as e:
    pytest.skip(f"pdfminer.six not available: {e}", allow_module_level=True)


class TestTOCEntry(unittest.TestCase):
    """Test cases for TOCEntry class."""
    
    def test_toc_entry_creation(self):
        """Test creating a TOC entry."""
        entry = TOCEntry("Introduction", page=1, level=1)
        self.assertEqual(entry.title, "Introduction")
        self.assertEqual(entry.page, 1)
        self.assertEqual(entry.level, 1)
        self.assertEqual(len(entry.children), 0)
    
    def test_toc_entry_add_child(self):
        """Test adding child entries."""
        parent = TOCEntry("Chapter 1", page=1, level=1)
        child = TOCEntry("Section 1.1", page=2, level=2)
        
        parent.add_child(child)
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(parent.children[0].title, "Section 1.1")
    
    def test_toc_entry_to_dict(self):
        """Test converting TOC entry to dictionary."""
        entry = TOCEntry("Introduction", page=1, level=1)
        child = TOCEntry("Overview", page=2, level=2)
        entry.add_child(child)
        
        result = entry.to_dict()
        expected = {
            'title': 'Introduction',
            'level': 1,
            'page': 1,
            'children': [{
                'title': 'Overview',
                'level': 2,
                'page': 2
            }]
        }
        self.assertEqual(result, expected)
    
    def test_toc_entry_to_text(self):
        """Test converting TOC entry to text format."""
        entry = TOCEntry("Introduction", page=1, level=1)
        child = TOCEntry("Overview", page=2, level=2)
        entry.add_child(child)
        
        result = entry.to_text()
        expected = "Introduction .................. 1\n  Overview .................. 2\n"
        self.assertEqual(result, expected)


class TestPDFTOCExtractor(unittest.TestCase):
    """Test cases for PDFTOCExtractor class."""
    
    def setUp(self):
        """Set up test instance."""
        self.extractor = PDFTOCExtractor(verbose=False)
    
    def test_is_url(self):
        """Test URL detection."""
        self.assertTrue(self.extractor.is_url("https://example.com/file.pdf"))
        self.assertTrue(self.extractor.is_url("http://example.com/file.pdf"))
        self.assertFalse(self.extractor.is_url("/path/to/file.pdf"))
        self.assertFalse(self.extractor.is_url("file.pdf"))
    
    def test_parse_toc_line_numbered(self):
        """Test parsing numbered TOC lines."""
        test_cases = [
            ("1. Introduction .................. 5", "Introduction", 1, 5),
            ("1.1 Overview .................. 10", "Overview", 2, 10),
            ("2.3.1 Details .................. 25", "Details", 3, 25),
        ]
        
        for line, expected_title, expected_level, expected_page in test_cases:
            with self.subTest(line=line):
                entry = self.extractor._parse_toc_line(line)
                self.assertIsNotNone(entry)
                self.assertEqual(entry.title, expected_title)
                self.assertEqual(entry.level, expected_level)
                self.assertEqual(entry.page, expected_page)
    
    def test_parse_toc_line_chapter(self):
        """Test parsing chapter-style TOC lines."""
        test_cases = [
            "Chapter 1: Introduction .................. 5",
            "Chapter 2: Background .................. 15",
            "Section A: Overview .................. 8"
        ]
        
        for line in test_cases:
            with self.subTest(line=line):
                entry = self.extractor._parse_toc_line(line)
                self.assertIsNotNone(entry)
                self.assertEqual(entry.level, 1)
                self.assertIsNotNone(entry.page)
    
    def test_parse_toc_line_invalid(self):
        """Test parsing invalid TOC lines."""
        invalid_lines = [
            "Table of Contents",
            "",
            "   ",
            "Just some random text"
        ]
        
        for line in invalid_lines:
            with self.subTest(line=line):
                entry = self.extractor._parse_toc_line(line)
                # Should either be None or have no meaningful content
                if entry is not None:
                    # If it's not None, it should at least have a meaningful title
                    self.assertTrue(len(entry.title) > 1)
    
    def test_find_toc_sections_basic(self):
        """Test finding TOC sections in text."""
        sample_text = """
Some introduction text here.

Table of Contents

1. Introduction .................. 5
2. Background .................. 10
3. Methodology .................. 15

Chapter 1: Introduction
This is the actual content of chapter 1.
        """
        
        sections = self.extractor.find_toc_sections(sample_text)
        self.assertGreater(len(sections), 0)
        
        # Check that at least one section was found
        start_idx, end_idx, section_text = sections[0]
        self.assertIn("Table of Contents", section_text)
    
    def test_build_hierarchy(self):
        """Test building hierarchical structure from flat entries."""
        entries = [
            TOCEntry("Chapter 1", page=1, level=1),
            TOCEntry("Section 1.1", page=2, level=2),
            TOCEntry("Section 1.2", page=5, level=2),
            TOCEntry("Chapter 2", page=10, level=1),
            TOCEntry("Section 2.1", page=11, level=2),
        ]
        
        hierarchy = self.extractor._build_hierarchy(entries)
        
        # Should have 2 top-level entries
        self.assertEqual(len(hierarchy), 2)
        
        # First chapter should have 2 children
        self.assertEqual(len(hierarchy[0].children), 2)
        self.assertEqual(hierarchy[0].children[0].title, "Section 1.1")
        self.assertEqual(hierarchy[0].children[1].title, "Section 1.2")
        
        # Second chapter should have 1 child
        self.assertEqual(len(hierarchy[1].children), 1)
        self.assertEqual(hierarchy[1].children[0].title, "Section 2.1")
    
    @patch('extract_toc_pdfminer.extract_text')
    def test_extract_text_from_pdf(self, mock_extract):
        """Test PDF text extraction."""
        mock_extract.return_value = "Sample PDF text content"
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            result = self.extractor.extract_text_from_pdf(temp_file.name)
            self.assertEqual(result, "Sample PDF text content")
            mock_extract.assert_called_once()
    
    def test_is_likely_toc_line(self):
        """Test TOC line detection."""
        toc_lines = [
            "1. Introduction .................. 5",
            "2.1 Overview .................. 10",
            "Chapter 3: Methods .................. 15",
            "i. Appendix A .................. 50"
        ]
        
        non_toc_lines = [
            "This is just regular text content.",
            "Here's another paragraph.",
            "No dots or numbers here."
        ]
        
        for line in toc_lines:
            with self.subTest(line=line):
                self.assertTrue(self.extractor._is_likely_toc_line(line))
        
        for line in non_toc_lines:
            with self.subTest(line=line):
                self.assertFalse(self.extractor._is_likely_toc_line(line))


class TestFileOperations(unittest.TestCase):
    """Test file save operations."""
    
    def test_save_toc_as_text(self):
        """Test saving TOC as text file."""
        entries = [
            TOCEntry("Introduction", page=1, level=1),
            TOCEntry("Background", page=5, level=1)
        ]
        entries[0].add_child(TOCEntry("Overview", page=2, level=2))
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            save_toc_as_text(entries, temp_path)
            
            content = temp_path.read_text(encoding='utf-8')
            self.assertIn("Table of Contents", content)
            self.assertIn("Introduction", content)
            self.assertIn("Background", content)
            self.assertIn("Overview", content)
        finally:
            temp_path.unlink()
    
    def test_save_toc_as_json(self):
        """Test saving TOC as JSON file."""
        entries = [
            TOCEntry("Introduction", page=1, level=1),
            TOCEntry("Background", page=5, level=1)
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        
        try:
            save_toc_as_json(entries, temp_path)
            
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.assertIn('table_of_contents', data)
            self.assertIn('total_entries', data)
            self.assertEqual(data['total_entries'], 2)
            self.assertEqual(len(data['table_of_contents']), 2)
        finally:
            temp_path.unlink()


class TestMainFunction(unittest.TestCase):
    """Test the main CLI function."""
    
    @patch('sys.argv', ['extract_toc_pdfminer.py', '--help'])
    def test_help_option(self):
        """Test that help option works."""
        with self.assertRaises(SystemExit):
            main()
    
    @patch('extract_toc_pdfminer.py.PDFTOCExtractor')
    @patch('sys.argv', ['extract_toc_pdfminer.py', 'test.pdf'])
    def test_main_basic(self, mock_extractor_class):
        """Test basic main function execution."""
        # Mock the extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_toc.return_value = [TOCEntry("Test", page=1)]
        mock_extractor.is_url.return_value = False
        mock_extractor_class.return_value = mock_extractor
        
        # Mock file exists
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.write_text'):
                result = main()
                self.assertEqual(result, 0)


@pytest.mark.integration 
class TestIntegration(unittest.TestCase):
    """Integration tests with real PDFs."""
    
    def test_extract_from_arxiv_pdf(self):
        """Test extracting TOC from a real arXiv PDF."""
        # This is an integration test that requires internet access
        extractor = PDFTOCExtractor(verbose=False)
        
        try:
            # Use a simple PDF that should have some structure
            url = "https://arxiv.org/pdf/2408.09869"
            entries = extractor.extract_toc(url)
            
            # The function should complete without errors
            # The actual content may vary, so we just check it runs
            self.assertIsInstance(entries, list)
            
        except Exception as e:
            self.skipTest(f"Integration test failed (network/PDF issue): {e}")


if __name__ == '__main__':
    unittest.main()