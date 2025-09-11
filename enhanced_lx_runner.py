#!/usr/bin/env python3
"""Enhanced LangExtract Runner with Docling Document processing.

This runner implements the enhanced extraction pipeline as outlined in 
docs/prompts/extraction_pipeline_guide.md using Docling Documents directly,
with ToC-driven chunking and headline fixes.

Usage:
    python enhanced_lx_runner.py document.pdf --output-dir results/
    python enhanced_lx_runner.py document.pdf --docling-path converted.json --output-dir results/
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import tempfile

# Import enhanced pipeline components (commented out for chunking-only version)
# from extraction_pipeline.enhanced_pipeline import EnhancedExtractionPipeline

# Import existing langextract functionality (commented out for chunking-only version)  
# import langextract as lx
# from langextract import factory
# from langextract import providers

# Import existing modules (commented out for chunking-only version)
# from section_chunker import create_section_chunks
# from chunk_evaluator import evaluate_chunks


def setup_langextract_providers():
    """Setup LangExtract providers and configuration."""
    # Commented out for chunking-only test version
    pass


def create_extraction_config():
    """Create LangExtract model configuration."""
    # Commented out for chunking-only test version
    pass


def load_prompt_and_examples():
    """Load prompt and examples for extraction."""
    # Commented out for chunking-only test version
    return "", []


def extract_with_langextract(
    text: str, 
    prompt: str, 
    examples: List[Any], 
    config: Any
) -> Optional[Dict[str, Any]]:
    """Extract using LangExtract with error handling."""
    # Commented out for chunking-only test version
    return None


def create_chunks_from_toc_and_docling(
    toc_data: List[Dict[str, Any]],
    docling_document: Dict[str, Any],
    max_chars: int = 5000
) -> List[Tuple[str, Dict[str, Any]]]:
    """Create chunks based on ToC headlines, treating non-ToC section headers as text body.
    
    This function creates chunks based only on ToC entries. Section headers that are present
    in the Docling Document but not in the ToC are treated as part of the text body.
    
    Args:
        toc_data: Table of Contents data with hierarchical structure
        docling_document: The headline-fixed Docling Document JSON
        max_chars: Maximum characters per chunk
        
    Returns:
        List of (chunk_text, section_info) tuples
    """
    chunks = []
    texts = docling_document.get('texts', [])
    
    # Extract all ToC headline titles for comparison
    toc_titles = set()
    
    def collect_toc_titles(toc_nodes: List[Dict[str, Any]]) -> None:
        """Recursively collect all ToC titles."""
        for node in toc_nodes:
            title = node.get('title', '').strip()
            if title:
                toc_titles.add(title.lower())
            children = node.get('children', [])
            if children:
                collect_toc_titles(children)
    
    collect_toc_titles(toc_data)
    print(f"[DEBUG] Found {len(toc_titles)} ToC titles")
    
    # Process each ToC entry to create chunks
    def process_toc_node(
        node: Dict[str, Any], 
        parent_path: List[str] = None
    ) -> None:
        if parent_path is None:
            parent_path = []
            
        title = node.get('title', '').strip()
        level = node.get('level', 1)
        start_page = node.get('start_page')
        end_page = node.get('end_page')
        
        if not title:
            return
            
        # Skip index and document info sections
        full_path = parent_path + [title]
        if any('índice' in part.lower() or 'document info' in part.lower() 
               for part in full_path):
            return
        
        print(f"[DEBUG] Processing ToC section: {title} (pages {start_page}-{end_page})")
        
        # Collect content for this ToC section from the Docling document
        section_content_parts = []
        
        # Create a set of child ToC titles to exclude from this section's content
        child_toc_titles = set()
        children = node.get('children', [])
        for child in children:
            child_title = child.get('title', '').strip().lower()
            if child_title:
                child_toc_titles.add(child_title)
        
        # Find content within the page range of this ToC section
        for text_item in texts:
            # Get page number from provenance
            page_no = get_page_from_provenance(text_item)
            
            # Check if this content is within the ToC section's page range
            if start_page and end_page and start_page <= page_no <= end_page:
                text_content = text_item.get('text', '').strip()
                if text_content:
                    # Include ALL content (even section headers not in ToC) as text body
                    # But skip the main ToC header itself and child ToC headers
                    if text_item.get('label') == 'section_header':
                        if text_content.lower() == title.lower():
                            continue  # Skip the main section header for this ToC entry
                        elif text_content.lower() in child_toc_titles:
                            continue  # Skip child ToC headers (they'll be in their own chunks)
                    
                    section_content_parts.append(text_content)
        
        section_content = '\n'.join(section_content_parts)
        
        # Skip empty sections
        if not section_content.strip():
            print(f"[DEBUG] Skipping empty ToC section: {title}")
        else:
            # Create context header
            path_str = " → ".join(full_path)
            context_header = f"# Section: {title}\n"
            context_header += f"**Path:** {path_str}\n"
            context_header += f"**Level:** {level}\n"
            if start_page and end_page:
                context_header += f"**Pages:** {start_page}-{end_page}\n"
            
            # Create section info
            section_info = {
                "section_name": title,
                "section_level": level,
                "start_page": start_page,
                "end_page": end_page,
                "toc_path": full_path,
                "section_index": len(chunks)
            }
            
            if len(section_content) <= max_chars:
                # Single chunk
                chunk_text = f"{context_header}\n{section_content}"
                chunks.append((chunk_text, section_info))
                print(f"[DEBUG] Created chunk for ToC section '{title}' ({len(section_content)} chars)")
            else:
                # Split large content into multiple chunks
                split_chunks = split_large_content(section_content, max_chars)
                for j, split_content in enumerate(split_chunks):
                    chunk_header = f"{context_header} (Part {j+1}/{len(split_chunks)})\n"
                    chunk_text = f"{chunk_header}\n{split_content}"
                    chunks.append((chunk_text, section_info))
                print(f"[DEBUG] Split ToC section '{title}' into {len(split_chunks)} chunks")
        
        # Process child ToC nodes
        for child in children:
            process_toc_node(child, full_path)
    
    # Process all root ToC nodes
    for root_node in toc_data:
        process_toc_node(root_node)
    
    return chunks


def create_fallback_toc_from_docling(docling_document: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create a fallback ToC from main section headers in Docling Document.
    
    Args:
        docling_document: Docling Document JSON
        
    Returns:
        Minimal ToC structure
    """
    texts = docling_document.get('texts', [])
    toc_entries = []
    
    # Find level 1 section headers
    for text_item in texts:
        if (text_item.get('label') == 'section_header' and 
            text_item.get('level', 1) == 1):
            
            page_no = get_page_from_provenance(text_item)
            title = text_item.get('text', '').strip()
            
            if title:
                toc_entries.append({
                    'title': title,
                    'level': 1,
                    'start_page': page_no,
                    'end_page': page_no + 1,  # Simple fallback
                    'children': []
                })
    
    print(f"[INFO] Created fallback ToC with {len(toc_entries)} entries")
    return toc_entries


