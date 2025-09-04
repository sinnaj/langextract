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

"""Tests for section-based chunking functionality."""

from absl.testing import absltest

from langextract import section_chunking
from langextract.core import data


class SectionChunkingTest(absltest.TestCase):

  def test_parse_markdown_sections_basic(self):
    """Test basic markdown section parsing."""
    text = """# Main Title

Content for main section.

## Section 1

Content for section 1.

### Subsection 1.1

Content for subsection.

## Section 2

Content for section 2.
"""
    
    sections = section_chunking.parse_markdown_sections(text)
    
    self.assertEqual(len(sections), 4)
    
    # Check first section
    _, metadata, _, _ = sections[0]
    self.assertEqual(metadata.section_name, "Main Title")
    self.assertEqual(metadata.section_level, 1)
    self.assertIsNone(metadata.parent_section_id)
    self.assertEqual(len(metadata.sub_sections), 2)
    
    # Check second section
    _, metadata, _, _ = sections[1]
    self.assertEqual(metadata.section_name, "Section 1")
    self.assertEqual(metadata.section_level, 2)
    self.assertEqual(metadata.parent_section_id, "section_001")
    
    # Check subsection
    _, metadata, _, _ = sections[2]
    self.assertEqual(metadata.section_name, "Subsection 1.1")
    self.assertEqual(metadata.section_level, 3)
    self.assertEqual(metadata.parent_section_id, "section_002")

  def test_section_chunk_iterator(self):
    """Test the section chunk iterator."""
    text = """# Header 1

Content 1.

## Header 2

Content 2.
"""
    
    document = data.Document(text=text, document_id="test_doc")
    iterator = section_chunking.SectionChunkIterator(document)
    
    chunks = list(iterator)
    self.assertEqual(len(chunks), 2)
    
    # Check first chunk
    chunk1 = chunks[0]
    self.assertEqual(chunk1.section_metadata.section_name, "Header 1")
    self.assertEqual(chunk1.section_metadata.section_level, 1)
    self.assertTrue(chunk1.chunk_text.startswith("# Header 1"))
    
    # Check second chunk
    chunk2 = chunks[1]
    self.assertEqual(chunk2.section_metadata.section_name, "Header 2")
    self.assertEqual(chunk2.section_metadata.section_level, 2)
    self.assertEqual(chunk2.section_metadata.parent_section_id, "section_001")

  def test_empty_document(self):
    """Test handling of empty document."""
    text = ""
    sections = section_chunking.parse_markdown_sections(text)
    self.assertEqual(len(sections), 0)

  def test_no_headers(self):
    """Test document with no markdown headers."""
    text = "Just plain text content without any headers."
    sections = section_chunking.parse_markdown_sections(text)
    self.assertEqual(len(sections), 1)
    
    # Should create a default section
    _, metadata, _, _ = sections[0]
    self.assertEqual(metadata.section_name, "Introduction")
    self.assertEqual(metadata.section_level, 1)


if __name__ == '__main__':
  absltest.main()