# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for langextract.preprocessing.headings module."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from langextract.preprocessing.headings import (
    OutlineHeading,
    _is_anchor,
    _numbering_level,
    _bbox_height,
    _vertical_gap,
    infer_outline_from_json,
    to_markdown,
    load_config,
    main
)


class TestAnchorPatterns(unittest.TestCase):
  """Test anchor pattern matching."""
  
  def test_spanish_section_patterns(self):
    """Test Spanish section patterns."""
    self.assertTrue(_is_anchor("Sección SI 2 Propagación exterior"))
    self.assertTrue(_is_anchor("Sección 3 Resistencia al fuego"))
    self.assertTrue(_is_anchor("  Sección SI 1  "))  # With whitespace
    self.assertTrue(_is_anchor("sección si 2"))  # Case insensitive
    
  def test_chapter_patterns(self):
    """Test chapter patterns."""
    self.assertTrue(_is_anchor("Capítulo 1"))
    self.assertTrue(_is_anchor("Capítulo IV"))
    self.assertTrue(_is_anchor("Capitulo 5"))  # Without accent
    
  def test_title_patterns(self):
    """Test title patterns."""
    self.assertTrue(_is_anchor("Título A"))
    self.assertTrue(_is_anchor("Título 1"))
    self.assertTrue(_is_anchor("Titulo B"))  # Without accent
    
  def test_appendix_patterns(self):
    """Test appendix patterns."""
    self.assertTrue(_is_anchor("Anexo A"))
    self.assertTrue(_is_anchor("Anexo 1"))
    self.assertTrue(_is_anchor("Apéndice B"))
    self.assertTrue(_is_anchor("Apendice 2"))  # Without accent
    
  def test_non_anchor_text(self):
    """Test that regular text doesn't match anchor patterns."""
    self.assertFalse(_is_anchor("Regular heading"))
    self.assertFalse(_is_anchor("1 Medianerías y fachadas"))
    self.assertFalse(_is_anchor("Some random text"))


class TestNumberingLevel(unittest.TestCase):
  """Test numbering level detection."""
  
  def test_multi_level_numbering(self):
    """Test multi-level numbering (e.g., 1.2.3)."""
    self.assertEqual(_numbering_level("1.2"), 3)  # count('.') + 2
    self.assertEqual(_numbering_level("1.2.3"), 4)
    self.assertEqual(_numbering_level("1.2.3.4"), 5)
    
  def test_single_level_numbering(self):
    """Test single level numbering."""
    self.assertEqual(_numbering_level("1"), 2)
    self.assertEqual(_numbering_level("123"), 2)
    self.assertEqual(_numbering_level("  1  "), 2)
    
  def test_letter_numbering(self):
    """Test letter numbering."""
    self.assertEqual(_numbering_level("A."), 2)
    self.assertEqual(_numbering_level("Z."), 2)
    
  def test_roman_numbering(self):
    """Test Roman numeral numbering."""
    self.assertEqual(_numbering_level("I."), 2)
    self.assertEqual(_numbering_level("IV."), 2)
    self.assertEqual(_numbering_level("XIV."), 2)
    
  def test_no_numbering(self):
    """Test text without numbering."""
    self.assertIsNone(_numbering_level("Regular text"))
    self.assertIsNone(_numbering_level("Benefits of something"))
    self.assertIsNone(_numbering_level("Sección SI 2"))  # This is an anchor


class TestBboxHeight(unittest.TestCase):
  """Test bbox height calculation."""
  
  def test_dict_format_ltrb(self):
    """Test bbox in dict format with l,t,r,b keys."""
    bbox = {'l': 10, 't': 100, 'r': 50, 'b': 80}
    self.assertEqual(_bbox_height(bbox), 20)  # |100 - 80|
    
  def test_dict_format_full_names(self):
    """Test bbox in dict format with full names."""
    bbox = {'left': 10, 'top': 100, 'right': 50, 'bottom': 80}
    self.assertEqual(_bbox_height(bbox), 20)  # |100 - 80|
    
  def test_tuple_format(self):
    """Test bbox in tuple format (l, t, r, b)."""
    bbox = (10, 100, 50, 80)
    self.assertEqual(_bbox_height(bbox), 20)  # |100 - 80|
    
  def test_none_bbox(self):
    """Test None bbox."""
    self.assertIsNone(_bbox_height(None))
    
  def test_invalid_bbox(self):
    """Test invalid bbox formats."""
    self.assertIsNone(_bbox_height({}))
    self.assertIsNone(_bbox_height([1, 2]))  # Too short
    self.assertIsNone(_bbox_height("invalid"))


class TestVerticalGap(unittest.TestCase):
  """Test vertical gap calculation."""
  
  def test_same_page_gap(self):
    """Test gap calculation on same page."""
    curr = {
      'bbox': {'l': 10, 't': 100, 'r': 50, 'b': 80},
      'page_no': 1
    }
    next_header = {
      'bbox': {'l': 10, 't': 120, 'r': 50, 'b': 110},
      'page_no': 1
    }
    self.assertEqual(_vertical_gap(curr, next_header), 40)  # 120 - 80
    
  def test_different_pages(self):
    """Test gap calculation across different pages."""
    curr = {'bbox': {'l': 10, 't': 100, 'r': 50, 'b': 80}, 'page_no': 1}
    next_header = {'bbox': {'l': 10, 't': 20, 'r': 50, 'b': 10}, 'page_no': 2}
    self.assertEqual(_vertical_gap(curr, next_header), 9999.0)
    
  def test_missing_data(self):
    """Test gap calculation with missing data."""
    self.assertEqual(_vertical_gap(None, None), 9999.0)
    self.assertEqual(_vertical_gap({}, None), 9999.0)
    self.assertEqual(_vertical_gap(None, {}), 9999.0)


