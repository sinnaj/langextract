#!/usr/bin/env python3
"""Test script to benchmark alignment performance and validate optimizations."""

import json
import time
import logging
from typing import List, Dict, Any
from langextract import data, tokenizer
from langextract.resolver import WordAligner

# Configure logging for testing
logging.basicConfig(level=logging.INFO)


def create_large_text(size_kb: int) -> str:
    """Create a large text string for performance testing."""
    base_text = "This is a sample sentence with various words that could match extraction patterns. "
    # Calculate how many repetitions needed to reach target size
    target_chars = size_kb * 1024
    repetitions = target_chars // len(base_text)
    return (base_text * repetitions)[:target_chars]


def create_test_extractions(num_extractions: int) -> List[data.Extraction]:
    """Create test extractions for alignment."""
    extractions = []
    for i in range(num_extractions):
        extraction = data.Extraction(
            extraction_text=f"sample sentence {i} with various words",
            extraction_class="TestClass",
            description=f"Test extraction for performance testing {i}",
            extraction_index=i
        )
        extractions.append(extraction)
    return extractions


def benchmark_alignment(
    source_text_size_kb: int, 
    num_extractions: int,
    description: str
) -> Dict[str, Any]:
    """Benchmark the alignment process."""
    print(f"\n{description}")
    print("=" * len(description))
    
    # Create test data
    source_text = create_large_text(source_text_size_kb)
    extractions = create_test_extractions(num_extractions)
    
    print(f"Source text size: {len(source_text):,} characters ({source_text_size_kb} KB)")
    print(f"Number of extractions: {num_extractions}")
    print(f"Source text tokens: {len(tokenizer.tokenize(source_text).tokens):,}")
    
    # Time the alignment
    aligner = WordAligner()
    start_time = time.time()
    
    try:
        aligned_results = aligner.align_extractions(
            [extractions],
            source_text,
            token_offset=0,
            char_offset=0,
            enable_fuzzy_alignment=True,
            fuzzy_alignment_threshold=0.6
        )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Count successful alignments
        successful_alignments = 0
        for group in aligned_results:
            for extraction in group:
                if extraction.token_interval is not None:
                    successful_alignments += 1
        
        result = {
            "source_size_kb": source_text_size_kb,
            "num_extractions": num_extractions,
            "elapsed_seconds": elapsed,
            "successful_alignments": successful_alignments,
            "success_rate": successful_alignments / num_extractions if num_extractions > 0 else 0,
            "characters_per_second": len(source_text) / elapsed if elapsed > 0 else 0
        }
        
        print(f"Alignment took: {elapsed:.2f} seconds")
        print(f"Successful alignments: {successful_alignments}/{num_extractions} ({result['success_rate']:.1%})")
        print(f"Processing rate: {result['characters_per_second']:,.0f} chars/sec")
        
        return result
        
    except Exception as e:
        print(f"ERROR: {e}")
        return {
            "error": str(e),
            "source_size_kb": source_text_size_kb,
            "num_extractions": num_extractions
        }


def main():
    """Run alignment performance benchmarks."""
    print("Alignment Performance Benchmark")
    print("=" * 50)
    
    # Test scenarios from small to large
    test_scenarios = [
        (10, 5, "Small text with few extractions"),
        (50, 10, "Medium text with moderate extractions"),
        (100, 15, "Large text with many extractions"),
        (250, 20, "Very large text (similar to problematic chunks)"),
        (500, 25, "Extremely large text (stress test)")
    ]
    
    results = []
    for size_kb, num_extractions, description in test_scenarios:
        result = benchmark_alignment(size_kb, num_extractions, description)
        results.append(result)
        
        # Stop if alignment takes too long
        if result.get("elapsed_seconds", 0) > 60:
            print("\n⚠️  Stopping benchmarks - alignment taking too long (>60s)")
            break
    
    # Summary
    print("\n" + "=" * 50)
    print("PERFORMANCE SUMMARY")
    print("=" * 50)
    
    for result in results:
        if "error" not in result:
            print(f"{result['source_size_kb']}KB: {result['elapsed_seconds']:.2f}s "
                  f"({result['characters_per_second']:,.0f} chars/sec)")
        else:
            print(f"{result['source_size_kb']}KB: ERROR - {result['error']}")
    
    # Save results for analysis
    with open("/tmp/alignment_benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to /tmp/alignment_benchmark_results.json")


if __name__ == "__main__":
    main()