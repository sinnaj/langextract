#!/usr/bin/env python3
"""
PDF to Markdown Conversion Script using Docling

This script uses the docling library to parse PDF files and convert them to
Markdown format. It supports both local files and URLs.

Usage:
    python pdf_to_markdown.py input.pdf [output.md]
    python pdf_to_markdown.py https://example.com/document.pdf [output.md]

Example:
    python pdf_to_markdown.py document.pdf converted_document.md
    python pdf_to_markdown.py https://arxiv.org/pdf/2408.09869 arxiv_paper.md
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(verbose: bool = False) -> None:
  """Set up logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )


def convert_pdf_to_markdown(
    source: str | Path,
    output_path: Optional[str | Path] = None,
    verbose: bool = False,
) -> str:
  """
  Convert a PDF file to Markdown using docling.

  Args:
      source: Path to PDF file or URL
      output_path: Optional output path for Markdown file
      verbose: Enable verbose logging

  Returns:
      The Markdown content as a string

  Raises:
      ImportError: If docling is not installed
      Exception: If conversion fails
  """
  try:
    # pylint: disable=import-outside-toplevel
    from docling.document_converter import DocumentConverter
  except ImportError as e:
    raise ImportError(
        'docling is required for PDF conversion. '
        "Install with: pip install 'langextract[docling]'"
    ) from e

  setup_logging(verbose)
  logger = logging.getLogger(__name__)

  logger.info('Converting document from: %s', source)

  try:
    # Initialize the document converter
    converter = DocumentConverter()

    # Convert the document
    result = converter.convert(source)

    # Export to Markdown
    markdown_content = result.document.export_to_markdown()

    logger.info('Document converted successfully')

    # Save to file if output path is provided
    if output_path:
      output_file = Path(output_path)
      output_file.write_text(markdown_content, encoding='utf-8')
      logger.info('Markdown saved to: %s', output_file)

    return markdown_content

  except Exception as e:
    logger.error('Failed to convert document: %s', e)
    raise


def main() -> None:
  """Main command-line interface."""
  parser = argparse.ArgumentParser(
      description='Convert PDF files to Markdown using docling',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog=__doc__,
  )

  parser.add_argument('input', help='Path to PDF file or URL')

  parser.add_argument(
      'output', nargs='?', help='Output Markdown file path (optional)'
  )

  parser.add_argument(
      '-v', '--verbose', action='store_true', help='Enable verbose logging'
  )

  args = parser.parse_args()

  try:
    # Generate default output filename if not provided
    output_path = args.output
    if not output_path:
      input_path = Path(args.input)
      if input_path.suffix == '.pdf':
        output_path = input_path.with_suffix('.md')
      else:
        # For URLs or files without .pdf extension
        output_path = Path('converted_document.md')

    # Convert the document
    markdown_content = convert_pdf_to_markdown(
        args.input, output_path, args.verbose
    )

    # Print to stdout if no output file specified
    if not args.output:
      print(markdown_content)

  except ImportError as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    print(f'Conversion failed: {e}', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()
