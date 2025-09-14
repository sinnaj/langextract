#!/usr/bin/env python3
"""Quick test to validate alignment performance optimizations."""

import time
import logging
from langextract.resolver import WordAligner
from langextract import data

# Configure logging to show performance messages
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_optimized_alignment():
    """Test that the optimizations work for a moderately sized chunk."""
    
    # Create a 150KB test text (should trigger large chunk protection)
    base_text = "This is a sample sentence with various words that could match extraction patterns. "
    target_size = 150 * 1024  # 150KB
    repetitions = target_size // len(base_text)
    source_text = (base_text * repetitions)[:target_size]
    
    # Create some test extractions
    extractions = [
        data.Extraction("sample sentence", "TestClass"),
        data.Extraction("various words", "TestClass"), 
        data.Extraction("extraction patterns", "TestClass"),
        data.Extraction("non-matching text that will need fuzzy alignment", "TestClass"),
        data.Extraction("another unmatched phrase for testing", "TestClass")
    ]
    
    print(f"Testing alignment with:")
    print(f"  Source text: {len(source_text):,} characters")
    print(f"  Extractions: {len(extractions)}")
    
    # Run alignment with timing
    aligner = WordAligner()
    start_time = time.time()
    
    result = aligner.align_extractions(
        [extractions],
        source_text,
        enable_fuzzy_alignment=True,
        fuzzy_alignment_threshold=0.6
    )
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Count successful alignments
    successful = 0
    for group in result:
        for extraction in group:
            if extraction.token_interval is not None:
                successful += 1
    
    print(f"\nResults:")
    print(f"  Time taken: {elapsed:.2f} seconds")
    print(f"  Successful alignments: {successful}/{len(extractions)}")
    print(f"  Success rate: {successful/len(extractions):.1%}")
    
    if elapsed < 10:  # Should be much faster than 10 seconds
        print("✓ Performance test PASSED - alignment completed quickly")
        return True
    else:
        print("✗ Performance test FAILED - alignment took too long") 
        return False

if __name__ == "__main__":
    success = test_optimized_alignment()
    exit(0 if success else 1)