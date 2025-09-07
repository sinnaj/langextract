#!/usr/bin/env python3
"""
PDF to Markdown Conversion Script using Docling

This script uses the docling library to parse PDF files and convert them to
Markdown format or DoclingDocument format. It supports both local files and URLs.

Usage:
    python pdf_to_markdown.py input.pdf [output.md]
    python pdf_to_markdown.py https://example.com/document.pdf [output.md]
    python pdf_to_markdown.py input.pdf output.json --format docling

Example:
    python pdf_to_markdown.py document.pdf converted_document.md
    python pdf_to_markdown.py https://arxiv.org/pdf/2408.09869 arxiv_paper.md
    python pdf_to_markdown.py document.pdf document.json --format docling
"""

import argparse
import logging
from pathlib import Path
import sys
from typing import Literal, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
  from docling_core.types.doc import DoclingDocument


def setup_logging(verbose: bool = False) -> None:
  """Set up logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )


def convert_pdf_to_markdown(
    source: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    verbose: bool = False,
    output_format: Literal['markdown', 'docling'] = 'markdown',
) -> Union[str, 'DoclingDocument']:
  """
  Convert a PDF file to Markdown or DoclingDocument using docling.

  Args:
      source: Path to PDF file or URL
      output_path: Optional output path for output file
      verbose: Enable verbose logging
      output_format: Output format - 'markdown' or 'docling'

  Returns:
      The content as a string (markdown) or DoclingDocument object (docling)

  Raises:
      ImportError: If docling is not installed
      Exception: If conversion fails
  """
  try:
    # pylint: disable=import-outside-toplevel
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc import DoclingDocument
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

    logger.info('Document converted successfully')

    if output_format == 'docling':
      # Return the DoclingDocument directly
      content = result.document

      # Save to file if output path is provided
      if output_path:
        output_file = Path(output_path)
        if output_file.suffix.lower() == '.json':
          result.document.save_as_json(output_file)
        elif output_file.suffix.lower() in ['.yaml', '.yml']:
          result.document.save_as_yaml(output_file)
        else:
          # Default to JSON if extension not recognized
          result.document.save_as_json(output_file)
        logger.info('DoclingDocument saved to: %s', output_file)

    else:
      # Export to Markdown (default behavior)
      content = result.document.export_to_markdown()

      # Save to file if output path is provided
      if output_path:
        output_file = Path(output_path)
        output_file.write_text(content, encoding='utf-8')
        logger.info('Markdown saved to: %s', output_file)

    return content

  except Exception as e:
    logger.error('Failed to convert document: %s', e)
    raise


def main() -> None:
  """Main command-line interface."""
  parser = argparse.ArgumentParser(
      description=(
          'Convert PDF files to Markdown or DoclingDocument using docling'
      ),
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog=__doc__,
  )

  parser.add_argument('input', help='Path to PDF file or URL')

  parser.add_argument('output', nargs='?', help='Output file path (optional)')

  parser.add_argument(
      '-v', '--verbose', action='store_true', help='Enable verbose logging'
  )

  parser.add_argument(
      '--format',
      choices=['markdown', 'docling'],
      default='markdown',
      help='Output format: markdown (default) or docling document',
  )

  args = parser.parse_args()

  try:
    # Generate default output filename if not provided
    output_path = args.output
    if not output_path:
      input_path = Path(args.input)
      if input_path.suffix == '.pdf':
        if args.format == 'docling':
          output_path = input_path.with_suffix('.json')
        else:
          output_path = input_path.with_suffix('.md')
      else:
        # For URLs or files without .pdf extension
        if args.format == 'docling':
          output_path = Path('converted_document.json')
        else:
          output_path = Path('converted_document.md')

    # Convert the document
    content = convert_pdf_to_markdown(
        args.input, output_path, args.verbose, args.format
    )

    # Print to stdout if no output file specified
    if not args.output:
      if args.format == 'docling':
        # For DoclingDocument, print JSON representation
        print(content.model_dump_json(indent=2))
      else:
        print(content)

  except ImportError as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    print(f'Conversion failed: {e}', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()
