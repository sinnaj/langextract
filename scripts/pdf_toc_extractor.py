#!/usr/bin/env python3
"""
PDF Table of Contents (ToC) Extraction and DoclingDocument Mapping Script

This script extracts table of contents from PDF files using PyMuPDF and maps
the ToC levels to section headers in DoclingDocument JSON files.

Usage:
    python pdf_toc_extractor.py input.pdf docling_document.json

The script will:
1. Extract ToC from the PDF
2. Map ToC headlines to DoclingDocument section headers
3. Generate a detailed mapping report
4. Create headline_fixed_doclingdocument.json with corrected hierarchical levels
5. Update parent references based on the hierarchy
6. Add a new ToC visualization to the report based on the corrected document

Example:
    python pdf_toc_extractor.py document.pdf document.json
"""

import argparse
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Tuple
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


def generate_toc_mapping_report(
    mapping_report: Dict[str, Any],
    toc_entries: List[Dict[str, Any]],
    corrected_docling_data: Dict[str, Any]
) -> str:
  """
  Generate a detailed ToC mapping report in markdown format.
  
  Args:
      mapping_report: Report data from mapping process
      toc_entries: Original ToC entries from PDF
      corrected_docling_data: Updated DoclingDocument with corrected hierarchy
      
  Returns:
      Markdown formatted report string
  """
  lines = [
    "# Table of Contents Mapping Report",
    "",
    "This report details the mapping process between PDF Table of Contents and DoclingDocument section headers.",
    ""
  ]
  
  # Section 1: Initial ToC extracted from PDF
  lines.extend([
    "## 1. Initial Table of Contents from PDF",
    ""
  ])
  
  lines.append(f"**Total ToC entries found:** {len(toc_entries)}")
  lines.append("")
  lines.append("| Level | Title | Page |")
  lines.append("|-------|-------|------|")
  
  for entry in toc_entries:
    # Escape pipe characters in titles for proper markdown table formatting
    title = entry['title'].replace('|', '\\|')
    lines.append(f"| {entry['level']} | {title} | {entry['page']} |")
  
  lines.append("")
  
  # Section 2: Mapping Issues Report
  lines.extend([
    "## 2. Mapping Issues Report",
    ""
  ])
  
  # Unmapped ToC entries
  unmapped_toc = mapping_report.get('unmapped_toc_entries', [])
  if unmapped_toc:
    lines.extend([
      f"### 2.1 PDF ToC Headlines Not Matched to DoclingDocument ({len(unmapped_toc)} entries)",
      "",
      "These ToC entries from the PDF could not be matched to any section headers in the DoclingDocument:",
      ""
    ])
    
    for i, entry in enumerate(unmapped_toc, 1):
      lines.append(f"{i}. **Level {entry['level']}**: {entry['title']} (Page {entry['page']})")
    
    lines.append("")
  else:
    lines.extend([
      "### 2.1 PDF ToC Headlines Not Matched to DoclingDocument",
      "",
      "*All PDF ToC entries were successfully matched to DoclingDocument section headers.*",
      ""
    ])
  
  # Unmapped section headers
  unmapped_sections = mapping_report.get('unmapped_section_headers', [])
  if unmapped_sections:
    lines.extend([
      f"### 2.2 DoclingDocument Section Headers Not Mapped to ToC ({len(unmapped_sections)} entries)",
      "",
      "These section headers in the DoclingDocument could not be matched to any PDF ToC entries:",
      ""
    ])
    
    for i, header in enumerate(unmapped_sections, 1):
      # Truncate long titles for readability
      title = header['text']
      if len(title) > 80:
        title = title[:77] + "..."
      lines.append(f"{i}. {title}")
    
    lines.append("")
  else:
    lines.extend([
      "### 2.2 DoclingDocument Section Headers Not Mapped to ToC",
      "",
      "*All DoclingDocument section headers were successfully mapped to PDF ToC entries.*",
      ""
    ])
  
  # Section 3: Successful Mappings
  lines.extend([
    "## 3. Successful Mappings",
    ""
  ])
  
  successful_mappings = mapping_report.get('successful_mappings', [])
  if successful_mappings:
    lines.append(f"**Total successful mappings:** {len(successful_mappings)}")
    lines.append("")
    lines.append("| ToC Level | ToC Title | Matched Section Header | Similarity |")
    lines.append("|-----------|-----------|------------------------|------------|")
    
    for mapping in successful_mappings:
      toc_entry = mapping['toc_entry']
      section_header = mapping['section_header']
      similarity = mapping['similarity']
      
      # Escape pipe characters and truncate long titles
      toc_title = toc_entry['title'].replace('|', '\\|')
      if len(toc_title) > 40:
        toc_title = toc_title[:37] + "..."
      
      section_title = section_header['text'].replace('|', '\\|')
      if len(section_title) > 40:
        section_title = section_title[:37] + "..."
      
      lines.append(f"| {toc_entry['level']} | {toc_title} | {section_title} | {similarity:.3f} |")
    
    lines.append("")
  else:
    lines.extend([
      "*No successful mappings found.*",
      ""
    ])
  
  # Section 4: Summary Statistics
  lines.extend([
    "## 4. Summary Statistics",
    ""
  ])
  
  total_toc_entries = len(toc_entries)
  total_section_headers = mapping_report.get('total_section_headers', 0)
  successful_mappings_count = len(successful_mappings)
  unmapped_toc_count = len(unmapped_toc)
  unmapped_sections_count = len(unmapped_sections)
  updated_levels_count = mapping_report.get('updated_levels_count', 0)
  unmapped_updates_count = mapping_report.get('unmapped_updates_count', 0)
  
  lines.extend([
    f"- **PDF ToC entries found:** {total_toc_entries}",
    f"- **DoclingDocument section headers:** {total_section_headers}",
    f"- **Successful mappings:** {successful_mappings_count}",
    f"- **Unmapped ToC entries:** {unmapped_toc_count}",
    f"- **Unmapped section headers:** {unmapped_sections_count}",
    f"- **Section headers with updated levels (from ToC):** {updated_levels_count}",
    f"- **Section headers with inferred levels (unmapped):** {unmapped_updates_count}",
    ""
  ])
  
  if total_toc_entries > 0:
    mapping_rate = (successful_mappings_count / total_toc_entries) * 100
    lines.append(f"- **Mapping success rate:** {mapping_rate:.1f}%")
  
  if total_section_headers > 0:
    coverage_rate = (successful_mappings_count / total_section_headers) * 100
    lines.append(f"- **Section header coverage:** {coverage_rate:.1f}%")
  
  lines.append("")
  
  # Section 5: New Table of Contents from Corrected Document
  lines.extend([
    "## 5. New Table of Contents from Corrected Document",
    "",
    "This ToC is generated from the headline_fixed_doclingdocument.json with corrected hierarchical levels:",
    "",
  ])
  
  # Generate ToC from corrected document
  corrected_toc = generate_toc_markdown(corrected_docling_data)
  # Remove the header and description from the generated ToC, keep only the list
  toc_lines = corrected_toc.split('\n')[4:]  # Skip header lines
  lines.extend(toc_lines)
  
  lines.append("")
  
  # Add generation timestamp
  from datetime import datetime
  timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
  lines.extend([
    "---",
    f"*Report generated on {timestamp}*"
  ])
  
  return "\n".join(lines)


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
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
  """
  Map ToC entries to DoclingDocument section headers and update their levels and parent references.
  
  Args:
      toc_entries: List of ToC entries with level, title, and page
      docling_data: DoclingDocument JSON data
      similarity_threshold: Minimum similarity score for matching
      
  Returns:
      Tuple of (updated DoclingDocument, mapping report data)
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
  unmapped_toc_entries = []
  used_section_indices = set()
  
  for toc_entry in toc_entries:
    toc_title = toc_entry['title']
    toc_level = toc_entry['level']
    
    best_match = None
    best_similarity = 0.0
    
    for header in section_headers:
      # Skip headers that are already matched
      if header['index'] in used_section_indices:
        continue
        
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
      used_section_indices.add(best_match['index'])
      logger.debug(f'Mapped "{toc_title}" (level {toc_level}) to "{best_match["text"]}" (similarity: {best_similarity:.3f})')
    else:
      unmapped_toc_entries.append(toc_entry)
      logger.debug(f'Could not map ToC entry "{toc_title}" (level {toc_level})')
  
  logger.info(f'Successfully mapped {len(mappings)} ToC entries to section headers')
  if unmapped_toc_entries:
    logger.info(f'{len(unmapped_toc_entries)} ToC entries could not be mapped')
  
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
  unmapped_section_headers = [h for h in section_headers if h['index'] not in mapped_indices]
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
  
  # Prepare mapping report data
  mapping_report = {
    'toc_entries': toc_entries,
    'successful_mappings': mappings,
    'unmapped_toc_entries': unmapped_toc_entries,
    'unmapped_section_headers': unmapped_section_headers,
    'total_section_headers': len(section_headers),
    'updated_levels_count': updates_count,
    'unmapped_updates_count': unmapped_updates_count
  }
  
  return updated_data, mapping_report


def extract_pdf_toc(pdf_path: str) -> List[Dict[str, Any]]:
  """
  Extract table of contents from a PDF file using PyMuPDF.

  Args:
      pdf_path: Path to PDF file

  Returns:
      List of ToC entries with level, title, and page

  Raises:
      ImportError: If PyMuPDF is not installed
      FileNotFoundError: If the PDF file doesn't exist
      Exception: For other processing errors
  """
  try:
    import fitz  # PyMuPDF
  except ImportError as e:
    raise ImportError(
        'PyMuPDF (fitz) is required for PDF ToC extraction. '
        "Install with: pip install 'langextract[pymupdf]'"
    ) from e

  logger = logging.getLogger(__name__)
  logger.info('Extracting ToC from: %s', pdf_path)

  try:
    # Open the PDF document
    doc = fitz.open(pdf_path)

    # Extract table of contents
    toc = doc.get_toc()

    # Close the document
    doc.close()

    logger.info('Successfully extracted ToC with %d entries', len(toc))

    if not toc:
      logger.warning('No table of contents found in the PDF')

    # Convert to structured format
    toc_entries = []
    for level, title, page in toc:
      toc_entries.append({'level': level, 'title': title.strip(), 'page': page})

    return toc_entries

  except Exception as e:
    logger.error('Failed to extract ToC: %s', e)
    raise


def process_pdf_and_docling(pdf_path: str, docling_json_path: str) -> None:
  """
  Main processing function for the PDF ToC extractor use case.
  
  This function:
  1. Extracts ToC from PDF
  2. Maps ToC headlines to DoclingDocument section headers  
  3. Generates a mapping report
  4. Creates headline_fixed_doclingdocument.json with updated levels
  5. Updates parent references based on hierarchy
  6. Adds new ToC visualization to the report
  
  Args:
      pdf_path: Path to PDF file
      docling_json_path: Path to DoclingDocument JSON file
  """
  logger = logging.getLogger(__name__)
  
  try:
    # Step 1: Extract ToC from PDF
    logger.info('Step 1: Extracting ToC from PDF...')
    toc_entries = extract_pdf_toc(pdf_path)
    
    # Step 2: Load DoclingDocument
    logger.info('Step 2: Loading DoclingDocument...')
    with open(docling_json_path, 'r', encoding='utf-8') as f:
      docling_data = json.load(f)
    
    # Step 3: Map ToC to DoclingDocument section headers
    logger.info('Step 3: Mapping ToC to DoclingDocument section headers...')
    updated_docling_data, mapping_report = map_toc_to_docling_sections(toc_entries, docling_data)
    
    # Step 4: Save headline_fixed_doclingdocument.json
    logger.info('Step 4: Saving corrected DoclingDocument...')
    output_json_path = Path(docling_json_path).with_name('headline_fixed_doclingdocument.json')
    output_json_path.write_text(
        json.dumps(updated_docling_data, indent=2, ensure_ascii=False), 
        encoding='utf-8'
    )
    logger.info('Corrected DoclingDocument saved to: %s', output_json_path)
    
    # Step 5: Generate comprehensive report
    logger.info('Step 5: Generating mapping report...')
    report_content = generate_toc_mapping_report(mapping_report, toc_entries, updated_docling_data)
    report_path = Path(docling_json_path).with_name('report.md')
    report_path.write_text(report_content, encoding='utf-8')
    logger.info('Mapping report saved to: %s', report_path)
    
    logger.info('Processing completed successfully!')
    
  except Exception as e:
    logger.error('Processing failed: %s', e)
    raise


def main() -> None:
  """Main command-line interface."""
  parser = argparse.ArgumentParser(
      description='Extract PDF ToC and map to DoclingDocument section headers',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
Example:
  %(prog)s document.pdf document.json
  
This will:
  1. Extract ToC from document.pdf
  2. Map ToC headlines to section headers in document.json
  3. Create headline_fixed_doclingdocument.json with corrected levels
  4. Generate report.md with mapping analysis and new ToC
      """.strip(),
  )

  parser.add_argument('pdf_file', help='Input PDF file path')
  parser.add_argument('docling_json', help='DoclingDocument JSON file path')
  parser.add_argument(
      '--verbose', '-v', action='store_true', help='Enable verbose logging'
  )

  try:
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.verbose)
    
    # Validate input files exist
    pdf_path = Path(args.pdf_file)
    json_path = Path(args.docling_json)
    
    if not pdf_path.exists():
      print(f'Error: PDF file not found: {pdf_path}', file=sys.stderr)
      sys.exit(1)
      
    if not json_path.exists():
      print(f'Error: DoclingDocument JSON file not found: {json_path}', file=sys.stderr)
      sys.exit(1)
    
    # Process the files
    process_pdf_and_docling(str(pdf_path), str(json_path))

  except ImportError as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    print(f'Processing failed: {e}', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()
