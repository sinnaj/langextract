#!/usr/bin/env python3
"""
Post-processing script to merge incomplete run chunks into combined_extractions.json
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import glob


def load_annotated_extractions(chunks_dir: Path):
    """Load all annotated extraction files from chunks directory"""
    print(f"[INFO] Loading annotated extractions from: {chunks_dir}")
    
    all_extractions = []
    all_sections = []
    processing_log = []
    section_metadata_map = {}
    
    # Find all annotated extraction files
    pattern = chunks_dir / "annotated_extractions_*.json"
    extraction_files = sorted(glob.glob(str(pattern)))
    
    print(f"[INFO] Found {len(extraction_files)} extraction files")
    
    for file_path in extraction_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract chunk number from filename
            filename = Path(file_path).name
            chunk_num = filename.replace('annotated_extractions_', '').replace('.json', '')
            
            extractions = data.get('extractions', [])
            section_metadata_list = data.get('section_metadata', [])
            
            # Process extractions
            for extraction in extractions:
                if isinstance(extraction, dict):
                    # Add chunk information
                    extraction['source_chunk'] = chunk_num
                    all_extractions.append(extraction)
            
            # Process section metadata
            for section_meta in section_metadata_list:
                section_id = section_meta.get('section_id')
                if section_id and section_id not in section_metadata_map:
                    section_metadata_map[section_id] = {
                        "section_id": section_id,
                        "section_name": section_meta.get('section_name', ''),
                        "section_level": section_meta.get('section_level', 0),
                        "parent_section": section_meta.get('parent_section', ''),
                        "sub_sections": section_meta.get('sub_sections', []),
                        "section_summary": section_meta.get('section_summary', ''),
                        "has_extractions": True,
                        "extraction_count": len([e for e in extractions if e.get('section_metadata', {}).get('section_id') == section_id]),
                        "source_chunks": [chunk_num]
                    }
                elif section_id in section_metadata_map:
                    # Update existing section with additional chunk
                    section_metadata_map[section_id]['source_chunks'].append(chunk_num)
                    section_metadata_map[section_id]['extraction_count'] += len([e for e in extractions if e.get('section_metadata', {}).get('section_id') == section_id])
            
            processing_log.append(f"Processed chunk {chunk_num}: {len(extractions)} extractions")
            print(f"[INFO] Processed {filename}: {len(extractions)} extractions")
            
        except Exception as e:
            print(f"[WARN] Failed to process {file_path}: {e}")
            processing_log.append(f"Failed to process chunk {chunk_num}: {str(e)}")
    
    # Convert section metadata map to list
    all_sections = list(section_metadata_map.values())
    
    return all_extractions, all_sections, processing_log


def calculate_statistics(extractions, sections):
    """Calculate processing statistics"""
    stats = {
        'total_extractions': len(extractions),
        'total_sections': len(sections),
        'extraction_types': Counter(),
        'sections_with_extractions': len([s for s in sections if s.get('has_extractions', False)]),
        'extraction_classes': Counter()
    }
    
    for extraction in extractions:
        extraction_class = extraction.get('extraction_class', 'unknown')
        stats['extraction_classes'][extraction_class] += 1
        
        # Count attributes types if available
        attributes = extraction.get('attributes', {})
        if isinstance(attributes, dict):
            for key in attributes.keys():
                stats['extraction_types'][key] += 1
    
    return stats


def create_combined_extractions(run_id: str, chunks_dir: Path, output_dir: Path):
    """Create combined_extractions.json from incomplete run"""
    
    # Load all annotated extractions
    all_extractions, all_sections, processing_log = load_annotated_extractions(chunks_dir)
    
    if not all_extractions:
        print("[WARN] No extractions found in chunks directory")
        return False
    
    # Calculate statistics
    stats = calculate_statistics(all_extractions, all_sections)
    
    # Determine source file
    input_dir = chunks_dir.parent / "input"
    source_files = list(input_dir.glob("*")) if input_dir.exists() else []
    source_file = source_files[0] if source_files else "unknown"
    
    # Create combined result structure
    combined_result = {
        "document_metadata": {
            "source_file": str(source_file),
            "processing_method": "post_processed_incomplete_run",
            "run_id": run_id,
            "total_original_sections": stats['total_sections'],
            "total_processed_sections": stats['sections_with_extractions'],
            "total_extractions": stats['total_extractions'],
            "processing_timestamp": datetime.now().isoformat(),
            "post_processing_timestamp": datetime.now().isoformat(),
            "incomplete_run_recovery": True
        },
        "extraction_statistics": {
            "total_extractions": stats['total_extractions'],
            "extraction_classes": dict(stats['extraction_classes']),
            "attribute_types": dict(stats['extraction_types']),
            "sections_with_extractions": stats['sections_with_extractions'],
            "total_sections": stats['total_sections']
        },
        "sections": all_sections,
        "extractions": all_extractions,
        "processing_log": processing_log,
        "recovery_info": {
            "chunks_processed": len(processing_log),
            "recovery_method": "post_processing_script",
            "original_chunks_dir": str(chunks_dir)
        }
    }
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save combined extractions
    combined_output_file = output_dir / "combined_extractions.json"
    try:
        with open(combined_output_file, 'w', encoding='utf-8') as f:
            json.dump(combined_result, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] Combined extractions saved to: {combined_output_file}")
        print(f"[INFO] Total extractions: {stats['total_extractions']}")
        print(f"[INFO] Total sections: {stats['total_sections']}")
        print(f"[INFO] Extraction classes: {dict(stats['extraction_classes'])}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to save combined extractions: {e}")
        return False


def main():
    """Main processing function"""
    if len(sys.argv) < 2:
        print("Usage: python post_process_incomplete_run.py <chunks_directory>")
        print("Example: python post_process_incomplete_run.py C:\\Projects\\Arqio\\LangExtract\\langextract\\output_runs\\1757118170\\chunks")
        sys.exit(1)
    
    chunks_path = Path(sys.argv[1])
    
    if not chunks_path.exists():
        print(f"[ERROR] Chunks directory not found: {chunks_path}")
        sys.exit(1)
    
    if not chunks_path.is_dir():
        print(f"[ERROR] Path is not a directory: {chunks_path}")
        sys.exit(1)
    
    # Extract run ID from path
    run_id = chunks_path.parent.name
    
    # Output directory is the "lx output" folder in the run directory
    output_dir = chunks_path.parent / "lx output"
    
    print(f"[INFO] Processing incomplete run: {run_id}")
    print(f"[INFO] Chunks directory: {chunks_path}")
    print(f"[INFO] Output directory: {output_dir}")
    
    success = create_combined_extractions(run_id, chunks_path, output_dir)
    
    if success:
        print("[INFO] Post-processing completed successfully!")
        return 0
    else:
        print("[ERROR] Post-processing failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())