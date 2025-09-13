#!/usr/bin/env python3
"""
Retroactive Tree Fix Script

This script fixes existing enhanced_extraction_results.json files to add proper
parent_section_id fields and regenerate the node tree for proper hierarchy display.

Usage:
    python retroactive_tree_fix.py path/to/enhanced_extraction_results.json
    python retroactive_tree_fix.py path/to/output_run_directory/
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_parent_section_id(current_level: int, current_index: int, sections: List[Dict[str, Any]]) -> Optional[str]:
    """Find the parent section ID based on hierarchy levels."""
    if current_level <= 1:
        return None  # Root level sections have no parent
        
    # Look backwards to find the most recent section at a higher level (lower number)
    for j in range(current_index - 1, -1, -1):
        prev_section = sections[j]
        prev_level = prev_section.get("section_level", 1)
        if prev_level < current_level:
            return prev_section.get("section_id")
    
    return None  # No parent found


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


def build_node_tree(sections: List[Dict[str, Any]], extractions: List[Dict[str, Any]], tags: List[Dict[str, Any]], parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build hierarchical node tree from sections and extractions, matching enhanced_lx_runner.py format."""
    
    print(f"[DEBUG] Building tree from {len(sections)} sections, {len(extractions)} extractions")
    
    # Create section hierarchy
    section_nodes = {}
    root_sections = []
    section_ids = []
    
    # Build section hierarchy
    for i, section in enumerate(sections):
        section_id = section.get("section_id", section.get("section_name", ""))
        section_ids.append(section_id)
        
        # Debug section processing
        print(f"[DEBUG] Processing section {i+1}/{len(sections)}: '{section_id}' (level {section.get('section_level', 1)})")
        
        # Check for duplicate IDs
        if section_id in section_nodes:
            print(f"[WARNING] Duplicate section ID detected: '{section_id}' - this will overwrite the previous section!")
        
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
    
    print(f"[DEBUG] Created {len(section_nodes)} unique section nodes from {len(sections)} sections")
    print(f"[DEBUG] Section IDs: {section_ids[:5]}{'...' if len(section_ids) > 5 else ''}")
    
    # Build parent-child relationships for sections
    for section_id, section_node in section_nodes.items():
        parent_id = section_node.get("parent_id")
        if parent_id and parent_id in section_nodes:
            section_nodes[parent_id]["children"].append(section_node)
            print(f"[DEBUG] Added section '{section_id}' as child of '{parent_id}'")
        else:
            root_sections.append(section_node)
            print(f"[DEBUG] Added section '{section_id}' as root section (parent_id: {parent_id})")
    
    print(f"[DEBUG] Created {len(root_sections)} root sections")
    
    # Add extractions to their parent sections
    extractions_matched = 0
    extractions_orphaned = 0
    
    for extraction in extractions:
        extraction_class = extraction.get("extraction_class", "")
        attributes = extraction.get("attributes") or {}  # Handle None case
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
            extractions_matched += 1
        else:
            extractions_orphaned += 1
            if extractions_orphaned <= 5:  # Only show first 5 to avoid spam
                print(f"[DEBUG] Orphaned extraction: {extraction_class} with parent_section_id='{parent_section_id}' (not found in sections)")
    
    print(f"[DEBUG] Matched {extractions_matched} extractions to sections, {extractions_orphaned} orphaned")
    
    # Create final tree structure matching enhanced_lx_runner.py format
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


