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
import gc
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import tempfile

# Memory management constants
MAX_SECTION_SIZE_MB = 50  # Maximum size for a section before chunking
MAX_CHUNK_SIZE_CHARS = 50000  # Maximum characters per chunk to prevent OOM
MEMORY_WARNING_THRESHOLD_MB = 1000  # Warn if memory usage exceeds this

# Import LangExtract functionality
import langextract as lx
from langextract import factory
from langextract import providers
from dotenv import load_dotenv

# Import postprocessing modules
from postprocessing.extract_tags import extract_tags_from_norms
from postprocessing.extract_params import extract_parameters_from_norms


def setup_langextract_providers():
    """Setup LangExtract providers and configuration."""
    load_dotenv()
    
    # Ensure provider registry is populated
    providers.load_builtins_once()
    providers.load_plugins_once()
    
    try:
        avail = providers.list_providers()
        print(f"[DEBUG] Providers available: {sorted(list(avail.keys()))}")
    except Exception as e:
        print(f"[WARNING] Could not list providers: {e}")
    
    # Check for API keys
    USE_OPENROUTER = os.getenv("USE_OPENROUTER", "1").lower() in {"1","true","yes"}
    OPENROUTER_KEY = os.environ.get("OPENAI_API_KEY")
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    
    if USE_OPENROUTER and not OPENROUTER_KEY:
        print("WARNING: OPENROUTER (OPENAI_API_KEY) key not set – OpenRouter call will fail.", file=sys.stderr)
    elif not USE_OPENROUTER and not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set – direct Gemini call will likely fail.", file=sys.stderr)
    
    return USE_OPENROUTER, OPENROUTER_KEY, GOOGLE_API_KEY


def get_memory_usage_mb() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        # Fallback - no memory monitoring
        return 0.0


def check_memory_usage(operation: str = "") -> None:
    """Check and log memory usage, warn if high."""
    memory_mb = get_memory_usage_mb()
    if memory_mb > MEMORY_WARNING_THRESHOLD_MB:
        print(f"[WARNING] High memory usage during {operation}: {memory_mb:.1f} MB")
    else:
        print(f"[DEBUG] Memory usage during {operation}: {memory_mb:.1f} MB")


def force_garbage_collection() -> None:
    """Force garbage collection to free memory."""
    gc.collect()
    print("[DEBUG] Forced garbage collection")


def estimate_content_size_mb(content: str) -> float:
    """Estimate memory size of content in MB."""
    return len(content.encode('utf-8')) / 1024 / 1024


def create_extraction_config(model_id: str = "google/gemini-2.0-flash-exp", temperature: float = 0.15):
    """Create LangExtract model configuration."""
    USE_OPENROUTER, OPENROUTER_KEY, GOOGLE_API_KEY = setup_langextract_providers()
    
    # Process model ID - use provided model if it contains provider info, otherwise prepend prefix
    if USE_OPENROUTER and not model_id.startswith("google/"):
        MODEL_ID = f"google/{model_id}" if not "/" in model_id else model_id
    else:
        MODEL_ID = model_id
    MODEL_TEMPERATURE = temperature
    
    if USE_OPENROUTER:
        cfg = factory.ModelConfig(
            model_id=MODEL_ID,
            provider="OpenAILanguageModel",
            provider_kwargs={
                "api_key": OPENROUTER_KEY,
                "base_url": "https://openrouter.ai/api/v1",
                "temperature": MODEL_TEMPERATURE,
                "format_type": lx.data.FormatType.JSON,
                "max_workers": 20,
            },
        )
    else:
        cfg = factory.ModelConfig(
            model_id=MODEL_ID,
            provider="GeminiLanguageModel",
            provider_kwargs={
                "api_key": GOOGLE_API_KEY,
                "temperature": MODEL_TEMPERATURE,
                "format_type": lx.data.FormatType.JSON,
            },
        )
    
    return cfg, USE_OPENROUTER, OPENROUTER_KEY


