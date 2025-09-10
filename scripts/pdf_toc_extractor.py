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

# Regex pattern for numbering detection  
RE_NUM = re.compile(r'^(?P<head>([A-Z].)?\d+(?:.\d+){0,5})\b')


def setup_logging(verbose: bool = False) -> None:
  """Set up logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )


def normalize_text(text: str) -> str:
  """
  Stronger text normalization for better canonicalization.
  Handles accents, OCR spacing issues, punctuation variations.
  
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
  
  # Remove common OCR artifacts and punctuation
  # Remove extra spaces around punctuation
  text_clean = re.sub(r'\s*([.,;:!?])\s*', r'\1 ', ascii_text)
  
  # Normalize common OCR spacing issues (e.g., "D ocumento B ásico" -> "Documento Basico")
  text_clean = re.sub(r'(?<=[a-zA-Z])\s+(?=[a-zA-Z])', '', text_clean)
  
  # Remove special characters but keep alphanumeric and basic punctuation
  text_clean = re.sub(r'[^\w\s.,;:!?()\-/]', '', text_clean)
  
  # Normalize multiple spaces and convert to lowercase
  text_clean = re.sub(r'\s+', ' ', text_clean.lower()).strip()
  
  # Remove leading/trailing punctuation
  text_clean = re.sub(r'^[.,;:!?\-\s]+|[.,;:!?\-\s]+$', '', text_clean)
  
  return text_clean


def normalize_text_for_matching(text: str) -> str:
  """
  Enhanced text normalization specifically for ToC-to-section matching.
  Handles footnote references like "(1)" or "( 1 )" better than standard normalization.
  Also handles empty parentheses "( )" which can appear in ToC entries.
  Enhanced to handle invisible characters and various Unicode parentheses.
  
  Args:
      text: Text to normalize
      
  Returns:
      Normalized text string optimized for matching
  """
  # First, handle various Unicode parentheses and invisible characters
  # Replace various Unicode parentheses with standard ones
  text_clean = text.replace('（', '(').replace('）', ')')
  text_clean = text_clean.replace('❨', '(').replace('❩', ')')
  
  # Remove zero-width characters and other invisible characters
  text_clean = ''.join(char for char in text_clean if ord(char) not in [0x200B, 0x200C, 0x200D, 0xFEFF])
  
  # Remove footnote references with various patterns:
  # - (1), ( 1 ), (1 ), ( ), (), etc. - numbered footnotes and empty parentheses
  # - Handle any whitespace including non-breaking spaces
  text_clean = re.sub(r'\(\s*\d*\s*\)', '', text_clean).strip()
  
  # Also handle other common footnote patterns
  text_clean = re.sub(r'\(\s*[a-zA-Z]\s*\)', '', text_clean).strip()  # (a), (b), etc.
  
  # Handle parentheses with special characters or symbols
  text_clean = re.sub(r'\(\s*[^\w\s]*\s*\)', '', text_clean).strip()
  
  # Clean up any double spaces that might result
  text_clean = re.sub(r'\s+', ' ', text_clean).strip()
  
  # Now apply standard normalization
  normalized = normalize_text(text_clean)
  
  # Additional cleanup for better matching - remove spaces around dots and numbers
  normalized = re.sub(r'\s*\.\s*', '', normalized)  # Remove dots and surrounding spaces completely
  normalized = re.sub(r'\s+', '', normalized)  # Remove all remaining spaces for better matching
  
  return normalized


def numbering_key(text: str) -> Tuple[str, int]:
  """
  Extract numbering prefix and depth from text for sibling level detection.
  Returns (prefix, depth) for use in keeping siblings flat.
  
  Args:
      text: Text to analyze for numbering patterns
      
  Returns:
      Tuple of (prefix, depth) where prefix is the numbering stem and depth is nesting level
  """
  # Use original text, not normalized (to preserve dots)
  m = RE_NUM.match(text.strip())
  if not m:
    return ("", 0)
  head = m.group('head')  # e.g. "E.2.3.2.1" or "11.2.3"
  depth = head.count('.') + 1
  prefix = head.rsplit('.', 1)[0] if '.' in head else head
  return (prefix, depth)


def build_toc_intervals(toc_entries: List[Dict[str, Any]], total_pages: int = 1000) -> List[Dict[str, Any]]:
  """
  Build ToC parent pointers + intervals.
  Enhance build_toc_intervals to compute id, parent_idx, start_page, end_page.
  
  Args:
      toc_entries: List of ToC entries with level, title, and page
      total_pages: Total number of pages in the document (for last entry)
      
  Returns:
      List of ToC entries with added id, parent_idx, start_page and end_page fields
  """
  if not toc_entries:
    return []
  
  # Create a copy to avoid modifying original data
  import copy
  entries = copy.deepcopy(toc_entries)
  entries.sort(key=lambda x: (x['page'], x['level']))
  
  # Parent via level stack
  stack = []  # (idx, level)
  for i, e in enumerate(entries):
    e['id'] = i
    while stack and stack[-1][1] >= e['level']:
      stack.pop()
    e['parent_idx'] = stack[-1][0] if stack else None
    stack.append((i, e['level']))
  
  # Intervals
  for i, e in enumerate(entries):
    e['start_page'] = e['page']
    end_page = total_pages
    for j in range(i + 1, len(entries)):
      if entries[j]['level'] <= e['level']:
        end_page = entries[j]['page'] - 1
        break
    e['end_page'] = max(e['start_page'], end_page)
    
  return entries


def extract_docling_element_page(text_item: Dict[str, Any]) -> int:
  """
  Extract page number from DoclingDocument text element.
  
  Args:
      text_item: DoclingDocument text element
      
  Returns:
      Page number (1-based) or 0 if not found
  """
  prov = text_item.get('prov', [])
  if prov and isinstance(prov, list) and len(prov) > 0:
    first_prov = prov[0]
    if isinstance(first_prov, dict) and 'page_no' in first_prov:
      return first_prov['page_no']
  return 0


def detect_auxiliary_content(text: str) -> Dict[str, Any]:
  """
  Detect auxiliary/non-heading content like tables, equations, captions.
  
  Args:
      text: Text content to analyze
      
  Returns:
      Dict with detection results: {
        'is_auxiliary': bool,
        'type': str,  # 'table', 'equation', 'caption', 'list', etc.
        'confidence': float
      }
  """
  text_lower = text.lower().strip()
  
  # Table indicators
  table_patterns = [
    r'\btabla\b.*\d+',  # "Tabla 1", "Tabla A.1"
    r'\btable\b.*\d+',
    r'^\d+[\.\-\s]*\d*[\.\-\s]*\d*$',  # Numeric table cells
    r'^[a-z]\s*\)\s*',  # List items like "a) ", "b) "
  ]
  
  # Equation indicators  
  equation_patterns = [
    r'\bfórmula\b.*\d+',  # "Fórmula 1"
    r'\becuación\b.*\d+',  # "Ecuación 1"
    r'^[a-zA-Z]\s*=\s*',  # Variable assignments
    r'^\s*[\(\[].*[=<>±∞∑∏∫].*[\)\]]\s*$',  # Mathematical expressions with operators
    r'^\s*[a-zA-Z]\s*[\(\[].*\d+[\.\d]*.*[\)\]]\s*$',  # Variable with parenthetical value (whole line)
  ]
  
  # Caption indicators
  caption_patterns = [
    r'\bfigura\b.*\d+',  # "Figura 1"
    r'\bfig\.\s*\d+',
    r'\bimagen\b.*\d+',
    r'^\s*fuente:',  # Source attributions
  ]
  
  # List item indicators
  list_patterns = [
    r'^\s*[\-\*\•]\s+',  # Bullet points
    r'^\s*\d+[\.\)\-]\s+',  # Numbered lists
    r'^\s*[a-zA-Z][\.\)]\s+',  # Lettered lists
  ]
  
  # Check patterns
  for pattern in table_patterns:
    if re.search(pattern, text_lower):
      return {'is_auxiliary': True, 'type': 'table', 'confidence': 0.8}
  
  for pattern in equation_patterns:
    if re.search(pattern, text_lower):
      return {'is_auxiliary': True, 'type': 'equation', 'confidence': 0.8}
  
  for pattern in caption_patterns:
    if re.search(pattern, text_lower):
      return {'is_auxiliary': True, 'type': 'caption', 'confidence': 0.9}
  
  for pattern in list_patterns:
    if re.search(pattern, text_lower):
      return {'is_auxiliary': True, 'type': 'list', 'confidence': 0.7}
  
  # Additional heuristics
  if len(text.strip()) < 3:
    return {'is_auxiliary': True, 'type': 'fragment', 'confidence': 0.9}
  
  # Check if it's mostly numbers or symbols
  non_alpha_ratio = len(re.sub(r'[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ\s]', '', text)) / max(len(text), 1)
  if non_alpha_ratio > 0.5:
    return {'is_auxiliary': True, 'type': 'technical', 'confidence': 0.6}
  
  return {'is_auxiliary': False, 'type': 'heading', 'confidence': 0.8}


