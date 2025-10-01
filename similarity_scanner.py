#!/usr/bin/env python3
"""
Similarity Scanner for LangExtract Tags and Parameters

This script reads enhanced_extraction_results.json files and identifies
similarly named tags and parameters (e.g., FIRE.EXIT vs FIRE_EXIT).

Usage:
    python similarity_scanner.py path/to/enhanced_extraction_results.json
    python similarity_scanner.py output_runs/1757868964/enhanced_output/enhanced_extraction_results.json

The script will output:
1. All tags that are overly similar to each other
2. All parameters that are overly similar to each other
"""

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any


class SimilarityScanner:
    """Scanner for detecting similar tags and parameters in langextract outputs."""
    
    def __init__(self, similarity_threshold: float = 0.8):
        """
        Initialize the similarity scanner.
        
        Args:
            similarity_threshold: Minimum similarity ratio (0.0-1.0) to consider items similar
        """
        self.similarity_threshold = similarity_threshold
    
    def normalize_name(self, name: str) -> str:
        """
        Normalize a tag or parameter name for comparison.
        
        This converts different separator styles to a common format:
        - FIRE.EXIT -> FIRE_EXIT
        - FIRE-EXIT -> FIRE_EXIT  
        - FIRE EXIT -> FIRE_EXIT
        
        Args:
            name: The tag or parameter name to normalize
            
        Returns:
            Normalized name for comparison
        """
        # Convert to uppercase and replace various separators with underscores
        normalized = name.upper()
        normalized = re.sub(r'[.\-\s]+', '_', normalized)
        # Remove multiple consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        return normalized
    
    def calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names.
        
        Uses multiple similarity measures:
        1. Exact match after normalization
        2. Sequence similarity (difflib)
        3. Substring containment
        
        Args:
            name1: First name to compare
            name2: Second name to compare
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if name1 == name2:
            return 1.0
            
        # Normalize both names
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        # Check for exact match after normalization
        if norm1 == norm2:
            return 1.0
        
        # Use SequenceMatcher for similarity
        seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Check substring containment (bidirectional)
        len1, len2 = len(norm1), len(norm2)
        if len1 > 0 and len2 > 0:
            # Check if one is contained in the other
            if norm1 in norm2 or norm2 in norm1:
                # Boost similarity for substring matches
                substring_bonus = 0.2
                seq_similarity = min(1.0, seq_similarity + substring_bonus)
        
        return seq_similarity
    
    def find_similar_items(self, items: List[str]) -> List[Tuple[str, str, float]]:
        """
        Find all pairs of similar items in a list.
        
        Args:
            items: List of item names to compare
            
        Returns:
            List of tuples (item1, item2, similarity_score) for similar pairs
        """
        similar_pairs = []
        
        for i, item1 in enumerate(items):
            for j, item2 in enumerate(items[i+1:], i+1):
                similarity = self.calculate_similarity(item1, item2)
                if similarity >= self.similarity_threshold:
                    similar_pairs.append((item1, item2, similarity))
        
        # Sort by similarity score descending
        similar_pairs.sort(key=lambda x: x[2], reverse=True)
        return similar_pairs
    
    def extract_tags_from_json(self, data: Dict[str, Any]) -> List[str]:
        """
        Extract all tag names from the JSON data.
        
        Args:
            data: Parsed JSON data from enhanced_extraction_results.json
            
        Returns:
            List of unique tag names
        """
        tags = set()
        
        # Extract from main tags array
        if 'tags' in data and isinstance(data['tags'], list):
            for tag_obj in data['tags']:
                if isinstance(tag_obj, dict):
                    attributes = tag_obj.get('attributes', {})
                    tag_name = attributes.get('tag')
                    if tag_name:
                        tags.add(tag_name)
        
        return sorted(list(tags))
    
    def extract_parameters_from_json(self, data: Dict[str, Any]) -> List[str]:
        """
        Extract all parameter names from the JSON data.
        
        Args:
            data: Parsed JSON data from enhanced_extraction_results.json
            
        Returns:
            List of unique parameter names
        """
        parameters = set()
        
        # Extract from main parameters array
        if 'parameters' in data and isinstance(data['parameters'], list):
            for param_obj in data['parameters']:
                if isinstance(param_obj, dict):
                    attributes = param_obj.get('attributes', {})
                    param_name = attributes.get('applies_for_tag')
                    if param_name:
                        parameters.add(param_name)
        
        return sorted(list(parameters))
    
    def scan_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Scan a single JSON file for similar tags and parameters.
        
        Args:
            file_path: Path to the enhanced_extraction_results.json file
            
        Returns:
            Dictionary containing similarity analysis results
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {
                'error': f'Failed to load file {file_path}: {str(e)}',
                'file_path': str(file_path)
            }
        
        # Extract tags and parameters
        tags = self.extract_tags_from_json(data)
        parameters = self.extract_parameters_from_json(data)
        
        # Find similar items
        similar_tags = self.find_similar_items(tags)
        similar_parameters = self.find_similar_items(parameters)
        
        return {
            'file_path': str(file_path),
            'total_tags': len(tags),
            'total_parameters': len(parameters),
            'similar_tags': similar_tags,
            'similar_parameters': similar_parameters,
            'all_tags': tags,
            'all_parameters': parameters
        }
    
    def print_results(self, results: Dict[str, Any]) -> None:
        """
        Print the similarity analysis results in a readable format.
        
        Args:
            results: Results dictionary from scan_file()
        """
        if 'error' in results:
            print(f"❌ Error: {results['error']}")
            return
        
        print(f"🔍 Similarity Analysis for: {results['file_path']}")
        print(f"📊 Total Tags: {results['total_tags']}, Total Parameters: {results['total_parameters']}")
        print()
        
        # Print similar tags
        similar_tags = results['similar_tags']
        if similar_tags:
            print(f"🏷️  Found {len(similar_tags)} pairs of similar tags:")
            print("=" * 80)
            for tag1, tag2, similarity in similar_tags:
                print(f"  {similarity:.3f} - '{tag1}' ≈ '{tag2}'")
                # Show normalized versions to help understand the match
                norm1 = self.normalize_name(tag1)
                norm2 = self.normalize_name(tag2)
                if norm1 != tag1 or norm2 != tag2:
                    print(f"          (normalized: '{norm1}' ≈ '{norm2}')")
            print()
        else:
            print("✅ No overly similar tags found.")
            print()
        
        # Print similar parameters
        similar_parameters = results['similar_parameters']
        if similar_parameters:
            print(f"⚙️  Found {len(similar_parameters)} pairs of similar parameters:")
            print("=" * 80)
            for param1, param2, similarity in similar_parameters:
                print(f"  {similarity:.3f} - '{param1}' ≈ '{param2}'")
                # Show normalized versions to help understand the match
                norm1 = self.normalize_name(param1)
                norm2 = self.normalize_name(param2)
                if norm1 != param1 or norm2 != param2:
                    print(f"          (normalized: '{norm1}' ≈ '{norm2}')")
            print()
        else:
            print("✅ No overly similar parameters found.")
            print()
        
        # Summary statistics
        tag_similarity_count = len(similar_tags)
        param_similarity_count = len(similar_parameters)
        total_issues = tag_similarity_count + param_similarity_count
        
        if total_issues > 0:
            print(f"⚠️  Summary: Found {total_issues} potential naming inconsistencies")
            print(f"   - {tag_similarity_count} tag similarity issues")
            print(f"   - {param_similarity_count} parameter similarity issues")
        else:
            print("🎉 No naming inconsistencies found!")


def main():
    """Main entry point for the similarity scanner."""
    parser = argparse.ArgumentParser(
        description='Scan langextract JSON output for similar tag and parameter names',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s output_runs/1757868964/enhanced_output/enhanced_extraction_results.json
  %(prog)s path/to/enhanced_extraction_results.json --threshold 0.9
        """
    )
    
    parser.add_argument(
        'file_path',
        type=str,
        help='Path to enhanced_extraction_results.json file'
    )
    
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.8,
        help='Similarity threshold (0.0-1.0, default: 0.8)'
    )
    
    args = parser.parse_args()
    
    # Validate threshold
    if not 0.0 <= args.threshold <= 1.0:
        print("❌ Error: Threshold must be between 0.0 and 1.0")
        return 1
    
    # Validate file path
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"❌ Error: File not found: {file_path}")
        return 1
    
    # Run similarity scan
    scanner = SimilarityScanner(similarity_threshold=args.threshold)
    results = scanner.scan_file(file_path)
    
    # Print results
    scanner.print_results(results)
    
    return 0


if __name__ == '__main__':
    exit(main())