def should_skip_section_for_extraction(section_name: str) -> bool:
    """Check if section should be skipped from LX extraction.
    
    Skips sections that match Índice (Index) or Anejo (Annex) patterns.
    
    Args:
        section_name: Name of the section to check
        
    Returns:
        True if section should be skipped from extraction, False otherwise
    """
    import re
    
    if not section_name:
        return False
    
    # Convert to lowercase for case-insensitive matching
    section_lower = section_name.lower().strip()
    
    # Define patterns for indices and annexes
    skip_patterns = [
        r'\bíndice\b',               # Spanish: Índice
        r'\bindex\b',                # English: Index
        r'\btable\s+of\s+contents\b', # English: Table of Contents
        r'\banejo\b',                # Spanish: Anejo (Annex)  
        r'\bannex\b',                # English: Annex
        r'\bappendix\b',             # English: Appendix
        r'\bapéndice\b',             # Spanish: Apéndice
    ]
    
    # Check if any pattern matches
    for pattern in skip_patterns:
        if re.search(pattern, section_lower):
            print(f"[INFO] Skipping section from LX extraction (matches {pattern}): {section_name}")
            return True
    
    return False


def load_prompt_and_examples(
    prompt_file: Optional[str] = None, 
    examples_file: Optional[str] = None
):
    """Load prompt and examples for extraction."""
    # Default file paths
    PROMPT_FILE = Path(prompt_file) if prompt_file else Path("input_promptfiles/prompt.md")
    DEFAULT_EXAMPLES_PATH = Path(examples_file) if examples_file else Path("input_examplefiles/default.py")
    
    # Load prompt
    if PROMPT_FILE.exists():
        PROMPT_DESCRIPTION = PROMPT_FILE.read_text(encoding="utf-8")
    else:
        print(f"[WARN] Prompt file missing at {PROMPT_FILE}; using minimal default prompt.", file=sys.stderr)
        PROMPT_DESCRIPTION = (
            "Extract Norms, Tags, and Parameters from the given text. "
            "Return a JSON object with an 'extractions' array."
        )
    
    # Load examples
    examples = []
    if DEFAULT_EXAMPLES_PATH.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("lx_examples", str(DEFAULT_EXAMPLES_PATH))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                examples = getattr(module, "EXAMPLES", [])
                print(f"[INFO] Loaded {len(examples)} few-shot examples from {DEFAULT_EXAMPLES_PATH}")
        except Exception as e:
            print(f"[WARN] Failed to load examples from {DEFAULT_EXAMPLES_PATH}: {e}")
    else:
        print(f"[WARN] Examples file not found at {DEFAULT_EXAMPLES_PATH}")
    
    return PROMPT_DESCRIPTION, examples


