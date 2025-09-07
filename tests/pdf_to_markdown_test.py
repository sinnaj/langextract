"""
Tests for PDF to Markdown conversion script.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from scripts.pdf_to_markdown import convert_pdf_to_markdown


class TestPdfToMarkdown(unittest.TestCase):
  """Test cases for PDF to Markdown conversion."""

  def test_docling_not_installed_raises_import_error(self):
    """Test that ImportError is raised when docling is not available."""
    with mock.patch.dict("sys.modules", {"docling.document_converter": None}):
      with self.assertRaises(ImportError) as cm:
        convert_pdf_to_markdown("dummy.pdf")

      self.assertIn("docling is required", str(cm.exception))
      self.assertIn("pip install", str(cm.exception))

  @pytest.mark.integration
  def test_convert_pdf_url_to_markdown(self):
    """Test converting a PDF URL to Markdown (integration test)."""
    pytest.importorskip("docling")

    # Use a simple, small PDF from a reliable source
    url = "https://arxiv.org/pdf/2408.09869"

    with tempfile.TemporaryDirectory() as temp_dir:
      output_file = Path(temp_dir) / "test_output.md"

      # Convert the PDF
      markdown_content = convert_pdf_to_markdown(
          url, output_file, verbose=False
      )

      # Verify the content is not empty
      self.assertIsInstance(markdown_content, str)
      self.assertGreater(len(markdown_content), 100)

      # Verify the file was created
      self.assertTrue(output_file.exists())

      # Verify file content matches return value
      file_content = output_file.read_text(encoding="utf-8")
      self.assertEqual(markdown_content, file_content)

      # Basic content checks for the Docling paper
      self.assertIn("Docling", markdown_content)
      self.assertIn("Technical Report", markdown_content)

  def test_convert_pdf_without_output_file(self):
    """Test converting PDF without specifying output file."""
    pytest.importorskip("docling")

    # Use a simple, small PDF URL
    url = "https://arxiv.org/pdf/2408.09869"

    # Convert without output file
    markdown_content = convert_pdf_to_markdown(url, verbose=False)

    # Verify content is returned
    self.assertIsInstance(markdown_content, str)
    self.assertGreater(len(markdown_content), 100)

  def test_convert_nonexistent_file_raises_exception(self):
    """Test that converting a non-existent file raises an exception."""
    pytest.importorskip("docling")

    with self.assertRaises(Exception):
      convert_pdf_to_markdown("/nonexistent/file.pdf")


if __name__ == "__main__":
  unittest.main()
