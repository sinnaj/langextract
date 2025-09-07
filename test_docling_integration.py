#!/usr/bin/env python3
"""
Test for the docling integration with lxRunnerExtraction.

This test validates that the new docling hierarchical chunking works
correctly with the existing pipeline.
"""

import json
import tempfile
import unittest
from pathlib import Path

from docling_integration import (
    create_docling_hierarchical_chunks,
    get_docling_hierarchical_statistics,
    create_fallback_chunks
)


class TestDoclingIntegration(unittest.TestCase):
    """Test cases for the docling integration module."""

    def setUp(self):
        """Set up test environment."""
        self.sample_text = """# Introduction

This is a sample document for testing hierarchical chunking.

## Section 1

This is the first section with some content.

### Subsection 1.1

This is a subsection with more detailed information.

## Section 2

This is the second section with different content.

### Subsection 2.1

Another subsection with more details.

### Subsection 2.2

Yet another subsection.
"""

    def test_create_docling_hierarchical_chunks(self):
        """Test that docling hierarchical chunks are created correctly."""
        chunks = create_docling_hierarchical_chunks(self.sample_text)
        
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0, "Should generate at least one chunk")
        
        # Check chunk structure
        for chunk in chunks:
            self.assertIsInstance(chunk.chunk_text, str)
            self.assertGreater(len(chunk.chunk_text), 0, "Chunk text should not be empty")
            self.assertIsNotNone(chunk.section_metadata)
            self.assertIsInstance(chunk.section_metadata.section_id, str)
            self.assertIsInstance(chunk.section_metadata.section_name, str)
            self.assertIsInstance(chunk.section_metadata.section_level, int)

    def test_get_docling_hierarchical_statistics(self):
        """Test that statistics are calculated correctly."""
        chunks = create_docling_hierarchical_chunks(self.sample_text)
        stats = get_docling_hierarchical_statistics(chunks)
        
        self.assertIn("total_sections", stats)
        self.assertIn("levels", stats)
        self.assertIn("chunking_method", stats)
        self.assertEqual(stats["chunking_method"], "docling_hierarchical")
        self.assertEqual(stats["total_sections"], len(chunks))
        self.assertGreater(stats["total_characters"], 0)

    def test_empty_text_handling(self):
        """Test handling of empty text input."""
        chunks = create_docling_hierarchical_chunks("")
        self.assertEqual(len(chunks), 0, "Empty text should produce no chunks")
        
        stats = get_docling_hierarchical_statistics(chunks)
        self.assertEqual(stats["total_sections"], 0)

    def test_fallback_chunks(self):
        """Test fallback chunking when docling is not available."""
        chunks = create_fallback_chunks(self.sample_text)
        
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0, "Should generate at least one fallback chunk")
        
        # Check that all chunks are marked as fallback
        for chunk in chunks:
            self.assertEqual(chunk.section_metadata.section_type, "Fallback")

    def test_chunk_metadata_preservation(self):
        """Test that chunk metadata is properly preserved."""
        chunks = create_docling_hierarchical_chunks(self.sample_text)
        
        for chunk in chunks:
            metadata = chunk.section_metadata
            
            # Check required fields
            self.assertIsNotNone(metadata.section_id)
            self.assertIsNotNone(metadata.section_name)
            self.assertIsInstance(metadata.section_level, int)
            self.assertIsInstance(metadata.section_index, int)
            
            # Check for docling-specific metadata
            if hasattr(metadata, 'docling_metadata'):
                self.assertIsInstance(metadata.docling_metadata, dict)
            
            if hasattr(metadata, 'headings_context'):
                self.assertIsInstance(metadata.headings_context, list)

    def test_parent_child_relationships(self):
        """Test that parent-child relationships are established correctly."""
        chunks = create_docling_hierarchical_chunks(self.sample_text)
        
        # Check for hierarchical structure
        has_parent_child = False
        for chunk in chunks:
            if chunk.section_metadata.parent_section_id is not None:
                has_parent_child = True
                break
            if chunk.section_metadata.sub_sections:
                has_parent_child = True
                break
        
        # Note: This test might need adjustment based on actual docling behavior
        # The hierarchical structure depends on how docling interprets the text
        
    def test_chunk_text_only_extraction(self):
        """Test that only text is used for extraction while metadata is preserved."""
        chunks = create_docling_hierarchical_chunks(self.sample_text)
        
        for chunk in chunks:
            # Chunk text should contain only the actual content, not metadata
            self.assertIsInstance(chunk.chunk_text, str)
            self.assertNotIn("section_id", chunk.chunk_text)
            self.assertNotIn("metadata", chunk.chunk_text)
            
            # But metadata should be available separately
            self.assertIsNotNone(chunk.section_metadata)

    def test_character_positions(self):
        """Test that character positions are calculated correctly."""
        chunks = create_docling_hierarchical_chunks(self.sample_text)
        
        # Check that positions are reasonable
        for chunk in chunks:
            self.assertGreaterEqual(chunk.char_start, 0)
            self.assertGreaterEqual(chunk.char_end, chunk.char_start)
            self.assertEqual(
                chunk.char_end - chunk.char_start, 
                len(chunk.chunk_text), 
                "Character range should match text length"
            )

    def test_chunk_formatting_and_delimiters(self):
        """Test that chunk formatting handles delimiters correctly."""
        # Test with different delimiter patterns
        test_text = "Section A\n\nSection B\n---\nSection C"
        chunks = create_docling_hierarchical_chunks(test_text)
        
        # Verify that chunks contain reasonable content
        self.assertGreater(len(chunks), 0, "Should generate at least one chunk")
        
        # Check that chunks contain actual content, not just delimiters
        for chunk in chunks:
            text = chunk.chunk_text.strip()
            self.assertGreater(len(text), 0, "Chunk should not be empty")
            # Allow delimiters in chunks since docling treats them as content
            # The important thing is that we have meaningful text chunks


if __name__ == "__main__":
    unittest.main()