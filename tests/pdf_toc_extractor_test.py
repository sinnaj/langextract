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
  from pdf_toc_extractor import extract_pdf_toc, format_toc_as_text, setup_logging
except ImportError as e:
  # Handle import issues in test environment
  print(f'Warning: Could not import pdf_toc_extractor: {e}')
  extract_pdf_toc = None
  format_toc_as_text = None
  setup_logging = None


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

  def test_format_toc_as_text_empty(self):
    """Test text formatting with empty ToC."""
    result = format_toc_as_text([])
    expected = 'No table of contents found.\n'
    self.assertEqual(result, expected)

  def test_format_toc_as_text_with_entries(self):
    """Test text formatting with ToC entries."""
    toc_entries = [
        {'level': 1, 'title': 'Chapter 1', 'page': 1},
        {'level': 2, 'title': 'Section 1.1', 'page': 5},
        {'level': 1, 'title': 'Chapter 2', 'page': 10},
    ]
    result = format_toc_as_text(toc_entries)
    expected_lines = [
        'Table of Contents',
        '=' * 18,
        '',
        'Chapter 1 ... 1',
        '  Section 1.1 ... 5',
        'Chapter 2 ... 10',
        '',
    ]
    expected = '\n'.join(expected_lines)
    self.assertEqual(result, expected)

  def test_extract_pdf_toc_missing_fitz(self):
    """Test error handling when PyMuPDF is not available."""
    with patch.dict('sys.modules', {'fitz': None}):
      with self.assertRaises(ImportError) as context:
        extract_pdf_toc('dummy.pdf')

      self.assertIn('PyMuPDF (fitz) is required', str(context.exception))

  @patch('fitz.open')
  def test_extract_pdf_toc_no_toc(self, mock_fitz_open):
    """Test extraction when PDF has no ToC."""
    # Mock PyMuPDF document
    mock_doc = MagicMock()
    mock_doc.get_toc.return_value = []
    mock_fitz_open.return_value = mock_doc

    result = extract_pdf_toc('dummy.pdf', output_format='json')

    self.assertEqual(result, [])
    mock_fitz_open.assert_called_once_with('dummy.pdf')
    mock_doc.get_toc.assert_called_once()
    mock_doc.close.assert_called_once()

  @patch('fitz.open')
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

    result = extract_pdf_toc('dummy.pdf', output_format='json')

    expected = [
        {'level': 1, 'title': 'Introduction', 'page': 1},
        {'level': 2, 'title': 'Background', 'page': 3},
        {'level': 1, 'title': 'Methods', 'page': 10},
    ]

    self.assertEqual(result, expected)
    mock_fitz_open.assert_called_once_with('dummy.pdf')
    mock_doc.get_toc.assert_called_once()
    mock_doc.close.assert_called_once()

  @patch('fitz.open')
  def test_extract_pdf_toc_text_format(self, mock_fitz_open):
    """Test extraction with text output format."""
    # Mock PyMuPDF document with ToC
    mock_doc = MagicMock()
    mock_toc = [(1, 'Chapter 1', 1), (2, 'Section 1.1', 5)]
    mock_doc.get_toc.return_value = mock_toc
    mock_fitz_open.return_value = mock_doc

    result = extract_pdf_toc('dummy.pdf', output_format='text')

    self.assertIsInstance(result, str)
    self.assertIn('Table of Contents', result)
    self.assertIn('Chapter 1 ... 1', result)
    self.assertIn('Section 1.1 ... 5', result)

  @patch('fitz.open')
  def test_extract_pdf_toc_with_output_file_json(self, mock_fitz_open):
    """Test extraction with JSON output file."""
    # Mock PyMuPDF document
    mock_doc = MagicMock()
    mock_toc = [(1, 'Test Chapter', 1)]
    mock_doc.get_toc.return_value = mock_toc
    mock_fitz_open.return_value = mock_doc

    with tempfile.TemporaryDirectory() as temp_dir:
      output_path = Path(temp_dir) / 'test_toc.json'

      result = extract_pdf_toc(
          'dummy.pdf', output_path=output_path, output_format='json'
      )

      # Check that file was created
      self.assertTrue(output_path.exists())

      # Check file contents
      with open(output_path, 'r', encoding='utf-8') as f:
        file_content = json.load(f)

      expected = [{'level': 1, 'title': 'Test Chapter', 'page': 1}]
      self.assertEqual(file_content, expected)
      self.assertEqual(result, expected)

  @patch('fitz.open')
  def test_extract_pdf_toc_with_output_file_text(self, mock_fitz_open):
    """Test extraction with text output file."""
    # Mock PyMuPDF document
    mock_doc = MagicMock()
    mock_toc = [(1, 'Test Chapter', 1)]
    mock_doc.get_toc.return_value = mock_toc
    mock_fitz_open.return_value = mock_doc

    with tempfile.TemporaryDirectory() as temp_dir:
      output_path = Path(temp_dir) / 'test_toc.txt'

      result = extract_pdf_toc(
          'dummy.pdf', output_path=output_path, output_format='text'
      )

      # Check that file was created
      self.assertTrue(output_path.exists())

      # Check file contents
      file_content = output_path.read_text(encoding='utf-8')

      self.assertIn('Table of Contents', file_content)
      self.assertIn('Test Chapter ... 1', file_content)
      self.assertIsInstance(result, str)

  @patch('os.unlink')
  @patch('tempfile.NamedTemporaryFile')
  @patch('urllib.request.urlopen')
  @patch('fitz.open')
  def test_extract_pdf_toc_from_url(
      self, mock_fitz_open, mock_urlopen, mock_tempfile, mock_unlink
  ):
    """Test extraction from URL."""
    # Mock temporary file
    mock_temp = MagicMock()
    mock_temp.name = '/tmp/test.pdf'
    mock_temp.__enter__ = MagicMock(return_value=mock_temp)
    mock_temp.__exit__ = MagicMock(return_value=None)
    mock_tempfile.return_value = mock_temp

    # Mock URL response
    mock_response = MagicMock()
    mock_response.read.return_value = b'fake pdf content'
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)
    mock_urlopen.return_value = mock_response

    # Mock PyMuPDF document
    mock_doc = MagicMock()
    mock_doc.get_toc.return_value = [(1, 'URL Chapter', 1)]
    mock_fitz_open.return_value = mock_doc

    result = extract_pdf_toc(
        'https://example.com/test.pdf', output_format='json'
    )

    expected = [{'level': 1, 'title': 'URL Chapter', 'page': 1}]
    self.assertEqual(result, expected)

    # Verify URL was opened and temp file was used
    mock_urlopen.assert_called_once_with('https://example.com/test.pdf')
    mock_fitz_open.assert_called_once_with('/tmp/test.pdf')
    mock_unlink.assert_called_once_with('/tmp/test.pdf')

  @patch('fitz.open')
  def test_extract_pdf_toc_handles_exceptions(self, mock_fitz_open):
    """Test error handling in extraction process."""
    # Make fitz.open raise an exception
    mock_fitz_open.side_effect = Exception('Cannot open PDF')

    with self.assertRaises(Exception) as context:
      extract_pdf_toc('dummy.pdf')

    self.assertIn('Cannot open PDF', str(context.exception))

  def test_format_toc_as_text_handles_multiline_titles(self):
    """Test text formatting with complex titles."""
    toc_entries = [
        {'level': 1, 'title': '  Chapter 1: Introduction  ', 'page': 1},
        {
            'level': 2,
            'title': 'Section with very long title that might wrap',
            'page': 5,
        },
    ]
    result = format_toc_as_text(toc_entries)

    # The script does not strip whitespace from titles in format function
    self.assertIn('Chapter 1: Introduction   ... 1', result)
    self.assertIn('Section with very long title that might wrap ... 5', result)


if __name__ == '__main__':
  unittest.main()
