#!/usr/bin/env python3
"""Test enhanced table section creation functionality."""

import unittest
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extraction_pipeline.enhanced_chunking import (
    create_enhanced_sections_from_toc, 
    create_table_sections_from_docling,
    extract_section_content
)
from extraction_pipeline.data_models import EnhancedSection


class TestEnhancedTableSections(unittest.TestCase):
    """Test cases for enhanced table section functionality."""

    def test_create_table_sections_from_docling(self):
        """Test creation of table sections from Docling document."""
        # Create a mock docling document with tables
        docling_document = {
            "tables": [
                {
                    "prov": [{"page_no": 2}],
                    "data": {
                        "table_cells": [
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Column 1"},
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "Column 2"}
                        ]
                    }
                },
                {
                    "prov": [{"page_no": 3}],
                    "data": {
                        "table_cells": [
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Header A"},
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "Header B"}
                        ]
                    }
                }
            ]
        }
        
        # Create existing sections that tables can belong to
        existing_sections = [
            EnhancedSection(
                section_id="section_001",
                section_name="Introduction", 
                section_level=1,
                section_index=0,
                toc_path=["Introduction"],
                start_page=1,
                end_page=3,
                section_type="Headline"
            )
        ]
        
        # Create table sections
        table_sections = create_table_sections_from_docling(docling_document, existing_sections, 1)
        
        # Verify we got 2 table sections
        self.assertEqual(len(table_sections), 2)
        
        # Check first table section
        table1 = table_sections[0]
        self.assertEqual(table1.section_name, "Table 1")
        self.assertEqual(table1.section_type, "Table")
        self.assertEqual(table1.start_page, 2)
        self.assertEqual(table1.end_page, 2)
        self.assertEqual(table1.parent_section_id, "section_001")
        self.assertEqual(table1.toc_path, ["Introduction", "Table 1"])
        self.assertEqual(table1.section_level, 2)  # One level deeper than parent
        
        # Check second table section
        table2 = table_sections[1]
        self.assertEqual(table2.section_name, "Table 2")
        self.assertEqual(table2.section_type, "Table")
        self.assertEqual(table2.start_page, 3)
        self.assertEqual(table2.parent_section_id, "section_001")
        
        # Verify parent section now has table sections as children
        self.assertIn(table1.section_id, existing_sections[0].sub_section_ids)
        self.assertIn(table2.section_id, existing_sections[0].sub_section_ids)

    def test_create_enhanced_sections_from_toc_includes_tables(self):
        """Test that create_enhanced_sections_from_toc includes table sections."""
        # Mock ToC data
        toc_data = [
            {
                "title": "Chapter 1",
                "level": 1,
                "start_page": 1,
                "end_page": 5,
                "children": []
            }
        ]
        
        # Mock docling document with table
        docling_document = {
            "tables": [
                {
                    "prov": [{"page_no": 3}],
                    "data": {
                        "table_cells": [
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Data 1"},
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "Data 2"}
                        ]
                    }
                }
            ]
        }
        
        # Create sections
        sections = create_enhanced_sections_from_toc(toc_data, docling_document)
        
        # Should have 2 sections: 1 ToC section + 1 table section
        self.assertEqual(len(sections), 2)
        
        # Check regular section
        chapter_section = sections[0]
        self.assertEqual(chapter_section.section_name, "Chapter 1")
        self.assertEqual(chapter_section.section_type, "Headline")
        
        # Check table section
        table_section = sections[1]
        self.assertEqual(table_section.section_name, "Table 1")
        self.assertEqual(table_section.section_type, "Table")
        self.assertEqual(table_section.parent_section_id, chapter_section.section_id)

    def test_extract_content_for_table_section(self):
        """Test content extraction for table sections."""
        # Create a table section
        table_section = EnhancedSection(
            section_id="table_001",
            section_name="Table 1",
            section_level=2,
            section_index=1,
            toc_path=["Chapter", "Table 1"],
            start_page=2,
            end_page=2,
            section_type="Table"
        )
        
        # Mock docling document
        docling_document = {
            "tables": [
                {
                    "prov": [{"page_no": 2}],
                    "data": {
                        "table_cells": [
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Name"},
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 1, "text": "Value"},
                            {"start_row_offset_idx": 1, "start_col_offset_idx": 0, "text": "Temperature"},
                            {"start_row_offset_idx": 1, "start_col_offset_idx": 1, "text": "25°C"}
                        ]
                    }
                }
            ]
        }
        
        # Extract content
        content = extract_section_content(table_section, docling_document)
        
        # Should be markdown table
        self.assertIn("| Name | Value |", content)
        self.assertIn("| Temperature | 25°C |", content)
        self.assertIn("---", content)  # Table separator

    def test_extract_content_for_regular_section_excludes_tables(self):
        """Test that regular sections no longer include tables in their content."""
        # Create a regular section
        regular_section = EnhancedSection(
            section_id="section_001",
            section_name="Chapter 1",
            section_level=1,
            section_index=0,
            toc_path=["Chapter 1"],
            start_page=1,
            end_page=3,
            section_type="Headline"
        )
        
        # Mock docling document with both text and table content
        docling_document = {
            "pages": [
                {
                    "page": 2,
                    "elements": [
                        {"type": "text", "text": "This is regular text content."},
                        {"type": "text", "text": "More text content here."}
                    ]
                }
            ],
            "tables": [
                {
                    "prov": [{"page_no": 2}],  # Table on same page
                    "data": {
                        "table_cells": [
                            {"start_row_offset_idx": 0, "start_col_offset_idx": 0, "text": "Should not appear"}
                        ]
                    }
                }
            ]
        }
        
        # Extract content
        content = extract_section_content(regular_section, docling_document)
        
        # Should contain text but NOT table content
        self.assertIn("This is regular text content.", content)
        self.assertIn("More text content here.", content)
        self.assertNotIn("Should not appear", content)  # Table content should be excluded


if __name__ == '__main__':
    unittest.main()