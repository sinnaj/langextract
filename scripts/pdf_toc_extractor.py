#!/usr/bin/env python3
"""
PDF Table of Contents (ToC) Extraction Script using PyMuPDF

This script uses the PyMuPDF library to extract table of contents from PDF files.
It supports both local files and URLs, with multiple output formats.

Usage:
    python pdf_toc_extractor.py input.pdf
    python pdf_toc_extractor.py https://example.com/document.pdf
    python pdf_toc_extractor.py input.pdf --output toc.json --format json
    python pdf_toc_extractor.py input.pdf --output toc.txt --format text

Example:
    python pdf_toc_extractor.py document.pdf
    python pdf_toc_extractor.py https://arxiv.org/pdf/2408.09869 --format json
    python pdf_toc_extractor.py document.pdf --output document_toc.json
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Literal, Optional, Union
import urllib.parse
import urllib.request


def setup_logging(verbose: bool = False) -> None:
  """Set up logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )


def extract_pdf_toc(
    source: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    verbose: bool = False,
    output_format: Literal['json', 'text'] = 'json',
) -> Union[List[Dict[str, Any]], str]:
  """
  Extract table of contents from a PDF file using PyMuPDF.

  Args:
      source: Path to PDF file or URL
      output_path: Optional output path for output file
      verbose: Enable verbose logging
      output_format: Output format - 'json' or 'text'

  Returns:
      List of ToC entries (json format) or formatted text string

  Raises:
      ImportError: If PyMuPDF is not installed
      FileNotFoundError: If the source file doesn't exist
      Exception: For other processing errors
  """
  try:
    import fitz  # PyMuPDF
  except ImportError as e:
    raise ImportError(
        'PyMuPDF (fitz) is required for PDF ToC extraction. '
        "Install with: pip install 'langextract[pymupdf]'"
    ) from e

  setup_logging(verbose)
  logger = logging.getLogger(__name__)

  logger.info('Extracting ToC from: %s', source)

  try:
    # Handle URLs by downloading to temporary location
    temp_file = None
    if isinstance(source, str) and (
        source.startswith('http://') or source.startswith('https://')
    ):
      logger.info('Downloading PDF from URL: %s', source)
      import tempfile

      with tempfile.NamedTemporaryFile(
          delete=False, suffix='.pdf'
      ) as temp_file:
        with urllib.request.urlopen(source) as response:
          temp_file.write(response.read())
        pdf_path = temp_file.name
    else:
      pdf_path = str(source)

    # Open the PDF document
    doc = fitz.open(pdf_path)

    # Extract table of contents
    toc = doc.get_toc()

    # Close the document
    doc.close()

    # Clean up temporary file if it was created
    if temp_file:
      import os

      os.unlink(temp_file.name)

    logger.info('Successfully extracted ToC with %d entries', len(toc))

    if not toc:
      logger.warning('No table of contents found in the PDF')

    # Convert to structured format
    toc_entries = []
    for level, title, page in toc:
      toc_entries.append({'level': level, 'title': title.strip(), 'page': page})

    # Format output based on requested format
    if output_format == 'text':
      content = format_toc_as_text(toc_entries)
    else:
      content = toc_entries

    # Save to file if output path is provided
    if output_path:
      output_file = Path(output_path)
      if output_format == 'text':
        output_file.write_text(content, encoding='utf-8')
      else:
        output_file.write_text(
            json.dumps(content, indent=2, ensure_ascii=False), encoding='utf-8'
        )
      logger.info('ToC saved to: %s', output_file)

    return content

  except Exception as e:
    logger.error('Failed to extract ToC: %s', e)
    raise


def format_toc_as_text(toc_entries: List[Dict[str, Any]]) -> str:
  """
  Format ToC entries as readable text.

  Args:
      toc_entries: List of ToC entry dictionaries

  Returns:
      Formatted text string
  """
  if not toc_entries:
    return 'No table of contents found.\n'

  lines = ['Table of Contents', '=' * 18, '']

  for entry in toc_entries:
    indent = '  ' * (entry['level'] - 1)
    line = f"{indent}{entry['title']} ... {entry['page']}"
    lines.append(line)

  return '\n'.join(lines) + '\n'


def main() -> None:
  """Main command-line interface."""
  parser = argparse.ArgumentParser(
      description='Extract table of contents from PDF files using PyMuPDF',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
Examples:
  %(prog)s document.pdf
  %(prog)s document.pdf --format text
  %(prog)s document.pdf --output toc.json --format json
  %(prog)s https://arxiv.org/pdf/2408.09869 --format text --verbose
      """.strip(),
  )

  parser.add_argument('input', help='Input PDF file path or URL')
  parser.add_argument(
      '--output',
      '-o',
      help='Output file path (if not specified, prints to stdout)',
  )
  parser.add_argument(
      '--format',
      '-f',
      choices=['json', 'text'],
      default='json',
      help=(
          'Output format: json (structured) or text (human-readable). Default:'
          ' json'
      ),
  )
  parser.add_argument(
      '--verbose', '-v', action='store_true', help='Enable verbose logging'
  )

  try:
    args = parser.parse_args()

    # Determine output file if not specified
    output_path = args.output
    if not output_path and not sys.stdout.isatty():
      # When piping output, use stdout
      output_path = None
    elif not output_path:
      # Generate default output filename
      input_path = Path(args.input)
      if input_path.suffix.lower() == '.pdf':
        if args.format == 'text':
          output_path = input_path.with_suffix('.toc.txt')
        else:
          output_path = input_path.with_suffix('.toc.json')
      else:
        # For URLs or files without .pdf extension
        if args.format == 'text':
          output_path = Path('extracted_toc.txt')
        else:
          output_path = Path('extracted_toc.json')

    # Extract the ToC
    content = extract_pdf_toc(
        args.input, output_path, args.verbose, args.format
    )

    # Print to stdout if no output file specified
    if not args.output:
      if args.format == 'json':
        print(json.dumps(content, indent=2, ensure_ascii=False))
      else:
        print(content, end='')

  except ImportError as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    print(f'ToC extraction failed: {e}', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()