def fix_extraction_results_file(file_path: Path) -> bool:
    """Fix an enhanced_extraction_results.json file by adding parent_section_id fields."""
    
    print(f"Processing: {file_path}")
    
    # Read the results file
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not read {file_path}: {e}")
        return False
    
    sections = data.get("sections", [])
    extractions = data.get("extractions", [])
    tags = data.get("tags", [])
    parameters = data.get("parameters", [])
    
    print(f"[DEBUG] Loaded {len(sections)} sections, {len(extractions)} extractions, {len(tags)} tags, {len(parameters)} parameters")
    
    # Debug first few sections
    for i, section in enumerate(sections[:3]):  # Show first 3 sections
        section_id = section.get("section_id", section.get("section_name", ""))
        section_name = section.get("section_name", "")
        section_level = section.get("section_level", 1)
        print(f"[DEBUG] Section {i+1}: ID='{section_id}', Name='{section_name}', Level={section_level}")
    
    # Debug first few extractions  
    for i, extraction in enumerate(extractions[:3]):  # Show first 3 extractions
        extraction_class = extraction.get("extraction_class", "")
        attributes = extraction.get("attributes") or {}
        parent_section_id = attributes.get("parent_section_id") or attributes.get("section_parent_id")
        print(f"[DEBUG] Extraction {i+1}: Class='{extraction_class}', Parent='{parent_section_id}'")
    
    # Check if sections already have parent_section_id
    sections_updated = 0
    for i, section in enumerate(sections):
        if "parent_section_id" not in section:
            # Add parent_section_id based on hierarchy
            current_level = section.get("section_level", 1)
            parent_id = find_parent_section_id(current_level, i, sections)
            section["parent_section_id"] = parent_id
            sections_updated += 1
    
    # Update extractions to have parent_section_id if missing
    extractions_updated = 0
    for extraction in extractions:
        attributes = extraction.get("attributes", {})
        if "parent_section_id" not in attributes:
            # Try to determine parent section from position or other clues
            # For now, we'll leave this as is since it's more complex
            pass
    
    # Rebuild node tree with proper hierarchy including extractions
    node_tree = build_node_tree(sections, extractions, tags, parameters)
    data["node_tree"] = node_tree
    
    # Create backup of original file
    backup_path = file_path.with_suffix('.json.backup')
    if not backup_path.exists():
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")
    
    # Write updated file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Updated {sections_updated} sections with parent_section_id")
        
        # Calculate tree statistics
        root_count = len(node_tree.get("document_tree", {}).get("children", []))
        total_extractions = node_tree.get("statistics", {}).get("extractions_count", 0)
        
        print(f"✅ Regenerated node tree with {root_count} root sections and {total_extractions} extractions")
        
        # Also save the tree separately
        tree_path = file_path.parent / "node_tree.json"
        with open(tree_path, 'w', encoding='utf-8') as f:
            json.dump(node_tree, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved tree to: {tree_path}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Could not write {file_path}: {e}")
        return False


def main():
    if len(sys.argv) != 2:
        print("Usage: python retroactive_tree_fix.py <path_to_results_file_or_directory>")
        print("Examples:")
        print("  python retroactive_tree_fix.py output_runs/1234567890/enhanced_output/enhanced_extraction_results.json")
        print("  python retroactive_tree_fix.py output_runs/1234567890/")
        sys.exit(1)
    
    path = Path(sys.argv[1])
    
    if not path.exists():
        print(f"ERROR: Path does not exist: {path}")
        sys.exit(1)
    
    files_processed = 0
    files_updated = 0
    
    if path.is_file():
        # Single file
        if path.name == "enhanced_extraction_results.json":
            if fix_extraction_results_file(path):
                files_updated += 1
            files_processed += 1
        else:
            print(f"ERROR: File must be named 'enhanced_extraction_results.json', got: {path.name}")
            sys.exit(1)
    
    elif path.is_dir():
        # Directory - look for enhanced_extraction_results.json files
        results_files = list(path.rglob("enhanced_extraction_results.json"))
        
        if not results_files:
            print(f"ERROR: No enhanced_extraction_results.json files found in: {path}")
            sys.exit(1)
        
        print(f"Found {len(results_files)} enhanced extraction results files")
        
        for results_file in results_files:
            if fix_extraction_results_file(results_file):
                files_updated += 1
            files_processed += 1
    
    print(f"\nSummary: {files_updated}/{files_processed} files updated successfully")
    
    if files_updated > 0:
        print("\n📁 Tree hierarchy has been fixed! The web interface should now display proper nested structure.")


if __name__ == "__main__":
    main()