def split_combined_headings(text: str) -> List[str]:
  """
  Split combined headings like "Anejo SI A ... Anejo SI B ..." into multiple headings.
  
  Args:
      text: Text that might contain multiple combined headings
      
  Returns:
      List of individual headings
  """
  # Look for patterns that indicate combined headings
  combined_patterns = [
    # "Anejo SI A ... Anejo SI B ..."
    r'(Anejo\s+SI\s+[A-Z]\s+[^.]*?)(?=\s+Anejo\s+SI\s+[A-Z])',
    # "Sección SI 1 ... Sección SI 2 ..."  
    r'(Sección\s+SI\s+\d+\s+[^.]*?)(?=\s+Sección\s+SI\s+\d+)',
    # General pattern for repeated structures
    r'(\d+(?:\.\d+)*\s+[^.]*?)(?=\s+\d+(?:\.\d+)*\s+)',
  ]
  
  text = text.strip()
  split_headings = []
  
  for pattern in combined_patterns:
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    if matches:
      # Extract all matched parts
      for match in matches:
        heading = match.group(1).strip()
        if heading and len(heading) > 3:
          split_headings.append(heading)
      
      # Get the remaining part after the last match
      last_match = matches[-1]
      remaining = text[last_match.end():].strip()
      if remaining and len(remaining) > 3:
        split_headings.append(remaining)
      
      # If we found splits, return them
      if len(split_headings) > 1:
        return split_headings
  
  # No splitting patterns found, return original text
  return [text] if text else []


def detect_and_merge_split_headlines(
    toc_entries: List[Dict[str, Any]], 
    docling_sections: List[Dict[str, Any]],
    docling_data: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
  """
  Detect when Docling incorrectly splits headlines and merge them.
  
  Sometimes Docling splits a single headline from the ToC into multiple consecutive 
  section headers. This function detects such cases and merges them.
  
  Args:
      toc_entries: List of ToC entries with intervals
      docling_sections: List of DoclingDocument section headers
      docling_data: Full DoclingDocument data (to update the actual text elements)
      
  Returns:
      Updated list of DoclingDocument sections with merged headlines
  """
  logger = logging.getLogger(__name__)
  
  if not toc_entries or not docling_sections:
    return docling_sections
  
  # Create a copy to avoid modifying the original
  import copy
  sections = copy.deepcopy(docling_sections)
  
  # Sort sections by page and then by position on page (using bbox if available)
  sections.sort(key=lambda s: (s.get('page', 0), s.get('index', 0)))
  
  merged_count = 0
  indices_to_remove = set()
  
  # For each ToC entry, check if there are consecutive DoclingDocument sections
  # on the same page that together might form the complete ToC title
  for toc_entry in toc_entries:
    toc_title = toc_entry['title']
    toc_page = toc_entry['page']
    toc_normalized = normalize_text_for_matching(toc_title)
    
    # Find all sections on this page
    page_sections = [s for s in sections if s.get('page') == toc_page]
    
    if len(page_sections) < 2:
      continue
    
    # Look for consecutive sections that might be parts of the same headline
    for i in range(len(page_sections) - 1):
      if page_sections[i]['index'] in indices_to_remove:
        continue
        
      current_section = page_sections[i]
      next_section = page_sections[i + 1]
      
      # Check if current section is similar to start of ToC entry
      current_text = current_section['text']
      current_normalized = normalize_text_for_matching(current_text)
      
      # Skip if current section already matches the ToC entry well
      if calculate_text_similarity(current_normalized, toc_normalized) > 0.8:
        continue
      
      # Try merging current and next section
      combined_text = f"{current_text} {next_section['text']}".strip()
      combined_normalized = normalize_text_for_matching(combined_text)
      
      # Check if merged text matches ToC entry better than individual parts
      combined_similarity = calculate_text_similarity(combined_normalized, toc_normalized)
      current_similarity = calculate_text_similarity(current_normalized, toc_normalized)
      next_similarity = calculate_text_similarity(
        normalize_text_for_matching(next_section['text']), toc_normalized
      )
      
      # If combined similarity is significantly better, merge them
      if (combined_similarity > 0.7 and 
          combined_similarity > current_similarity + 0.2 and
          combined_similarity > next_similarity + 0.2):
        
        logger.info(f'Merging split headlines on page {toc_page}:')
        logger.info(f'  Part 1: "{current_text}"')
        logger.info(f'  Part 2: "{next_section["text"]}"')
        logger.info(f'  Combined: "{combined_text}"')
        logger.info(f'  ToC target: "{toc_title}"')
        logger.info(f'  Similarity improvement: {current_similarity:.3f} -> {combined_similarity:.3f}')
        
        # Update the current section with merged text
        current_section['text'] = combined_text
        current_section['merged_from'] = [current_section['index'], next_section['index']]
        
        # Update the DoclingDocument data if provided
        if docling_data is not None:
          texts = docling_data.get('texts', [])
          if current_section['index'] < len(texts):
            texts[current_section['index']]['text'] = combined_text
            texts[current_section['index']]['merged_from'] = current_section['merged_from']
        
        # Mark the next section for removal
        indices_to_remove.add(next_section['index'])
        merged_count += 1
        
        # Try to extend the merge to include more consecutive sections
        j = i + 2
        while j < len(page_sections):
          if page_sections[j]['index'] in indices_to_remove:
            j += 1
            continue
            
          extended_text = f"{combined_text} {page_sections[j]['text']}".strip()
          extended_normalized = normalize_text_for_matching(extended_text)
          extended_similarity = calculate_text_similarity(extended_normalized, toc_normalized)
          
          if extended_similarity > combined_similarity + 0.1:
            logger.info(f'  Extended merge with: "{page_sections[j]["text"]}"')
            combined_text = extended_text
            combined_similarity = extended_similarity
            current_section['text'] = combined_text
            current_section['merged_from'].append(page_sections[j]['index'])
            indices_to_remove.add(page_sections[j]['index'])
            
            # Update DoclingDocument data for extended merge
            if docling_data is not None:
              texts = docling_data.get('texts', [])
              if current_section['index'] < len(texts):
                texts[current_section['index']]['text'] = combined_text
                texts[current_section['index']]['merged_from'] = current_section['merged_from']
            
            j += 1
          else:
            break
        
        break  # Move to next ToC entry
  
  # Remove sections that were merged into others
  sections_filtered = [s for s in sections if s['index'] not in indices_to_remove]
  
  # Also update the DoclingDocument data to remove/demote merged sections
  if docling_data is not None and indices_to_remove:
    texts = docling_data.get('texts', [])
    for index in indices_to_remove:
      if index < len(texts) and texts[index].get('label') == 'section_header':
        # Convert merged sections to regular text instead of removing them entirely
        # This preserves the content but removes them from the section hierarchy
        texts[index]['label'] = 'text'  # Demote from section_header to text
        texts[index]['merged_into'] = True  # Mark as merged
        logger.debug(f'Demoted merged section at index {index}: "{texts[index].get("text", "")[:50]}..."')
  
  if merged_count > 0:
    logger.info(f'Successfully merged {merged_count} split headlines')
  
  return sections_filtered


def scan_page_for_text_matches(
    page_number: int,
    docling_data: Dict[str, Any],
    target_text: str,
    similarity_threshold: float = 0.6
) -> List[Dict[str, Any]]:
  """
  Scan all text elements on a specific page for matches, including table cells.
  This addresses the issue where some headlines are identified as table elements.
  
  Args:
      page_number: Page number to scan
      docling_data: DoclingDocument data
      target_text: Text to match against
      similarity_threshold: Minimum similarity score to consider a match
      
  Returns:
      List of potential matches with similarity scores and element info
  """
  logger = logging.getLogger(__name__)
  matches = []
  
  # Get all texts elements
  texts = docling_data.get('texts', [])
  tables = docling_data.get('tables', [])
  
  target_normalized = normalize_text_for_matching(target_text)
  
  # Scan text elements
  for i, text_item in enumerate(texts):
    if extract_docling_element_page(text_item) != page_number:
      continue
      
    text_content = text_item.get('text', '').strip()
    if not text_content:
      continue
      
    # Try matching with enhanced normalization
    content_normalized = normalize_text_for_matching(text_content)
    similarity = calculate_text_similarity(target_normalized, content_normalized)
    
    if similarity >= similarity_threshold:
      matches.append({
        'type': 'text',
        'index': i,
        'text': text_content,
        'similarity': similarity,
        'label': text_item.get('label', 'unknown'),
        'page': page_number,
        'element': text_item
      })
      logger.debug(f'Page scan found text match: "{text_content[:50]}..." (sim={similarity:.3f})')
  
  # Scan table cells
  for table_idx, table in enumerate(tables):
    if extract_docling_element_page(table) != page_number:
      continue
      
    table_data = table.get('data', {})
    table_cells = table_data.get('table_cells', [])
    
    for cell in table_cells:
      cell_text = cell.get('text', '').strip()
      if not cell_text:
        continue
        
      # Try matching with enhanced normalization
      cell_normalized = normalize_text_for_matching(cell_text)
      similarity = calculate_text_similarity(target_normalized, cell_normalized)
      
      if similarity >= similarity_threshold:
        matches.append({
          'type': 'table_cell',
          'table_index': table_idx,
          'text': cell_text,
          'similarity': similarity,
          'label': 'table_cell',
          'page': page_number,
          'element': table,
          'cell_data': cell
        })
        logger.debug(f'Page scan found table cell match: "{cell_text[:50]}..." (sim={similarity:.3f})')
  
  # Sort by similarity (highest first)
  matches.sort(key=lambda x: x['similarity'], reverse=True)
  
  logger.debug(f'Page {page_number} scan found {len(matches)} potential matches for "{target_text[:30]}..."')
  return matches


def calculate_text_similarity(text1: str, text2: str) -> float:
  """
  Calculate similarity between two text strings using multiple approaches.
  Uses enhanced normalization for better matching of footnoted text.
  
  Args:
      text1: First text string
      text2: Second text string
      
  Returns:
      Similarity score between 0.0 and 1.0
  """
  # Try both standard normalization and enhanced normalization for matching
  norm1 = normalize_text(text1)
  norm2 = normalize_text(text2)
  
  # Also try enhanced normalization for footnotes
  norm1_enhanced = normalize_text_for_matching(text1) 
  norm2_enhanced = normalize_text_for_matching(text2)
  
  # Use the better of the two normalization approaches
  if norm1 == norm2:
    return 1.0
  if norm1_enhanced == norm2_enhanced:
    return 1.0
  
  # Calculate Jaccard similarity with both approaches and take the maximum
  def jaccard_similarity(text_a: str, text_b: str) -> float:
    tokens1 = set(text_a.split())
    tokens2 = set(text_b.split())
    
    if not tokens1 and not tokens2:
      return 1.0
    if not tokens1 or not tokens2:
      return 0.0
    
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union) if union else 0.0
  
  # Try both normalization approaches
  jaccard_sim1 = jaccard_similarity(norm1, norm2)
  jaccard_sim2 = jaccard_similarity(norm1_enhanced, norm2_enhanced)
  jaccard_sim = max(jaccard_sim1, jaccard_sim2)
  
  # Add substring similarity bonus
  if (norm1 in norm2 or norm2 in norm1) or (norm1_enhanced in norm2_enhanced or norm2_enhanced in norm1_enhanced):
    jaccard_sim = max(jaccard_sim, 0.7)
  
  # Add structural similarity for numbered sections
  for n1, n2 in [(norm1, norm2), (norm1_enhanced, norm2_enhanced)]:
    if re.search(r'\d+', n1) and re.search(r'\d+', n2):
      nums1 = re.findall(r'\d+', n1) 
      nums2 = re.findall(r'\d+', n2)
      if nums1 and nums2 and nums1[0] == nums2[0]:
        jaccard_sim = max(jaccard_sim, 0.6)
        break
  
  return jaccard_sim


