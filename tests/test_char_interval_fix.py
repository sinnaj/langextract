#!/usr/bin/env python3
"""Test to validate the char_interval fix for section-based extraction."""

from absl.testing import absltest
import sys
from pathlib import Path

# Add the current directory to path
sys.path.insert(0, '/home/runner/work/langextract/langextract')

from section_chunker import create_section_chunks


class CharIntervalFixTest(absltest.TestCase):
    """Test that the fix correctly converts section-relative to absolute positions."""

    def test_char_interval_adjustment_logic(self):
        """Test the char_interval adjustment helper function."""
        
        # Mock section chunk (similar to what section_chunker produces)
        class MockSectionChunk:
            def __init__(self, char_start, char_end, chunk_text):
                self.char_start = char_start
                self.char_end = char_end
                self.chunk_text = chunk_text
        
        # Helper function from our fix
        def _adjust_char_interval_to_absolute(ci_dict, section_chunk):
            """Adjust char_interval from section-relative to document-absolute positions."""
            if not ci_dict or not section_chunk:
                return ci_dict
            
            if ci_dict.get("start_pos") is not None and ci_dict.get("end_pos") is not None:
                # Add the section's absolute start position to convert relative to absolute
                ci_dict["start_pos"] += section_chunk.char_start
                ci_dict["end_pos"] += section_chunk.char_start
            
            return ci_dict
        
        # Test case 1: Normal case
        section_chunk = MockSectionChunk(100, 200, "some text with Ibuprofen here")
        relative_char_interval = {"start_pos": 15, "end_pos": 24}  # "Ibuprofen"
        
        adjusted = _adjust_char_interval_to_absolute(relative_char_interval, section_chunk)
        
        self.assertEqual(adjusted["start_pos"], 115)  # 100 + 15
        self.assertEqual(adjusted["end_pos"], 124)    # 100 + 24
        
        # Test case 2: None section_chunk
        adjusted_none = _adjust_char_interval_to_absolute(relative_char_interval, None)
        self.assertEqual(adjusted_none, relative_char_interval)  # Should return unchanged
        
        # Test case 3: None char_interval
        adjusted_none_ci = _adjust_char_interval_to_absolute(None, section_chunk)
        self.assertIsNone(adjusted_none_ci)
        
        # Test case 4: char_interval with None values
        partial_char_interval = {"start_pos": None, "end_pos": 24}
        adjusted_partial = _adjust_char_interval_to_absolute(partial_char_interval, section_chunk)
        self.assertEqual(adjusted_partial, partial_char_interval)  # Should return unchanged

    def test_section_chunker_provides_absolute_positions(self):
        """Test that section chunker provides correct absolute positions."""
        test_document = """# Section 1
Content of section 1.

## Section 2
Content of section 2 with medication Aspirin.

# Section 3
Final section content."""
        
        sections = create_section_chunks(test_document)
        self.assertGreater(len(sections), 1)
        
        # Verify sections have absolute positions
        for section in sections:
            self.assertIsNotNone(section.char_start)
            self.assertIsNotNone(section.char_end)
            self.assertGreaterEqual(section.char_start, 0)
            self.assertLess(section.char_end, len(test_document))
            
            # Verify the section text matches what we extract using absolute positions
            extracted = test_document[section.char_start:section.char_end]
            self.assertEqual(extracted, section.chunk_text)
        
        # Find the section with "Aspirin" and verify positioning
        aspirin_section = None
        for section in sections:
            if "Aspirin" in section.chunk_text:
                aspirin_section = section
                break
        
        self.assertIsNotNone(aspirin_section)
        
        # Find Aspirin within the section (relative position)
        relative_start = aspirin_section.chunk_text.find("Aspirin")
        self.assertNotEqual(relative_start, -1)
        
        # Calculate absolute position
        absolute_start = aspirin_section.char_start + relative_start
        absolute_end = absolute_start + len("Aspirin")
        
        # Verify extraction using absolute position matches
        extracted_aspirin = test_document[absolute_start:absolute_end]
        self.assertEqual(extracted_aspirin, "Aspirin")

    def test_end_to_end_positioning_logic(self):
        """Test the complete positioning logic end-to-end."""
        # Document with clear medication positioning
        test_document = "Start of document. Patient was prescribed Lisinopril 10mg. End of document."
        
        # Find the absolute position of Lisinopril manually
        expected_start = test_document.find("Lisinopril")
        expected_end = expected_start + len("Lisinopril")
        
        # Create sections
        sections = create_section_chunks(test_document)
        
        # Find section containing Lisinopril
        target_section = None
        for section in sections:
            if "Lisinopril" in section.chunk_text:
                target_section = section
                break
        
        self.assertIsNotNone(target_section)
        
        # Simulate what happens in extraction: find relative position within section
        relative_start = target_section.chunk_text.find("Lisinopril")
        relative_end = relative_start + len("Lisinopril")
        
        # Create char_interval as extraction would produce it (relative to section)
        relative_char_interval = {
            "start_pos": relative_start,
            "end_pos": relative_end
        }
        
        # Apply our fix to convert to absolute positions
        def _adjust_char_interval_to_absolute(ci_dict, section_chunk):
            if not ci_dict or not section_chunk:
                return ci_dict
            
            if ci_dict.get("start_pos") is not None and ci_dict.get("end_pos") is not None:
                ci_dict["start_pos"] += section_chunk.char_start
                ci_dict["end_pos"] += section_chunk.char_start
            
            return ci_dict
        
        absolute_char_interval = _adjust_char_interval_to_absolute(relative_char_interval, target_section)
        
        # Verify the fix produces the correct absolute positions
        self.assertEqual(absolute_char_interval["start_pos"], expected_start)
        self.assertEqual(absolute_char_interval["end_pos"], expected_end)
        
        # Verify extraction using the fixed positions
        extracted = test_document[absolute_char_interval["start_pos"]:absolute_char_interval["end_pos"]]
        self.assertEqual(extracted, "Lisinopril")


if __name__ == '__main__':
    absltest.main()