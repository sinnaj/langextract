#!/usr/bin/env python3
"""
PDF Outline Extractor Script

This script extracts the hierarchical structure (outline) from PDF documents using
Docling's advanced document understanding capabilities. It identifies document titles
and hierarchical headings (H1-H4) and outputs them in a structured JSON format.

The script leverages the existing PDF processing infrastructure in langextract,
specifically the Docling-based document parsing and structure recognition.

Usage:
    python pdf_outline_extractor.py input.pdf [output.json]
    python pdf_outline_extractor.py https://example.com/document.pdf [output.json]
    python pdf_outline_extractor.py input.pdf --stdout

Example:
    python pdf_outline_extractor.py document.pdf outline.json
    python pdf_outline_extractor.py https://arxiv.org/pdf/2408.09869 paper_outline.json
    python pdf_outline_extractor.py document.pdf --stdout
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Dict, List, Any, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from docling_core.types.doc import DoclingDocument, TextItem


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def convert_pdf_to_docling(source: Union[str, Path], verbose: bool = False) -> 'DoclingDocument':
    """
    Convert a PDF file to DoclingDocument using the existing pdf_to_markdown script.

    Args:
        source: Path to PDF file or URL
        verbose: Enable verbose logging

    Returns:
        DoclingDocument object

    Raises:
        ImportError: If docling is not installed
        Exception: If conversion fails
    """
    try:
        from scripts.pdf_to_markdown import convert_pdf_to_markdown
        return convert_pdf_to_markdown(source, output_format='docling', verbose=verbose)
    except ImportError as e:
        raise ImportError(
            'PDF conversion requires docling. '
            "Install with: pip install 'langextract[docling]'"
        ) from e


def extract_title_from_document(document: 'DoclingDocument') -> str:
    """
    Extract the document title from a DoclingDocument.

    Args:
        document: The DoclingDocument to extract title from

    Returns:
        The document title or empty string if not found
    """
    # Try to get title from document description
    if hasattr(document, 'description') and document.description:
        if isinstance(document.description, dict) and 'title' in document.description:
            title = document.description['title']
            if title and isinstance(title, str):
                return title.strip()

    # Try to find title from text items
    if hasattr(document, 'texts') and document.texts:
        try:
            from docling_core.types.doc import TitleItem, SectionHeaderItem
            
            # Look for TitleItem first
            for item in document.texts:
                if isinstance(item, TitleItem) and hasattr(item, 'text'):
                    return item.text.strip()
        except ImportError:
            # If docling_core is not available, fall back to heuristics
            pass
        
        # If no TitleItem, look for the first section header or text with large font
        # This is a heuristic approach similar to the ML-based extractor
        first_text_items = document.texts[:5]  # Check first 5 items
        for item in first_text_items:
            if hasattr(item, 'text') and item.text:
                text = item.text.strip()
                # Simple heuristics for title detection
                if (len(text) < 150 and  # Not too long
                    not text.startswith(('Abstract', 'Introduction', '1.', 'Chapter')) and
                    text.count('\n') == 0):  # Single line
                    return text

    return ""


def extract_outline_from_document(document: 'DoclingDocument') -> List[Dict[str, Any]]:
    """
    Extract hierarchical outline from a DoclingDocument.

    Args:
        document: The DoclingDocument to extract outline from

    Returns:
        List of outline items with level, text, and page information
    """
    outline = []
    
    if not hasattr(document, 'texts') or not document.texts:
        return outline

    try:
        from docling_core.types.doc import SectionHeaderItem, TitleItem
        has_docling_types = True
    except ImportError:
        has_docling_types = False
    
    # Track page numbers if available
    current_page = 1
    
    for item in document.texts:
        # Skip title items as they're handled separately
        if has_docling_types and isinstance(item, TitleItem):
            continue
            
        if has_docling_types and isinstance(item, SectionHeaderItem) and hasattr(item, 'text'):
            text = item.text.strip()
            if not text:
                continue
                
            # Determine heading level based on text patterns and document structure
            level = determine_heading_level(text, item)
            
            # Try to extract page number from provenance or estimate
            page_num = extract_page_number(item, current_page)
            if page_num > current_page:
                current_page = page_num
            
            outline.append({
                "level": level,
                "text": text,
                "page": page_num
            })
        
        elif hasattr(item, 'text') and item.text:
            # Check if this might be a heading based on text patterns
            text = item.text.strip()
            if is_likely_heading(text):
                level = determine_heading_level(text, item)
                page_num = extract_page_number(item, current_page)
                if page_num > current_page:
                    current_page = page_num
                
                outline.append({
                    "level": level,
                    "text": text,
                    "page": page_num
                })
    
    return outline


def determine_heading_level(text: str, item: 'TextItem') -> str:
    """
    Determine the heading level (H1-H4) based on text content and structure.
    
    Args:
        text: The heading text
        item: The text item object
        
    Returns:
        Heading level as string (H1, H2, H3, H4)
    """
    # Pattern-based level detection (similar to PDF-Outline-Extractor)
    text_lower = text.lower()
    
    # H1 indicators: Chapter, main sections
    if any(pattern in text_lower for pattern in ['chapter', 'abstract', 'introduction', 'conclusion']):
        return "H1"
    
    # Check for numbered sections
    import re
    
    # H1: Single number (1, 2, 3, etc.)
    if re.match(r'^\d+\.?\s+', text):
        return "H1"
    
    # H2: Two-level numbering (1.1, 1.2, etc.)
    if re.match(r'^\d+\.\d+\.?\s+', text):
        return "H2"
    
    # H3: Three-level numbering (1.1.1, 1.1.2, etc.)
    if re.match(r'^\d+\.\d+\.\d+\.?\s+', text):
        return "H3"
    
    # H4: Four-level numbering or deeper
    if re.match(r'^\d+\.\d+\.\d+\.\d+', text):
        return "H4"
    
    # Fallback based on text length and characteristics
    if len(text) < 50 and text[0].isupper():
        # Short, capitalized text likely to be higher level
        return "H2"
    else:
        return "H3"


def is_likely_heading(text: str) -> bool:
    """
    Determine if a text item is likely to be a heading.
    
    Args:
        text: The text to analyze
        
    Returns:
        True if the text is likely a heading
    """
    if not text or len(text.strip()) == 0:
        return False
    
    text = text.strip()
    
    # Too long to be a heading
    if len(text) > 200:
        return False
    
    # Contains multiple sentences (likely paragraph)
    if text.count('.') > 1 and not text.startswith(('Fig.', 'Table')):
        return False
    
    # Single line and not too long
    if text.count('\n') == 0 and len(text) < 150:
        # Check for heading patterns
        import re
        
        # Numbered sections
        if re.match(r'^\d+(?:\.\d+)*\.?\s+', text):
            return True
        
        # Common heading words
        heading_words = ['abstract', 'introduction', 'conclusion', 'discussion', 
                        'methodology', 'results', 'analysis', 'summary', 'appendix',
                        'references', 'bibliography', 'acknowledgments', 'chapter']
        
        text_lower = text.lower()
        if any(word in text_lower for word in heading_words):
            return True
        
        # All caps or title case
        if text.isupper() or text.istitle():
            return True
    
    return False


def extract_page_number(item: 'TextItem', default_page: int = 1) -> int:
    """
    Extract page number from a text item's provenance information.
    
    Args:
        item: The text item
        default_page: Default page number if extraction fails
        
    Returns:
        Page number (1-based)
    """
    # Try to get page from provenance
    if hasattr(item, 'prov') and item.prov:
        for prov in item.prov:
            if hasattr(prov, 'page') and prov.page is not None:
                return max(1, prov.page + 1)  # Convert to 1-based
            # Check for page in bbox if available
            if hasattr(prov, 'bbox') and hasattr(prov.bbox, 'page'):
                return max(1, prov.bbox.page + 1)
    
    # Try to get from item directly
    if hasattr(item, 'page') and item.page is not None:
        return max(1, item.page + 1)
    
    return default_page


def extract_pdf_outline(source: Union[str, Path], verbose: bool = False) -> Dict[str, Any]:
    """
    Extract hierarchical outline from a PDF file.

    Args:
        source: Path to PDF file or URL
        verbose: Enable verbose logging

    Returns:
        Dictionary containing title and outline structure
    """
    logger = logging.getLogger(__name__)
    logger.info('Extracting outline from: %s', source)

    try:
        # Convert PDF to DoclingDocument
        document = convert_pdf_to_docling(source, verbose)
        logger.info('PDF converted to DoclingDocument successfully')

        # Extract title
        title = extract_title_from_document(document)
        logger.info('Extracted title: %s', title or '(no title found)')

        # Extract outline
        outline = extract_outline_from_document(document)
        logger.info('Extracted %d outline items', len(outline))

        result = {
            "title": title,
            "outline": outline
        }

        return result

    except Exception as e:
        logger.error('Failed to extract outline: %s', e)
        raise


def save_outline(outline_data: Dict[str, Any], output_path: Optional[Union[str, Path]] = None) -> None:
    """
    Save outline data to a file or print to stdout.

    Args:
        outline_data: The outline data to save
        output_path: Optional output file path
    """
    logger = logging.getLogger(__name__)

    if output_path:
        output_file = Path(output_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(outline_data, f, indent=2, ensure_ascii=False)
        logger.info('Outline saved to: %s', output_file)
    else:
        # Print to stdout
        json.dump(outline_data, sys.stdout, indent=2, ensure_ascii=False)
        print()  # Add newline at end


def main() -> None:
    """Main command-line interface."""
    parser = argparse.ArgumentParser(
        description=(
            'Extract hierarchical structure (outline) from PDF documents using '
            'Docling document understanding capabilities'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument('input', help='Path to PDF file or URL')

    parser.add_argument(
        'output',
        nargs='?',
        help='Output file path (optional, prints to stdout if not provided)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--stdout',
        action='store_true',
        help='Force output to stdout (overrides output file)'
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    try:
        # Extract outline from PDF
        outline_data = extract_pdf_outline(args.input, args.verbose)

        # Determine output destination
        output_path = None if args.stdout else args.output

        # Save or print results
        save_outline(outline_data, output_path)

        # Print summary to stderr so it doesn't interfere with stdout output
        if not args.stdout:
            title = outline_data['title']
            outline_count = len(outline_data['outline'])
            print(f"✓ Extracted outline: '{title}' with {outline_count} items", file=sys.stderr)

    except ImportError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'Outline extraction failed: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()