def get_page_from_provenance(text_item: Dict[str, Any]) -> int:
    """Extract page number from text item provenance.
    
    Args:
        text_item: Text item from Docling document
        
    Returns:
        Page number (1-based) or 0 if not found
    """
    prov = text_item.get('prov', [])
    if prov and isinstance(prov, list) and len(prov) > 0:
        first_prov = prov[0]
        if isinstance(first_prov, dict) and 'page_no' in first_prov:
            return first_prov['page_no']
    return 0


def split_large_content(content: str, max_chars: int) -> List[str]:
    """Split large content into smaller chunks with sentence overlap.
    
    Args:
        content: Content to split
        max_chars: Maximum characters per chunk
        
    Returns:
        List of content chunks
    """
    import re
    
    # Split into sentences
    sentences = re.split(r'[.!?]+\s+', content)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return [content]
    
    chunks = []
    current_chunk = []
    current_length = 0
    overlap_size = max(1, len(sentences) // 20)  # 5% overlap
    
    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        
        if current_length + len(sentence) <= max_chars:
            current_chunk.append(sentence)
            current_length += len(sentence) + 1  # +1 for space
            i += 1
        else:
            if current_chunk:
                # Finish current chunk
                chunks.append(' '.join(current_chunk))
                
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - overlap_size)
                current_chunk = current_chunk[overlap_start:]
                current_length = sum(len(s) + 1 for s in current_chunk)
            else:
                # Sentence too long, take it anyway
                current_chunk.append(sentence)
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_length = 0
                i += 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def run_enhanced_extraction(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    docling_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Run enhanced extraction pipeline on PDF document.
    
    Args:
        pdf_path: Path to source PDF file
        output_dir: Optional output directory
        docling_path: Optional path to pre-converted docling document (if None, will convert PDF)
        
    Returns:
        Dictionary with extraction results and metrics
    """
    if output_dir is None:
        output_dir = Path("output_runs") / "enhanced_run"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("[INFO] Setting up enhanced extraction pipeline...")
    print(f"[INFO] Processing PDF: {pdf_path}")
    
    # Generate Docling Document from PDF if not provided
    if docling_path is None or not docling_path.exists():
        print("[INFO] Converting PDF to Docling Document...")
        docling_path = output_dir / "converted_document.json"
        
        # Import and use the PDF to Docling Document converter
        sys.path.insert(0, str(Path(__file__).parent / "scripts"))
        try:
            from pdf_to_docling_document import convert_pdf_to_docling_document
            convert_pdf_to_docling_document(
                source=pdf_path,
                output_path=docling_path,
                verbose=False
            )
            print(f"[INFO] Docling Document saved to: {docling_path}")
        except ImportError as e:
            print(f"[ERROR] Could not import pdf_to_docling_document: {e}")
            print("[ERROR] Please ensure docling is installed: pip install docling")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] PDF to Docling Document conversion failed: {e}")
            sys.exit(1)
    
    # Apply ToC extraction and headline fixes using pdf_toc_extractor.py
    print("[INFO] Extracting ToC and fixing headlines in Docling Document...")
    fixed_docling_path = output_dir / "headline_fixed_doclingdocument.json" 
    
    try:
        from scripts.pdf_toc_extractor import process_pdf_and_docling
        process_pdf_and_docling(str(pdf_path), str(docling_path))
        
        # The pdf_toc_extractor saves the fixed document as headline_fixed_doclingdocument.json
        # in the same directory as the original docling document
        original_fixed_path = docling_path.parent / "headline_fixed_doclingdocument.json"
        if original_fixed_path.exists():
            # Move to our output directory
            import shutil
            shutil.move(str(original_fixed_path), str(fixed_docling_path))
            print(f"[INFO] Headline-fixed Docling Document saved to: {fixed_docling_path}")
        else:
            print("[WARNING] Headline fixing may have failed, using original Docling Document")
            fixed_docling_path = docling_path
            
    except Exception as e:
        print(f"[ERROR] ToC extraction and headline fixing failed: {e}")
        print("[INFO] Continuing with original Docling Document")
        fixed_docling_path = docling_path
    
    # Load the fixed Docling Document
    print("[INFO] Loading headline-fixed Docling Document...")
    with open(fixed_docling_path, 'r', encoding='utf-8') as f:
        docling_document = json.load(f)
    
    # Load ToC data generated by pdf_toc_extractor
    toc_path = docling_path.parent / "toc.json"
    toc_data = []
    
    if toc_path.exists():
        print(f"[INFO] Loading ToC data from: {toc_path}")
        with open(toc_path, 'r', encoding='utf-8') as f:
            toc_data = json.load(f)
        print(f"[INFO] Loaded {len(toc_data)} ToC entries")
    else:
        print("[WARNING] ToC data not found, attempting to extract from Docling Document headers")
        # Fallback: create minimal ToC from section headers
        toc_data = create_fallback_toc_from_docling(docling_document)
    
    # Create sections and chunks from ToC and fixed Docling Document
    print("[INFO] Creating ToC-based chunks (non-ToC headers treated as text body)...")
    chunks = create_chunks_from_toc_and_docling(toc_data, docling_document, max_chars=5000)
    
    print(f"[INFO] Created {len(chunks)} chunks for processing")
    
    # Save chunks for testing as requested
    chunks_output_path = output_dir / "generated_chunks.json"
    chunks_data = []
    
    for i, (chunk_text, section_info) in enumerate(chunks):
        chunk_data = {
            "chunk_id": i + 1,
            "section_name": section_info.get("section_name", f"Section {i+1}"),
            "section_path": section_info.get("toc_path", []),
            "start_page": section_info.get("start_page"),
            "end_page": section_info.get("end_page"), 
            "section_level": section_info.get("section_level", 1),
            "chunk_text": chunk_text,
            "char_count": len(chunk_text),
            "has_context_header": chunk_text.startswith("# Section:")
        }
        chunks_data.append(chunk_data)
    
    # Save chunks to JSON file for testing and validation
    with open(chunks_output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "pipeline_info": {
                "version": "1.0",
                "method": "docling_toc_based_chunking", 
                "pdf_source": str(pdf_path),
                "docling_document": str(fixed_docling_path),
                "total_chunks": len(chunks)
            },
            "chunks": chunks_data
        }, f, indent=2, ensure_ascii=False)
    
    print(f"[INFO] Generated chunks saved to: {chunks_output_path}")
    print(f"[SUCCESS] Enhanced pipeline test completed up to chunk creation!")
    print(f"  - Input PDF: {pdf_path}")
    print(f"  - Docling Document: {fixed_docling_path}")
    print(f"  - Generated chunks: {len(chunks)}")
    print(f"  - Chunks saved to: {chunks_output_path}")
    
    # For now, return the chunks data instead of running full extraction
    return {
        "chunks": chunks_data,
        "docling_document": docling_document,
        "output_files": {
            "docling_document": fixed_docling_path,
            "chunks": chunks_output_path
        }
    }


def main():
    """Main entry point for enhanced extraction runner."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Enhanced LangExtract Runner with PDF anchoring and quality metrics"
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to source PDF file"
    )
    parser.add_argument(
        "--docling-path",
        type=Path,
        help="Optional path to pre-converted Docling Document file (if not provided, PDF will be converted)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for results (default: output_runs/enhanced_run)"
    )
    
    args = parser.parse_args()
    
    if not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    if args.docling_path and not args.docling_path.exists():
        print(f"Error: Docling Document file not found: {args.docling_path}")
        sys.exit(1)
    
    try:
        results = run_enhanced_extraction(
            args.pdf_path,
            args.output_dir,
            args.docling_path
        )
        
        print("\n[SUCCESS] Enhanced pipeline test completed successfully!")
        
        # Print summary statistics
        chunks_data = results["chunks"]
        print("\nPipeline Summary:")
        print(f"  Total Chunks Generated: {len(chunks_data)}")
        print(f"  Average Chunk Size: {sum(c['char_count'] for c in chunks_data) // len(chunks_data) if chunks_data else 0} characters")
        
        sections_by_level = {}
        for chunk in chunks_data:
            level = chunk.get('section_level', 1)
            sections_by_level[level] = sections_by_level.get(level, 0) + 1
        
        print("  Sections by Level:")
        for level in sorted(sections_by_level.keys()):
            print(f"    Level {level}: {sections_by_level[level]} sections")
        
        print(f"\nOutput Files:")
        for file_type, file_path in results["output_files"].items():
            print(f"  {file_type}: {file_path}")
        
        print(f"\nNext steps: Run langextract on the generated chunks to extract norms and parameters.")
        
    except Exception as e:
        print(f"[ERROR] Enhanced extraction failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()