def extract_with_langextract(
    text: str, 
    prompt: str, 
    examples: List[Any], 
    config: Any,
    section_metadata: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Extract using LangExtract with error handling."""
    try:
        # Set up extraction parameters
        MAX_CHAR_BUFFER = 5000
        EXTRACTION_PASSES = 2
        
        extract_kwargs = dict(
            text_or_documents=text,
            prompt_description=prompt,
            examples=examples,
            config=config,
            fence_output=False,
            use_schema_constraints=False,
            max_char_buffer=MAX_CHAR_BUFFER,
            extraction_passes=EXTRACTION_PASSES,
            resolver_params={
                "fence_output": False,
                "format_type": lx.data.FormatType.JSON,
                "suppress_parse_errors_default": os.getenv("LX_SUPPRESS_PARSE_ERRORS", "false").lower() in {"1", "true", "yes"},
            },
        )
        
        print(f"[DEBUG] Calling lx.extract for {len(text)} characters of text")
        
        annotated = lx.extract(**extract_kwargs)
        
        if annotated is None:
            raise ValueError("lx.extract returned None")
        
        # Process extractions
        extractions = getattr(annotated, "extractions", [])
        processed_extractions = []
        
        for extraction in extractions:
            if extraction is None:
                continue
                
            attributes = getattr(extraction, "attributes", {})
            extraction_class = getattr(extraction, "extraction_class", None)
            
            # Add section metadata to extraction
            if section_metadata and attributes:
                if not isinstance(attributes, dict):
                    attributes = {}
                else:
                    attributes = dict(attributes)
                attributes["parent_section_id"] = section_metadata.get("section_id")
                attributes["section_name"] = section_metadata.get("section_name")
                attributes["section_level"] = section_metadata.get("section_level")
            
            item = {
                "extraction_class": extraction_class,
                "extraction_text": getattr(extraction, "extraction_text", None),
                "attributes": attributes,
                "char_interval": {
                    "start_pos": getattr(getattr(extraction, "char_interval", None), "start_pos", None),
                    "end_pos": getattr(getattr(extraction, "char_interval", None), "end_pos", None),
                } if hasattr(extraction, "char_interval") and extraction.char_interval else None,
                "alignment_status": getattr(extraction, "alignment_status", None),
                "section_metadata": section_metadata
            }
            processed_extractions.append(item)
        
        return {
            "document_id": getattr(annotated, "document_id", None),
            "extractions": processed_extractions
        }
        
    except Exception as e:
        print(f"[ERROR] LangExtract extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_chunks_from_toc_and_docling(
    toc_data: List[Dict[str, Any]],
    docling_document: Dict[str, Any],
    max_chars: int = 5000
) -> List[Tuple[str, Dict[str, Any]]]:
    """Create chunks based on ToC headlines, treating non-ToC section headers as text body.
    
    This function creates chunks based on ALL ToC entries (all levels). Section headers that are present
    in the Docling Document but not in the ToC are treated as part of the text body.
    Page headers are ignored completely.
    
    Args:
        toc_data: Table of Contents data with hierarchical structure
        docling_document: The headline-fixed Docling Document JSON
        max_chars: Maximum characters per chunk
        
    Returns:
        List of (chunk_text, section_info) tuples
    """
    chunks = []
    texts = docling_document.get('texts', [])
    
    # Flatten all ToC entries into a list with proper ordering
    all_toc_sections = []
    
    def collect_all_toc_sections(toc_nodes: List[Dict[str, Any]], parent_path: List[str] = None) -> None:
        """Recursively collect all ToC sections in document order."""
        if parent_path is None:
            parent_path = []
            
        for node in toc_nodes:
            title = node.get('title', '').strip()
            level = node.get('level', 1)
            start_page = node.get('start_page')
            end_page = node.get('end_page')
            
            if not title or not start_page:
                continue
                
            # Skip index and document info sections
            full_path = parent_path + [title]
            if any('índice' in part.lower() or 'document info' in part.lower() 
                   for part in full_path):
                continue
            
            # Add this section to our flat list
            all_toc_sections.append({
                'title': title,
                'level': level,
                'start_page': start_page,
                'end_page': end_page,
                'full_path': full_path,
                'has_children': bool(node.get('children', []))
            })
            
            # Process children recursively
            children = node.get('children', [])
            if children:
                collect_all_toc_sections(children, full_path)
    
    collect_all_toc_sections(toc_data)
    
    # Sort sections by start page and level to ensure correct ordering
    all_toc_sections.sort(key=lambda x: (x['start_page'], x['level']))
    
    print(f"[DEBUG] Found {len(all_toc_sections)} total ToC sections (all levels)")
    
    # Create a mapping of ToC titles to their positions for quick lookup
    toc_title_to_position = {}
    for i, section in enumerate(all_toc_sections):
        toc_title_to_position[section['title'].lower()] = i
    
    # Create document-ordered text elements with their positions
    text_elements = []
    for i, text_item in enumerate(texts):
        # Skip page headers entirely
        if text_item.get('label') == 'page_header':
            continue
            
        text_content = text_item.get('text', '').strip()
        if text_content:
            page_no = get_page_from_provenance(text_item)
            charspan_start = 0
            if text_item.get('prov') and len(text_item['prov']) > 0:
                charspan_start = text_item['prov'][0].get('charspan', [0, 0])[0]
            
            text_elements.append({
                'text': text_content,
                'label': text_item.get('label', ''),
                'page': page_no,
                'charspan_start': charspan_start,
                'doc_position': i,
                'is_toc_header': (text_item.get('label') == 'section_header' and 
                                text_content.lower() in toc_title_to_position)
            })
    
    # Sort text elements by document position (page, then charspan)  
    text_elements.sort(key=lambda x: (x['page'], x['charspan_start'], x['doc_position']))
    
    print(f"[DEBUG] Processing {len(text_elements)} text elements (excluding page headers)")
    
    # Process each ToC section to create chunks
    for i, section in enumerate(all_toc_sections):
        title = section['title']
        level = section['level']
        start_page = section['start_page']
        end_page = section['end_page']
        full_path = section['full_path']
        
        print(f"[DEBUG] Processing ToC section: {title} (Level {level}, pages {start_page}-{end_page})")
        
        # Memory check before processing large sections
        if i % 10 == 0:  # Check every 10 sections
            check_memory_usage(f"section {i+1}/{len(all_toc_sections)}")
            if get_memory_usage_mb() > MEMORY_WARNING_THRESHOLD_MB:
                force_garbage_collection()
        
        # Find the start and end positions for this section's content
        section_start_idx = None
        section_end_idx = len(text_elements)  # Default to end of document
        
        # Find where this ToC section starts in the document
        for j, elem in enumerate(text_elements):
            if elem['is_toc_header'] and elem['text'].lower() == title.lower():
                section_start_idx = j
                break
        
        if section_start_idx is None:
            print(f"[WARNING] Could not find ToC header '{title}' in document")
            continue
        
        # Find where the next ToC section starts (this section's content ends there)
        for next_section in all_toc_sections[i+1:]:
            next_title = next_section['title']
            for j, elem in enumerate(text_elements[section_start_idx+1:], section_start_idx+1):
                if elem['is_toc_header'] and elem['text'].lower() == next_title.lower():
                    section_end_idx = j
                    break
            if section_end_idx < len(text_elements):
                break  # Found the next section
        
        # Collect content between this ToC header and the next ToC header
        section_content_parts = []
        
        for j in range(section_start_idx + 1, section_end_idx):
            elem = text_elements[j]
            
            # Skip the header itself but include all other content (even non-ToC headers)
            if j == section_start_idx:
                continue  # Skip the ToC header itself
                
            section_content_parts.append(elem['text'])
        
        section_content = '\n'.join(section_content_parts)
        
        # Check memory usage for large sections
        content_size_mb = estimate_content_size_mb(section_content)
        if content_size_mb > MAX_SECTION_SIZE_MB:
            print(f"[WARNING] Large section detected: {title} ({content_size_mb:.1f} MB)")
            print("[INFO] Will use memory-safe chunking for this section")
        
        # Skip empty sections
        if not section_content.strip():
            print(f"[DEBUG] Skipping empty ToC section: {title}")
            continue
        
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
            # Split large content into multiple chunks using memory-safe splitting
            try:
                split_chunks = split_large_content_safe(section_content, max_chars, title)
                for j, split_content in enumerate(split_chunks):
                    chunk_header = f"{context_header} (Part {j+1}/{len(split_chunks)})\n"
                    chunk_text = f"{chunk_header}\n{split_content}"
                    chunks.append((chunk_text, section_info))
                print(f"[DEBUG] Split ToC section '{title}' into {len(split_chunks)} chunks")
            except MemoryError:
                print(f"[ERROR] Out of memory processing section: {title}")
                print("[INFO] Skipping this section to prevent crash")
                continue
        
        # Periodic garbage collection for large documents
        if (i + 1) % 20 == 0:
            force_garbage_collection()
    
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
    # Use the memory-safe version
    return split_large_content_safe(content, max_chars, "")


def split_large_content_safe(content: str, max_chars: int, section_title: str = "") -> List[str]:
    """Memory-safe content splitting with proper error handling.
    
    Args:
        content: Content to split
        max_chars: Maximum characters per chunk
        section_title: Section title for debugging
        
    Returns:
        List of content chunks
        
    Raises:
        MemoryError: If content is too large to process safely
    """
    import re
    
    # Check content size upfront
    content_size_mb = estimate_content_size_mb(content)
    if content_size_mb > MAX_SECTION_SIZE_MB:
        print(f"[WARNING] Attempting to split very large section: {section_title} ({content_size_mb:.1f} MB)")
    
    # For extremely large content, use aggressive chunking
    if content_size_mb > MAX_SECTION_SIZE_MB * 2:  # 100MB+
        print(f"[ERROR] Section too large for safe processing: {section_title}")
        print("[INFO] Using emergency chunking strategy...")
        return emergency_chunk_content(content, max_chars)
    
    try:
        # Split into sentences with memory check
        sentences = re.split(r'[.!?]+\s+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return [content] if content.strip() else []
        
        print(f"[DEBUG] Splitting content into {len(sentences)} sentences for section: {section_title}")
        
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
                    chunk_content = ' '.join(current_chunk)
                    chunks.append(chunk_content)
                    
                    # Memory check after each chunk
                    if len(chunks) % 10 == 0:  # Every 10 chunks
                        check_memory_usage(f"chunk {len(chunks)} of {section_title}")
                    
                    # Start new chunk with overlap
                    overlap_start = max(0, len(current_chunk) - overlap_size)
                    current_chunk = current_chunk[overlap_start:]
                    current_length = sum(len(s) + 1 for s in current_chunk)
                else:
                    # Single sentence is too large, split it further
                    if len(sentence) > max_chars:
                        print(f"[WARNING] Very long sentence in {section_title}, splitting...")
                        sub_chunks = emergency_split_sentence(sentence, max_chars)
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(sentence)
                    i += 1
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    except MemoryError:
        print(f"[ERROR] Memory error while processing section: {section_title}")
        print("[INFO] Falling back to emergency chunking...")
        return emergency_chunk_content(content, max_chars)


def emergency_chunk_content(content: str, max_chars: int) -> List[str]:
    """Emergency content chunking for very large sections."""
    chunks = []
    start = 0
    content_len = len(content)
    
    print("[INFO] Using emergency chunking (character-based splitting)")
    
    while start < content_len:
        end = min(start + max_chars, content_len)
        
        # Try to find a good break point (sentence or paragraph end)
        if end < content_len:
            # Look back for sentence end
            for i in range(end, max(start, end - 200), -1):
                if content[i] in '.!?\n':
                    end = i + 1
                    break
        
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end
        
        # Prevent infinite loops
        if start >= content_len:
            break
    
    print(f"[INFO] Emergency chunking created {len(chunks)} chunks")
    return chunks


def emergency_split_sentence(sentence: str, max_chars: int) -> List[str]:
    """Emergency splitting of extremely long sentences."""
    chunks = []
    words = sentence.split()
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 <= max_chars:
            current_chunk.append(word)
            current_length += len(word) + 1
        else:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                # Single word is too long, split it
                chunks.append(word[:max_chars])
                remaining = word[max_chars:]
                while remaining:
                    chunks.append(remaining[:max_chars])
                    remaining = remaining[max_chars:]
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def process_extractions_with_postprocessing(extractions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process extractions and derive tags and parameters from norms."""
    all_extractions = []
    all_tags = []
    all_parameters = []
    
    # Collect norms for postprocessing
    norms_to_process = []
    
    for extraction in extractions:
        all_extractions.append(extraction)
        
        if extraction.get("extraction_class") == "NORM":
            attributes = extraction.get("attributes", {})
            if attributes:
                norms_to_process.append(attributes)
    
    print(f"[INFO] Processing {len(norms_to_process)} norms for tag/parameter extraction")
    
    # Extract tags and parameters using modularized functions
    if norms_to_process:
        try:
            derived_tags = extract_tags_from_norms(norms_to_process, tag_counter_start=1)
            derived_params = extract_parameters_from_norms(norms_to_process, param_counter_start=1)
            
            all_tags.extend(derived_tags)
            all_parameters.extend(derived_params)
            
            print(f"[INFO] Derived {len(derived_tags)} tags and {len(derived_params)} parameters")
            
        except Exception as e:
            print(f"[ERROR] Postprocessing failed: {e}")
    
    return all_extractions, all_tags, all_parameters


def generate_node_tree(sections: List[Dict[str, Any]], extractions: List[Dict[str, Any]], tags: List[Dict[str, Any]], parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a node tree structure compatible with web Tree View UI."""
    
    # Create section hierarchy
    section_nodes = {}
    root_sections = []
    
    # Build section hierarchy
    for section in sections:
        section_id = section.get("section_id", section.get("section_name", ""))
        section_node = {
            "id": section_id,
            "title": section.get("section_name", "Unnamed Section"),
            "type": "SECTION",
            "level": section.get("section_level", 1),
            "parent_id": section.get("parent_section_id"),
            "children": [],
            "metadata": {
                "start_page": section.get("start_page"),
                "end_page": section.get("end_page"),
                "toc_path": section.get("toc_path", []),
                "section_summary": section.get("section_summary", ""),
                "extraction_count": 0
            }
        }
        section_nodes[section_id] = section_node
    
    # Build parent-child relationships
    for section_id, section_node in section_nodes.items():
        parent_id = section_node.get("parent_id")
        if parent_id and parent_id in section_nodes:
            section_nodes[parent_id]["children"].append(section_node)
        else:
            root_sections.append(section_node)
    
    # Add extractions to their parent sections
    for extraction in extractions:
        extraction_class = extraction.get("extraction_class", "")
        attributes = extraction.get("attributes", {})
        parent_section_id = attributes.get("parent_section_id") or attributes.get("section_parent_id")
        
        if parent_section_id and parent_section_id in section_nodes:
            section_node = section_nodes[parent_section_id]
            
            # Create extraction node
            extraction_id = attributes.get("id", f"{extraction_class}_{len(section_node['children'])}")
            extraction_node = {
                "id": extraction_id,
                "title": get_extraction_title(extraction),
                "type": extraction_class,
                "parent_id": parent_section_id,
                "children": [],
                "metadata": {
                    "extraction_text": extraction.get("extraction_text", ""),
                    "attributes": attributes,
                    "char_interval": extraction.get("char_interval"),
                    "alignment_status": extraction.get("alignment_status")
                }
            }
            
            section_node["children"].append(extraction_node)
            section_node["metadata"]["extraction_count"] += 1
    
    # Create final tree structure
    tree_structure = {
        "document_tree": {
            "type": "DOCUMENT",
            "title": "Enhanced Extraction Document",
            "children": root_sections,
            "metadata": {
                "total_sections": len(sections),
                "total_extractions": len(extractions),
                "total_tags": len(tags),
                "total_parameters": len(parameters),
                "processing_method": "docling_toc_based_enhanced_extraction"
            }
        },
        "statistics": {
            "sections_count": len(sections),
            "extractions_count": len(extractions),
            "tags_count": len(tags),
            "parameters_count": len(parameters),
            "section_hierarchy_levels": max([s.get("section_level", 1) for s in sections]) if sections else 0
        }
    }
    
    return tree_structure


def get_extraction_title(extraction: Dict[str, Any]) -> str:
    """Get a display title for an extraction."""
    extraction_class = extraction.get("extraction_class", "")
    attributes = extraction.get("attributes", {})
    
    if extraction_class == "NORM":
        statement = attributes.get("norm_statement", "")
        return statement[:80] + "..." if len(statement) > 80 else statement
    elif extraction_class == "TAG":
        return attributes.get("tag", f"Tag {attributes.get('id', '')}")
    elif extraction_class == "PARAMETER":
        param_name = attributes.get("parameter_name", "")
        value = attributes.get("value", "")
        unit = attributes.get("unit", "")
        return f"{param_name}: {value} {unit}".strip()
    else:
        return attributes.get("id", f"{extraction_class} Item")


def run_enhanced_extraction(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    docling_path: Optional[Path] = None,
    enable_gpu: bool = True,
    max_chunk_chars: int = MAX_CHUNK_SIZE_CHARS,
    # LangExtract configuration parameters (from web application)
    MODEL_ID: str = "google/gemini-2.0-flash-exp",
    MODEL_TEMPERATURE: float = 0.15,
    MAX_NORMS_PER_5K: int = 10,
    MAX_CHAR_BUFFER: int = 5000,
    EXTRACTION_PASSES: int = 1,
    INPUT_PROMPTFILE: Optional[str] = None,
    INPUT_GLOSSARYFILE: Optional[str] = None,
    INPUT_EXAMPLESFILE: Optional[str] = None,
    INPUT_SEMANTCSFILE: Optional[str] = None,
    INPUT_TEACHFILE: Optional[str] = None
) -> Dict[str, Any]:
    """Run enhanced extraction pipeline on PDF document.
    
    Args:
        pdf_path: Path to source PDF file
        output_dir: Optional output directory
        docling_path: Optional path to pre-converted docling document (if None, will convert PDF)
        enable_gpu: Enable GPU acceleration if available
        max_chunk_chars: Maximum characters per chunk
        MODEL_ID: LangExtract model ID (e.g., "google/gemini-2.0-flash-exp")
        MODEL_TEMPERATURE: Model temperature for extraction
        MAX_NORMS_PER_5K: Maximum norms per 5K characters
        MAX_CHAR_BUFFER: Maximum character buffer size
        EXTRACTION_PASSES: Number of extraction passes
        INPUT_PROMPTFILE: Path to prompt file
        INPUT_GLOSSARYFILE: Path to glossary file
        INPUT_EXAMPLESFILE: Path to examples file
        INPUT_SEMANTCSFILE: Path to semantics file
        INPUT_TEACHFILE: Path to teaching file
        
    Returns:
        Dictionary with extraction results and metrics
    """
    if output_dir is None:
        output_dir = Path("output_runs") / "enhanced_run"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("[INFO] Setting up enhanced extraction pipeline...")
    print(f"[INFO] Processing PDF: {pdf_path}")
    check_memory_usage("pipeline start")
    
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
                verbose=False,
                enable_gpu=enable_gpu
            )
            print(f"[INFO] Docling Document saved to: {docling_path}")
            check_memory_usage("PDF conversion")
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
    check_memory_usage("before chunking")
    
    chunks = create_chunks_from_toc_and_docling(toc_data, docling_document, max_chars=max_chunk_chars)
    
    print(f"[INFO] Created {len(chunks)} chunks for processing")
    check_memory_usage("after chunking")
    
    # Setup LangExtract configuration
    print("[INFO] Setting up LangExtract configuration...")
    config, use_openrouter, openrouter_key = create_extraction_config(MODEL_ID, MODEL_TEMPERATURE)
    prompt, examples = load_prompt_and_examples(INPUT_PROMPTFILE, INPUT_EXAMPLESFILE)
    
    # Process chunks with LangExtract
    print("[INFO] Processing chunks with LangExtract...")
    all_extractions = []
    all_sections = []
    
    for i, (chunk_text, section_info) in enumerate(chunks):
        print(f"[INFO] Processing chunk {i+1}/{len(chunks)}: {section_info.get('section_name', f'Chunk {i+1}')}")
        
        # Create section metadata for extraction
        section_metadata = {
            "section_id": section_info.get("section_name", f"section_{i+1}").replace(" ", "_").lower(),
            "section_name": section_info.get("section_name", f"Section {i+1}"),
            "section_level": section_info.get("section_level", 1),
            "start_page": section_info.get("start_page"),
            "end_page": section_info.get("end_page"),
            "toc_path": section_info.get("toc_path", []),
            "section_summary": f"Section at level {section_info.get('section_level', 1)}"
        }
        
        all_sections.append(section_metadata)
        
        # Check if section should be skipped from LX extraction
        section_name = section_info.get("section_name", "")
        if should_skip_section_for_extraction(section_name):
            print(f"[INFO] Skipping LX extraction for section: {section_name}")
            continue
        
        # Extract using LangExtract
        extraction_result = extract_with_langextract(
            text=chunk_text,
            prompt=prompt,
            examples=examples,
            config=config,
            section_metadata=section_metadata
        )
        
        if extraction_result and extraction_result.get("extractions"):
            all_extractions.extend(extraction_result["extractions"])
            print(f"[INFO] Extracted {len(extraction_result['extractions'])} items from chunk {i+1}")
        else:
            print(f"[WARNING] No extractions from chunk {i+1}")
        
        # Memory management
        if (i + 1) % 5 == 0:
            check_memory_usage(f"chunk {i+1}/{len(chunks)}")
            force_garbage_collection()
    
    print(f"[INFO] Total extractions collected: {len(all_extractions)}")
    
    # Postprocess extractions to derive tags and parameters
    print("[INFO] Performing postprocessing to derive tags and parameters...")
    processed_extractions, derived_tags, derived_parameters = process_extractions_with_postprocessing(all_extractions)
    
    # Generate node tree for web UI
    print("[INFO] Generating node tree structure...")
    node_tree = generate_node_tree(all_sections, processed_extractions, derived_tags, derived_parameters)
    
    # Save results
    results_data = {
        "pipeline_info": {
            "version": "2.0",
            "method": "enhanced_docling_toc_based_extraction",
            "pdf_source": str(pdf_path),
            "docling_document": str(fixed_docling_path),
            "total_chunks": len(chunks),
            "total_sections": len(all_sections),
            "total_extractions": len(processed_extractions),
            "total_tags": len(derived_tags),
            "total_parameters": len(derived_parameters)
        },
        "sections": all_sections,
        "extractions": processed_extractions,
        "tags": derived_tags,
        "parameters": derived_parameters,
        "node_tree": node_tree,
        "processing_stats": {
            "chunks_processed": len(chunks),
            "successful_extractions": len([e for e in processed_extractions if e]),
            "sections_with_extractions": len([s for s in all_sections if any(
                e.get("attributes", {}).get("parent_section_id") == s.get("section_id")
                for e in processed_extractions
            )])
        }
    }
    
    # Save main results
    results_path = output_dir / "enhanced_extraction_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)
    
    # Save node tree separately for web UI
    tree_path = output_dir / "node_tree.json" 
    with open(tree_path, 'w', encoding='utf-8') as f:
        json.dump(node_tree, f, indent=2, ensure_ascii=False)
    
    # Save chunks for debugging
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
    
    with open(chunks_output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "pipeline_info": results_data["pipeline_info"],
            "chunks": chunks_data
        }, f, indent=2, ensure_ascii=False)
    
    print(f"[SUCCESS] Enhanced extraction pipeline completed!")
    print(f"  - Input PDF: {pdf_path}")
    print(f"  - Sections processed: {len(all_sections)}")
    print(f"  - Extractions: {len(processed_extractions)}")
    print(f"  - Tags: {len(derived_tags)}")
    print(f"  - Parameters: {len(derived_parameters)}")
    print(f"  - Results saved to: {results_path}")
    print(f"  - Node tree saved to: {tree_path}")
    
    # Return compatible format for web runner
    return {
        "quality_metrics": {
            "total_sections": len(all_sections),
            "total_norms": len([e for e in processed_extractions if e.get("extraction_class") == "NORM"]),
            "total_tags": len(derived_tags),
            "total_parameters": len(derived_parameters),
            "anchoring_success_rate": lambda: 1.0,  # Placeholder for compatibility
            "parameter_normalization_coverage": 1.0  # Placeholder for compatibility
        },
        "sections": all_sections,
        "extractions": processed_extractions,
        "tags": derived_tags,
        "parameters": derived_parameters,
        "node_tree": node_tree,
        "output_files": {
            "results": results_path,
            "node_tree": tree_path,
            "chunks": chunks_output_path,
            "docling_document": fixed_docling_path
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
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable GPU acceleration (use CPU only)"
    )
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=MAX_CHUNK_SIZE_CHARS,
        help=f"Maximum characters per chunk (default: {MAX_CHUNK_SIZE_CHARS})"
    )
    
    args = parser.parse_args()
    
    if not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    if args.docling_path and not args.docling_path.exists():
        print(f"Error: Docling Document file not found: {args.docling_path}")
        sys.exit(1)
    
    # Print configuration
    print(f"[INFO] GPU acceleration: {'disabled' if args.no_gpu else 'enabled'}")
    print(f"[INFO] Max chunk size: {args.max_chunk_chars} characters")
    check_memory_usage("startup")
    
    try:
        results = run_enhanced_extraction(
            args.pdf_path,
            args.output_dir,
            args.docling_path,
            enable_gpu=not args.no_gpu,
            max_chunk_chars=args.max_chunk_chars
        )
        
        print("\n[SUCCESS] Enhanced pipeline test completed successfully!")
        check_memory_usage("completion")
        
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