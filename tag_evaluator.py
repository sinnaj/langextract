#!/usr/bin/env python3
"""Tag evaluator for extraction quality assessment.

This script evaluates tag extractions using an LLM (OpenRouter with Gemini 2.5 Flash)
to assess tag quality based on two key criteria:

1. Uniqueness of the Tag: Are there similar tags with essentially the same content?
2. Tag Entity Structure: Are there cases where main entities are showing up in the 
   middle of a tag string?

It provides quality scores for each dimension and generates comprehensive reports.
"""

import json
import os
import sys
import argparse
import statistics
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

import langextract as lx
from langextract.data import ExampleData, Extraction


def create_evaluation_prompt(tag: Dict[str, Any], all_tags: List[Dict[str, Any]]) -> str:
    """Create evaluation prompt for a single tag.
    
    Args:
        tag: Tag extraction dictionary containing tag attributes
        all_tags: List of all tags for comparison analysis
        
    Returns:
        Evaluation prompt string
    """
    attributes = tag.get('attributes', {})
    tag_value = attributes.get('tag', '')
    related_topics = attributes.get('related_topics', [])
    used_by_norms = attributes.get('used_by_norm_ids', [])
    
    # Create a sample of other tags for comparison (to detect duplicates)
    other_tags = []
    for other_tag in all_tags:
        if other_tag.get('attributes', {}).get('id') != attributes.get('id'):
            other_tags.append(other_tag.get('attributes', {}).get('tag', ''))
    
    # Limit comparison tags to avoid prompt bloat
    comparison_tags = other_tags[:50] if len(other_tags) > 50 else other_tags
    
    prompt = f"""You are an expert evaluator assessing the quality of extracted regulatory tags. 

Please evaluate the following tag on two key dimensions:

**TAG TO EVALUATE:**
Tag: {tag_value}
Related Topics: {related_topics}
Used by {len(used_by_norms)} norm(s)

**OTHER TAGS IN SYSTEM (for comparison):**
{json.dumps(comparison_tags[:20], indent=2)}
{"... and " + str(len(comparison_tags) - 20) + " more tags" if len(comparison_tags) > 20 else ""}

**EVALUATION CRITERIA:**

1. **Uniqueness** (Score 1-10): Are there similar tags with essentially the same content? Consider:
   - Is this tag truly unique or are there near-duplicates?
   - Does this tag provide distinct value compared to other tags?
   - Are there other tags that could be consolidated with this one?
   - Is the tag specific enough to be meaningful?

2. **Tag Entity Structure** (Score 1-10): Are there cases where main entities are showing up in the middle of a tag string? Consider:
   - Does the tag follow a logical hierarchical structure (e.g., MAIN.SUB.DETAIL)?
   - Are the most important concepts at the beginning of the tag path?
   - Is the tag structure intuitive and discoverable?
   - Are there structural inconsistencies or misplaced entities?

**RESPONSE FORMAT:**
Please respond with a JSON object containing:
{{
  "uniqueness_score": <integer 1-10>,
  "uniqueness_reasoning": "<brief explanation>",
  "entity_structure_score": <integer 1-10>, 
  "entity_structure_reasoning": "<brief explanation>",
  "overall_quality": <average of the two scores>,
  "similar_tags": ["<tag1>", "<tag2>", ...],
  "structural_issues": ["<issue1>", "<issue2>", ...],
  "suggestions": ["<suggestion1>", "<suggestion2>", ...]
}}

Focus on being precise and constructive in your evaluation."""

    return prompt


