"""
Tests for PDF ToC Extraction Script using PyMuPDF

This module tests the pdf_toc_extractor.py script functionality.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the module we're testing
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

try:
  from pdf_toc_extractor import (
    extract_pdf_toc, 
    setup_logging, 
    normalize_text, 
    normalize_text_for_matching,
    numbering_key,
    calculate_text_similarity,
    calculate_enhanced_similarity,
    enhanced_map_toc_to_docling_sections,
    update_parent_references,
    generate_toc_markdown,
    build_toc_intervals,
    extract_docling_element_page,
    detect_auxiliary_content,
    split_combined_headings,
    multi_pass_mapping,
    scan_page_for_text_matches,
    find_deepest_toc_ancestor,
    page_driven_parenting,
    perform_consistency_checks
  )
except ImportError as e:
  # Handle import issues in test environment
  print(f'Warning: Could not import pdf_toc_extractor: {e}')
  extract_pdf_toc = None


class TestPdfTocExtractor(unittest.TestCase):
  """Test cases for PDF ToC extraction functionality."""

  def setUp(self):
    """Set up test fixtures."""
    if extract_pdf_toc is None:
      self.skipTest('pdf_toc_extractor module could not be imported')

  def test_setup_logging_verbose_false(self):
    """Test logging setup with verbose=False."""
    with patch('logging.basicConfig') as mock_basic_config:
      setup_logging(verbose=False)
      mock_basic_config.assert_called_once()
      args, kwargs = mock_basic_config.call_args
      self.assertEqual(kwargs['level'], 20)  # logging.INFO = 20

  def test_setup_logging_verbose_true(self):
    """Test logging setup with verbose=True."""
    with patch('logging.basicConfig') as mock_basic_config:
      setup_logging(verbose=True)
      mock_basic_config.assert_called_once()
      args, kwargs = mock_basic_config.call_args
      self.assertEqual(kwargs['level'], 10)  # logging.DEBUG = 10

  def test_normalize_text(self):
    """Test text normalization functionality."""
    # Test Unicode escape sequences
    text1 = "Secci\\u00f3n SI 2 Propagaci\\u00f3n exterior"
    normalized1 = normalize_text(text1)
    self.assertIn('seccion', normalized1.lower())
    
    # Test whitespace normalization (enhanced version removes spaces between letters)
    text2 = "  Multiple   spaces  "
    normalized2 = normalize_text(text2)
    self.assertEqual(normalized2, "multiplespaces")  # Updated expectation

  def test_calculate_text_similarity(self):
    """Test text similarity calculation."""
    # Identical texts
    similarity1 = calculate_text_similarity("test", "test")
    self.assertEqual(similarity1, 1.0)
    
    # Similar texts
    similarity2 = calculate_text_similarity("Sección SI 1", "Seccion SI 1")
    self.assertGreater(similarity2, 0.8)
    
    # Different texts
    similarity3 = calculate_text_similarity("hello", "world")
    self.assertLess(similarity3, 0.5)

  def test_extract_pdf_toc_missing_fitz(self):
    """Test error handling when PyMuPDF is not available."""
    with patch.dict('sys.modules', {'fitz': None}):
      with self.assertRaises(ImportError) as context:
        extract_pdf_toc('dummy.pdf')

      self.assertIn('PyMuPDF (fitz) is required', str(context.exception))

  @patch('pdf_toc_extractor.fitz.open')
  def test_extract_pdf_toc_no_toc(self, mock_fitz_open):
    """Test extraction when PDF has no ToC."""
    # Mock PyMuPDF document
    mock_doc = MagicMock()
    mock_doc.get_toc.return_value = []
    mock_fitz_open.return_value = mock_doc

    with patch('pdf_toc_extractor.fitz'):
      result = extract_pdf_toc('dummy.pdf')

    self.assertEqual(result, [])
    mock_fitz_open.assert_called_once_with('dummy.pdf')
    mock_doc.get_toc.assert_called_once()
    mock_doc.close.assert_called_once()

  @patch('pdf_toc_extractor.fitz.open')
  def test_extract_pdf_toc_with_entries(self, mock_fitz_open):
    """Test extraction with actual ToC entries."""
    # Mock PyMuPDF document with ToC
    mock_doc = MagicMock()
    mock_toc = [
        (1, 'Introduction', 1),
        (2, 'Background', 3),
        (1, 'Methods', 10),
    ]
    mock_doc.get_toc.return_value = mock_toc
    mock_fitz_open.return_value = mock_doc

    with patch('pdf_toc_extractor.fitz'):
      result = extract_pdf_toc('dummy.pdf')

    expected = [
        {'level': 1, 'title': 'Introduction', 'page': 1},
        {'level': 2, 'title': 'Background', 'page': 3},
        {'level': 1, 'title': 'Methods', 'page': 10},
    ]

    self.assertEqual(result, expected)
    mock_fitz_open.assert_called_once_with('dummy.pdf')
    mock_doc.get_toc.assert_called_once()
    mock_doc.close.assert_called_once()

  def test_map_toc_to_docling_sections(self):
    """Test mapping ToC entries to DoclingDocument section headers."""
    toc_entries = [
        {'level': 1, 'title': 'Introduction', 'page': 1},
        {'level': 2, 'title': 'Background', 'page': 3},
    ]
    
    docling_data = {
        'texts': [
            {
                'label': 'section_header', 
                'text': 'Introduction', 
                'level': 1,
                'prov': [{'page_no': 1}]
            },
            {
                'label': 'section_header', 
                'text': 'Background Info', 
                'level': 1,
                'prov': [{'page_no': 3}]
            },
            {'label': 'paragraph', 'text': 'Some content'},
        ]
    }
    
    updated_data, mapping_report = enhanced_map_toc_to_docling_sections(toc_entries, docling_data)
    
    # Check that levels were updated
    self.assertEqual(updated_data['texts'][0]['level'], 1)  # Introduction
    self.assertEqual(updated_data['texts'][1]['level'], 2)  # Background (mapped)
    
    # Check mapping report
    self.assertEqual(len(mapping_report['successful_mappings']), 2)
    self.assertEqual(mapping_report['total_section_headers'], 2)

  def test_update_parent_references(self):
    """Test updating parent references based on hierarchy."""
    docling_data = {
        'texts': [
            {'label': 'section_header', 'text': 'Chapter 1', 'level': 1, 'parent': {'$ref': '#/body'}},
            {'label': 'section_header', 'text': 'Section 1.1', 'level': 2, 'parent': {'$ref': '#/body'}},
            {'label': 'section_header', 'text': 'Section 1.1.1', 'level': 3, 'parent': {'$ref': '#/body'}},
        ]
    }
    
    updated_data = update_parent_references(docling_data)
    
    # Check parent references
    self.assertEqual(updated_data['texts'][0]['parent']['$ref'], '#/body')  # Level 1 keeps #/body
    self.assertEqual(updated_data['texts'][1]['parent']['$ref'], '#/texts/0')  # Level 2 points to Level 1
    self.assertEqual(updated_data['texts'][2]['parent']['$ref'], '#/texts/1')  # Level 3 points to Level 2

  def test_generate_toc_markdown(self):
    """Test ToC markdown generation."""
    docling_data = {
        'texts': [
            {'label': 'section_header', 'text': 'Chapter 1', 'level': 1},
            {'label': 'section_header', 'text': 'Section 1.1', 'level': 2},
            {'label': 'paragraph', 'text': 'Some content'},
        ]
    }
    
    result = generate_toc_markdown(docling_data)
    
    self.assertIn('# Table of Contents', result)
    self.assertIn('- Chapter 1', result)
    self.assertIn('  - Section 1.1', result)
    self.assertNotIn('Some content', result)  # Should not include non-headers

  def test_enhanced_normalize_text(self):
    """Test enhanced text normalization with OCR artifacts."""
    # Test Unicode handling
    self.assertEqual(normalize_text('Secci\\u00f3n SI 1'), 'seccionsi 1')  # Updated expectation
    
    # Test OCR spacing issues - spaces between letters are removed
    self.assertEqual(normalize_text('D ocumento B ásico'), 'documentobasico')
    
    # Test punctuation normalization (exclamation mark gets stripped at end)
    self.assertEqual(normalize_text('Title , with ; punctuation !'), 'title, with; punctuation')
    
    # Test leading/trailing punctuation removal
    self.assertEqual(normalize_text('- Title -'), 'title')

  def test_build_toc_intervals(self):
    """Test ToC interval calculation."""
    toc_entries = [
      {'level': 1, 'title': 'Chapter 1', 'page': 1},
      {'level': 2, 'title': 'Section 1.1', 'page': 3},
      {'level': 1, 'title': 'Chapter 2', 'page': 10}
    ]
    
    intervals = build_toc_intervals(toc_entries, 20)
    
    self.assertEqual(len(intervals), 3)
    self.assertEqual(intervals[0]['start_page'], 1)
    self.assertEqual(intervals[0]['end_page'], 9)  # Before Chapter 2
    self.assertEqual(intervals[1]['start_page'], 3)
    self.assertEqual(intervals[1]['end_page'], 9)  # Before Chapter 2
    self.assertEqual(intervals[2]['start_page'], 10)
    self.assertEqual(intervals[2]['end_page'], 20)  # End of document

  def test_extract_docling_element_page(self):
    """Test page extraction from DoclingDocument elements."""
    # Element with page info
    element_with_page = {
      'text': 'Test header',
      'prov': [{'page_no': 5, 'bbox': {}}]
    }
    self.assertEqual(extract_docling_element_page(element_with_page), 5)
    
    # Element without page info
    element_without_page = {'text': 'Test header'}
    self.assertEqual(extract_docling_element_page(element_without_page), 0)

  def test_detect_auxiliary_content(self):
    """Test auxiliary content detection."""
    # Table content
    table_result = detect_auxiliary_content('Tabla 1.1 Valores')
    self.assertTrue(table_result['is_auxiliary'])
    self.assertEqual(table_result['type'], 'table')
    
    # Equation content
    equation_result = detect_auxiliary_content('Fórmula 2.3')
    self.assertTrue(equation_result['is_auxiliary']) 
    self.assertEqual(equation_result['type'], 'equation')
    
    # Caption content
    caption_result = detect_auxiliary_content('Figura 1.5 Ejemplo')
    self.assertTrue(caption_result['is_auxiliary'])
    self.assertEqual(caption_result['type'], 'caption')
    
    # Valid heading
    heading_result = detect_auxiliary_content('Sección SI 1 Propagación interior')
    self.assertFalse(heading_result['is_auxiliary'])
    self.assertEqual(heading_result['type'], 'heading')

  def test_split_combined_headings(self):
    """Test splitting of combined headings."""
    # Combined Anejo headings
    combined = 'Anejo SI A Terminología Anejo SI B Referencias'
    split_result = split_combined_headings(combined)
    self.assertEqual(len(split_result), 2)
    self.assertIn('Anejo SI A Terminología', split_result)
    self.assertIn('Anejo SI B Referencias', split_result)
    
    # Single heading (no splitting)
    single = 'Sección SI 1 Propagación interior'
    single_result = split_combined_headings(single)
    self.assertEqual(len(single_result), 1)
    self.assertEqual(single_result[0], single)

  def test_calculate_enhanced_similarity(self):
    """Test enhanced similarity calculation with confidence and page proximity."""
    # High similarity, same page
    result = calculate_enhanced_similarity(
      'Sección SI 1 Propagación interior',
      'Sección SI 1 Propagación interior', 
      5, 5
    )
    self.assertGreater(result['similarity'], 0.9)
    self.assertGreater(result['confidence'], 0.8)
    self.assertEqual(result['page_distance'], 0)
    
    # Structural match with page proximity
    result = calculate_enhanced_similarity(
      'SI 2 Propagación exterior',
      'Sección SI 2 Propagación exterior',
      10, 11
    )
    self.assertGreater(result['similarity'], 0.7)
    self.assertGreater(result['structure_bonus'], 0)
    self.assertEqual(result['page_distance'], 1)

  def test_numbering_key(self):
    """Test numbering key extraction for sibling detection."""
    # Test various numbering patterns
    result1 = numbering_key('11.1 Some text')
    self.assertEqual(result1, ('11', 2))  # prefix=11, depth=2
    
    result2 = numbering_key('E.2.3.2.1 Some text')  
    self.assertEqual(result2, ('E.2.3.2', 5))  # prefix=E.2.3.2, depth=5
    
    result3 = numbering_key('No numbers here')
    self.assertEqual(result3, ('', 0))  # no numbering
    
    result4 = numbering_key('5 Simple number')
    self.assertEqual(result4, ('5', 1))  # prefix=5, depth=1

  def test_build_toc_intervals_with_parent_pointers(self):
    """Test enhanced ToC interval building with parent pointers and IDs."""
    toc_entries = [
      {'level': 1, 'title': 'Chapter 1', 'page': 1},
      {'level': 2, 'title': 'Section 1.1', 'page': 3},
      {'level': 2, 'title': 'Section 1.2', 'page': 5},
      {'level': 1, 'title': 'Chapter 2', 'page': 10}
    ]
    
    intervals = build_toc_intervals(toc_entries, 20)
    
    self.assertEqual(len(intervals), 4)
    
    # Check IDs are assigned
    for i, entry in enumerate(intervals):
      self.assertEqual(entry['id'], i)
    
    # Check parent pointers  
    self.assertIsNone(intervals[0]['parent_idx'])  # Chapter 1, no parent
    self.assertEqual(intervals[1]['parent_idx'], 0)  # Section 1.1 -> Chapter 1
    self.assertEqual(intervals[2]['parent_idx'], 0)  # Section 1.2 -> Chapter 1  
    self.assertIsNone(intervals[3]['parent_idx'])  # Chapter 2, no parent
    
    # Check intervals
    self.assertEqual(intervals[0]['start_page'], 1)
    self.assertEqual(intervals[0]['end_page'], 9)  # Before Chapter 2
    self.assertEqual(intervals[3]['start_page'], 10)
    self.assertEqual(intervals[3]['end_page'], 20)  # End of document

  def test_page_driven_parenting_guardrails(self):
    """Test page-driven parenting with guardrails (Índice, Anejo/Sección separation)."""
    # Test data with Índice (should not parent under it)
    toc_entries = [
      {'level': 1, 'title': 'Índice', 'page': 1, 'id': 0, 'parent_idx': None, 'start_page': 1, 'end_page': 5},
      {'level': 1, 'title': 'Sección SI 1', 'page': 6, 'id': 1, 'parent_idx': None, 'start_page': 6, 'end_page': 20}
    ]
    
    mappings = [
      {
        'toc_idx': 0, 
        'section_header': {'index': 0}, 
        'toc_entry': toc_entries[0]
      },
      {
        'toc_idx': 1,
        'section_header': {'index': 1},
        'toc_entry': toc_entries[1]  
      }
    ]
    
    docling_data = {
      'texts': [
        {'label': 'section_header', 'text': 'Índice', 'level': 1},
        {'label': 'section_header', 'text': 'Sección SI 1 Propagación', 'level': 1, 'prov': [{'page_no': 6}]},
      ]
    }
    
    updated_data = page_driven_parenting(mappings, toc_entries, docling_data)
    
    # Sección should not be parented under Índice due to guardrail
    self.assertEqual(updated_data['texts'][1]['parent']['$ref'], '#/body')

  def test_normalize_text_for_matching(self):
    """Test enhanced normalization that handles footnote references."""
    # Test footnote reference removal
    self.assertEqual(
      normalize_text_for_matching('1 Condiciones de aproximación y entorno (1)'),
      '1condicionesdeaproximacionyentorno'
    )
    
    # Test spaced footnote reference
    self.assertEqual(
      normalize_text_for_matching('B.5 Valor característico ( 1 )'),
      'b5valorcaracteristico'
    )
    
    # Test empty parentheses (specific issue from user comment)
    self.assertEqual(
      normalize_text_for_matching('1 Condiciones de aproximación y entorno( )'),
      '1condicionesdeaproximacionyentorno'
    )
    
    # Test matching between empty parentheses and numbered footnotes
    toc_text = '1 Condiciones de aproximación y entorno( )'
    docling_text = '1 Condiciones de aproximación y entorno (1)'
    self.assertEqual(
      normalize_text_for_matching(toc_text),
      normalize_text_for_matching(docling_text)
    )
    
    # Test Unicode parentheses
    self.assertEqual(
      normalize_text_for_matching('Test （1）'),
      'test'
    )
    
    # Test various invisible characters
    text_with_invisible = '1 Condiciones de aproximación\u200B y entorno( )'
    self.assertEqual(
      normalize_text_for_matching(text_with_invisible),
      '1condicionesdeaproximacionyentorno'
    )
    
    # Test parentheses with symbols
    self.assertEqual(
      normalize_text_for_matching('Section title (*) with symbols'),
      'sectiontitlewithsymbols'
    )
    
    # Test multiple footnote patterns
    result = normalize_text_for_matching('Section title (a) with (1) references')
    self.assertNotIn('(', result)  # All footnotes should be removed
    self.assertIn('section', result)
    
    # Test text without footnotes (should still normalize)
    self.assertEqual(
      normalize_text_for_matching('Normal section title'),
      'normalsectiontitle'
    )

  def test_scan_page_for_text_matches(self):
    """Test page scanning for text matches including table cells."""
    docling_data = {
      'texts': [
        {
          'text': '1 Condiciones de aproximación y entorno (1)',
          'label': 'section_header',
          'prov': [{'page_no': 36}]
        },
        {
          'text': 'Other content',
          'label': 'text', 
          'prov': [{'page_no': 36}]
        }
      ],
      'tables': [
        {
          'prov': [{'page_no': 36}],
          'data': {
            'table_cells': [
              {
                'text': '2 Resistencia al fuego',
                'bbox': {'l': 70, 't': 426, 'r': 202, 'b': 435}
              },
              {
                'text': '',
                'bbox': {'l': 202, 't': 426, 'r': 300, 'b': 435}
              }
            ]
          }
        }
      ]
    }
    
    # Search for text that matches ToC entry with footnote
    matches = scan_page_for_text_matches(
      36, 
      docling_data, 
      '1 Condiciones de aproximación y entorno',
      similarity_threshold=0.6
    )
    
    # Should find at least one match
    self.assertGreater(len(matches), 0)
    
    # The first match should be the section header
    self.assertEqual(matches[0]['type'], 'text')
    self.assertIn('condiciones', matches[0]['text'].lower())
    
    # Search for text that's in table cell
    table_matches = scan_page_for_text_matches(
      36,
      docling_data,
      '2 Resistencia al fuego',
      similarity_threshold=0.6
    )
    
    # Should find the table cell match
    self.assertGreater(len(table_matches), 0)
    table_match = next((m for m in table_matches if m['type'] == 'table_cell'), None)
    self.assertIsNotNone(table_match)
    self.assertIn('resistencia', table_match['text'].lower())

  def test_enhanced_text_similarity_with_footnotes(self):
    """Test that enhanced text similarity handles footnotes properly."""
    # Test similarity with footnote references
    sim1 = calculate_text_similarity(
      '1 Condiciones de aproximación y entorno (1)',
      '1 Condiciones de aproximación y entorno'
    )
    self.assertGreater(sim1, 0.8)  # Should be high similarity despite footnote
    
    # Test similarity with spaced footnote
    sim2 = calculate_text_similarity(
      'B.5 Valor característico de la densidad ( 1 )',
      'B.5 Valor característico de la densidad'
    )
    self.assertGreater(sim2, 0.8)  # Should be high similarity despite footnote

  def test_detect_and_merge_split_headlines(self):
    """Test detection and merging of split headlines."""
    from pdf_toc_extractor import detect_and_merge_split_headlines
    
    # Test data: ToC entry that should match merged sections
    toc_entries = [{
      'title': 'Sección SI 4 Instalaciones de protección contra incendios',
      'page': 32,
      'level': 1
    }]
    
    # DoclingDocument sections that are incorrectly split
    docling_sections = [
      {
        'index': 0,
        'text': 'Sección SI 4',
        'page': 32,
        'original_level': 1
      },
      {
        'index': 1, 
        'text': 'Instalaciones de protección contra incendios',
        'page': 32,
        'original_level': 2
      },
      {
        'index': 2,
        'text': 'Different section',
        'page': 33,
        'original_level': 1
      }
    ]
    
    # Run the split detection
    merged_sections = detect_and_merge_split_headlines(toc_entries, docling_sections)
    
    # Should have merged the first two sections
    self.assertEqual(len(merged_sections), 2)  # One less section after merging
    
    # First section should contain merged text
    merged_section = merged_sections[0]
    self.assertIn('Sección SI 4', merged_section['text'])
    self.assertIn('Instalaciones de protección contra incendios', merged_section['text'])
    self.assertIn('merged_from', merged_section)
    self.assertEqual(len(merged_section['merged_from']), 2)
    
    # Third section should remain unchanged
    self.assertEqual(merged_sections[1]['text'], 'Different section')

  def test_enhanced_parentheses_normalization(self):
    """Test enhanced parentheses handling including Unicode and invisible characters."""
    # Test empty parentheses
    result1 = normalize_text_for_matching('1 Condiciones de aproximación y entorno( )')
    result2 = normalize_text_for_matching('1 Condiciones de aproximación y entorno (1)')
    self.assertEqual(result1, result2)
    
    # Test various Unicode parentheses
    result3 = normalize_text_for_matching('1 Condiciones de aproximación y entorno（１）')
    self.assertEqual(result1, result3)
    
    # Test symbol parentheses
    result4 = normalize_text_for_matching('1 Condiciones de aproximación y entorno (*)')
    self.assertEqual(result1, result4)
    
    # Test lettered footnotes
    result5 = normalize_text_for_matching('1 Condiciones de aproximación y entorno (a)')
    self.assertEqual(result1, result5)

  def test_auxiliary_content_detection_fixed(self):
    """Test that section headers with footnote references are not flagged as auxiliary content."""
    # This should NOT be flagged as auxiliary content
    valid_header = '1 Condiciones de aproximación y entorno (1)'
    result = detect_auxiliary_content(valid_header)
    self.assertFalse(result['is_auxiliary'])
    self.assertEqual(result['type'], 'heading')
    
    # This should still be flagged as equation
    equation = 'A = π × r² (1)'
    eq_result = detect_auxiliary_content(equation)
    self.assertTrue(eq_result['is_auxiliary'])
    self.assertEqual(eq_result['type'], 'equation')
    
    # Another valid header with different footnote
    valid_header2 = 'B.5 Valor característico de la densidad de carga de fuego ( 1 )'
    result2 = detect_auxiliary_content(valid_header2)
    self.assertFalse(result2['is_auxiliary'])
    self.assertEqual(result2['type'], 'heading')


if __name__ == '__main__':
  unittest.main()
