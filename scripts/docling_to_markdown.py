#!/usr/bin/env python3
"""
DoclingDocument to Markdown Conversion Script

This script converts DoclingDocument files (in JSON or YAML format) to Markdown.
It's complementary to the pdf_to_markdown.py script which converts PDFs to
DoclingDocuments or directly to markdown.

Usage:
    python docling_to_markdown.py document.json [output.md]
    python docling_to_markdown.py document.yaml [output.md]

Example:
    python docling_to_markdown.py docling_document.json converted.md
    python docling_to_markdown.py docling_document.yaml converted.md
"""

import argparse
import logging
from pathlib import Path
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from docling_core.types.doc import DoclingDocument


def setup_logging(verbose: bool = False) -> None:
  """Set up logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )


def convert_docling_to_markdown(
    source: str | Path,
    output_path: str | Path | None = None,
    verbose: bool = False,
) -> str:
  """
  Convert a DoclingDocument file to Markdown.

  Args:
      source: Path to DoclingDocument file (JSON or YAML)
      output_path: Optional output path for markdown file
      verbose: Enable verbose logging

  Returns:
      The markdown content as a string

  Raises:
      ImportError: If docling is not installed
      FileNotFoundError: If source file doesn't exist
      Exception: If conversion fails
  """
  try:
    # pylint: disable=import-outside-toplevel
    from docling_core.types.doc import DoclingDocument
  except ImportError as e:
    raise ImportError(
        'docling is required for DoclingDocument conversion. '
        "Install with: pip install 'langextract[docling]'"
    ) from e

  setup_logging(verbose)
  logger = logging.getLogger(__name__)

  source_path = Path(source)
  if not source_path.exists():
    raise FileNotFoundError(f'Source file not found: {source_path}')

  logger.info('Converting DoclingDocument from: %s', source_path)

  try:
    # Load the DoclingDocument based on file extension
    if source_path.suffix.lower() == '.json':
      doc = DoclingDocument.load_from_json(source_path)
    elif source_path.suffix.lower() in ['.yaml', '.yml']:
      doc = DoclingDocument.load_from_yaml(source_path)
    else:
      # Try to load as JSON first, then YAML
      try:
        doc = DoclingDocument.load_from_json(source_path)
      except Exception:
        try:
          doc = DoclingDocument.load_from_yaml(source_path)
        except Exception as yaml_error:
          raise ValueError(
              f'Unable to parse {source_path} as JSON or YAML: {yaml_error}'
          ) from yaml_error

    logger.info('DoclingDocument loaded successfully')

    # Export to Markdown
    markdown_content = doc.export_to_markdown()

    # Save to file if output path is provided
    if output_path:
      output_file = Path(output_path)
      output_file.write_text(markdown_content, encoding='utf-8')
      logger.info('Markdown saved to: %s', output_file)

    logger.info('Conversion completed successfully')
    return markdown_content

  except Exception as e:
    logger.error('Failed to convert DoclingDocument: %s', e)
    raise


def main() -> None:
  """Main command-line interface."""
  parser = argparse.ArgumentParser(
      description='Convert DoclingDocument files (JSON/YAML) to Markdown',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog=__doc__,
  )

  parser.add_argument(
      'input', help='Path to DoclingDocument file (JSON or YAML)'
  )

  parser.add_argument(
      'output', nargs='?', help='Output markdown file path (optional)'
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
      output_path = input_path.with_suffix('.md')

    # Convert the document
    markdown_content = convert_docling_to_markdown(
        args.input, output_path, args.verbose
    )

    # Print to stdout if no output file specified
    if not args.output:
      print(markdown_content)

  except ImportError as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
  except FileNotFoundError as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    print(f'Conversion failed: {e}', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()
