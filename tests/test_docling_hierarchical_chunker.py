#!/usr/bin/env python3
"""
Test for the Docling hierarchical chunking script.

This test validates that the script works correctly with the built-in test mode.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestDoclingHierarchicalChunker(unittest.TestCase):
    """Test cases for the Docling hierarchical chunking script."""

    def setUp(self):
        """Set up test environment."""
        self.script_path = Path(__file__).parent.parent / "scripts" / "docling_hierarchical_chunker.py"
        self.assertTrue(self.script_path.exists(), f"Script not found: {self.script_path}")

    def test_help_option(self):
        """Test that the help option works."""
        result = subprocess.run([
            sys.executable, str(self.script_path), "--help"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        self.assertIn("hierarchical chunking", result.stdout.lower())
        self.assertIn("--test", result.stdout)

    def test_test_mode_stdout(self):
        """Test the built-in test mode with stdout output."""
        result = subprocess.run([
            sys.executable, str(self.script_path), "--test"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
        
        # Parse the JSON output
        try:
            output_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.fail(f"Failed to parse JSON output: {e}\nOutput: {result.stdout}")
        
        # Validate structure
        self.assertIn("metadata", output_data)
        self.assertIn("chunks", output_data)
        
        metadata = output_data["metadata"]
        self.assertEqual(metadata["chunking_method"], "hierarchical")
        self.assertEqual(metadata["chunker"], "docling_hierarchical_chunker")
        
        chunks = output_data["chunks"]
        self.assertGreater(len(chunks), 0, "Should generate at least one chunk")
        self.assertEqual(metadata["total_chunks"], len(chunks))
        
        # Validate chunk structure
        for i, chunk in enumerate(chunks):
            with self.subTest(chunk_id=i+1):
                self.assertIn("chunk_id", chunk)
                self.assertIn("text", chunk)
                self.assertIn("metadata", chunk)
                self.assertEqual(chunk["chunk_id"], i + 1)
                self.assertIsInstance(chunk["text"], str)
                self.assertGreater(len(chunk["text"]), 0, "Chunk text should not be empty")

    def test_test_mode_file_output(self):
        """Test the built-in test mode with file output."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            output_path = temp_file.name

        try:
            result = subprocess.run([
                sys.executable, str(self.script_path), "--test", "dummy", output_path
            ], capture_output=True, text=True)
            
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
            
            # Check that output file was created
            output_file = Path(output_path)
            self.assertTrue(output_file.exists(), "Output file should be created")
            
            # Validate file content
            with open(output_file, 'r') as f:
                output_data = json.load(f)
            
            self.assertIn("metadata", output_data)
            self.assertIn("chunks", output_data)
            self.assertGreater(len(output_data["chunks"]), 0)

        finally:
            # Clean up
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_chunking_options(self):
        """Test various chunking options."""
        # Test no-merge-lists option
        result = subprocess.run([
            sys.executable, str(self.script_path), "--test", "--no-merge-lists"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Script failed with --no-merge-lists: {result.stderr}")
        
        # Test custom delimiter
        result = subprocess.run([
            sys.executable, str(self.script_path), "--test", "--delimiter", "\n---\n"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Script failed with custom delimiter: {result.stderr}")

    def test_error_handling(self):
        """Test error handling for invalid inputs."""
        # Test without input when not in test mode
        result = subprocess.run([
            sys.executable, str(self.script_path)
        ], capture_output=True, text=True)
        
        self.assertNotEqual(result.returncode, 0, "Should fail without input when not in test mode")
        self.assertIn("input file required", result.stderr.lower())

    def test_chunk_metadata_structure(self):
        """Test that chunk metadata has the expected structure."""
        result = subprocess.run([
            sys.executable, str(self.script_path), "--test"
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0)
        output_data = json.loads(result.stdout)
        
        chunks = output_data["chunks"]
        self.assertGreater(len(chunks), 0)
        
        for chunk in chunks:
            metadata = chunk["metadata"]
            
            # Check required metadata fields
            self.assertIn("schema_name", metadata)
            self.assertIn("version", metadata)
            self.assertIn("doc_items", metadata)
            
            # Check that headings context is preserved
            if "headings" in metadata and metadata["headings"]:
                self.assertIsInstance(metadata["headings"], list)


if __name__ == "__main__":
    unittest.main()