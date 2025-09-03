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

"""Tests for hierarchical inference functionality."""

import unittest
from langextract import hierarchy_inference
from langextract.core import data


class HierarchyInferenceTest(unittest.TestCase):
    """Test hierarchical relationship inference."""

    def test_infer_section_hierarchy(self):
        """Test section hierarchy inference."""
        sections = [
            data.Extraction(
                extraction_class="SECTION",
                extraction_text="# Chapter 1",
                attributes={
                    "id": "ch1",
                    "section_title": "Chapter 1",
                    "section_level": 1,
                    "sectioning_type": "Chapter"
                }
            ),
            data.Extraction(
                extraction_class="SECTION", 
                extraction_text="## 1.1 Section",
                attributes={
                    "id": "sec1-1",
                    "section_title": "1.1 Section",
                    "section_level": 2,
                    "sectioning_type": "Headline"
                    # Missing parent_id - should be inferred
                }
            ),
            data.Extraction(
                extraction_class="SECTION",
                extraction_text="### 1.1.1 Subsection", 
                attributes={
                    "id": "subsec1-1-1",
                    "section_title": "1.1.1 Subsection",
                    "section_level": 3,
                    "sectioning_type": "Headline"
                    # Missing parent_id - should be inferred
                }
            )
        ]
        
        result = hierarchy_inference.infer_hierarchical_relationships(sections)
        
        # Check that parent relationships were inferred
        self.assertEqual(len(result), 3)
        
        # First section (level 1) should have no parent
        ch1 = next(e for e in result if e.attributes.get("id") == "ch1")
        self.assertIsNone(ch1.attributes.get("parent_id"))
        
        # Second section (level 2) should have ch1 as parent
        sec1_1 = next(e for e in result if e.attributes.get("id") == "sec1-1")
        self.assertEqual(sec1_1.attributes.get("parent_id"), "ch1")
        self.assertEqual(sec1_1.attributes.get("parent_type"), "Chapter")
        
        # Third section (level 3) should have sec1-1 as parent
        subsec1_1_1 = next(e for e in result if e.attributes.get("id") == "subsec1-1-1")
        self.assertEqual(subsec1_1_1.attributes.get("parent_id"), "sec1-1")
        self.assertEqual(subsec1_1_1.attributes.get("parent_type"), "Headline")

    def test_infer_norm_parent_relationships(self):
        """Test norm parent section relationship inference."""
        sections = [
            data.Extraction(
                extraction_class="SECTION",
                extraction_text="# Safety Requirements",
                attributes={
                    "id": "safety-sec",
                    "section_title": "Safety Requirements"
                }
            )
        ]
        
        norms = [
            data.Extraction(
                extraction_class="NORM",
                extraction_text="Buildings must be safe",
                attributes={
                    "id": "norm1",
                    "norm_statement": "Buildings must be safe"
                    # Missing parent_section_id - should be inferred  
                }
            )
        ]
        
        all_extractions = sections + norms
        result = hierarchy_inference.infer_hierarchical_relationships(all_extractions)
        
        # Find the norm in the result
        norm = next(e for e in result if e.extraction_class == "NORM")
        
        # Check that parent section was inferred
        self.assertEqual(norm.attributes.get("parent_section_id"), "safety-sec")

    def test_mixed_extraction_types(self):
        """Test with mixed extraction types including non-hierarchical ones."""
        extractions = [
            data.Extraction(
                extraction_class="SECTION",
                extraction_text="# Introduction",
                attributes={
                    "id": "intro",
                    "section_title": "Introduction",
                    "section_level": 1
                }
            ),
            data.Extraction(
                extraction_class="NORM",
                extraction_text="Must comply with regulations",
                attributes={
                    "id": "norm1",
                    "norm_statement": "Must comply with regulations"
                }
            ),
            data.Extraction(
                extraction_class="TABLE",
                extraction_text="Table 1: Values",
                attributes={
                    "id": "table1",
                    "table_title": "Values"
                }
            )
        ]
        
        result = hierarchy_inference.infer_hierarchical_relationships(extractions)
        
        # Should return all extractions
        self.assertEqual(len(result), 3)
        
        # Check that section is unchanged (no parent needed)
        section = next(e for e in result if e.extraction_class == "SECTION")
        self.assertIsNone(section.attributes.get("parent_id"))
        
        # Check that norm got parent section assigned
        norm = next(e for e in result if e.extraction_class == "NORM")
        self.assertEqual(norm.attributes.get("parent_section_id"), "intro")
        
        # Check that other extraction types are preserved
        table = next(e for e in result if e.extraction_class == "TABLE")
        self.assertEqual(table.attributes.get("id"), "table1")

    def test_empty_extractions(self):
        """Test with empty list of extractions."""
        result = hierarchy_inference.infer_hierarchical_relationships([])
        self.assertEqual(result, [])

    def test_sections_with_existing_parents(self):
        """Test that sections with existing parent_id are not modified."""
        sections = [
            data.Extraction(
                extraction_class="SECTION",
                extraction_text="## 1.1 Section",
                attributes={
                    "id": "sec1-1",
                    "section_title": "1.1 Section", 
                    "section_level": 2,
                    "parent_id": "existing-parent",
                    "parent_type": "Chapter"
                }
            )
        ]
        
        result = hierarchy_inference.infer_hierarchical_relationships(sections)
        
        # Should preserve existing parent
        section = result[0]
        self.assertEqual(section.attributes.get("parent_id"), "existing-parent")
        self.assertEqual(section.attributes.get("parent_type"), "Chapter")


class DocumentStructureContextTest(unittest.TestCase):
    """Test document structure context extraction."""

    def test_extract_document_structure_context(self):
        """Test extraction of document structure context."""
        from langextract.chunking import _extract_document_structure_context
        
        text = """
# Chapter 1: Introduction

Some introductory text.

## 1.1 Overview

Overview content.

### 1.1.1 Details

Detailed information.

## 1.2 Summary

Summary content.

# Chapter 2: Main Content  

Main content here.
"""
        
        context = _extract_document_structure_context(text)
        
        self.assertIn("Document Structure:", context)
        self.assertIn("- Chapter 1: Introduction", context)
        self.assertIn("  - 1.1 Overview", context)
        self.assertIn("    - 1.1.1 Details", context)
        self.assertIn("  - 1.2 Summary", context)
        self.assertIn("- Chapter 2: Main Content", context)

    def test_extract_document_structure_context_no_headers(self):
        """Test with text that has no headers."""
        from langextract.chunking import _extract_document_structure_context
        
        text = "Just plain text with no headers."
        context = _extract_document_structure_context(text)
        
        self.assertEqual(context, "")

    def test_extract_document_structure_context_max_length(self):
        """Test context length limiting."""
        from langextract.chunking import _extract_document_structure_context
        
        # Create text with many headers
        text = "\n".join([f"# Header {i}" for i in range(100)])
        
        context = _extract_document_structure_context(text, max_context_length=100)
        
        # Should be limited in length
        self.assertLessEqual(len(context), 150)  # Some buffer for "Document Structure:" prefix


if __name__ == "__main__":
    unittest.main()