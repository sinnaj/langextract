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
import warnings
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
    enable_gpu: bool = True,
) -> 'DoclingDocument':
    """
    Convert a PDF file to DoclingDocument using docling.

    Args:
        source: Path to PDF file or URL
        output_path: Optional output path for JSON file
        verbose: Enable verbose logging
        enable_gpu: Enable GPU acceleration if available

    Returns:
        The DoclingDocument object

    Raises:
        ImportError: If docling is not installed
        Exception: If conversion fails
    """
    try:
        # pylint: disable=import-outside-toplevel
        from docling.document_converter import DocumentConverter
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TableFormerMode,
            TableStructureOptions,
            AcceleratorOptions,
        )
        from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
        from docling_core.types.doc import DoclingDocument
    except ImportError as e:
        raise ImportError(
            'docling is required for PDF conversion. '
            "Install with: pip install 'langextract[docling]'"
        ) from e

    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    logger.info('Converting PDF to DoclingDocument: %s', source)
    
    # Configure GPU acceleration
    if enable_gpu:
        try:
            import torch
            if torch.cuda.is_available():
                device = torch.device('cuda')
                logger.info(f'Using GPU acceleration on device: {torch.cuda.get_device_name()}')
            else:
                device = torch.device('cpu')
                logger.info('CUDA not available, using CPU')
        except ImportError:
            logger.info('PyTorch not available, using default configuration')
            device = None
    else:
        device = None
        logger.info('GPU acceleration disabled')

    try:
        # Configure GPU acceleration
        accelerator_options = AcceleratorOptions(
            device='cuda' if enable_gpu else 'cpu',
            num_threads=4
        )
        
        # Configure table structure options
        table_structure_options = TableStructureOptions(
            mode=TableFormerMode.ACCURATE if enable_gpu else TableFormerMode.FAST,
            do_cell_matching=True
        )
        
        # Configure OCR options with GPU support
        from docling.datamodel.pipeline_options import EasyOcrOptions
        ocr_options = EasyOcrOptions(
            use_gpu=enable_gpu,
            lang=['en', 'fr', 'de', 'es'],
            confidence_threshold=0.5
        )
        
        # Configure pipeline options for better GPU utilization
        pipeline_options = PdfPipelineOptions(
            accelerator_options=accelerator_options,
            do_table_structure=True,
            table_structure_options=table_structure_options,
            do_ocr=True,
            ocr_options=ocr_options,
        )
        
        # Initialize the document converter with GPU configuration
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pipeline_options,
            }
        )

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
    
    parser.add_argument(
        '--no-gpu', action='store_true', 
        help='Disable GPU acceleration (use CPU only)'
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
            args.input, output_path, args.verbose, enable_gpu=not args.no_gpu
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