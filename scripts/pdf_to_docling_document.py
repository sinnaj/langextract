#!/usr/bin/env python3
"""
PDF to Docling Document Conversion Script

This script uses the docling library to parse PDF files and convert them to
DoclingDocument format. Unlike pdf_to_markdown.py, this script focuses on
producing structured DoclingDocument objects for further processing.

Usage:
    python pdf_to_docling_document.py input.pdf [output.json]
    python pdf_to_docling_document.py https://example.com/document.pdf [output.json]

Example:
    python pdf_to_docling_document.py document.pdf document.json
    python pdf_to_docling_document.py https://arxiv.org/pdf/2408.09869 arxiv_paper.json
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


def convert_pdf_to_docling_document(
    source: str | Path,
    output_path: str | Path | None = None,
    verbose: bool = False,
) -> 'DoclingDocument':
    """
    Convert a PDF file to DoclingDocument using docling.

    Args:
        source: Path to PDF file or URL
        output_path: Optional output path for JSON file
        verbose: Enable verbose logging

    Returns:
        The DoclingDocument object

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

    logger.info('Converting PDF to DoclingDocument: %s', source)

    try:
        # Initialize the document converter
        converter = DocumentConverter()

        # Convert the document
        result = converter.convert(source)

        logger.info('PDF converted to DoclingDocument successfully')

        # Get the DoclingDocument
        docling_document = result.document

        # Save to file if output path is provided
        if output_path:
            output_file = Path(output_path)
            # Save as JSON
            docling_document.save_as_json(output_file)
            logger.info('DoclingDocument saved to: %s', output_file)

        return docling_document

    except Exception as e:
        logger.error('Failed to convert PDF to DoclingDocument: %s', e)
        raise


def main() -> None:
    """Main command-line interface."""
    parser = argparse.ArgumentParser(
        description='Convert PDF files to DoclingDocument using docling',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument('input', help='Path to PDF file or URL')

    parser.add_argument('output', nargs='?', help='Output JSON file path (optional)')

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
                output_path = input_path.with_suffix('.json')
            else:
                # For URLs or files without .pdf extension
                output_path = Path('converted_document.json')

        # Convert the document
        docling_document = convert_pdf_to_docling_document(
            args.input, output_path, args.verbose
        )

        # Print success message
        print(f"Successfully converted PDF to DoclingDocument: {output_path}")

    except ImportError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Conversion failed: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()