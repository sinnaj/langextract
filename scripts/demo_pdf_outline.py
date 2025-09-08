#!/usr/bin/env python3
"""
Demo script showing PDF outline extractor functionality with mock data.

This script demonstrates what the PDF outline extractor would output
for a typical academic paper without requiring actual PDF dependencies.
"""

import json
import sys
from pathlib import Path

# Add current directory to path for importing
sys.path.insert(0, str(Path(__file__).parent))

from pdf_outline_extractor import save_outline


def create_demo_outline():
    """Create a demo outline that represents a typical academic paper."""
    demo_outline = {
        "title": "Advanced Machine Learning Techniques for Document Understanding",
        "outline": [
            {
                "level": "H1",
                "text": "Abstract",
                "page": 1
            },
            {
                "level": "H1", 
                "text": "1. Introduction",
                "page": 1
            },
            {
                "level": "H2",
                "text": "1.1 Background",
                "page": 2
            },
            {
                "level": "H2",
                "text": "1.2 Related Work",
                "page": 3
            },
            {
                "level": "H3",
                "text": "1.2.1 Traditional Approaches",
                "page": 3
            },
            {
                "level": "H3",
                "text": "1.2.2 Modern Deep Learning Methods",
                "page": 4
            },
            {
                "level": "H1",
                "text": "2. Methodology",
                "page": 5
            },
            {
                "level": "H2",
                "text": "2.1 Data Collection",
                "page": 5
            },
            {
                "level": "H2",
                "text": "2.2 Model Architecture",
                "page": 6
            },
            {
                "level": "H3",
                "text": "2.2.1 Feature Extraction",
                "page": 7
            },
            {
                "level": "H3",
                "text": "2.2.2 Classification Layer",
                "page": 8
            },
            {
                "level": "H2",
                "text": "2.3 Training Procedure",
                "page": 9
            },
            {
                "level": "H1",
                "text": "3. Experiments and Results",
                "page": 10
            },
            {
                "level": "H2",
                "text": "3.1 Experimental Setup",
                "page": 10
            },
            {
                "level": "H2",
                "text": "3.2 Quantitative Results",
                "page": 11
            },
            {
                "level": "H3",
                "text": "3.2.1 Accuracy Metrics",
                "page": 12
            },
            {
                "level": "H3",
                "text": "3.2.2 Performance Comparison",
                "page": 13
            },
            {
                "level": "H2",
                "text": "3.3 Qualitative Analysis",
                "page": 14
            },
            {
                "level": "H1",
                "text": "4. Discussion",
                "page": 15
            },
            {
                "level": "H2",
                "text": "4.1 Implications",
                "page": 15
            },
            {
                "level": "H2",
                "text": "4.2 Limitations",
                "page": 16
            },
            {
                "level": "H1",
                "text": "5. Conclusion",
                "page": 17
            },
            {
                "level": "H1",
                "text": "References",
                "page": 18
            },
            {
                "level": "H1",
                "text": "Appendix A: Additional Results",
                "page": 19
            }
        ]
    }
    return demo_outline


def print_outline_summary(outline_data):
    """Print a human-readable summary of the outline."""
    title = outline_data["title"]
    outline = outline_data["outline"]
    
    print("=" * 60)
    print(f"DOCUMENT TITLE: {title}")
    print("=" * 60)
    print()
    
    print("HIERARCHICAL OUTLINE:")
    print("-" * 30)
    
    for item in outline:
        level = item["level"]
        text = item["text"]
        page = item["page"]
        
        # Create indentation based on level
        indent_map = {"H1": "", "H2": "  ", "H3": "    ", "H4": "      "}
        indent = indent_map.get(level, "")
        
        print(f"{indent}{level}: {text} (page {page})")
    
    print()
    print("-" * 30)
    print(f"Total sections: {len(outline)}")
    
    # Count by level
    level_counts = {}
    for item in outline:
        level = item["level"]
        level_counts[level] = level_counts.get(level, 0) + 1
    
    print("Level distribution:")
    for level in ["H1", "H2", "H3", "H4"]:
        if level in level_counts:
            print(f"  {level}: {level_counts[level]} sections")


def main():
    """Main demo function."""
    print("PDF Outline Extractor - Demo Output")
    print("This demonstrates the typical output format")
    print()
    
    # Create demo outline
    demo_data = create_demo_outline()
    
    # Show human-readable summary
    print_outline_summary(demo_data)
    
    print()
    print("JSON OUTPUT FORMAT:")
    print("=" * 60)
    
    # Show JSON format (same as script output)
    print(json.dumps(demo_data, indent=2, ensure_ascii=False))
    
    print()
    print("=" * 60)
    print("This JSON format is compatible with PDF-Outline-Extractor")
    print("and can be used for further document processing.")


if __name__ == "__main__":
    main()