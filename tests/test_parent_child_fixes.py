#!/usr/bin/env python3
"""Tests for section postprocessor parent-child relationship fixes."""

import unittest
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from section_postprocessor import _cleanup_orphaned_children, _update_children_parent, post_process_section_evaluations
from section_chunker import SectionChunk, SectionMetadata
from chunk_evaluator import ChunkEvaluation


class TestSectionPostprocessorFixes(unittest.TestCase):
    """Test cases for section postprocessor parent-child relationship fixes."""

    def setUp(self):
        """Set up test data."""
        self.valid_parent_chunk = SectionChunk(
            chunk_text="Parent section content",
            section_metadata=SectionMetadata(
                section_id="parent_001",
                section_name="Parent Section",
                section_level=1,
                section_index=0,
                parent_section_id=None
            ),
            char_start=0,
            char_end=100
        )
        
        self.child_chunk = SectionChunk(
            chunk_text="Child section content",
            section_metadata=SectionMetadata(
                section_id="child_001",
                section_name="Child Section",
                section_level=2,
                section_index=1,
                parent_section_id="parent_001"
            ),
            char_start=100,
            char_end=200
        )
        
        self.orphaned_chunk = SectionChunk(
            chunk_text="Orphaned section content",
            section_metadata=SectionMetadata(
                section_id="orphan_001",
                section_name="Orphaned Section",
                section_level=2,
                section_index=2,
                parent_section_id="nonexistent_parent"
            ),
            char_start=200,
            char_end=300
        )
        
        self.extract_eval = ChunkEvaluation(
            should_extract=True,
            reason="Valid section",
            processing_type="extract"
        )

    def test_cleanup_orphaned_children(self):
        """Test that orphaned children are cleaned up correctly."""
        evaluations = [
            (self.valid_parent_chunk, self.extract_eval),
            (self.child_chunk, self.extract_eval),
            (self.orphaned_chunk, self.extract_eval)
        ]
        
        # Check initial state
        self.assertEqual(self.orphaned_chunk.section_metadata.parent_section_id, "nonexistent_parent")
        
        # Run cleanup
        cleanup_log = _cleanup_orphaned_children(evaluations)
        
        # Verify orphaned child was cleaned up
        self.assertIsNone(self.orphaned_chunk.section_metadata.parent_section_id)
        self.assertEqual(len(cleanup_log), 1)
        self.assertIn("orphan_001", cleanup_log[0])
        self.assertIn("nonexistent_parent", cleanup_log[0])
        
        # Verify valid parent-child relationship is unchanged
        self.assertEqual(self.child_chunk.section_metadata.parent_section_id, "parent_001")

    def test_update_children_parent_valid_target(self):
        """Test updating children's parent with valid target parent."""
        evaluations = [
            (self.valid_parent_chunk, self.extract_eval),
            (self.child_chunk, self.extract_eval)
        ]
        
        # Change child's parent to an old parent
        self.child_chunk.section_metadata.parent_section_id = "old_parent"
        
        # Update parent
        _update_children_parent("parent_001", ["old_parent"], evaluations)
        
        # Verify update worked
        self.assertEqual(self.child_chunk.section_metadata.parent_section_id, "parent_001")

    def test_update_children_parent_invalid_target(self):
        """Test updating children's parent with invalid target parent."""
        evaluations = [
            (self.child_chunk, self.extract_eval)
        ]
        
        original_parent = self.child_chunk.section_metadata.parent_section_id
        
        # Try to update to nonexistent parent
        _update_children_parent("nonexistent_target", ["parent_001"], evaluations)
        
        # Verify no update occurred (parent remains unchanged)
        self.assertEqual(self.child_chunk.section_metadata.parent_section_id, original_parent)

    def test_no_orphaned_children_cleanup_when_all_valid(self):
        """Test that cleanup does nothing when all parent relationships are valid."""
        evaluations = [
            (self.valid_parent_chunk, self.extract_eval),
            (self.child_chunk, self.extract_eval)
        ]
        
        cleanup_log = _cleanup_orphaned_children(evaluations)
        
        # Should be no cleanup needed
        self.assertEqual(len(cleanup_log), 0)
        
        # Parent relationships should remain unchanged
        self.assertIsNone(self.valid_parent_chunk.section_metadata.parent_section_id)
        self.assertEqual(self.child_chunk.section_metadata.parent_section_id, "parent_001")

    def test_post_process_integration(self):
        """Test that post-processing integrates orphaned children cleanup."""
        # Create evaluations with an orphaned child
        evaluations = [
            (self.valid_parent_chunk, self.extract_eval),
            (self.child_chunk, self.extract_eval),
            (self.orphaned_chunk, self.extract_eval)
        ]
        
        result = post_process_section_evaluations(evaluations)
        
        # Check that cleanup was performed
        cleanup_logs = [log for log in result.processing_log if "Orphaned section" in log]
        self.assertEqual(len(cleanup_logs), 1)
        self.assertIn("orphan_001", cleanup_logs[0])
        
        # Verify the orphaned section was fixed
        orphaned_section = None
        for chunk, _ in result.processed_evaluations:
            if chunk.section_metadata.section_id == "orphan_001":
                orphaned_section = chunk
                break
        
        self.assertIsNotNone(orphaned_section)
        self.assertIsNone(orphaned_section.section_metadata.parent_section_id)


if __name__ == '__main__':
    unittest.main()