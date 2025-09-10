"""
Tests for DoclingDocument to Markdown conversion script.
"""

from pathlib import Path
import tempfile
import unittest
from unittest import mock
import json

import pytest

from scripts.docling_to_markdown import convert_docling_to_markdown


class TestDoclingToMarkdown(unittest.TestCase):
  """Test cases for DoclingDocument to Markdown conversion."""

  def test_docling_not_installed_raises_import_error(self):
    """Test that ImportError is raised when docling is not available."""
    with mock.patch.dict("sys.modules", {"docling_core.types.doc": None}):
      with self.assertRaises(ImportError) as cm:
        convert_docling_to_markdown("dummy.json")

      self.assertIn("docling is required", str(cm.exception))
      self.assertIn("pip install", str(cm.exception))

  def test_nonexistent_file_raises_file_not_found_error(self):
    """Test that FileNotFoundError is raised for non-existent files."""
    pytest.importorskip("docling")

    with self.assertRaises(FileNotFoundError) as cm:
      convert_docling_to_markdown("/nonexistent/file.json")

    self.assertIn("Source file not found", str(cm.exception))

  def test_convert_invalid_file_format_raises_exception(self):
    """Test that invalid file formats raise an exception."""
    pytest.importorskip("docling")

    with tempfile.TemporaryDirectory() as temp_dir:
      # Create an invalid file
      invalid_file = Path(temp_dir) / "invalid.txt"
      invalid_file.write_text("This is not a valid JSON or YAML file.")

      # Try to convert it
      with self.assertRaises(ValueError) as cm:
        convert_docling_to_markdown(invalid_file)

      self.assertIn("Unable to parse", str(cm.exception))

  @pytest.mark.integration
  def test_convert_docling_from_pdf_roundtrip(self):
    """Test converting DoclingDocument created from PDF (integration test)."""
    pytest.importorskip("docling")

    from scripts.pdf_to_markdown import convert_pdf_to_markdown

    # Use a simple, small PDF from a reliable source
    url = "https://arxiv.org/pdf/2408.09869"

    with tempfile.TemporaryDirectory() as temp_dir:
      # First convert PDF to DoclingDocument JSON
      docling_json_file = Path(temp_dir) / "test_doc.json"
      docling_document = convert_pdf_to_markdown(
          url, docling_json_file, verbose=False, output_format="docling"
      )

      # Verify the DoclingDocument was saved
      self.assertTrue(docling_json_file.exists())

      # Now convert the DoclingDocument JSON to markdown
      markdown_file = Path(temp_dir) / "converted.md"
      markdown_content = convert_docling_to_markdown(
          docling_json_file, markdown_file, verbose=False
      )

      # Verify the conversion worked
      self.assertIsInstance(markdown_content, str)
      self.assertGreater(len(markdown_content), 100)

      # Verify the file was created
      self.assertTrue(markdown_file.exists())

      # Verify file content matches return value
      file_content = markdown_file.read_text(encoding="utf-8")
      self.assertEqual(markdown_content, file_content)

      # Basic content checks for the Docling paper
      self.assertIn("Docling", markdown_content)

  @pytest.mark.integration
  def test_convert_docling_yaml_from_pdf_roundtrip(self):
    """Test converting DoclingDocument YAML created from PDF."""
    pytest.importorskip("docling")

    from scripts.pdf_to_markdown import convert_pdf_to_markdown

    # Use a simple, small PDF from a reliable source
    url = "https://arxiv.org/pdf/2408.09869"

    with tempfile.TemporaryDirectory() as temp_dir:
      # First convert PDF to DoclingDocument YAML
      docling_yaml_file = Path(temp_dir) / "test_doc.yaml"
      docling_document = convert_pdf_to_markdown(
          url, docling_yaml_file, verbose=False, output_format="docling"
      )

      # Verify the DoclingDocument was saved
      self.assertTrue(docling_yaml_file.exists())

      # Now convert the DoclingDocument YAML to markdown
      markdown_file = Path(temp_dir) / "converted.md"
      markdown_content = convert_docling_to_markdown(
          docling_yaml_file, markdown_file, verbose=False
      )

      # Verify the conversion worked
      self.assertIsInstance(markdown_content, str)
      self.assertGreater(len(markdown_content), 100)

      # Verify the file was created
      self.assertTrue(markdown_file.exists())

      # Verify file content matches return value
      file_content = markdown_file.read_text(encoding="utf-8")
      self.assertEqual(markdown_content, file_content)

      # Basic content checks
      self.assertIn("Docling", markdown_content)

  @pytest.mark.integration
  def test_convert_docling_document_without_output_file(self):
    """Test converting DoclingDocument without specifying output file."""
    pytest.importorskip("docling")

    from scripts.pdf_to_markdown import convert_pdf_to_markdown

    # Use a simple, small PDF from a reliable source
    url = "https://arxiv.org/pdf/2408.09869"

    with tempfile.TemporaryDirectory() as temp_dir:
      # First convert PDF to DoclingDocument JSON
      docling_json_file = Path(temp_dir) / "test_doc.json"
      convert_pdf_to_markdown(
          url, docling_json_file, verbose=False, output_format="docling"
      )

      # Convert DoclingDocument to markdown without output file
      markdown_content = convert_docling_to_markdown(
          docling_json_file, verbose=False
      )

      # Verify content is returned
      self.assertIsInstance(markdown_content, str)
      self.assertGreater(len(markdown_content), 100)
      self.assertIn("Docling", markdown_content)

  @pytest.mark.integration
  def test_convert_file_without_extension_tries_both_formats(self):
    """Test that files without clear extensions try both JSON and YAML."""
    pytest.importorskip("docling")

    from scripts.pdf_to_markdown import convert_pdf_to_markdown

    # Use a simple, small PDF from a reliable source
    url = "https://arxiv.org/pdf/2408.09869"

    with tempfile.TemporaryDirectory() as temp_dir:
      # First convert PDF to DoclingDocument JSON
      docling_json_file = Path(temp_dir) / "test_doc.json"
      convert_pdf_to_markdown(
          url, docling_json_file, verbose=False, output_format="docling"
      )

      # Copy to a file without extension
      no_ext_file = Path(temp_dir) / "test_doc_no_ext"
      no_ext_file.write_bytes(docling_json_file.read_bytes())

      # Convert the file without extension
      markdown_content = convert_docling_to_markdown(no_ext_file, verbose=False)

      # Verify content is returned
      self.assertIsInstance(markdown_content, str)
      self.assertGreater(len(markdown_content), 100)
      self.assertIn("Docling", markdown_content)


if __name__ == "__main__":
  unittest.main()
