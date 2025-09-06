#!/usr/bin/env python3
"""Test to validate that char_interval stores absolute positions, not relative to chunks."""

from absl.testing import absltest
from langextract import chunking, tokenizer, resolver
from langextract.core import data


class CharIntervalAbsolutePositionTest(absltest.TestCase):
    """Test that char_interval contains absolute positions in the original document."""

    def test_char_interval_absolute_positions_single_chunk(self):
        """Test char_interval with single chunk (should be same as relative)."""
        test_text = "Patient was prescribed Ibuprofen 400mg for pain relief."
        expected_med_start = test_text.find("Ibuprofen")
        expected_med_end = expected_med_start + len("Ibuprofen")
        
        # Create extraction
        extraction = data.Extraction(
            extraction_class="medication",
            extraction_text="Ibuprofen",
        )
        
        # Test alignment
        res = resolver.Resolver()
        aligned = list(res.align(
            [extraction],
            test_text,
            token_offset=0,
            char_offset=0,  # No offset for single chunk
        ))
        
        self.assertEqual(len(aligned), 1)
        aligned_extraction = aligned[0]
        
        self.assertIsNotNone(aligned_extraction.char_interval)
        self.assertEqual(aligned_extraction.char_interval.start_pos, expected_med_start)
        self.assertEqual(aligned_extraction.char_interval.end_pos, expected_med_end)
        
        # Verify extraction from original text
        extracted_text = test_text[aligned_extraction.char_interval.start_pos:aligned_extraction.char_interval.end_pos]
        self.assertEqual(extracted_text.lower(), "ibuprofen")
    
    def test_char_interval_absolute_positions_multiple_chunks(self):
        """Test char_interval with multiple chunks to verify absolute positioning."""
        # Create a document that will be split into multiple chunks
        test_document = "The patient was prescribed Lisinopril 10mg daily. After two weeks, the doctor added Metoprolol 25mg twice daily for better control."
        
        # Find expected absolute positions
        lisinopril_start = test_document.find("Lisinopril")
        lisinopril_end = lisinopril_start + len("Lisinopril")
        metoprolol_start = test_document.find("Metoprolol") 
        metoprolol_end = metoprolol_start + len("Metoprolol")
        
        # Create chunks
        tokenized = tokenizer.tokenize(test_document)
        chunk_iterator = chunking.ChunkIterator(
            text=tokenized,
            max_char_buffer=60,  # Small buffer to force chunking
            document=None
        )
        chunks = list(chunk_iterator)
        
        # Verify we have multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Test each chunk that contains medications
        res = resolver.Resolver()
        all_aligned_extractions = []
        
        for chunk in chunks:
            chunk_medications = []
            
            # Check for Lisinopril in this chunk
            if "Lisinopril" in chunk.chunk_text:
                chunk_medications.append(data.Extraction(
                    extraction_class="medication",
                    extraction_text="Lisinopril",
                ))
            
            # Check for Metoprolol in this chunk
            if "Metoprolol" in chunk.chunk_text:
                chunk_medications.append(data.Extraction(
                    extraction_class="medication", 
                    extraction_text="Metoprolol",
                ))
            
            if chunk_medications:
                # Align extractions for this chunk
                aligned = list(res.align(
                    chunk_medications,
                    chunk.chunk_text,
                    token_offset=chunk.token_interval.start_index,
                    char_offset=chunk.char_interval.start_pos,  # Absolute chunk start
                ))
                all_aligned_extractions.extend(aligned)
        
        # Verify we found both medications
        extraction_texts = [e.extraction_text for e in all_aligned_extractions]
        self.assertIn("Lisinopril", extraction_texts)
        self.assertIn("Metoprolol", extraction_texts)
        
        # Verify absolute positioning for each medication
        for extraction in all_aligned_extractions:
            self.assertIsNotNone(extraction.char_interval)
            start = extraction.char_interval.start_pos
            end = extraction.char_interval.end_pos
            
            # Extract text using char_interval from original document
            extracted_text = test_document[start:end]
            self.assertEqual(extracted_text.lower(), extraction.extraction_text.lower())
            
            # Verify against expected absolute positions
            if extraction.extraction_text == "Lisinopril":
                self.assertEqual(start, lisinopril_start)
                self.assertEqual(end, lisinopril_end)
            elif extraction.extraction_text == "Metoprolol":
                self.assertEqual(start, metoprolol_start)
                self.assertEqual(end, metoprolol_end)

    def test_char_interval_with_chunk_offset(self):
        """Test that char_offset properly converts relative to absolute positions."""
        # Simulate a chunk from the middle of a document
        full_document = "This is the beginning. Patient was prescribed Ibuprofen 400mg for pain. This is the end."
        chunk_text = "Patient was prescribed Ibuprofen 400mg for pain."
        chunk_offset = full_document.find(chunk_text)  # Absolute start of chunk
        
        # Expected absolute position of Ibuprofen in full document
        expected_start = full_document.find("Ibuprofen")
        expected_end = expected_start + len("Ibuprofen")
        
        # Create extraction
        extraction = data.Extraction(
            extraction_class="medication",
            extraction_text="Ibuprofen",
        )
        
        # Test alignment with char_offset
        res = resolver.Resolver()
        aligned = list(res.align(
            [extraction],
            chunk_text,
            token_offset=0,
            char_offset=chunk_offset,  # Apply the chunk offset
        ))
        
        self.assertEqual(len(aligned), 1)
        aligned_extraction = aligned[0]
        
        self.assertIsNotNone(aligned_extraction.char_interval)
        self.assertEqual(aligned_extraction.char_interval.start_pos, expected_start)
        self.assertEqual(aligned_extraction.char_interval.end_pos, expected_end)
        
        # Verify extraction from full document using absolute positions
        extracted_text = full_document[aligned_extraction.char_interval.start_pos:aligned_extraction.char_interval.end_pos]
        self.assertEqual(extracted_text.lower(), "ibuprofen")


if __name__ == '__main__':
    absltest.main()