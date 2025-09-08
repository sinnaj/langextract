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
import re
import sys
from typing import Any, Dict, List, Literal, Optional, Union
import urllib.parse
import urllib.request
import unicodedata


def setup_logging(verbose: bool = False) -> None:
  """Set up logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )


def normalize_text(text: str) -> str:
  """
  Normalize text for comparison by handling Unicode and cleaning whitespace.
  
  Args:
      text: Text to normalize
      
  Returns:
      Normalized text string
  """
  # Decode Unicode escape sequences if present
  try:
    if '\\u' in text:
      text = text.encode().decode('unicode_escape')
  except UnicodeDecodeError:
    pass
  
  # Normalize Unicode characters to NFD form and remove diacritics
  normalized = unicodedata.normalize('NFD', text)
  ascii_text = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
  
  # Clean up whitespace and convert to lowercase
  return re.sub(r'\s+', ' ', ascii_text.lower()).strip()


def calculate_text_similarity(text1: str, text2: str) -> float:
  """
  Calculate similarity between two text strings using simple token matching.
  
  Args:
      text1: First text string
      text2: Second text string
      
  Returns:
      Similarity score between 0.0 and 1.0
  """
  norm1 = normalize_text(text1)
  norm2 = normalize_text(text2)
  
  if norm1 == norm2:
    return 1.0
  
  # Split into tokens and calculate Jaccard similarity
  tokens1 = set(norm1.split())
  tokens2 = set(norm2.split())
  
  if not tokens1 and not tokens2:
    return 1.0
  
  if not tokens1 or not tokens2:
    return 0.0
  
  intersection = tokens1.intersection(tokens2)
  union = tokens1.union(tokens2)
  
  return len(intersection) / len(union) if union else 0.0


def update_parent_references(docling_data: Dict[str, Any]) -> Dict[str, Any]:
  """
  Update parent references in DoclingDocument to reflect hierarchical structure.
  
  Args:
      docling_data: DoclingDocument JSON data with corrected levels
      
  Returns:
      Updated DoclingDocument with corrected parent references
  """
  logger = logging.getLogger(__name__)
  
  # Create a deep copy of the docling data
  import copy
  updated_data = copy.deepcopy(docling_data)
  
  texts = updated_data.get('texts', [])
  
  # Find all section headers and track their hierarchical relationships
  section_headers = []
  for i, text_item in enumerate(texts):
    if text_item.get('label') == 'section_header':
      section_headers.append({
        'index': i,
        'text': text_item.get('text', ''),
        'level': text_item.get('level', 1),
        'ref': f"#/texts/{i}"
      })
  
  logger.info(f'Updating parent references for {len(section_headers)} section headers')
  
  # Track the most recent parent at each level
  parent_stack = {}  # level -> {'index': index, 'ref': ref}
  updates_count = 0
  
  for header in section_headers:
    current_level = header['level']
    current_index = header['index']
    current_ref = header['ref']
    
    # Determine the appropriate parent
    parent_ref = "#/body"  # Default for level 1
    
    if current_level > 1:
      # Find the most recent parent at the previous level
      for parent_level in range(current_level - 1, 0, -1):
        if parent_level in parent_stack:
          parent_ref = parent_stack[parent_level]['ref']
          break
    
    # Update the parent reference if it changed
    old_parent_ref = texts[current_index].get('parent', {}).get('$ref', '')
    if parent_ref != old_parent_ref:
      texts[current_index]['parent'] = {'$ref': parent_ref}
      updates_count += 1
      logger.debug(f'Updated parent for "{header["text"][:50]}..." from "{old_parent_ref}" to "{parent_ref}"')
    
    # Update the parent stack for this level and clear deeper levels
    parent_stack[current_level] = {
      'index': current_index,
      'ref': current_ref
    }
    
    # Clear deeper levels from the stack
    levels_to_remove = [level for level in parent_stack.keys() if level > current_level]
    for level in levels_to_remove:
      del parent_stack[level]
  
  logger.info(f'Updated parent references for {updates_count} section headers')
  
  return updated_data


def generate_toc_markdown(docling_data: Dict[str, Any]) -> str:
  """
  Generate a table of contents in markdown format from DoclingDocument section headers.
  
  Args:
      docling_data: DoclingDocument JSON data with corrected levels
      
  Returns:
      Markdown formatted table of contents
  """
  texts = docling_data.get('texts', [])
  
  # Extract section headers with their levels
  section_headers = []
  for text_item in texts:
    if text_item.get('label') == 'section_header':
      section_headers.append({
        'text': text_item.get('text', ''),
        'level': text_item.get('level', 1)
      })
  
  if not section_headers:
    return "# Table of Contents\n\nNo section headers found.\n"
  
  # Generate markdown
  lines = [
    "# Table of Contents",
    "",
    "Generated from DoclingDocument section hierarchy.",
    ""
  ]
  
  for header in section_headers:
    # Create indentation based on level (level 1 = no indent, level 2 = 2 spaces, etc.)
    indent = "  " * (header['level'] - 1)
    # Use dashes for all levels
    line = f"{indent}- {header['text']}"
    lines.append(line)
  
  lines.append("")  # Add final newline
  return "\n".join(lines)


def map_toc_to_docling_sections(
    toc_entries: List[Dict[str, Any]], 
    docling_data: Dict[str, Any],
    similarity_threshold: float = 0.5
) -> Dict[str, Any]:
  """
  Map ToC entries to DoclingDocument section headers and update their levels and parent references.
  
  Args:
      toc_entries: List of ToC entries with level, title, and page
      docling_data: DoclingDocument JSON data
      similarity_threshold: Minimum similarity score for matching
      
  Returns:
      Updated DoclingDocument with corrected section header levels and parent references
  """
  logger = logging.getLogger(__name__)
  
  # Create a deep copy of the docling data
  import copy
  updated_data = copy.deepcopy(docling_data)
  
  # Find all section headers in the texts array
  section_headers = []
  texts = updated_data.get('texts', [])
  
  for i, text_item in enumerate(texts):
    if text_item.get('label') == 'section_header':
      section_headers.append({
        'index': i,
        'text': text_item.get('text', ''),
        'original_level': text_item.get('level', 1)
      })
  
  logger.info(f'Found {len(section_headers)} section headers in DoclingDocument')
  logger.info(f'Found {len(toc_entries)} ToC entries to map')
  
  # Map ToC entries to section headers
  mappings = []
  for toc_entry in toc_entries:
    toc_title = toc_entry['title']
    toc_level = toc_entry['level']
    
    best_match = None
    best_similarity = 0.0
    
    for header in section_headers:
      similarity = calculate_text_similarity(toc_title, header['text'])
      
      if similarity > best_similarity and similarity >= similarity_threshold:
        best_similarity = similarity
        best_match = header
    
    if best_match:
      mappings.append({
        'toc_entry': toc_entry,
        'section_header': best_match,
        'similarity': best_similarity
      })
      logger.debug(f'Mapped "{toc_title}" (level {toc_level}) to "{best_match["text"]}" (similarity: {best_similarity:.3f})')
  
  logger.info(f'Successfully mapped {len(mappings)} ToC entries to section headers')
  
  # Update the levels in the DoclingDocument
  updates_count = 0
  for mapping in mappings:
    section_index = mapping['section_header']['index']
    new_level = mapping['toc_entry']['level']
    old_level = texts[section_index].get('level', 1)
    
    texts[section_index]['level'] = new_level
    updates_count += 1
    
    logger.debug(f'Updated section "{texts[section_index].get("text", "")}" level from {old_level} to {new_level}')
  
  logger.info(f'Updated levels for {updates_count} section headers')
  
  # Process unmapped section headers: set their level to previous level + 1
  mapped_indices = {mapping['section_header']['index'] for mapping in mappings}
  unmapped_updates_count = 0
  
  # Sort section headers by their index to process them in document order
  section_headers_sorted = sorted(section_headers, key=lambda x: x['index'])
  
  previous_level = 1  # Default level for the first section
  
  for header in section_headers_sorted:
    section_index = header['index']
    
    if section_index in mapped_indices:
      # This section was mapped to a ToC entry, use its updated level as reference
      previous_level = texts[section_index].get('level', 1)
    else:
      # This section was not mapped, set its level to previous level + 1
      new_level = previous_level + 1
      old_level = texts[section_index].get('level', 1)
      
      if new_level != old_level:
        texts[section_index]['level'] = new_level
        unmapped_updates_count += 1
        logger.debug(f'Updated unmapped section "{texts[section_index].get("text", "")[:50]}..." level from {old_level} to {new_level}')
      
      previous_level = new_level
  
  if unmapped_updates_count > 0:
    logger.info(f'Updated levels for {unmapped_updates_count} unmapped section headers')
  
  # Update parent references based on the new hierarchical structure
  updated_data = update_parent_references(updated_data)
  
  return updated_data


def infer_hierarchical_levels_from_text(docling_data: Dict[str, Any]) -> Dict[str, Any]:
  """
  Infer hierarchical levels from section header text patterns when no PDF ToC is available.
  
  Args:
      docling_data: DoclingDocument JSON data
      
  Returns:
      Updated DoclingDocument with inferred section header levels and parent references
  """
  logger = logging.getLogger(__name__)
  
  # Create a deep copy of the docling data
  import copy
  updated_data = copy.deepcopy(docling_data)
  
  # Find all section headers in the texts array
  section_headers = []
  texts = updated_data.get('texts', [])
  
  for i, text_item in enumerate(texts):
    if text_item.get('label') == 'section_header':
      section_headers.append({
        'index': i,
        'text': text_item.get('text', ''),
        'original_level': text_item.get('level', 1)
      })
  
  logger.info(f'Found {len(section_headers)} section headers for level inference')
  
  # Define patterns for different levels (Spanish document patterns)
  level_patterns = [
    # Level 1: Main titles and sections
    (1, [
      r'^D\s*ocumento\s+B\s*ásico',  # Documento Básico
      r'^Seguridad\s+en\s+caso\s+de\s+incendio',  # Main title
      r'^Introducción$',  # Introduction
      r'^I{1,3}\s+[A-Z]',  # Roman numerals (I, II, III)
      r'^Artículo\s+\d+',  # Article numbers
      r'^Índice$',  # Index
      r'^Anejo\s+[A-Z]+',  # Anejo sections
      r'^Disposiciones\s+normativas',  # Regulations
      r'^Documento\s+Básico\s+consolidado',  # Consolidated document
    ]),
    
    # Level 2: Section headers like "Sección SI X"
    (2, [
      r'^Sección\s+SI\s+\d+',  # Sección SI 1, Sección SI 2, etc.
    ]),
    
    # Level 3: Numbered subsections like "1 Title", "2 Title"  
    (3, [
      r'^\d+\s+[A-Z]',  # Number followed by title (1 Title, 2 Title)
      r'^\d+\.\d+\s+[A-Z]',  # Decimal numbering (1.1 Title, 1.2 Title)
    ]),
    
    # Level 4: Sub-numbered sections like "1.1 Title"
    (4, [
      r'^\d+\.\d+\.\d+\s+[A-Z]',  # Triple decimal (1.1.1 Title)
    ]),
  ]
  
  # Apply pattern matching to infer levels
  updates_count = 0
  
  for header in section_headers:
    text = header['text']
    inferred_level = 1  # Default level
    
    # Test patterns in order
    for level, patterns in level_patterns:
      for pattern in patterns:
        if re.match(pattern, text.strip(), re.IGNORECASE):
          inferred_level = level
          break
      if inferred_level != 1:  # If we found a match, stop checking
        break
    
    # Update the level if it changed
    section_index = header['index']
    old_level = texts[section_index].get('level', 1)
    
    if inferred_level != old_level:
      texts[section_index]['level'] = inferred_level
      updates_count += 1
      logger.debug(f'Inferred level {inferred_level} for "{text[:50]}..." (was {old_level})')
  
  logger.info(f'Updated levels for {updates_count} section headers based on text patterns')
  
  # Update parent references based on the new hierarchical structure
  updated_data = update_parent_references(updated_data)
  
  return updated_data


def process_docling_document_only(
    docling_json_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    verbose: bool = False,
    generate_toc_md: bool = False,
) -> Dict[str, Any]:
  """
  Process a DoclingDocument JSON file to infer hierarchical levels without PDF ToC.
  
  Args:
      docling_json_path: Path to DoclingDocument JSON file
      output_path: Optional output path for corrected JSON file
      verbose: Enable verbose logging
      generate_toc_md: Generate a table of contents markdown file
      
  Returns:
      Updated DoclingDocument with corrected section header levels and parent references
      
  Raises:
      FileNotFoundError: If the JSON file doesn't exist
      Exception: For other processing errors
  """
  setup_logging(verbose)
  logger = logging.getLogger(__name__)
  
  logger.info(f'Processing DoclingDocument from: {docling_json_path}')
  
  try:
    with open(docling_json_path, 'r', encoding='utf-8') as f:
      docling_data = json.load(f)
    
    # Infer hierarchical levels from text patterns
    updated_docling_data = infer_hierarchical_levels_from_text(docling_data)
    
    # Save updated DoclingDocument if output path provided
    if output_path:
      output_file = Path(output_path)
      output_file.write_text(
          json.dumps(updated_docling_data, indent=2, ensure_ascii=False), 
          encoding='utf-8'
      )
      logger.info('Updated DoclingDocument saved to: %s', output_file)
      
      # Generate ToC markdown if requested
      if generate_toc_md:
        toc_md_content = generate_toc_markdown(updated_docling_data)
        toc_md_path = output_file.with_suffix('.md')
        toc_md_path.write_text(toc_md_content, encoding='utf-8')
        logger.info('ToC markdown saved to: %s', toc_md_path)
    
    return updated_docling_data
    
  except Exception as e:
    logger.error('Failed to process DoclingDocument: %s', e)
    raise


def extract_pdf_toc(
    source: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    verbose: bool = False,
    output_format: Literal['json', 'text'] = 'json',
    docling_json_path: Optional[Union[str, Path]] = None,
    generate_toc_md: bool = False,
) -> Union[List[Dict[str, Any]], str, Dict[str, Any]]:
  """
  Extract table of contents from a PDF file using PyMuPDF and optionally map to DoclingDocument.

  Args:
      source: Path to PDF file or URL
      output_path: Optional output path for output file
      verbose: Enable verbose logging
      output_format: Output format - 'json' or 'text'
      docling_json_path: Optional path to DoclingDocument JSON for level mapping
      generate_toc_md: Generate a table of contents markdown file

  Returns:
      List of ToC entries (json format), formatted text string, or updated DoclingDocument

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

    # If DoclingDocument JSON path is provided, map ToC to section headers
    if docling_json_path:
      logger.info(f'Loading DoclingDocument from: {docling_json_path}')
      
      try:
        with open(docling_json_path, 'r', encoding='utf-8') as f:
          docling_data = json.load(f)
        
        # Map ToC entries to DoclingDocument section headers
        updated_docling_data = map_toc_to_docling_sections(toc_entries, docling_data)
        
        # Save updated DoclingDocument if output path provided
        if output_path:
          output_file = Path(output_path)
          output_file.write_text(
              json.dumps(updated_docling_data, indent=2, ensure_ascii=False), 
              encoding='utf-8'
          )
          logger.info('Updated DoclingDocument saved to: %s', output_file)
        
        # Generate ToC markdown if requested
        if generate_toc_md:
          toc_md_content = generate_toc_markdown(updated_docling_data)
          toc_md_path = output_file.with_suffix('.md') if output_path else Path('toc.md')
          toc_md_path.write_text(toc_md_content, encoding='utf-8')
          logger.info('ToC markdown saved to: %s', toc_md_path)
        
        return updated_docling_data
        
      except Exception as e:
        logger.error('Failed to process DoclingDocument: %s', e)
        raise

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
  %(prog)s document.pdf --docling-json document.json --output corrected_document.json --generate-toc-md
  %(prog)s --docling-json-only --docling-json document.json --output corrected_document.json --generate-toc-md
      """.strip(),
  )

  parser.add_argument('input', nargs='?', help='Input PDF file path or URL (optional if using --docling-json-only)')
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
      '--docling-json',
      '-d',
      help='Path to DoclingDocument JSON file for ToC level mapping',
  )
  parser.add_argument(
      '--docling-json-only',
      action='store_true',
      help='Process only DoclingDocument JSON file without PDF (infer levels from text patterns)',
  )
  parser.add_argument(
      '--generate-toc-md',
      action='store_true',
      help='Generate a table of contents markdown file (.md) showing section hierarchy',
  )
  parser.add_argument(
      '--verbose', '-v', action='store_true', help='Enable verbose logging'
  )

  try:
    args = parser.parse_args()

    # Handle docling-json-only mode
    if args.docling_json_only:
      if not args.docling_json:
        print('Error: --docling-json is required when using --docling-json-only', file=sys.stderr)
        sys.exit(1)
      
      # Process DoclingDocument without PDF
      content = process_docling_document_only(
          args.docling_json,
          args.output,
          args.verbose,
          args.generate_toc_md
      )
      
      # Print to stdout if no output file specified
      if not args.output:
        print(json.dumps(content, indent=2, ensure_ascii=False))
      
      return

    # Validate input for PDF processing
    if not args.input:
      print('Error: input PDF file is required unless using --docling-json-only', file=sys.stderr)
      sys.exit(1)

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
        args.input, 
        output_path, 
        args.verbose, 
        args.format,
        args.docling_json,
        args.generate_toc_md
    )

    # Print to stdout if no output file specified
    if not args.output:
      if args.docling_json:
        # If processing DoclingDocument, always output as JSON
        print(json.dumps(content, indent=2, ensure_ascii=False))
      elif args.format == 'json':
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
