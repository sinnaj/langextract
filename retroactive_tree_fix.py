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


def build_node_tree(sections: List[Dict[str, Any]], extractions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build hierarchical node tree from sections and extractions."""
    
    # Create section nodes with children
    section_nodes = {}
    root_sections = []
    
    for section in sections:
        section_id = section["section_id"]
        parent_id = section.get("parent_section_id")
        
        # Count extractions for this section
        section_extractions = [e for e in extractions if e.get("parent_section_id") == section_id]
        
        node = {
            "id": section_id,
            "name": section["section_name"],
            "type": "section", 
            "level": section["section_level"],
            "start_page": section.get("start_page"),
            "end_page": section.get("end_page"),
            "extraction_count": len(section_extractions),
            "children": [],
            "parent_id": parent_id
        }
        
        section_nodes[section_id] = node
        
        if parent_id is None:
            root_sections.append(node)
    
    # Build parent-child relationships
    for section in sections:
        section_id = section["section_id"]
        parent_id = section.get("parent_section_id")
        
        if parent_id and parent_id in section_nodes:
            # Add this section as child of parent
            parent_node = section_nodes[parent_id]
            child_node = section_nodes[section_id]
            parent_node["children"].append(child_node)
    
    return root_sections


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
        if "parent_section_id" not in extraction:
            # Try to determine parent section from position or other clues
            # For now, we'll leave this as is since it's more complex
            pass
    
    # Rebuild node tree with proper hierarchy
    node_tree = build_node_tree(sections, extractions)
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
        print(f"✅ Regenerated node tree with {len(node_tree)} root nodes")
        
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