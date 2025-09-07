"""
Tests for PDF to Markdown conversion script.
"""

from pathlib import Path
import tempfile
import unittest
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

  @pytest.mark.integration
  def test_convert_pdf_url_to_docling_document(self):
    """Test converting a PDF URL to DoclingDocument (integration test)."""
    pytest.importorskip("docling")

    # Use a simple, small PDF from a reliable source
    url = "https://arxiv.org/pdf/2408.09869"

    with tempfile.TemporaryDirectory() as temp_dir:
      output_file = Path(temp_dir) / "test_output.json"

      # Convert the PDF to DoclingDocument
      docling_document = convert_pdf_to_markdown(
          url, output_file, verbose=False, output_format="docling"
      )

      # Verify the content is a DoclingDocument
      from docling_core.types.doc import DoclingDocument

      self.assertIsInstance(docling_document, DoclingDocument)

      # Verify the file was created
      self.assertTrue(output_file.exists())

      # Verify file is valid JSON
      import json

      with open(output_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)
        self.assertIsInstance(json_data, dict)

      # Basic content checks
      self.assertGreater(len(docling_document.texts), 0)

  @pytest.mark.integration
  def test_convert_pdf_url_to_docling_yaml(self):
    """Test converting a PDF URL to DoclingDocument saved as YAML."""
    pytest.importorskip("docling")

    # Use a simple, small PDF from a reliable source
    url = "https://arxiv.org/pdf/2408.09869"

    with tempfile.TemporaryDirectory() as temp_dir:
      output_file = Path(temp_dir) / "test_output.yaml"

      # Convert the PDF to DoclingDocument and save as YAML
      docling_document = convert_pdf_to_markdown(
          url, output_file, verbose=False, output_format="docling"
      )

      # Verify the content is a DoclingDocument
      from docling_core.types.doc import DoclingDocument

      self.assertIsInstance(docling_document, DoclingDocument)

      # Verify the file was created and is valid YAML
      self.assertTrue(output_file.exists())
      import yaml

      with open(output_file, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)
        self.assertIsInstance(yaml_data, dict)

  def test_convert_pdf_to_docling_without_output_file(self):
    """Test converting PDF to DoclingDocument without specifying output file."""
    pytest.importorskip("docling")

    # Use a simple, small PDF URL
    url = "https://arxiv.org/pdf/2408.09869"

    # Convert without output file
    docling_document = convert_pdf_to_markdown(
        url, verbose=False, output_format="docling"
    )

    # Verify content is returned as DoclingDocument
    from docling_core.types.doc import DoclingDocument

    self.assertIsInstance(docling_document, DoclingDocument)
    self.assertGreater(len(docling_document.texts), 0)

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

  def test_convert_nonexistent_file_to_docling_raises_exception(self):
    """Test that converting a non-existent file to DoclingDocument raises an exception."""
    pytest.importorskip("docling")

    with self.assertRaises(Exception):
      convert_pdf_to_markdown("/nonexistent/file.pdf", output_format="docling")


if __name__ == "__main__":
  unittest.main()
