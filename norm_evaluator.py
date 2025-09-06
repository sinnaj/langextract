#!/usr/bin/env python3
"""Norm evaluator for extraction quality assessment.

This script evaluates norm extractions using an LLM (OpenRouter with Gemini 2.5 Flash)
to assess norm quality based on two key criteria:

1. Atomicity: How well is this norm interpretable/implementable without additional context
2. Applicability & Satisfied structure: How meaningful & actionable are the application 
   and what needs to be satisfied criteria

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


def create_evaluation_prompt(norm: Dict[str, Any]) -> str:
    """Create evaluation prompt for a single norm.
    
    Args:
        norm: Norm extraction dictionary containing norm attributes
        
    Returns:
        Evaluation prompt string
    """
    attributes = norm.get('attributes', {})
    norm_statement = attributes.get('norm_statement', '')
    applies_if = attributes.get('applies_if', '')
    satisfied_if = attributes.get('satisfied_if', '')
    
    prompt = f"""You are an expert evaluator assessing the quality of extracted regulatory norms. 

Please evaluate the following norm on two key dimensions:

**NORM TO EVALUATE:**
Statement: {norm_statement}
Applies If: {applies_if}
Satisfied If: {satisfied_if}

**EVALUATION CRITERIA:**

1. **Atomicity** (Score 1-10): How well is this norm interpretable and implementable without requiring additional context? Consider:
   - Is the norm self-contained and complete?
   - Can someone understand the requirements without external references?
   - Are all necessary conditions and parameters clearly specified?

2. **Applicability & Satisfied Structure** (Score 1-10): How meaningful and actionable are the "applies_if" and "satisfied_if" criteria? Consider:
   - Are the conditions clearly defined and measurable?
   - Can the criteria be practically evaluated/verified?
   - Is the logic sound and implementable?
   - Are the conditions specific enough to be actionable?

