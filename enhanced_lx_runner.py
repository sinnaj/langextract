#!/usr/bin/env python3
"""Enhanced LangExtract Runner with improved extraction pipeline.

This runner implements the enhanced extraction pipeline as outlined in 
docs/prompts/extraction_pipeline_guide.md with deterministic IDs, PDF anchoring,
and comprehensive quality metrics.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import tempfile

# Import enhanced pipeline components
from extraction_pipeline.enhanced_pipeline import EnhancedExtractionPipeline

# Import existing langextract functionality
import langextract as lx
from langextract import factory
from langextract import providers

# Import existing modules
from section_chunker import create_section_chunks
from chunk_evaluator import evaluate_chunks


def setup_langextract_providers():
    """Setup LangExtract providers and configuration."""
    providers.load_builtins_once()
    providers.load_plugins_once()
    
    try:
        avail = providers.list_providers()
        print(f"[DEBUG] Providers available: {sorted(list(avail.keys()))}")
    except Exception:
        pass


def create_extraction_config() -> factory.ModelConfig:
    """Create LangExtract model configuration."""
    from dotenv import load_dotenv
    load_dotenv()
    
    USE_OPENROUTER = os.getenv("USE_OPENROUTER", "1").lower() in {"1","true","yes"}
    OPENROUTER_KEY = os.environ.get("OPENAI_API_KEY")
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    
    if USE_OPENROUTER:
        if not OPENROUTER_KEY:
            print("WARNING: OPENROUTER (OPENAI_API_KEY) key not set – OpenRouter call will fail.", file=sys.stderr)
        
        MODEL_ID = "google/gemini-2.5-flash"
        return factory.ModelConfig(
            model_id=MODEL_ID,
            provider="OpenAILanguageModel",
            provider_kwargs={
                "api_key": OPENROUTER_KEY,
                "base_url": "https://openrouter.ai/api/v1",
                "temperature": 0.15,
                "format_type": lx.data.FormatType.JSON,
                "max_workers": 20,
            },
        )
    else:
        if not GOOGLE_API_KEY:
            print("WARNING: GOOGLE_API_KEY not set – direct Gemini call will likely fail.", file=sys.stderr)
        
        MODEL_ID = "gemini-2.5-flash"
        return factory.ModelConfig(
            model_id=MODEL_ID,
            provider="GeminiLanguageModel",
            provider_kwargs={
                "api_key": GOOGLE_API_KEY,
                "temperature": 0.15,
                "format_type": lx.data.FormatType.JSON,
            },
        )


def load_prompt_and_examples() -> tuple[str, List[Any]]:
    """Load prompt and examples for extraction."""
    # Load prompt
    prompt_file = Path("input_promptfiles/prompt_norm_extraction.md")
    if prompt_file.exists():
        prompt_description = prompt_file.read_text(encoding="utf-8")
    else:
        prompt_description = (
            "Extract Norms, Tags, and Parameters. Return a JSON object with an 'extractions' array."
        )
    
    # Load examples
    import importlib.util
    examples_file = Path("input_examplefiles/default.py")
    if examples_file.exists():
        spec = importlib.util.spec_from_file_location("lx_examples", str(examples_file))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            examples = getattr(module, "EXAMPLES", [])
        else:
            examples = []
    else:
        examples = []
    
    return prompt_description, examples


def extract_with_langextract(
    text: str, 
    prompt: str, 
    examples: List[Any], 
    config: factory.ModelConfig
) -> Optional[Dict[str, Any]]:
    """Extract using LangExtract with error handling."""
    try:
        extract_kwargs = {
            "text_or_documents": text,
            "prompt_description": prompt,
            "examples": examples,
            "config": config,
            "fence_output": False,
            "use_schema_constraints": False,
            "max_char_buffer": 5000,
            "extraction_passes": 2,
            "resolver_params": {
                "fence_output": False,
                "format_type": lx.data.FormatType.JSON,
                "suppress_parse_errors_default": False,
            },
        }
        
        annotated = lx.extract(**extract_kwargs)
        
        # Convert to dict format
        result_items = []
        extractions = getattr(annotated, "extractions", [])
        
        for extraction in extractions:
            if extraction is None:
                continue
                
            attributes = getattr(extraction, "attributes", {})
            extraction_class = getattr(extraction, "extraction_class", None)
            
            item = {
                "extraction_class": extraction_class,
                "extraction_text": getattr(extraction, "extraction_text", None),
                "attributes": attributes,
                "char_interval": getattr(extraction, "char_interval", None),
                "alignment_status": getattr(extraction, "alignment_status", None),
            }
            result_items.append(item)
        
        return {
            "document_id": getattr(annotated, "document_id", None),
            "extractions": result_items
        }
        
    except Exception as e:
        print(f"[ERROR] LangExtract failed: {e}", file=sys.stderr)
        return None


def run_enhanced_extraction(
    input_path: Path,
    pdf_path: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Run enhanced extraction pipeline on input document.
    
    Args:
        input_path: Path to input markdown/text file
        pdf_path: Optional path to source PDF for ToC/anchoring
        output_dir: Optional output directory
        
    Returns:
        Dictionary with extraction results and metrics
    """
    if output_dir is None:
        output_dir = Path("output_runs") / "enhanced_run"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("[INFO] Setting up enhanced extraction pipeline...")
    
    # Setup providers and configuration
    setup_langextract_providers()
    config = create_extraction_config()
    prompt, examples = load_prompt_and_examples()
    
    # Initialize enhanced pipeline
    if pdf_path and pdf_path.exists():
        pipeline = EnhancedExtractionPipeline(pdf_path)
        pipeline.load_document_data()
        pipeline.create_sections()
        
        # Create chunks from enhanced sections
        print("[INFO] Creating section-based chunks from ToC intervals...")
        chunks = pipeline.create_chunks_for_extraction(max_chars=5000)
        
    else:
        # Fallback: use existing section chunker on input text
        print("[INFO] Using fallback section chunking (no PDF ToC available)...")
        input_text = input_path.read_text(encoding="utf-8")
        
        # Use existing section chunker
        section_chunks = create_section_chunks(input_text)
        chunk_evaluations = evaluate_chunks(section_chunks)
        
        # Convert to format expected by enhanced pipeline
        chunks = []
        for section_chunk, evaluation in chunk_evaluations:
            if evaluation.processing_type == "extract":
                chunk_text = section_chunk.chunk_text
                # Create a minimal enhanced section for compatibility
                from extraction_pipeline.data_models import EnhancedSection
                section = EnhancedSection(
                    section_id=section_chunk.section_metadata.section_id,
                    section_name=section_chunk.section_metadata.section_name,
                    section_level=section_chunk.section_metadata.section_level,
                    section_index=section_chunk.section_metadata.section_index,
                    toc_path=[section_chunk.section_metadata.section_name]
                )
                chunks.append((chunk_text, section))
        
        # Create minimal pipeline for processing
        pipeline = EnhancedExtractionPipeline()
        pipeline.sections = [section for _, section in chunks]
    
    print(f"[INFO] Processing {len(chunks)} section chunks...")
    
    # Extract from each chunk
    extraction_results = []
    for i, (chunk_text, section) in enumerate(chunks):
        print(f"[INFO] Extracting from chunk {i+1}/{len(chunks)}: {section.section_name}")
        
        result = extract_with_langextract(chunk_text, prompt, examples, config)
        if result:
            extraction_results.append(result)
        else:
            # Create empty result for failed extractions
            extraction_results.append({
                "document_id": f"chunk_{i}",
                "extractions": []
            })
    
    # Process results through enhanced pipeline
    print("[INFO] Processing extraction results through enhanced pipeline...")
    enhanced_sections, quality_metrics = pipeline.process_extraction_results(
        extraction_results, [section for _, section in chunks]
    )
    
    # Generate comprehensive report
    report = pipeline.generate_extraction_report()
    
    # Save enhanced results
    enhanced_output_path = output_dir / "enhanced_extractions.json"
    pipeline.export_enhanced_results(enhanced_output_path, include_raw_data=True)
    
    # Save extraction report
    report_path = output_dir / "extraction_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"[INFO] Enhanced extraction complete:")
    print(f"  - Sections processed: {quality_metrics.total_sections}")
    print(f"  - Norms extracted: {quality_metrics.total_norms}")
    print(f"  - Anchoring success rate: {quality_metrics.anchoring_success_rate():.1%}")
    print(f"  - Parameter normalization: {quality_metrics.parameter_normalization_coverage:.1%}")
    print(f"  - Results saved to: {enhanced_output_path}")
    print(f"  - Report saved to: {report_path}")
    
    return {
        "enhanced_sections": enhanced_sections,
        "quality_metrics": quality_metrics,
        "extraction_report": report,
        "output_files": {
            "enhanced_results": enhanced_output_path,
            "extraction_report": report_path
        }
    }


