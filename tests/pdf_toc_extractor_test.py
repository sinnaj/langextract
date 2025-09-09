"""
Tests for PDF ToC Extraction Script using PyMuPDF

This module tests the pdf_toc_extractor.py script functionality.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the module we're testing
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
  from pdf_toc_extractor import (
    extract_pdf_toc, 
    setup_logging, 
    normalize_text, 
    calculate_text_similarity,
    map_toc_to_docling_sections,
    update_parent_references,
    generate_toc_markdown
  )
except ImportError as e:
  # Handle import issues in test environment
  print(f'Warning: Could not import pdf_toc_extractor: {e}')
  extract_pdf_toc = None


class TestPdfTocExtractor(unittest.TestCase):
  """Test cases for PDF ToC extraction functionality."""

  def setUp(self):
    """Set up test fixtures."""
    if extract_pdf_toc is None:
      self.skipTest('pdf_toc_extractor module could not be imported')

  def test_setup_logging_verbose_false(self):
    """Test logging setup with verbose=False."""
    with patch('logging.basicConfig') as mock_basic_config:
      setup_logging(verbose=False)
      mock_basic_config.assert_called_once()
      args, kwargs = mock_basic_config.call_args
      self.assertEqual(kwargs['level'], 20)  # logging.INFO = 20

  def test_setup_logging_verbose_true(self):
    """Test logging setup with verbose=True."""
    with patch('logging.basicConfig') as mock_basic_config:
      setup_logging(verbose=True)
      mock_basic_config.assert_called_once()
      args, kwargs = mock_basic_config.call_args
      self.assertEqual(kwargs['level'], 10)  # logging.DEBUG = 10

  def test_normalize_text(self):
    """Test text normalization functionality."""
    # Test Unicode escape sequences
    text1 = "Secci\\u00f3n SI 2 Propagaci\\u00f3n exterior"
    normalized1 = normalize_text(text1)
    self.assertIn('seccion', normalized1.lower())
    
    # Test whitespace normalization
    text2 = "  Multiple   spaces  "
    normalized2 = normalize_text(text2)
    self.assertEqual(normalized2, "multiple spaces")

  def test_calculate_text_similarity(self):
    """Test text similarity calculation."""
    # Identical texts
    similarity1 = calculate_text_similarity("test", "test")
    self.assertEqual(similarity1, 1.0)
    
    # Similar texts
    similarity2 = calculate_text_similarity("Sección SI 1", "Seccion SI 1")
    self.assertGreater(similarity2, 0.8)
    
    # Different texts
    similarity3 = calculate_text_similarity("hello", "world")
    self.assertLess(similarity3, 0.5)

  def test_extract_pdf_toc_missing_fitz(self):
    """Test error handling when PyMuPDF is not available."""
    with patch.dict('sys.modules', {'fitz': None}):
      with self.assertRaises(ImportError) as context:
        extract_pdf_toc('dummy.pdf')

      self.assertIn('PyMuPDF (fitz) is required', str(context.exception))

  @patch('pdf_toc_extractor.fitz.open')
  def test_extract_pdf_toc_no_toc(self, mock_fitz_open):
    """Test extraction when PDF has no ToC."""
    # Mock PyMuPDF document
    mock_doc = MagicMock()
    mock_doc.get_toc.return_value = []
    mock_fitz_open.return_value = mock_doc

    with patch('pdf_toc_extractor.fitz'):
      result = extract_pdf_toc('dummy.pdf')

    self.assertEqual(result, [])
    mock_fitz_open.assert_called_once_with('dummy.pdf')
    mock_doc.get_toc.assert_called_once()
    mock_doc.close.assert_called_once()

  @patch('pdf_toc_extractor.fitz.open')
  def test_extract_pdf_toc_with_entries(self, mock_fitz_open):
    """Test extraction with actual ToC entries."""
    # Mock PyMuPDF document with ToC
    mock_doc = MagicMock()
    mock_toc = [
        (1, 'Introduction', 1),
        (2, 'Background', 3),
        (1, 'Methods', 10),
    ]
    mock_doc.get_toc.return_value = mock_toc
    mock_fitz_open.return_value = mock_doc

    with patch('pdf_toc_extractor.fitz'):
      result = extract_pdf_toc('dummy.pdf')

    expected = [
        {'level': 1, 'title': 'Introduction', 'page': 1},
        {'level': 2, 'title': 'Background', 'page': 3},
        {'level': 1, 'title': 'Methods', 'page': 10},
    ]

    self.assertEqual(result, expected)
    mock_fitz_open.assert_called_once_with('dummy.pdf')
    mock_doc.get_toc.assert_called_once()
    mock_doc.close.assert_called_once()

  def test_map_toc_to_docling_sections(self):
    """Test mapping ToC entries to DoclingDocument section headers."""
    toc_entries = [
        {'level': 1, 'title': 'Introduction', 'page': 1},
        {'level': 2, 'title': 'Background', 'page': 3},
    ]
    
    docling_data = {
        'texts': [
            {'label': 'section_header', 'text': 'Introduction', 'level': 1},
            {'label': 'section_header', 'text': 'Background Info', 'level': 1},
            {'label': 'paragraph', 'text': 'Some content'},
        ]
    }
    
    updated_data, mapping_report = map_toc_to_docling_sections(toc_entries, docling_data)
    
    # Check that levels were updated
    self.assertEqual(updated_data['texts'][0]['level'], 1)  # Introduction
    self.assertEqual(updated_data['texts'][1]['level'], 2)  # Background (mapped)
    
    # Check mapping report
    self.assertEqual(len(mapping_report['successful_mappings']), 2)
    self.assertEqual(mapping_report['total_section_headers'], 2)

  def test_update_parent_references(self):
    """Test updating parent references based on hierarchy."""
    docling_data = {
        'texts': [
            {'label': 'section_header', 'text': 'Chapter 1', 'level': 1, 'parent': {'$ref': '#/body'}},
            {'label': 'section_header', 'text': 'Section 1.1', 'level': 2, 'parent': {'$ref': '#/body'}},
            {'label': 'section_header', 'text': 'Section 1.1.1', 'level': 3, 'parent': {'$ref': '#/body'}},
        ]
    }
    
    updated_data = update_parent_references(docling_data)
    
    # Check parent references
    self.assertEqual(updated_data['texts'][0]['parent']['$ref'], '#/body')  # Level 1 keeps #/body
    self.assertEqual(updated_data['texts'][1]['parent']['$ref'], '#/texts/0')  # Level 2 points to Level 1
    self.assertEqual(updated_data['texts'][2]['parent']['$ref'], '#/texts/1')  # Level 3 points to Level 2

  def test_generate_toc_markdown(self):
    """Test ToC markdown generation."""
    docling_data = {
        'texts': [
            {'label': 'section_header', 'text': 'Chapter 1', 'level': 1},
            {'label': 'section_header', 'text': 'Section 1.1', 'level': 2},
            {'label': 'paragraph', 'text': 'Some content'},
        ]
    }
    
    result = generate_toc_markdown(docling_data)
    
    self.assertIn('# Table of Contents', result)
    self.assertIn('- Chapter 1', result)
    self.assertIn('  - Section 1.1', result)
    self.assertNotIn('Some content', result)  # Should not include non-headers


if __name__ == '__main__':
  unittest.main()