**RESPONSE FORMAT:**
Please respond with a JSON object containing:
{{
  "atomicity_score": <integer 1-10>,
  "atomicity_reasoning": "<brief explanation>",
  "applicability_structure_score": <integer 1-10>, 
  "applicability_structure_reasoning": "<brief explanation>",
  "overall_quality": <average of the two scores>,
  "key_issues": ["<issue1>", "<issue2>", ...],
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


def evaluate_norm(norm: Dict[str, Any], model: Any) -> Dict[str, Any]:
    """Evaluate a single norm using the LLM.
    
    Args:
        norm: Norm extraction dictionary
        model: LLM model instance
        
    Returns:
        Evaluation results dictionary
    """
    prompt = create_evaluation_prompt(norm)
    
    try:
        # Use langextract's extract function for structured output
        result = lx.extract(
            model=model,
            text=prompt,
            schema={
                "type": "object",
                "properties": {
                    "atomicity_score": {"type": "integer", "minimum": 1, "maximum": 10},
                    "atomicity_reasoning": {"type": "string"},
                    "applicability_structure_score": {"type": "integer", "minimum": 1, "maximum": 10},
                    "applicability_structure_reasoning": {"type": "string"},
                    "overall_quality": {"type": "number"},
                    "key_issues": {"type": "array", "items": {"type": "string"}},
                    "suggestions": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["atomicity_score", "applicability_structure_score", "overall_quality"]
            }
        )
        
        evaluation = result[0] if result else {}
        
        # Add norm identification
        evaluation["norm_id"] = norm.get('attributes', {}).get('id', 'unknown')
        evaluation["norm_statement"] = norm.get('attributes', {}).get('norm_statement', '')
        
        return evaluation
        
    except Exception as e:
        # Return error evaluation
        return {
            "norm_id": norm.get('attributes', {}).get('id', 'unknown'),
            "norm_statement": norm.get('attributes', {}).get('norm_statement', ''),
            "atomicity_score": 1,
            "atomicity_reasoning": f"Evaluation failed: {str(e)}",
            "applicability_structure_score": 1,
            "applicability_structure_reasoning": f"Evaluation failed: {str(e)}",
            "overall_quality": 1.0,
            "key_issues": ["Evaluation failed"],
            "suggestions": ["Re-evaluate manually"],
            "evaluation_error": str(e)
        }


def evaluate_norms(input_file: Path, output_file: Optional[Path] = None) -> Dict[str, Any]:
    """Evaluate all norms in a combined_extractions.json file.
    
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
    norms = [ext for ext in extractions if ext.get('extraction_class') == 'NORM']
    
    if not norms:
        print(f"No NORM extractions found in {input_file}")
        return {"error": "No norms found"}
    
    print(f"Found {len(norms)} norms to evaluate...")
    
    # Create LLM client
    model = create_llm_client()
    
    # Evaluate norms
    evaluations = []
    for i, norm in enumerate(norms):
        print(f"Evaluating norm {i+1}/{len(norms)}: {norm.get('attributes', {}).get('id', 'unknown')}")
        
        evaluation = evaluate_norm(norm, model)
        evaluations.append(evaluation)
    
    # Sort by overall quality (lowest first)
    evaluations.sort(key=lambda x: x.get('overall_quality', 10))
    
    # Calculate meta statistics
    quality_scores = [eval.get('overall_quality', 0) for eval in evaluations if eval.get('overall_quality')]
    atomicity_scores = [eval.get('atomicity_score', 0) for eval in evaluations if eval.get('atomicity_score')]
    applicability_scores = [eval.get('applicability_structure_score', 0) for eval in evaluations if eval.get('applicability_structure_score')]
    
    meta_report = {
        "total_norms_evaluated": len(evaluations),
        "average_overall_quality": round(statistics.mean(quality_scores), 2) if quality_scores else 0,
        "average_atomicity": round(statistics.mean(atomicity_scores), 2) if atomicity_scores else 0,
        "average_applicability_structure": round(statistics.mean(applicability_scores), 2) if applicability_scores else 0,
        "median_overall_quality": round(statistics.median(quality_scores), 2) if quality_scores else 0,
        "min_quality": min(quality_scores) if quality_scores else 0,
        "max_quality": max(quality_scores) if quality_scores else 0,
        "evaluation_timestamp": datetime.now().isoformat(),
        "source_file": str(input_file)
    }
    
    # Compile final report
    report = {
        "meta_report": meta_report,
        "norm_evaluations": evaluations,
        "summary": {
            "lowest_quality_norms": evaluations[:5],  # Top 5 lowest quality
            "quality_distribution": {
                "excellent": len([e for e in evaluations if e.get('overall_quality', 0) >= 8]),
                "good": len([e for e in evaluations if 6 <= e.get('overall_quality', 0) < 8]),
                "fair": len([e for e in evaluations if 4 <= e.get('overall_quality', 0) < 6]),
                "poor": len([e for e in evaluations if e.get('overall_quality', 0) < 4])
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
    print("NORM QUALITY EVALUATION REPORT")
    print("="*60)
    
    print(f"Total norms evaluated: {meta.get('total_norms_evaluated', 0)}")
    print(f"Average overall quality: {meta.get('average_overall_quality', 0)}/10")
    print(f"Average atomicity: {meta.get('average_atomicity', 0)}/10")
    print(f"Average applicability structure: {meta.get('average_applicability_structure', 0)}/10")
    print(f"Quality range: {meta.get('min_quality', 0)}-{meta.get('max_quality', 0)}")
    
    dist = summary.get('quality_distribution', {})
    print("\nQuality Distribution:")
    print(f"  Excellent (8-10): {dist.get('excellent', 0)}")
    print(f"  Good (6-8):       {dist.get('good', 0)}")
    print(f"  Fair (4-6):       {dist.get('fair', 0)}")
    print(f"  Poor (<4):        {dist.get('poor', 0)}")
    
    lowest = summary.get('lowest_quality_norms', [])
    if lowest:
        print(f"\nLowest Quality Norms (showing top {len(lowest)}):")
        for i, norm in enumerate(lowest, 1):
            print(f"  {i}. ID: {norm.get('norm_id', 'unknown')} | Quality: {norm.get('overall_quality', 0)}/10")
            print(f"     Statement: {norm.get('norm_statement', '')[:100]}...")
            if norm.get('key_issues'):
                print(f"     Issues: {', '.join(norm.get('key_issues', [])[:2])}")
            print()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Evaluate norm quality from combined_extractions.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python norm_evaluator.py combined_extractions.json
  python norm_evaluator.py input.json --output norm_evaluation_report.json
  
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
        report = evaluate_norms(args.input_file, args.output)
        
        if not args.quiet and "error" not in report:
            print_summary_report(report)
            
    except Exception as e:
        print(f"Error during evaluation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()