def main():
    """Main entry point for enhanced extraction runner."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced LangExtract Runner with PDF anchoring and quality metrics"
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to input markdown/text file"
    )
    parser.add_argument(
        "--pdf-path",
        type=Path,
        help="Optional path to source PDF for ToC extraction and anchoring"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for results (default: output_runs/enhanced_run)"
    )
    
    args = parser.parse_args()
    
    if not args.input_path.exists():
        print(f"Error: Input file not found: {args.input_path}")
        sys.exit(1)
    
    if args.pdf_path and not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    try:
        results = run_enhanced_extraction(
            args.input_path,
            args.pdf_path,
            args.output_dir
        )
        
        print("\n[SUCCESS] Enhanced extraction completed successfully!")
        
        # Print summary statistics
        quality_metrics = results["quality_metrics"]
        print("\nQuality Metrics Summary:")
        print(f"  Total Sections: {quality_metrics.total_sections}")
        print(f"  Total Norms: {quality_metrics.total_norms}")
        print(f"  Anchoring Success: {quality_metrics.anchoring_success_rate():.1%}")
        print(f"    - Exact matches: {quality_metrics.anchoring_success_exact}")
        print(f"    - Normalized matches: {quality_metrics.anchoring_success_normalized}")
        print(f"    - Fuzzy matches: {quality_metrics.anchoring_success_fuzzy}")
        print(f"    - Fallbacks: {quality_metrics.anchoring_fallback}")
        print(f"  Parameter normalization: {quality_metrics.parameter_normalization_coverage:.1%}")
        print(f"  Low confidence norms: {len(quality_metrics.low_confidence_norms)}")
        
    except Exception as e:
        print(f"[ERROR] Enhanced extraction failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()