def calculate_enhanced_similarity(
    toc_title: str, 
    section_text: str, 
    toc_page: int, 
    section_page: int,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
  """
  Calculate enhanced similarity with confidence scoring and context awareness.
  
  Args:
      toc_title: ToC entry title
      section_text: DoclingDocument section header text
      toc_page: ToC entry page number
      section_page: Section header page number
      context: Additional context for similarity calculation
      
  Returns:
      Dict with similarity score, confidence, and matching details
  """
  if context is None:
    context = {}
  
  # Base text similarity
  text_sim = calculate_text_similarity(toc_title, section_text)
  
  # Page proximity bonus/penalty
  page_distance = abs(toc_page - section_page) if section_page > 0 else 0
  page_factor = 1.0
  if section_page > 0:
    if page_distance == 0:
      page_factor = 1.2  # Same page bonus
    elif page_distance <= 2:
      page_factor = 1.1  # Close page bonus
    elif page_distance > 10:
      page_factor = 0.8  # Far page penalty
  
  # Structural matching bonuses
  structure_bonus = 0.0
  
  # Exact structural patterns (e.g., "SI 1", "SI 2")
  toc_numbers = re.findall(r'SI\s+\d+|Sección\s+\d+|Anejo\s+[A-Z]|\d+(?:\.\d+)*', toc_title, re.IGNORECASE)
  section_numbers = re.findall(r'SI\s+\d+|Sección\s+\d+|Anejo\s+[A-Z]|\d+(?:\.\d+)*', section_text, re.IGNORECASE)
  
  if toc_numbers and section_numbers:
    for toc_num in toc_numbers:
      for sec_num in section_numbers:
        # Use enhanced normalization for structural comparison
        if normalize_text_for_matching(toc_num) == normalize_text_for_matching(sec_num):
          structure_bonus = 0.3
          break
      if structure_bonus > 0:
        break
  
  # Calculate final similarity
  final_similarity = min(1.0, (text_sim * page_factor) + structure_bonus)
  
  # Confidence calculation
  confidence = 0.5  # Base confidence
  
  if text_sim > 0.8:
    confidence += 0.3
  elif text_sim > 0.6:
    confidence += 0.2
  elif text_sim > 0.4:
    confidence += 0.1
  
  if page_distance <= 1:
    confidence += 0.2
  elif page_distance <= 5:
    confidence += 0.1
  
  if structure_bonus > 0:
    confidence += 0.2
  
  confidence = min(1.0, confidence)
  
  return {
    'similarity': final_similarity,
    'confidence': confidence,
    'text_similarity': text_sim,
    'page_distance': page_distance,
    'structure_bonus': structure_bonus,
    'match_type': 'exact' if text_sim > 0.9 else 'structural' if structure_bonus > 0 else 'fuzzy'
  }


def multi_pass_mapping(
    toc_entries_with_intervals: List[Dict[str, Any]], 
    docling_sections: List[Dict[str, Any]],
    docling_data: Dict[str, Any] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
  """
  Perform multi-pass mapping with four strategies: exact/near, structured/numbered, fuzzy+context, page scanning.
  Remember which ToC node each section matched by storing toc_idx.
  
  Args:
      toc_entries_with_intervals: ToC entries with page intervals
      docling_sections: DoclingDocument section headers with page info
      docling_data: Full DoclingDocument data (for page scanning)
      
  Returns:
      Tuple of (successful_mappings, unmapped_toc_entries, unmapped_sections)
  """
  logger = logging.getLogger(__name__)
  
  mappings = []
  used_section_indices = set()
  used_toc_indices = set()
  
  # Pass 1: Exact and near-exact matches
  logger.info('Pass 1: Exact and near-exact matches')
  for i, toc_entry in enumerate(toc_entries_with_intervals):
    if i in used_toc_indices:
      continue
      
    for j, section in enumerate(docling_sections):
      if j in used_section_indices:
        continue
      
      # Check if section page is within ToC interval
      section_page = section.get('page', 0)
      if section_page < toc_entry['start_page'] or section_page > toc_entry['end_page']:
        continue
      
      sim_result = calculate_enhanced_similarity(
        toc_entry['title'], 
        section['text'], 
        toc_entry['page'], 
        section_page
      )
      
      # High threshold for exact matches
      if sim_result['similarity'] > 0.85 and sim_result['confidence'] > 0.7:
        mappings.append({
          'toc_entry': toc_entry,
          'toc_idx': i,  # <— add this
          'section_header': section,
          'similarity_info': sim_result,
          'pass': 1
        })
        used_toc_indices.add(i)
        used_section_indices.add(j)
        logger.debug(f'Pass 1 match: "{toc_entry["title"]}" -> "{section["text"]}" (sim={sim_result["similarity"]:.3f})')
        break
  
  # Pass 2: Structural and numbered matches
  logger.info('Pass 2: Structural and numbered matches')
  for i, toc_entry in enumerate(toc_entries_with_intervals):
    if i in used_toc_indices:
      continue
      
    for j, section in enumerate(docling_sections):
      if j in used_section_indices:
        continue
      
      # Check if section page is within ToC interval
      section_page = section.get('page', 0)
      if section_page < toc_entry['start_page'] or section_page > toc_entry['end_page']:
        continue
      
      sim_result = calculate_enhanced_similarity(
        toc_entry['title'], 
        section['text'], 
        toc_entry['page'], 
        section_page
      )
      
      # Medium threshold with structural bonus
      if (sim_result['similarity'] > 0.6 and sim_result['structure_bonus'] > 0) or \
         (sim_result['similarity'] > 0.7 and sim_result['confidence'] > 0.6):
        mappings.append({
          'toc_entry': toc_entry,
          'toc_idx': i,  # <— add this
          'section_header': section,
          'similarity_info': sim_result,
          'pass': 2
        })
        used_toc_indices.add(i)
        used_section_indices.add(j)
        logger.debug(f'Pass 2 match: "{toc_entry["title"]}" -> "{section["text"]}" (sim={sim_result["similarity"]:.3f})')
        break
  
  # Pass 3: Fuzzy matching with context
  logger.info('Pass 3: Fuzzy matching with context')
  for i, toc_entry in enumerate(toc_entries_with_intervals):
    if i in used_toc_indices:
      continue
      
    best_match = None
    best_score = 0
    
    for j, section in enumerate(docling_sections):
      if j in used_section_indices:
        continue
      
      # Check if section page is within ToC interval
      section_page = section.get('page', 0)
      if section_page < toc_entry['start_page'] or section_page > toc_entry['end_page']:
        continue
      
      sim_result = calculate_enhanced_similarity(
        toc_entry['title'], 
        section['text'], 
        toc_entry['page'], 
        section_page
      )
      
      # Lower threshold for fuzzy matches
      if sim_result['similarity'] > 0.4 and sim_result['confidence'] > 0.5:
        if sim_result['similarity'] > best_score:
          best_score = sim_result['similarity']
          best_match = {
            'toc_entry': toc_entry,
            'toc_idx': i,  # <— add this
            'section_header': section,
            'similarity_info': sim_result,
            'pass': 3,
            'section_index': j
          }
    
    if best_match:
      mappings.append(best_match)
      used_toc_indices.add(i)
      used_section_indices.add(best_match['section_index'])
      logger.debug(f'Pass 3 match: "{toc_entry["title"]}" -> "{best_match["section_header"]["text"]}" (sim={best_score:.3f})')
  
  # Pass 4: Page scanning for unmapped ToC entries (including table cells)
  if docling_data is not None:
    logger.info('Pass 4: Page scanning for unmapped ToC entries')
    for i, toc_entry in enumerate(toc_entries_with_intervals):
      if i in used_toc_indices:
        continue
        
      # Scan the ToC entry's page for potential matches
      toc_page = toc_entry['page']
      page_matches = scan_page_for_text_matches(
        toc_page, 
        docling_data, 
        toc_entry['title'], 
        similarity_threshold=0.6
      )
      
      # Look for the best match that isn't already used
      best_page_match = None
      best_page_score = 0
      
      for match in page_matches:
        if match['type'] == 'text':
          # Check if this text element corresponds to any docling_sections entry
          text_index = match['index']
          section_match = next((s for s in docling_sections if s['index'] == text_index), None)
          if section_match and docling_sections.index(section_match) not in used_section_indices:
            if match['similarity'] > best_page_score:
              best_page_score = match['similarity']
              best_page_match = {
                'toc_entry': toc_entry,
                'toc_idx': i,
                'section_header': section_match,
                'similarity_info': {
                  'similarity': match['similarity'],
                  'confidence': 0.7 if match['similarity'] > 0.8 else 0.6,
                  'text_similarity': match['similarity'],
                  'page_distance': 0,
                  'structure_bonus': 0.0,
                  'match_type': 'page_scan'
                },
                'pass': 4,
                'section_index': docling_sections.index(section_match),
                'page_scan_match': match
              }
        elif match['type'] == 'table_cell':
          # For table cells, we need to create a synthetic section header
          # This addresses the issue where headlines are in table cells
          if match['similarity'] > best_page_score:
            best_page_score = match['similarity']
            # Create a synthetic section header from the table cell
            synthetic_section = {
              'index': f"table_{match['table_index']}_cell",
              'text': match['text'],
              'original_level': 1,  # Default level, will be updated
              'page': match['page'],
              'synthetic': True,  # Mark as synthetic
              'source_table_index': match['table_index'],
              'source_cell_data': match['cell_data']
            }
            best_page_match = {
              'toc_entry': toc_entry,
              'toc_idx': i,
              'section_header': synthetic_section,
              'similarity_info': {
                'similarity': match['similarity'],
                'confidence': 0.6,  # Lower confidence for table cell matches
                'text_similarity': match['similarity'],
                'page_distance': 0,
                'structure_bonus': 0.0,
                'match_type': 'table_cell_scan'
              },
              'pass': 4,
              'section_index': f"synthetic_{len(mappings)}",  # Synthetic index
              'page_scan_match': match
            }
      
      if best_page_match:
        mappings.append(best_page_match)
        used_toc_indices.add(i)
        if isinstance(best_page_match['section_index'], int):
          used_section_indices.add(best_page_match['section_index'])
        logger.debug(f'Pass 4 page scan match: "{toc_entry["title"]}" -> "{best_page_match["section_header"]["text"]}" (sim={best_page_score:.3f}, type={best_page_match["similarity_info"]["match_type"]})')
  
  # Collect unmapped entries
  unmapped_toc_entries = [toc_entries_with_intervals[i] for i in range(len(toc_entries_with_intervals)) if i not in used_toc_indices]
  unmapped_sections = [docling_sections[j] for j in range(len(docling_sections)) if j not in used_section_indices]
  
  logger.info(f'Multi-pass mapping complete: {len(mappings)} matches, {len(unmapped_toc_entries)} unmapped ToC, {len(unmapped_sections)} unmapped sections')
  
  return mappings, unmapped_toc_entries, unmapped_sections


def find_deepest_toc_ancestor(
    section_page: int, 
    toc_entries_with_intervals: List[Dict[str, Any]]
) -> Dict[str, Any]:
  """
  Find the deepest ToC ancestor whose interval contains the given page.
  
  Args:
      section_page: Page number of the section
      toc_entries_with_intervals: ToC entries with page intervals
      
  Returns:
      ToC entry that should be the parent, or None if no containing interval found
  """
  if section_page <= 0:
    return None
  
  # Find all ToC entries that contain this page
  containing_entries = []
  for entry in toc_entries_with_intervals:
    if entry['start_page'] <= section_page <= entry['end_page']:
      containing_entries.append(entry)
  
  if not containing_entries:
    return None
  
  # Return the entry with the highest level (deepest in hierarchy)
  # Higher level number means deeper nesting
  return max(containing_entries, key=lambda x: x['level'])


def page_driven_parenting(
    mappings: List[Dict[str, Any]], 
    toc_entries: List[Dict[str, Any]],
    docling_data: Dict[str, Any]
) -> Dict[str, Any]:
  """
  Rework parenting to use ToC ancestry (not "previous section").
  Replace the core logic with ToC ancestry-based parenting.
  
  Args:
      mappings: Successful ToC-to-section mappings
      toc_entries: ToC entries with parent pointers and intervals
      docling_data: DoclingDocument data to update
      
  Returns:
      Updated DoclingDocument with corrected parent references
  """
  logger = logging.getLogger(__name__)
  
  import copy
  updated = copy.deepcopy(docling_data)
  texts = updated.get('texts', [])
  
  # Map: ToC idx -> doc idx (for mapped headings)
  toc_idx_to_doc_idx = {m['toc_idx']: m['section_header']['index'] for m in mappings}
  
  def nearest_mapped_toc_ancestor_doc_idx(toc_idx):
    """Climb ToC parents until we find a mapped ancestor"""
    p = toc_entries[toc_idx].get('parent_idx')
    while p is not None:
      if p in toc_idx_to_doc_idx:
        return toc_idx_to_doc_idx[p]
      p = toc_entries[p].get('parent_idx')
    return None
  
  # 1) For mapped nodes: parent to their true ToC parent (or #/body if none)
  for m in mappings:
    doc_idx = m['section_header']['index']
    toc_idx = m['toc_idx']
    parent_doc_idx = nearest_mapped_toc_ancestor_doc_idx(toc_idx)
    parent_ref = "#/body" if parent_doc_idx is None else f"#/texts/{parent_doc_idx}"
    if texts[doc_idx].get('parent', {}).get('$ref') != parent_ref:
      texts[doc_idx]['parent'] = {'$ref': parent_ref}
  
  # Helpers for unmapped
  def containing_toc_idx(page: int):
    """Find containing ToC entry by page interval"""
    cand = [e for e in toc_entries if e['start_page'] <= page <= e['end_page']]
    if not cand:
      return None
    return max(cand, key=lambda e: e['level'])['id']  # deepest by level
  
  mapped_doc_indices = {m['section_header']['index'] for m in mappings}
  
  # 2) For unmapped headers: parent to deepest mapped ancestor by interval
  for i, t in enumerate(texts):
    if t.get('label') != 'section_header' or i in mapped_doc_indices:
      continue
    page = extract_docling_element_page(t)
    ci = containing_toc_idx(page) if page > 0 else None
    
    parent_doc_idx = None
    # climb ToC to find nearest mapped ancestor
    while ci is not None and parent_doc_idx is None:
      parent_doc_idx = toc_idx_to_doc_idx.get(ci)
      if parent_doc_idx is None:
        ci = toc_entries[ci].get('parent_idx')
    
    # Guardrails: Never parent under "Índice" 
    if parent_doc_idx is not None:
      parent_text = texts[parent_doc_idx].get('text', '').lower()
      if normalize_text(parent_text) == 'indice':
        parent_doc_idx = None
    
    # Guardrails: Keep Anejo/Sección families separate
    if parent_doc_idx is not None:
      current_text = t.get('text', '').lower()
      parent_text = texts[parent_doc_idx].get('text', '').lower()
      
      if ('anejo' in current_text and ('seccion' in parent_text or 'sección' in parent_text)) or \
         (('seccion' in current_text or 'sección' in current_text) and 'anejo' in parent_text):
        parent_doc_idx = None
    
    parent_ref = "#/body" if parent_doc_idx is None else f"#/texts/{parent_doc_idx}"
    if t.get('parent', {}).get('$ref') != parent_ref:
      t['parent'] = {'$ref': parent_ref}
  
  return updated


def perform_consistency_checks(
    docling_data: Dict[str, Any], 
    mappings: List[Dict[str, Any]]
) -> Dict[str, Any]:
  """
  Perform consistency checks: no level jumps, page order monotonicity, unique paths.
  
  Args:
      docling_data: DoclingDocument data
      mappings: ToC-to-section mappings
      
  Returns:
      Dict with consistency check results and warnings
  """
  logger = logging.getLogger(__name__)
  
  texts = docling_data.get('texts', [])
  issues = []
  warnings = []
  
  # Get all section headers in document order
  section_headers = []
  for i, text_item in enumerate(texts):
    if text_item.get('label') == 'section_header':
      section_headers.append({
        'index': i,
        'text': text_item.get('text', ''),
        'level': text_item.get('level', 1),
        'page': extract_docling_element_page(text_item)
      })
  
  # Check 1: No level jumps (level should not increase by more than 1)
  for i in range(1, len(section_headers)):
    prev_level = section_headers[i-1]['level']
    curr_level = section_headers[i]['level']
    
    if curr_level > prev_level + 1:
      issue = f"Level jump detected: section '{section_headers[i]['text'][:50]}...' jumps from level {prev_level} to {curr_level}"
      issues.append(issue)
      logger.warning(issue)
  
  # Check 2: Page order monotonicity (sections should generally appear in page order)
  page_order_violations = 0
  for i in range(1, len(section_headers)):
    prev_page = section_headers[i-1]['page']
    curr_page = section_headers[i]['page']
    
    if prev_page > 0 and curr_page > 0 and curr_page < prev_page - 2:  # Allow some tolerance
      page_order_violations += 1
      if page_order_violations <= 5:  # Limit warnings
        warning = f"Page order violation: section '{section_headers[i]['text'][:50]}...' on page {curr_page} after section on page {prev_page}"
        warnings.append(warning)
        logger.warning(warning)
  
  # Check 3: Unique paths (no duplicate parent-child relationships)
  parent_child_pairs = set()
  for header in section_headers:
    text_item = texts[header['index']]
    parent_ref = text_item.get('parent', {}).get('$ref', '')
    child_ref = f"#/texts/{header['index']}"
    
    pair = (parent_ref, child_ref)
    if pair in parent_child_pairs:
      issue = f"Duplicate parent-child relationship: {parent_ref} -> {child_ref}"
      issues.append(issue)
      logger.error(issue)
    else:
      parent_child_pairs.add(pair)
  
  # Check 4: Anejo/Sección isolation
  anejo_sections = []
  seccion_sections = []
  
  for header in section_headers:
    text_lower = header['text'].lower()
    if 'anejo' in text_lower:
      anejo_sections.append(header)
    elif 'sección' in text_lower or 'seccion' in text_lower:
      seccion_sections.append(header)
  
  # Check for cross-contamination
  for anejo in anejo_sections:
    anejo_text_item = texts[anejo['index']]
    parent_ref = anejo_text_item.get('parent', {}).get('$ref', '')
    
    if parent_ref.startswith('#/texts/'):
      parent_index = int(parent_ref.split('/')[-1])
      parent_text = texts[parent_index].get('text', '').lower()
      
      if 'sección' in parent_text or 'seccion' in parent_text:
        warning = f"Anejo section '{anejo['text'][:50]}...' has Sección parent"
        warnings.append(warning)
        logger.warning(warning)
  
  logger.info(f'Consistency checks complete: {len(issues)} issues, {len(warnings)} warnings')
  
  return {
    'issues': issues,
    'warnings': warnings,
    'level_jump_count': len([i for i in issues if 'Level jump' in i]),
    'page_order_violations': page_order_violations,
    'unique_path_violations': len([i for i in issues if 'Duplicate parent-child' in i]),
    'anejo_seccion_violations': len([w for w in warnings if 'Anejo section' in w and 'Sección parent' in w])
  }
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


def generate_enhanced_toc_mapping_report(
    mapping_report: Dict[str, Any],
    toc_entries: List[Dict[str, Any]],
    corrected_docling_data: Dict[str, Any]
) -> str:
  """
  Generate an enhanced ToC mapping report with confidence scores and detailed analysis.
  
  Args:
      mapping_report: Report data from enhanced mapping process
      toc_entries: Original ToC entries from PDF
      corrected_docling_data: Updated DoclingDocument with corrected hierarchy
      
  Returns:
      Markdown formatted report string
  """
  lines = [
    "# Enhanced Table of Contents Mapping Report",
    "",
    "This report details the enhanced ToC-driven hierarchy repair process with multi-pass mapping,",
    "page-driven parenting, auxiliary content detection, and comprehensive consistency checks.",
    ""
  ]
  
  # Section 1: Initial ToC extracted from PDF with intervals
  lines.extend([
    "## 1. Initial Table of Contents from PDF (with Page Intervals)",
    ""
  ])
  
  toc_with_intervals = mapping_report.get('toc_entries_with_intervals', toc_entries)
  lines.append(f"**Total ToC entries found:** {len(toc_with_intervals)}")
  lines.append("")
  lines.append("| Level | Title | Start Page | End Page | Interval Size |")
  lines.append("|-------|-------|------------|----------|---------------|")
  
  for entry in toc_with_intervals:
    title = entry['title'].replace('|', '\\|')
    start_page = entry.get('start_page', entry['page'])
    end_page = entry.get('end_page', entry['page'])
    interval_size = end_page - start_page + 1
    lines.append(f"| {entry['level']} | {title} | {start_page} | {end_page} | {interval_size} |")
  
  lines.append("")
  
  # Section 2: Multi-Pass Mapping Statistics
  lines.extend([
    "## 2. Multi-Pass Mapping Statistics",
    ""
  ])
  
  pass_stats = mapping_report.get('pass_statistics', {})
  successful_mappings = mapping_report.get('successful_mappings', [])
  
  lines.extend([
    f"**Pass 1 (Exact/Near matches):** {pass_stats.get('pass_1_matches', 0)} matches",
    f"**Pass 2 (Structural/Numbered):** {pass_stats.get('pass_2_matches', 0)} matches", 
    f"**Pass 3 (Fuzzy+Context):** {pass_stats.get('pass_3_matches', 0)} matches",
    f"**Pass 4 (Page Scanning):** {pass_stats.get('pass_4_matches', 0)} matches",
    f"**Total successful mappings:** {len(successful_mappings)}",
    ""
  ])
  
  # Section 3: Mapping Quality Analysis
  if successful_mappings:
    lines.extend([
      "## 3. Mapping Quality Analysis",
      "",
      "| Pass | ToC Title | Section Header | Similarity | Confidence | Match Type | Page Distance |",
      "|------|-----------|----------------|------------|------------|------------|---------------|"
    ])
    
    for mapping in successful_mappings[:20]:  # Show top 20 mappings
      toc_entry = mapping['toc_entry']
      section_header = mapping['section_header']
      sim_info = mapping.get('similarity_info', {})
      pass_num = mapping.get('pass', 'N/A')
      
      # Escape and truncate titles
      toc_title = toc_entry['title'].replace('|', '\\|')[:30]
      section_title = section_header['text'].replace('|', '\\|')[:30]
      
      similarity = sim_info.get('similarity', mapping.get('similarity', 0))
      confidence = sim_info.get('confidence', 0)
      match_type = sim_info.get('match_type', 'unknown')
      page_distance = sim_info.get('page_distance', 0)
      
      lines.append(f"| {pass_num} | {toc_title} | {section_title} | {similarity:.3f} | {confidence:.3f} | {match_type} | {page_distance} |")
    
    if len(successful_mappings) > 20:
      lines.append(f"*... and {len(successful_mappings) - 20} more mappings*")
    
    lines.append("")
  
  # Section 4: Consistency Check Results
  lines.extend([
    "## 4. Consistency Check Results",
    ""
  ])
  
  consistency = mapping_report.get('consistency_results', {})
  if consistency:
    lines.extend([
      f"**Level jump violations:** {consistency.get('level_jump_count', 0)}",
      f"**Page order violations:** {consistency.get('page_order_violations', 0)}",
      f"**Unique path violations:** {consistency.get('unique_path_violations', 0)}",
      f"**Anejo/Sección cross-contamination:** {consistency.get('anejo_seccion_violations', 0)}",
      ""
    ])
    
    issues = consistency.get('issues', [])
    warnings = consistency.get('warnings', [])
    
    if issues:
      lines.extend([
        "### Critical Issues:",
        ""
      ])
      for i, issue in enumerate(issues[:10], 1):  # Show first 10 issues
        lines.append(f"{i}. {issue}")
      if len(issues) > 10:
        lines.append(f"*... and {len(issues) - 10} more issues*")
      lines.append("")
    
    if warnings:
      lines.extend([
        "### Warnings:",
        ""
      ])
      for i, warning in enumerate(warnings[:10], 1):  # Show first 10 warnings
        lines.append(f"{i}. {warning}")
      if len(warnings) > 10:
        lines.append(f"*... and {len(warnings) - 10} more warnings*")
      lines.append("")
  
  # Section 5: Unmapped Content Analysis
  lines.extend([
    "## 5. Unmapped Content Analysis",
    ""
  ])
  
  unmapped_toc = mapping_report.get('unmapped_toc_entries', [])
  unmapped_sections = mapping_report.get('unmapped_section_headers', [])
  
  if unmapped_toc:
    lines.extend([
      f"### 5.1 PDF ToC Headlines Not Matched ({len(unmapped_toc)} entries)",
      "",
      "These ToC entries could not be matched to DoclingDocument section headers:",
      ""
    ])
    
    for i, entry in enumerate(unmapped_toc[:15], 1):  # Show first 15
      lines.append(f"{i}. **Level {entry['level']}**: {entry['title']} (Pages {entry.get('start_page', entry['page'])}-{entry.get('end_page', entry['page'])})")
    
    if len(unmapped_toc) > 15:
      lines.append(f"*... and {len(unmapped_toc) - 15} more unmapped ToC entries*")
    lines.append("")
  
  if unmapped_sections:
    lines.extend([
      f"### 5.2 DoclingDocument Headers Not Mapped ({len(unmapped_sections)} entries)", 
      "",
      "These section headers could not be matched to PDF ToC entries:",
      ""
    ])
    
    for i, header in enumerate(unmapped_sections[:15], 1):  # Show first 15
      title = header['text'][:60] + "..." if len(header['text']) > 60 else header['text']
      page = header.get('page', 'N/A')
      lines.append(f"{i}. {title} (Page {page})")
    
    if len(unmapped_sections) > 15:
      lines.append(f"*... and {len(unmapped_sections) - 15} more unmapped sections*")
    lines.append("")
  
  # Section 6: Processing Summary
  lines.extend([
    "## 6. Processing Summary",
    ""
  ])
  
  total_toc_entries = len(toc_entries)
  total_section_headers = mapping_report.get('total_section_headers', 0)
  successful_mappings_count = len(successful_mappings)
  updated_levels_count = mapping_report.get('updated_levels_count', 0)
  unmapped_updates_count = mapping_report.get('unmapped_updates_count', 0)
  synthetic_nodes_count = len(mapping_report.get('synthetic_toc_nodes', []))
  orphaned_info = mapping_report.get('orphaned_sections_info', {})
  
  lines.extend([
    f"- **PDF ToC entries processed:** {total_toc_entries}",
    f"- **DoclingDocument section headers found:** {total_section_headers}",
    f"- **Successful ToC mappings:** {successful_mappings_count}",
    f"- **Ground-truth level updates:** {updated_levels_count}",
    f"- **Derived level updates:** {unmapped_updates_count}",
    f"- **Synthetic ToC nodes created:** {synthetic_nodes_count}",
    f"- **Auxiliary content demoted:** {mapping_report.get('demoted_content_count', 0)}",
    f"- **Orphaned metadata sections handled:** {orphaned_info.get('orphaned_sections_found', 0)}",
    ""
  ])
  
  if orphaned_info.get('synthetic_parent_created', False):
    lines.append(f"- **Synthetic 'Document Info' parent created:** Yes")
    lines.append("")
  
  if total_toc_entries > 0:
    mapping_rate = (successful_mappings_count / total_toc_entries) * 100
    lines.append(f"- **ToC mapping success rate:** {mapping_rate:.1f}%")
  
  if total_section_headers > 0:
    coverage_rate = (successful_mappings_count / total_section_headers) * 100
    lines.append(f"- **Section header coverage:** {coverage_rate:.1f}%")
  
  lines.append("")
  
  # Section 7: Final Table of Contents
  lines.extend([
    "## 7. Final Table of Contents (Ground-Truth + Derived)",
    "",
    "Generated from the corrected DoclingDocument with ToC-driven hierarchy:",
    ""
  ])
  
  # Generate ToC from corrected document
  corrected_toc = generate_toc_markdown(corrected_docling_data)
  toc_lines = corrected_toc.split('\n')[4:]  # Skip header lines
  lines.extend(toc_lines)
  
  lines.append("")
  
  # Add generation timestamp and metadata
  from datetime import datetime
  timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
  lines.extend([
    "---",
    f"*Enhanced ToC-driven hierarchy repair completed on {timestamp}*",
    f"*Multi-pass mapping with page intervals and consistency validation*"
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


def enhanced_map_toc_to_docling_sections(
    toc_entries: List[Dict[str, Any]], 
    docling_data: Dict[str, Any],
    total_pages: int = 1000
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
  """
  Enhanced ToC to DoclingDocument mapping with multi-pass strategy and page-driven parenting.
  
  Args:
      toc_entries: List of ToC entries with level, title, and page
      docling_data: DoclingDocument JSON data
      total_pages: Total pages in document (for interval calculation)
      
  Returns:
      Tuple of (updated DoclingDocument, comprehensive mapping report data)
  """
  logger = logging.getLogger(__name__)
  
  # Create a deep copy of the docling data
  import copy
  updated_data = copy.deepcopy(docling_data)
  
  # Step 1: Build ToC intervals
  logger.info('Step 1: Building ToC intervals')
  toc_entries_with_intervals = build_toc_intervals(toc_entries, total_pages)
  
  # Step 2: Extract DoclingDocument section headers with page info
  logger.info('Step 2: Extracting DoclingDocument section headers')
  section_headers = []
  texts = updated_data.get('texts', [])
  
  for i, text_item in enumerate(texts):
    if text_item.get('label') == 'section_header':
      section_text = text_item.get('text', '')
      
      # Check for auxiliary content
      aux_result = detect_auxiliary_content(section_text)
      if aux_result['is_auxiliary']:
        logger.debug(f'Detected auxiliary content: "{section_text[:50]}..." (type: {aux_result["type"]})')
        # Demote to body text instead of section header
        text_item['label'] = 'text'
        continue
      
      # Check for combined headings that need splitting
      split_headings = split_combined_headings(section_text)
      if len(split_headings) > 1:
        logger.info(f'Split combined heading into {len(split_headings)} parts: {split_headings}')
        # For now, use the first part and note the others
        # In a full implementation, we'd create additional text elements
        section_text = split_headings[0]
        text_item['text'] = section_text
      
      section_headers.append({
        'index': i,
        'text': section_text,
        'original_level': text_item.get('level', 1),
        'page': extract_docling_element_page(text_item)
      })
  
  logger.info(f'Found {len(section_headers)} valid section headers in DoclingDocument')
  logger.info(f'Found {len(toc_entries_with_intervals)} ToC entries with intervals')
  
  # Step 2.5: Detect and merge split headlines
  logger.info('Step 2.5: Detecting and merging split headlines')
  section_headers = detect_and_merge_split_headlines(toc_entries_with_intervals, section_headers, updated_data)
  logger.info(f'After split headline detection: {len(section_headers)} section headers')
  
  # Step 3: Multi-pass mapping
  logger.info('Step 3: Performing multi-pass mapping')
  mappings, unmapped_toc_entries, unmapped_sections = multi_pass_mapping(
    toc_entries_with_intervals, section_headers, updated_data
  )
  
  # Step 4: Update levels based on successful mappings
  logger.info('Step 4: Updating hierarchical levels')
  updates_count = 0
  synthetic_sections = []
  
  for mapping in mappings:
    section_header = mapping['section_header']
    section_index = section_header['index']
    new_level = mapping['toc_entry']['level']
    
    # Handle synthetic sections (from table cells)
    if section_header.get('synthetic', False):
      # For synthetic sections, we need to create a new text element
      synthetic_text_element = {
        'label': 'section_header',
        'text': section_header['text'],
        'level': new_level,
        'parent': {'$ref': '#/body'},  # Will be updated in parenting step
        'synthetic': True,
        'source_table_index': section_header.get('source_table_index'),
        'prov': [{
          'page_no': section_header['page'],
          'bbox': section_header.get('source_cell_data', {}).get('bbox', {}),
          'charspan': [0, len(section_header['text'])]
        }]
      }
      texts.append(synthetic_text_element)
      
      # Update the mapping to point to the new text element index
      new_index = len(texts) - 1
      mapping['section_header']['index'] = new_index
      section_index = new_index
      
      synthetic_sections.append({
        'original_table_index': section_header.get('source_table_index'),
        'new_text_index': new_index,
        'toc_entry': mapping['toc_entry']
      })
      
      logger.debug(f'Created synthetic section "{section_header["text"]}" from table cell at index {new_index}')
    else:
      # Regular section header
      old_level = texts[section_index].get('level', 1)
      texts[section_index]['level'] = new_level
      logger.debug(f'Updated section "{texts[section_index].get("text", "")}" level from {old_level} to {new_level}')
    
    updates_count += 1
  
  logger.info(f'Updated levels for {updates_count} section headers from ToC mappings')
  
  # Step 5: Process unmapped sections with enhanced logic
  logger.info('Step 5: Processing unmapped sections')
  unmapped_updates_count = 0
  synthetic_toc_nodes = []
  
  # Helper functions for containing ToC index
  def containing_toc_idx(page: int):
    """Find containing ToC entry by page interval"""
    cand = [e for e in toc_entries_with_intervals if e['start_page'] <= page <= e['end_page']]
    if not cand:
      return None
    return max(cand, key=lambda e: e['level'])['id']  # deepest by level
  
  # Map: ToC idx -> doc idx (for mapped headings)
  toc_idx_to_doc_idx = {m['toc_idx']: m['section_header']['index'] for m in mappings}
  mapped_doc_indices = {m['section_header']['index'] for m in mappings}
  
  # Sibling-level cache for consistency: (parent_doc_idx, prefix) -> level
  sibling_level_cache = {}
  
  # Process unmapped sections
  for i, t in enumerate(texts):
    if t.get('label') != 'section_header' or i in mapped_doc_indices:
      continue
      
    page = extract_docling_element_page(t)
    section_text = t.get('text', '')
    ci = containing_toc_idx(page) if page > 0 else None
    
    parent_doc_idx = None
    # climb ToC to find nearest mapped ancestor
    while ci is not None and parent_doc_idx is None:
      parent_doc_idx = toc_idx_to_doc_idx.get(ci)
      if parent_doc_idx is None:
        ci = toc_entries_with_intervals[ci].get('parent_idx')
    
    # After you compute parent_doc_idx via intervals:
    parent_level = 1 if parent_doc_idx is None else texts[parent_doc_idx].get('level', 1)
    prefix, depth = numbering_key(section_text)
    
    # Choose level relative to parent; keep siblings flat:
    cache_key = (parent_doc_idx, prefix)
    if cache_key in sibling_level_cache:
      # Use cached level for siblings with same numbering prefix
      new_level = sibling_level_cache[cache_key]
    else:
      # First time seeing this prefix under this parent
      new_level = parent_level + 1
      sibling_level_cache[cache_key] = new_level
    
    old_level = t.get('level', 1)
    
    if new_level != old_level:
      texts[i]['level'] = new_level
      texts[i]['derived'] = True  # Mark as derived, not ground-truth ToC
      unmapped_updates_count += 1
      logger.debug(f'Updated unmapped section "{section_text[:50]}..." level to {new_level} (derived from parent level {parent_level}, prefix "{prefix}")')
  
  logger.info(f'Processed {unmapped_updates_count} unmapped sections with enhanced logic')
  
  logger.info(f'Processed {unmapped_updates_count} unmapped sections with enhanced logic')
  
  # Step 6: Page-driven parenting
  logger.info('Step 6: Applying page-driven parenting')
  updated_data = page_driven_parenting(mappings, toc_entries_with_intervals, updated_data)
  
  # Step 7: Consistency checks
  logger.info('Step 7: Performing consistency checks')
  consistency_results = perform_consistency_checks(updated_data, mappings)
  
  # Step 8: Handle orphaned metadata sections
  logger.info('Step 8: Handling orphaned metadata sections')
  logger.debug(f'Before orphaned handling: {len(updated_data.get("texts", []))} text elements')
  updated_data, orphaned_info = handle_orphaned_metadata_sections(updated_data)
  logger.debug(f'After orphaned handling: {len(updated_data.get("texts", []))} text elements, found {orphaned_info.get("orphaned_sections_found", 0)} orphaned sections')
  
  # Prepare comprehensive mapping report
  mapping_report = {
    'toc_entries': toc_entries,
    'toc_entries_with_intervals': toc_entries_with_intervals,
    'successful_mappings': mappings,
    'unmapped_toc_entries': unmapped_toc_entries,
    'unmapped_section_headers': unmapped_sections,
    'total_section_headers': len(section_headers),
    'updated_levels_count': updates_count,
    'unmapped_updates_count': unmapped_updates_count,
    'synthetic_toc_nodes': synthetic_toc_nodes,
    'consistency_results': consistency_results,
    'orphaned_sections_info': orphaned_info,
    'pass_statistics': {
      'pass_1_matches': len([m for m in mappings if m.get('pass') == 1]),
      'pass_2_matches': len([m for m in mappings if m.get('pass') == 2]),
      'pass_3_matches': len([m for m in mappings if m.get('pass') == 3]),
      'pass_4_matches': len([m for m in mappings if m.get('pass') == 4])
    },
    'synthetic_sections': synthetic_sections
  }
  
  return updated_data, mapping_report


def handle_orphaned_metadata_sections(docling_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
  """
  Detect orphaned Level 1 sections at the beginning of the document that outline 
  metadata about the document and create a synthetic level 1 section_header 
  called "Document Info" to parent them, making them level 2.
  
  Args:
      docling_data: DoclingDocument JSON data
      
  Returns:
      Tuple of (updated DoclingDocument, info about changes made)
  """
  logger = logging.getLogger(__name__)
  
  import copy
  updated_data = copy.deepcopy(docling_data)
  texts = updated_data.get('texts', [])
  
  # Find orphaned metadata sections - level 1 sections at the beginning of document (pages 1-3)
  # that appear before the main structural content and represent document metadata
  orphaned_sections = []
  
  logger.debug(f'Checking {len(texts)} text elements for orphaned metadata sections')
  
  for i, text_item in enumerate(texts):
    if text_item.get('label') != 'section_header':
      continue
      
    page = extract_docling_element_page(text_item)
    level = text_item.get('level', 1)
    text_content = text_item.get('text', '').strip()
    
    # Debug logging for first few section headers
    if i < 50:  
      logger.debug(f'  Index {i}: "{text_content}" (Page {page}, Level {level}, Label: {text_item.get("label")})')
    
    # Look for sections on early pages (1-3) that are document metadata
    # NOTE: These sections may have been changed to level 2 during unmapped section processing
    if page <= 3 and level <= 2:
      # Check if this section looks like document metadata vs. main content structure
      metadata_indicators = [
        'documento', 'básico', 'seguridad', 'disposiciones', 'normativas', 
        'boletín', 'oficial', 'consolidado', 'exigencias', 'básicas'
      ]
      
      # Exclude sections that are clearly main structural content
      main_structure_indicators = [
        'introducción', 'índice', 'sección si', 'anejo', 'i objeto', 'ii ámbito', 
        'iii criterios', 'iv condiciones', 'v condiciones', 'vi laboratorios', 'vii terminología',
        'artículo 11', '11.1 exigencia', '11.2 exigencia', '11.3 exigencia', 
        '11.4 exigencia', '11.5 exigencia', '11.6 exigencia'
      ]
      
      text_lower = text_content.lower()
      
      # Check if it's document metadata and not main structure
      is_metadata = any(indicator in text_lower for indicator in metadata_indicators)
      is_main_structure = any(indicator in text_lower for indicator in main_structure_indicators)
      
      # Special case: "D ocumento B ásico" by itself (with space) is metadata
      # Handle Unicode characters by normalizing them and removing spaces
      import unicodedata
      normalized_text = unicodedata.normalize('NFD', text_lower)
      ascii_text = ''.join(c for c in normalized_text if unicodedata.category(c) != 'Mn')
      clean_text = ascii_text.replace(' ', '')
      is_document_basic = ('documentobasico' in clean_text and len(text_content.strip()) < 30)
      
      if (is_metadata or is_document_basic) and not is_main_structure:
        # Check if this section was already modified during unmapped processing by checking for 'derived' flag
        was_derived = text_item.get('derived', False)
        
        orphaned_sections.append({
          'index': i,
          'text': text_content,
          'page': page,
          'original_level': level,
          'was_derived': was_derived
        })
  
  if not orphaned_sections:
    logger.info('No orphaned metadata sections found')
    return updated_data, {'orphaned_sections_found': 0, 'synthetic_parent_created': False}
  
  logger.info(f'Found {len(orphaned_sections)} orphaned metadata sections:')
  for section in orphaned_sections:
    was_derived_note = " (already level 2 from unmapped processing)" if section.get('was_derived') else ""
    logger.info(f'  - "{section["text"]}" (Page {section["page"]}, Level {section["original_level"]}){was_derived_note}')
  
  # Create a synthetic "Document Info" level 1 section header
  synthetic_parent = {
    'self_ref': f'#/texts/{len(texts)}',
    'parent': {'$ref': '#/body'},
    'children': [],
    'content_layer': 'body',
    'label': 'section_header',
    'prov': [{
      'page_no': 1,
      'bbox': {'l': 0, 't': 0, 'r': 100, 'b': 10, 'coord_origin': 'TOPLEFT'},
      'charspan': [0, 13]
    }],
    'orig': 'Document Info',
    'text': 'Document Info',
    'level': 1,
    'synthetic': True,
    'created_for_orphaned_sections': True
  }
  
  # Add the synthetic parent to the texts array at the beginning (after headers but before content)
  # Insert it before the first orphaned section to maintain document order
  first_orphan_index = min(section['index'] for section in orphaned_sections)
  texts.insert(first_orphan_index, synthetic_parent)
  synthetic_parent_index = first_orphan_index
  
  # Update all indices for sections that come after the insertion point
  for section in orphaned_sections:
    if section['index'] >= first_orphan_index:
      section['index'] += 1  # Adjust for the insertion
  
  # Update the self_ref of the synthetic parent to reflect its actual position
  texts[synthetic_parent_index]['self_ref'] = f'#/texts/{synthetic_parent_index}'
  
  # Update the orphaned sections to be children of the synthetic parent
  for section in orphaned_sections:
    section_index = section['index']
    # Set parent reference to the synthetic parent
    texts[section_index]['parent'] = {'$ref': f'#/texts/{synthetic_parent_index}'}
    # Make them level 2 (children of level 1 Document Info)
    texts[section_index]['level'] = 2
    logger.info(f'Updated section "{section["text"]}" to be level 2 child of "Document Info"')
  
  # Update all subsequent self_ref values to maintain consistency
  for i in range(synthetic_parent_index + 1, len(texts)):
    if 'self_ref' in texts[i]:
      texts[i]['self_ref'] = f'#/texts/{i}'
  
  logger.info(f'Created synthetic "Document Info" parent section for {len(orphaned_sections)} orphaned metadata sections')
  
  changes_info = {
    'orphaned_sections_found': len(orphaned_sections),
    'synthetic_parent_created': True,
    'synthetic_parent_index': synthetic_parent_index,
    'updated_sections': [s['index'] for s in orphaned_sections]
  }
  
  return updated_data, changes_info


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
  Enhanced processing function with ToC-driven hierarchy repairs.
  
  This function:
  1. Extracts ToC from PDF with page intervals
  2. Performs multi-pass mapping (exact/near, structural, fuzzy+context)
  3. Applies page-driven parenting based on ToC intervals
  4. Detects and handles auxiliary content (tables, equations, captions)
  5. Splits combined headings and creates derived subclauses
  6. Performs consistency checks (level jumps, page order, unique paths)
  7. Generates comprehensive report with confidence scores and detailed metrics
  
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
    
    # Estimate total pages from DoclingDocument for interval calculation
    max_page = 0
    for text_item in docling_data.get('texts', []):
      page = extract_docling_element_page(text_item)
      if page > max_page:
        max_page = page
    
    total_pages = max(max_page, 1000)  # Use document max or fallback to 1000
    logger.info(f'Estimated document has {total_pages} pages')
    
    # Step 3: Enhanced ToC-to-DoclingDocument mapping
    logger.info('Step 3: Performing enhanced ToC-driven hierarchy mapping...')
    updated_docling_data, mapping_report = enhanced_map_toc_to_docling_sections(
      toc_entries, docling_data, total_pages
    )
    
    # Step 4: Save headline_fixed_doclingdocument.json
    logger.info('Step 4: Saving corrected DoclingDocument...')
    output_json_path = Path(docling_json_path).with_name('headline_fixed_doclingdocument.json')
    output_json_path.write_text(
        json.dumps(updated_docling_data, indent=2, ensure_ascii=False), 
        encoding='utf-8'
    )
    logger.info('Corrected DoclingDocument saved to: %s', output_json_path)
    
    # Step 5: Generate enhanced mapping report
    logger.info('Step 5: Generating enhanced mapping report...')
    report_content = generate_enhanced_toc_mapping_report(
      mapping_report, toc_entries, updated_docling_data
    )
    report_path = Path(docling_json_path).with_name('report.md')
    report_path.write_text(report_content, encoding='utf-8')
    logger.info('Enhanced mapping report saved to: %s', report_path)
    
    # Step 6: Log summary statistics
    consistency = mapping_report.get('consistency_results', {})
    pass_stats = mapping_report.get('pass_statistics', {})
    orphaned_info = mapping_report.get('orphaned_sections_info', {})
    
    logger.info('=== PROCESSING SUMMARY ===')
    logger.info(f'ToC entries processed: {len(toc_entries)}')
    logger.info(f'Section headers found: {mapping_report.get("total_section_headers", 0)}')
    logger.info(f'Successful mappings: {len(mapping_report.get("successful_mappings", []))}')
    logger.info(f'  - Pass 1 (exact): {pass_stats.get("pass_1_matches", 0)}')
    logger.info(f'  - Pass 2 (structural): {pass_stats.get("pass_2_matches", 0)}')
    logger.info(f'  - Pass 3 (fuzzy): {pass_stats.get("pass_3_matches", 0)}')
    logger.info(f'  - Pass 4 (page scan): {pass_stats.get("pass_4_matches", 0)}')
    logger.info(f'Synthetic sections created: {len(mapping_report.get("synthetic_sections", []))}')
    logger.info(f'Ground-truth updates: {mapping_report.get("updated_levels_count", 0)}')
    logger.info(f'Derived updates: {mapping_report.get("unmapped_updates_count", 0)}')
    logger.info(f'Orphaned metadata sections handled: {orphaned_info.get("orphaned_sections_found", 0)}')
    if orphaned_info.get("synthetic_parent_created", False):
      logger.info('  - Created synthetic "Document Info" parent section')
    logger.info(f'Consistency issues: {len(consistency.get("issues", []))}')
    logger.info(f'Consistency warnings: {len(consistency.get("warnings", []))}')
    
    logger.info('Enhanced ToC-driven hierarchy repair completed successfully!')
    
  except Exception as e:
    logger.error('Enhanced processing failed: %s', e)
    raise


def main() -> None:
  """Enhanced command-line interface for ToC-driven hierarchy repairs."""
  parser = argparse.ArgumentParser(
      description='Enhanced PDF ToC extractor with multi-pass mapping and page-driven hierarchy repairs',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
Enhanced Features:
  • Stronger text normalization (accents, OCR spacing, punctuation)
  • ToC page intervals for precise section containment
  • Multi-pass mapping: exact/near → structural/numbered → fuzzy+context → page scanning
  • Page scanning to find headers in table cells and other page elements
  • Enhanced footnote handling for markers like "(1)" or "( 1 )"
  • Page-driven parenting based on ToC intervals
  • Auxiliary content detection (tables, equations, captions)
  • Combined heading splitting (e.g., "Anejo SI A ... Anejo SI B ...")
  • Consistency checks (level jumps, page order, unique paths)
  • Comprehensive reporting with confidence scores and detailed metrics

Example:
  %(prog)s document.pdf document.json
  
This will:
  1. Extract ToC from document.pdf with page intervals
  2. Perform multi-pass mapping to DoclingDocument section headers
  3. Apply page-driven parenting and consistency validation
  4. Create headline_fixed_doclingdocument.json with ToC-driven hierarchy
  5. Generate report.md with comprehensive analysis and confidence scores
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