def create_llm_client() -> Any:
    """Create LLM client for OpenRouter with Gemini 2.5 Flash or local Gemini.
    
    Returns:
        Configured LLM client
    """
    # Try OpenRouter first (preferred)
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    if openrouter_key:
        try:
            # OpenRouter uses OpenAI-compatible API
            model = lx.get_language_model(
                'openai',
                model_id='google/gemini-2.5-flash',
                api_key=openrouter_key,
                base_url='https://openrouter.ai/api/v1',
                temperature=0.1
            )
            print("Using OpenRouter with Gemini 2.5 Flash")
            return model
        except Exception as e:
            print(f"OpenRouter initialization failed: {e}")
    
    # Fallback to local Gemini
    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        try:
            model = lx.get_language_model(
                'gemini',
                model_id='gemini-2.5-flash',
                api_key=gemini_key,
                temperature=0.1
            )
            print("Using local Gemini 2.5 Flash")
            return model
        except Exception as e:
            print(f"Gemini initialization failed: {e}")
    
    raise ValueError("Either OPENROUTER_API_KEY or GEMINI_API_KEY environment variable is required")


def evaluate_tag(tag: Dict[str, Any], all_tags: List[Dict[str, Any]], model: Any) -> Dict[str, Any]:
    """Evaluate a single tag using the LLM.
    
    Args:
        tag: Tag extraction dictionary
        all_tags: List of all tags for comparison
        model: LLM model instance
        
    Returns:
        Evaluation results dictionary
    """
    prompt = create_evaluation_prompt(tag, all_tags)
    
    try:
        # Use langextract's extract function for structured output
        result = lx.extract(
            model=model,
            text=prompt,
            schema={
                "type": "object",
                "properties": {
                    "uniqueness_score": {"type": "integer", "minimum": 1, "maximum": 10},
                    "uniqueness_reasoning": {"type": "string"},
                    "entity_structure_score": {"type": "integer", "minimum": 1, "maximum": 10},
                    "entity_structure_reasoning": {"type": "string"},
                    "overall_quality": {"type": "number"},
                    "similar_tags": {"type": "array", "items": {"type": "string"}},
                    "structural_issues": {"type": "array", "items": {"type": "string"}},
                    "suggestions": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["uniqueness_score", "entity_structure_score", "overall_quality"]
            }
        )
        
        evaluation = result[0] if result else {}
        
        # Add tag identification
        evaluation["tag_id"] = tag.get('attributes', {}).get('id', 'unknown')
        evaluation["tag_value"] = tag.get('attributes', {}).get('tag', '')
        evaluation["related_topics"] = tag.get('attributes', {}).get('related_topics', [])
        evaluation["used_by_norm_count"] = len(tag.get('attributes', {}).get('used_by_norm_ids', []))
        
        return evaluation
        
    except Exception as e:
        # Return error evaluation
        return {
            "tag_id": tag.get('attributes', {}).get('id', 'unknown'),
            "tag_value": tag.get('attributes', {}).get('tag', ''),
            "related_topics": tag.get('attributes', {}).get('related_topics', []),
            "used_by_norm_count": len(tag.get('attributes', {}).get('used_by_norm_ids', [])),
            "uniqueness_score": 1,
            "uniqueness_reasoning": f"Evaluation failed: {str(e)}",
            "entity_structure_score": 1,
            "entity_structure_reasoning": f"Evaluation failed: {str(e)}",
            "overall_quality": 1.0,
            "similar_tags": [],
            "structural_issues": ["Evaluation failed"],
            "suggestions": ["Re-evaluate manually"],
            "evaluation_error": str(e)
        }


def evaluate_tags(input_file: Path, output_file: Optional[Path] = None) -> Dict[str, Any]:
    """Evaluate all tags in a combined_extractions.json file.
    
    Args:
        input_file: Path to combined_extractions.json
        output_file: Optional path for output JSON file
        
    Returns:
        Complete evaluation report
    """
    # Load extractions
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    extractions = data.get('extractions', [])
    tags = [ext for ext in extractions if ext.get('extraction_class') == 'Tag']
    
    if not tags:
        print(f"No Tag extractions found in {input_file}")
        return {"error": "No tags found"}
    
    print(f"Found {len(tags)} tags to evaluate...")
    
    # Create LLM client
    model = create_llm_client()
    
    # Evaluate tags
    evaluations = []
    for i, tag in enumerate(tags):
        print(f"Evaluating tag {i+1}/{len(tags)}: {tag.get('attributes', {}).get('tag', 'unknown')}")
        
        evaluation = evaluate_tag(tag, tags, model)
        evaluations.append(evaluation)
    
    # Sort by overall quality (lowest first)
    evaluations.sort(key=lambda x: x.get('overall_quality', 10))
    
    # Calculate meta statistics
    quality_scores = [eval.get('overall_quality', 0) for eval in evaluations if eval.get('overall_quality')]
    uniqueness_scores = [eval.get('uniqueness_score', 0) for eval in evaluations if eval.get('uniqueness_score')]
    structure_scores = [eval.get('entity_structure_score', 0) for eval in evaluations if eval.get('entity_structure_score')]
    
    # Analyze tag patterns
    tag_values = [eval.get('tag_value', '') for eval in evaluations]
    unique_prefixes = set()
    for tag_val in tag_values:
        if '.' in tag_val:
            prefix = tag_val.split('.')[0]
            unique_prefixes.add(prefix)
    
    # Find potential duplicates (exact and similar)
    potential_duplicates = []
    for i, eval1 in enumerate(evaluations):
        for j, eval2 in enumerate(evaluations[i+1:], i+1):
            tag1 = eval1.get('tag_value', '')
            tag2 = eval2.get('tag_value', '')
            
            # Check for exact matches or very similar tags
            if tag1.lower() == tag2.lower() or (
                len(tag1) > 3 and len(tag2) > 3 and 
                (tag1.lower() in tag2.lower() or tag2.lower() in tag1.lower())
            ):
                potential_duplicates.append((tag1, tag2))
    
    meta_report = {
        "total_tags_evaluated": len(evaluations),
        "average_overall_quality": round(statistics.mean(quality_scores), 2) if quality_scores else 0,
        "average_uniqueness": round(statistics.mean(uniqueness_scores), 2) if uniqueness_scores else 0,
        "average_entity_structure": round(statistics.mean(structure_scores), 2) if structure_scores else 0,
        "median_overall_quality": round(statistics.median(quality_scores), 2) if quality_scores else 0,
        "min_quality": min(quality_scores) if quality_scores else 0,
        "max_quality": max(quality_scores) if quality_scores else 0,
        "unique_prefixes_count": len(unique_prefixes),
        "unique_prefixes": sorted(list(unique_prefixes)),
        "potential_duplicates_count": len(potential_duplicates),
        "potential_duplicates": potential_duplicates[:10],  # Top 10 examples
        "evaluation_timestamp": datetime.now().isoformat(),
        "source_file": str(input_file)
    }
    
    # Compile final report
    report = {
        "meta_report": meta_report,
        "tag_evaluations": evaluations,
        "summary": {
            "lowest_quality_tags": evaluations[:5],  # Top 5 lowest quality
            "quality_distribution": {
                "excellent": len([e for e in evaluations if e.get('overall_quality', 0) >= 8]),
                "good": len([e for e in evaluations if 6 <= e.get('overall_quality', 0) < 8]),
                "fair": len([e for e in evaluations if 4 <= e.get('overall_quality', 0) < 6]),
                "poor": len([e for e in evaluations if e.get('overall_quality', 0) < 4])
            },
            "most_used_tags": sorted(evaluations, key=lambda x: x.get('used_by_norm_count', 0), reverse=True)[:10],
            "structural_analysis": {
                "avg_depth": round(statistics.mean([
                    len(eval.get('tag_value', '').split('.')) 
                    for eval in evaluations if eval.get('tag_value')
                ]), 2) if evaluations else 0,
                "single_level_tags": len([
                    eval for eval in evaluations 
                    if '.' not in eval.get('tag_value', '')
                ]),
                "deep_tags": len([
                    eval for eval in evaluations 
                    if len(eval.get('tag_value', '').split('.')) > 4
                ])
            }
        }
    }
    
    # Save output if requested
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Evaluation report saved to {output_file}")
    
    return report


def print_summary_report(report: Dict[str, Any]) -> None:
    """Print a summary of the evaluation report.
    
    Args:
        report: Complete evaluation report
    """
    meta = report.get('meta_report', {})
    summary = report.get('summary', {})
    
    print("\n" + "="*60)
    print("TAG QUALITY EVALUATION REPORT")
    print("="*60)
    
    print(f"Total tags evaluated: {meta.get('total_tags_evaluated', 0)}")
    print(f"Average overall quality: {meta.get('average_overall_quality', 0)}/10")
    print(f"Average uniqueness: {meta.get('average_uniqueness', 0)}/10")
    print(f"Average entity structure: {meta.get('average_entity_structure', 0)}/10")
    print(f"Quality range: {meta.get('min_quality', 0)}-{meta.get('max_quality', 0)}")
    
    print(f"\nStructural Analysis:")
    struct = summary.get('structural_analysis', {})
    print(f"  Average tag depth: {struct.get('avg_depth', 0)}")
    print(f"  Single-level tags: {struct.get('single_level_tags', 0)}")
    print(f"  Deep tags (>4 levels): {struct.get('deep_tags', 0)}")
    print(f"  Unique prefixes: {meta.get('unique_prefixes_count', 0)}")
    
    print(f"\nDuplicate Analysis:")
    print(f"  Potential duplicates found: {meta.get('potential_duplicates_count', 0)}")
    if meta.get('potential_duplicates'):
        print("  Examples:")
        for tag1, tag2 in meta.get('potential_duplicates', [])[:3]:
            print(f"    '{tag1}' ~ '{tag2}'")
    
    dist = summary.get('quality_distribution', {})
    print("\nQuality Distribution:")
    print(f"  Excellent (8-10): {dist.get('excellent', 0)}")
    print(f"  Good (6-8):       {dist.get('good', 0)}")
    print(f"  Fair (4-6):       {dist.get('fair', 0)}")
    print(f"  Poor (<4):        {dist.get('poor', 0)}")
    
    lowest = summary.get('lowest_quality_tags', [])
    if lowest:
        print(f"\nLowest Quality Tags (showing top {len(lowest)}):")
        for i, tag in enumerate(lowest, 1):
            print(f"  {i}. Tag: {tag.get('tag_value', 'unknown')} | Quality: {tag.get('overall_quality', 0)}/10")
            print(f"     Used by {tag.get('used_by_norm_count', 0)} norm(s)")
            if tag.get('structural_issues'):
                print(f"     Issues: {', '.join(tag.get('structural_issues', [])[:2])}")
            print()
    
    most_used = summary.get('most_used_tags', [])
    if most_used:
        print(f"\nMost Used Tags:")
        for i, tag in enumerate(most_used[:5], 1):
            print(f"  {i}. {tag.get('tag_value', 'unknown')} ({tag.get('used_by_norm_count', 0)} norms) | Quality: {tag.get('overall_quality', 0)}/10")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Evaluate tag quality from combined_extractions.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tag_evaluator.py combined_extractions.json
  python tag_evaluator.py input.json --output tag_evaluation_report.json
  
Environment Variables:
  OPENROUTER_API_KEY: Required API key for OpenRouter service
        """
    )
    
    parser.add_argument(
        'input_file',
        type=Path,
        help='Path to combined_extractions.json file'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output path for evaluation report JSON file'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress output'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not args.input_file.exists():
        print(f"Error: Input file {args.input_file} does not exist")
        sys.exit(1)
    
    # Check for API key
    if not os.getenv('OPENROUTER_API_KEY') and not os.getenv('GEMINI_API_KEY'):
        print("Error: Either OPENROUTER_API_KEY or GEMINI_API_KEY environment variable is required")
        print("Get OpenRouter API key from: https://openrouter.ai/keys")
        print("Get Gemini API key from: https://ai.google.dev/gemini-api/docs/api-key")
        sys.exit(1)
    
    try:
        # Run evaluation
        report = evaluate_tags(args.input_file, args.output)
        
        if not args.quiet and "error" not in report:
            print_summary_report(report)
            
    except Exception as e:
        print(f"Error during evaluation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()