class TestInferOutlineFromJson(unittest.TestCase):
  """Test outline inference from JSON."""
  
  def setUp(self):
    """Set up test data."""
    self.test_doc = {
      'body': {
        'children': [
          {'cref': '#/texts/0'},
          {'cref': '#/texts/1'},
          {'cref': '#/texts/2'}
        ]
      },
      'texts': [
        {
          'self_ref': '#/texts/0',
          'text': 'Sección SI 2 Propagación exterior',
          'label': 'section_header',
          'prov': [{'page_no': 1, 'bbox': {'l': 10, 't': 100, 'r': 200, 'b': 80}}]
        },
        {
          'self_ref': '#/texts/1', 
          'text': '1 Medianerías y fachadas',
          'label': 'section_header',
          'prov': [{'page_no': 1, 'bbox': {'l': 10, 't': 140, 'r': 200, 'b': 125}}]
        },
        {
          'self_ref': '#/texts/2',
          'text': 'Regular section heading',
          'label': 'section_header', 
          'prov': [{'page_no': 1, 'bbox': {'l': 10, 't': 180, 'r': 200, 'b': 170}}]
        }
      ]
    }
  
  def test_acceptance_criteria(self):
    """Test the acceptance criteria from problem statement."""
    outline = infer_outline_from_json(self.test_doc)
    
    # Should have 3 headings
    self.assertEqual(len(outline), 3)
    
    # First heading should be level 1 (anchor)
    self.assertEqual(outline[0].level, 1)
    self.assertEqual(outline[0].text, 'Sección SI 2 Propagación exterior')
    self.assertTrue(outline[0].signals.get('anchor', False))
    
    # Second heading should be level 2 (numbering) 
    self.assertEqual(outline[1].level, 2)
    self.assertEqual(outline[1].text, '1 Medianerías y fachadas')
    self.assertEqual(outline[1].signals.get('num_level'), 2)
    
    # Third heading should be clamped to level 3 (no jump > 1)
    self.assertEqual(outline[2].level, 3)
  
  def test_empty_document(self):
    """Test with empty document."""
    empty_doc = {'body': None, 'texts': []}
    outline = infer_outline_from_json(empty_doc)
    self.assertEqual(len(outline), 0)
  
  def test_no_section_headers(self):
    """Test document with no section headers."""
    doc = {
      'body': {'children': [{'cref': '#/texts/0'}]},
      'texts': [{'self_ref': '#/texts/0', 'text': 'Regular text', 'label': 'text'}]
    }
    outline = infer_outline_from_json(doc)
    self.assertEqual(len(outline), 0)


class TestToMarkdown(unittest.TestCase):
  """Test Markdown conversion."""
  
  def test_markdown_output(self):
    """Test conversion to Markdown format."""
    outline = [
      OutlineHeading(1, "Main Title", None, None, None, {}),
      OutlineHeading(2, "Section 1", None, None, None, {}),
      OutlineHeading(3, "Subsection 1.1", None, None, None, {}),
      OutlineHeading(2, "Section 2", None, None, None, {})
    ]
    
    expected = "# Main Title\n## Section 1\n### Subsection 1.1\n## Section 2"
    self.assertEqual(to_markdown(outline), expected)
  
  def test_empty_outline(self):
    """Test empty outline."""
    self.assertEqual(to_markdown([]), "")


class TestLoadConfig(unittest.TestCase):
  """Test configuration loading."""
  
  def test_load_json_config(self):
    """Test loading JSON configuration."""
    config_data = {
      'GAP_THRESHOLD': 25.0,
      'ANCHOR_PATTERNS': [r'^\s*Test\s+\d+\b']
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
      json.dump(config_data, f)
      config_path = f.name
    
    try:
      # Import here to avoid circular imports
      from langextract.postprocess import headings
      original_gap = headings.GAP_THRESHOLD
      
      load_config(config_path)
      
      # Check that values were updated
      self.assertEqual(headings.GAP_THRESHOLD, 25.0)
      self.assertEqual(len(headings.ANCHOR_PATTERNS), 1)
      
      # Restore original value
      headings.GAP_THRESHOLD = original_gap
      
    finally:
      os.unlink(config_path)
  
  def test_load_invalid_config(self):
    """Test loading invalid configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
      f.write("invalid json")
      config_path = f.name
    
    try:
      # Should not raise exception, just print warning
      load_config(config_path)
    finally:
      os.unlink(config_path)


class TestCLI(unittest.TestCase):
  """Test CLI functionality."""
  
  def test_main_function(self):
    """Test main CLI function."""
    test_doc = {
      'body': {'children': [{'cref': '#/texts/0'}]},
      'texts': [{
        'self_ref': '#/texts/0',
        'text': 'Test Header',
        'label': 'section_header',
        'prov': []
      }]
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
      # Create input file
      input_path = os.path.join(tmpdir, 'input.json')
      with open(input_path, 'w') as f:
        json.dump(test_doc, f)
      
      # Set up output paths
      output_path = os.path.join(tmpdir, 'output.json')
      md_path = os.path.join(tmpdir, 'output.md')
      
      # Mock sys.argv to simulate command line arguments
      test_args = ['headings', input_path, output_path, '--md', md_path]
      
      with patch('sys.argv', test_args):
        main()
      
      # Check that output files were created
      self.assertTrue(os.path.exists(output_path))
      self.assertTrue(os.path.exists(md_path))
      
      # Check JSON output
      with open(output_path) as f:
        output_data = json.load(f)
      self.assertIsInstance(output_data, list)
      
      # Check Markdown output
      with open(md_path) as f:
        md_content = f.read()
      self.assertIn('Test Header', md_content)


if __name__ == '__main__':
  unittest.main()