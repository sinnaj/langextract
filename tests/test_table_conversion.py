#!/usr/bin/env python3
"""Tests for table conversion functionality in enhanced chunking."""

import unittest
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction_pipeline.enhanced_chunking import convert_table_to_markdown, extract_section_content
from extraction_pipeline.data_models import EnhancedSection


class TestTableConversion(unittest.TestCase):
    """Test cases for table conversion functionality."""

    def test_convert_simple_table_to_markdown(self):
        """Test conversion of a simple 2x2 table to markdown."""
        table_data = {
            "table_cells": [
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 0,
                    "text": "Header 1"
                },
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 1,
                    "text": "Header 2"
                },
                {
                    "start_row_offset_idx": 1,
                    "start_col_offset_idx": 0,
                    "text": "Cell 1"
                },
                {
                    "start_row_offset_idx": 1,
                    "start_col_offset_idx": 1,
                    "text": "Cell 2"
                }
            ]
        }
        
        result = convert_table_to_markdown(table_data)
        
        # Check structure
        lines = result.split('\n')
        self.assertEqual(len(lines), 3)  # Header, separator, data row
        
        # Check content
        self.assertIn("Header 1", result)
        self.assertIn("Header 2", result)
        self.assertIn("Cell 1", result)
        self.assertIn("Cell 2", result)
        
        # Check markdown structure
        self.assertIn("| Header 1 | Header 2 |", result)
        self.assertIn("| --- | --- |", result)
        self.assertIn("| Cell 1 | Cell 2 |", result)

    def test_convert_empty_table_to_markdown(self):
        """Test conversion of an empty table."""
        table_data = {"table_cells": []}
        result = convert_table_to_markdown(table_data)
        self.assertEqual(result, "")

    def test_convert_table_with_special_characters(self):
        """Test conversion of table with special markdown characters."""
        table_data = {
            "table_cells": [
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 0,
                    "text": "Text with | pipe"
                },
                {
                    "start_row_offset_idx": 0,
                    "start_col_offset_idx": 1,
                    "text": "Text with\nnewline"
                }
            ]
        }
        
        result = convert_table_to_markdown(table_data)
        
        # Check that pipe is escaped
        self.assertIn("Text with \\| pipe", result)
        
        # Check that newlines are replaced with spaces
        self.assertIn("Text with newline", result)

    def test_extract_section_content_with_table(self):
        """Test section content extraction - regular sections no longer include tables."""
        # Create a test section
        section = EnhancedSection.create_with_id(
            toc_path=["Test Section"],
            start_page=1,
            title_normalized="test section",
            section_name="Test Section",
            section_level=1,
            section_index=0,
            parent_section_id=None,
            end_page=1
        )
        
        # Mock docling document with text and table
        mock_docling = {
            "pages": [
                {
                    "page": 1,
                    "elements": [
                        {
                            "type": "text",
                            "text": "This is section content."
                        }
                    ]
                }
            ],
            "tables": [
                {
                    "prov": [{"page_no": 1}],
                    "data": {
                        "table_cells": [
                            {
                                "start_row_offset_idx": 0,
                                "start_col_offset_idx": 0,
                                "text": "Column A"
                            },
                            {
                                "start_row_offset_idx": 0,
                                "start_col_offset_idx": 1,
                                "text": "Column B"
                            }
                        ]
                    }
                }
            ]
        }
        
        content = extract_section_content(section, mock_docling)
        
        # Check that text content is included but table content is NOT
        # (tables now have their own sections)
        self.assertIn("This is section content.", content)
        self.assertNotIn("Column A", content)  # Table content should not be in regular sections
        self.assertNotIn("Column B", content)
        self.assertNotIn("|", content)  # No markdown table structure

    def test_extract_content_for_table_section(self):
        """Test content extraction specifically for table sections."""
        # Create a table section
        table_section = EnhancedSection.create_with_id(
            toc_path=["Test Section", "Table 1"],
            start_page=1,
            title_normalized="table 1",
            section_name="Table 1",
            section_level=2,
            section_index=1,
            parent_section_id="test_section_id",
            end_page=1,
            section_type="Table"
        )
        
        # Mock docling document with table
        mock_docling = {
            "tables": [
                {
                    "prov": [{"page_no": 1}],
                    "data": {
                        "table_cells": [
                            {
                                "start_row_offset_idx": 0,
                                "start_col_offset_idx": 0,
                                "text": "Column A"
                            },
                            {
                                "start_row_offset_idx": 0,
                                "start_col_offset_idx": 1,
                                "text": "Column B"
                            }
                        ]
                    }
                }
            ]
        }
        
        content = extract_section_content(table_section, mock_docling)
        
        # Check that table content is properly extracted as markdown
        self.assertIn("Column A", content)
        self.assertIn("Column B", content)
        self.assertIn("|", content)  # Markdown table structure

    def test_extract_section_content_table_outside_page_range(self):
        """Test that tables outside section page range are not included."""
        # Create a test section for pages 1-2
        section = EnhancedSection.create_with_id(
            toc_path=["Test Section"],
            start_page=1,
            title_normalized="test section",
            section_name="Test Section",
            section_level=1,
            section_index=0,
            parent_section_id=None,
            end_page=2
        )
        
        # Mock docling document with table on page 3 (outside range)
        mock_docling = {
            "pages": [
                {
                    "page": 1,
                    "elements": [
                        {
                            "type": "text",
                            "text": "This is section content."
                        }
                    ]
                }
            ],
            "tables": [
                {
                    "prov": [{"page_no": 3}],  # Outside page range
                    "data": {
                        "table_cells": [
                            {
                                "start_row_offset_idx": 0,
                                "start_col_offset_idx": 0,
                                "text": "Should not appear"
                            }
                        ]
                    }
                }
            ]
        }
        
        content = extract_section_content(section, mock_docling)
        
        # Check that text content is included but table is not
        self.assertIn("This is section content.", content)
        self.assertNotIn("Should not appear", content)


if __name__ == '__main__':
    unittest.main()