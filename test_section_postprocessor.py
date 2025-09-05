#!/usr/bin/env python3
"""Tests for section post-processor functionality."""

import unittest
import tempfile
import os
from section_chunker import create_section_chunks
from chunk_evaluator import evaluate_chunks
from section_postprocessor import (
    post_process_section_evaluations,
    drop_children_of_dropped_sections,
    identify_repeating_section_names,
    handle_repeating_sections
)


class TestSectionPostProcessor(unittest.TestCase):
    """Test cases for section post-processing functionality."""
    
    def setUp(self):
        """Set up test cases."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up temp files if needed
        pass
    
    def _create_test_file(self, content: str) -> str:
        """Create a temporary test file with given content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            return f.name
    
    def _process_markdown(self, content: str):
        """Helper to process markdown content through the full pipeline."""
        chunks = create_section_chunks(content)
        evaluations = evaluate_chunks(chunks)
        return post_process_section_evaluations(evaluations)
    
    def test_drop_children_of_dropped_sections(self):
        """Test that children of dropped sections are properly dropped."""
        content = """# Main Section
Content here.

## Table of Contents
1. Chapter 1 ..................... 5
2. Chapter 2 ..................... 10

### Child of TOC
This should be dropped.

#### Grandchild of TOC
This should also be dropped.

## Normal Section
Normal content."""
        
        result = self._process_markdown(content)
        
        # Should have dropped TOC and its children
        section_names = [chunk.section_metadata.section_name 
                        for chunk, _ in result.processed_evaluations]
        
        self.assertIn("Main Section", section_names)
        self.assertIn("Normal Section", section_names)
        self.assertNotIn("Table of Contents", section_names)
        self.assertNotIn("Child of TOC", section_names)
        self.assertNotIn("Grandchild of TOC", section_names)
        
        # Check processing log
        log_text = " ".join(result.processing_log)
        self.assertIn("Child of TOC", log_text)
        self.assertIn("Grandchild of TOC", log_text)
        self.assertIn("child of dropped section", log_text)
    
    def test_merge_all_manual_sections(self):
        """Test merging of sections all marked for manual processing."""
        content = """# Main Section
Content here.

## Manual Section

### Subsection 1

### Subsection 2

## Manual Section

### Child of Second Manual
Short.

## Normal Section
Normal content with substance."""
        
        result = self._process_markdown(content)
        
        # Should have only one "Manual Section" remaining
        manual_sections = [chunk for chunk, _ in result.processed_evaluations 
                          if chunk.section_metadata.section_name == "Manual Section"]
        
        self.assertEqual(len(manual_sections), 1)
        
        # Child should point to the remaining manual section
        remaining_manual_id = manual_sections[0].section_metadata.section_id
        child_section = next(chunk for chunk, _ in result.processed_evaluations 
                           if chunk.section_metadata.section_name == "Child of Second Manual")
        self.assertEqual(child_section.section_metadata.parent_section_id, remaining_manual_id)
        
        # Check merge info
        self.assertTrue(len(result.merged_sections) > 0)
    
    def test_mixed_manual_extraction_sections(self):
        """Test handling of mixed manual/extraction sections."""
        content = """# Main Section
Content here.

## Mixed Section
This section has proper content for extraction.

## Mixed Section

### Child of Mixed
Short.

## Normal Section
Normal content."""
        
        result = self._process_markdown(content)
        
        # Should have only one "Mixed Section" remaining (the extraction one)
        mixed_sections = [chunk for chunk, _ in result.processed_evaluations 
                         if chunk.section_metadata.section_name == "Mixed Section"]
        
        self.assertEqual(len(mixed_sections), 1)
        
        # The remaining section should be marked for extraction
        remaining_eval = next(eval for chunk, eval in result.processed_evaluations 
                            if chunk.section_metadata.section_name == "Mixed Section")
        self.assertEqual(remaining_eval.processing_type, "extract")
        
        # Child should point to the extraction section
        remaining_mixed_id = mixed_sections[0].section_metadata.section_id
        child_section = next(chunk for chunk, _ in result.processed_evaluations 
                           if chunk.section_metadata.section_name == "Child of Mixed")
        self.assertEqual(child_section.section_metadata.parent_section_id, remaining_mixed_id)
    
    def test_all_extraction_sections(self):
        """Test handling of duplicate sections all marked for extraction."""
        content = """# Main Section
Content here.

## Extract Section
Content here for first section.

## Extract Section
More content here for second section.

### Child of Second Extract
Child content.

## Normal Section
Normal content."""
        
        result = self._process_markdown(content)
        
        # Should have only one "Extract Section" remaining
        extract_sections = [chunk for chunk, _ in result.processed_evaluations 
                           if chunk.section_metadata.section_name == "Extract Section"]
        
        self.assertEqual(len(extract_sections), 1)
        
        # Should be the highest level (first) one
        remaining_section = extract_sections[0]
        self.assertEqual(remaining_section.section_metadata.section_level, 2)
        
        # Child should point to the remaining section
        remaining_id = remaining_section.section_metadata.section_id
        child_section = next(chunk for chunk, _ in result.processed_evaluations 
                           if chunk.section_metadata.section_name == "Child of Second Extract")
        self.assertEqual(child_section.section_metadata.parent_section_id, remaining_id)
    
    def test_different_levels_priority(self):
        """Test that higher level (lower number) sections are prioritized."""
        content = """# Main Section
Content here.

## Level 2 Section
Content here.

### Level 2 Section
More content at level 3.

#### Level 2 Section
Content at level 4.

## Normal Section
Normal content."""
        
        result = self._process_markdown(content)
        
        # Should keep the level 2 section (highest level = lowest number)
        sections = [chunk for chunk, _ in result.processed_evaluations 
                   if chunk.section_metadata.section_name == "Level 2 Section"]
        
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].section_metadata.section_level, 2)
    
    def test_no_repeating_sections(self):
        """Test behavior when there are no repeating section names."""
        content = """# Main Section
Content here.

## Section A
Content A.

## Section B
Content B.

## Table of Contents
1. Chapter 1 ..................... 5

## Section C
Content C."""
        
        result = self._process_markdown(content)
        
        # Should process normally, only dropping TOC
        section_names = [chunk.section_metadata.section_name 
                        for chunk, _ in result.processed_evaluations]
        
        self.assertIn("Main Section", section_names)
        self.assertIn("Section A", section_names)
        self.assertIn("Section B", section_names)
        self.assertIn("Section C", section_names)
        self.assertNotIn("Table of Contents", section_names)
        
        # Should have no merged sections
        self.assertEqual(len(result.merged_sections), 0)
    
    def test_identify_repeating_section_names(self):
        """Test the function that identifies repeating section names."""
        content = """# Main
Content.

## Section A
Content A1.

## Section B
Content B.

## Section A
Content A2.

## Section C
Content C.

## Section A
Content A3."""
        
        chunks = create_section_chunks(content)
        evaluations = evaluate_chunks(chunks)
        
        repeating = identify_repeating_section_names(evaluations)
        
        # Should identify "Section A" as repeating
        self.assertIn("Section A", repeating)
        self.assertEqual(len(repeating["Section A"]), 3)
        
        # Should not include single sections
        self.assertNotIn("Section B", repeating)
        self.assertNotIn("Section C", repeating)


if __name__ == "__main__":
    unittest.main()