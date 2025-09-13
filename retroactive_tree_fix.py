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
    
    print(f"[DEBUG] ========== BUILDING TREE ==========")
    print(f"[DEBUG] Input: {len(sections)} sections, {len(extractions)} extractions, {len(tags)} tags, {len(parameters)} parameters")
    
    # Create section hierarchy
    section_nodes = {}
    root_sections = []
    section_ids = []
    duplicate_count = 0
    
    print(f"[DEBUG] ========== SECTION PROCESSING ==========")
    
    # Build section hierarchy
    for i, section in enumerate(sections):
        section_id = section.get("section_id", section.get("section_name", ""))
        section_name = section.get("section_name", "Unnamed Section")
        section_level = section.get("section_level", 1)
        parent_section_id = section.get("parent_section_id")
        
        original_section_id = section_id  # Store original before potential modification
        section_ids.append(section_id)
        
        # Show details for all sections (truncated for readability)
        if i < 20 or section_level <= 2:  # Show first 20 and all level 1-2 sections
            print(f"[DEBUG] Section {i+1:3d}: ID='{section_id}' | Name='{section_name[:50]}...' | Level={section_level} | Parent='{parent_section_id or 'None'}'")
        elif i % 20 == 0:  # Show every 20th after that
            print(f"[DEBUG] Section {i+1:3d}: ID='{section_id}' | Level={section_level} | Parent='{parent_section_id or 'None'}' (every 20th)")
        
        # Check for duplicate IDs and handle them
        if section_id in section_nodes:
            duplicate_count += 1
            section_id = f"{section_id}_duplicate_{duplicate_count}"
            print(f"[WARNING] DUPLICATE SECTION ID FIXED: '{original_section_id}' -> '{section_id}'")
        
        section_node = {
            "id": section_id,
            "title": section_name,
            "type": "SECTION",
            "level": section_level,
            "parent_id": parent_section_id,
            "children": [],
            "metadata": {
                "start_page": section.get("start_page"),
                "end_page": section.get("end_page"),
                "toc_path": section.get("toc_path", []),
                "section_summary": section.get("section_summary", ""),
                "extraction_count": 0,
                "original_section_index": i
            }
        }
        section_nodes[section_id] = section_node
        
        # Update section ID back in original data if it was changed
        if section_id != original_section_id:
            section["section_id"] = section_id
    
    print(f"[DEBUG] Section processing complete: {len(section_nodes)} unique nodes, {duplicate_count} duplicates fixed")
    
    print(f"[DEBUG] ========== PARENT-CHILD RELATIONSHIPS ==========")
    
    # Build parent-child relationships for sections
    children_added = 0
    root_added = 0
    orphaned_sections = []
    parent_not_found = []
    
    for section_id, section_node in section_nodes.items():
        parent_id = section_node.get("parent_id")
        
        if parent_id and parent_id in section_nodes:
            # Valid parent found - add as child
            parent_node = section_nodes[parent_id]
            parent_node["children"].append(section_node)
            children_added += 1
            if children_added <= 10:  # Show first 10 relationships
                print(f"[DEBUG] CHILD: '{section_id}' -> parent: '{parent_id}' (level {section_node['level']})")
        elif parent_id:
            # Parent specified but not found
            parent_not_found.append((section_id, parent_id))
            root_sections.append(section_node)
            root_added += 1
            if root_added <= 10:
                print(f"[DEBUG] ORPHAN->ROOT: '{section_id}' (missing parent: '{parent_id}') (level {section_node['level']})")
        else:
            # No parent specified - true root
            root_sections.append(section_node)
            root_added += 1
            if root_added <= 10:
                print(f"[DEBUG] ROOT: '{section_id}' (level {section_node['level']})")
    
    print(f"[DEBUG] Relationships built: {children_added} children, {root_added} roots")
    if parent_not_found:
        print(f"[WARNING] {len(parent_not_found)} sections have missing parents:")
        for child_id, missing_parent in parent_not_found[:5]:  # Show first 5
            print(f"[WARNING]   '{child_id}' -> missing parent: '{missing_parent}'")
    
    print(f"[DEBUG] ========== EXTRACTION MAPPING ==========")
    
    # Add extractions to their parent sections
    extractions_matched = 0
    extractions_orphaned = 0
    parent_section_ids_seen = set()
    extraction_parent_mapping = {}
    
    print(f"[DEBUG] Processing {len(extractions)} extractions...")
    
    for i, extraction in enumerate(extractions):
        extraction_class = extraction.get("extraction_class", "")
        attributes = extraction.get("attributes") or {}  # Handle None case
        parent_section_id = attributes.get("parent_section_id") or attributes.get("section_parent_id")
        parent_section_ids_seen.add(parent_section_id)
        
        # Track which extractions map to which parents
        if parent_section_id not in extraction_parent_mapping:
            extraction_parent_mapping[parent_section_id] = []
        extraction_parent_mapping[parent_section_id].append(extraction_class)
        
        # Show detailed mapping for first few extractions
        if i < 10:
            print(f"[DEBUG] Extraction {i+1:3d}: {extraction_class:15s} -> parent: '{parent_section_id or 'None'}'")
        elif i % 100 == 0:  # Every 100th after that
            print(f"[DEBUG] Extraction {i+1:3d}: {extraction_class:15s} -> parent: '{parent_section_id or 'None'}' (every 100th)")
        
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
            if extractions_orphaned <= 10:  # Show first 10 orphaned
                print(f"[DEBUG] ORPHANED: {extraction_class} (parent '{parent_section_id}' not found in sections)")
    
    print(f"[DEBUG] Extraction mapping complete: {extractions_matched} matched, {extractions_orphaned} orphaned")
    print(f"[DEBUG] Unique parent IDs seen in extractions: {len(parent_section_ids_seen)}")
    
    print(f"[DEBUG] ========== PARENT ID ANALYSIS ==========")
    # Analyze parent ID mapping
    valid_parents = []
    missing_parents = []
    for parent_id in parent_section_ids_seen:
        if parent_id and parent_id in section_nodes:
            valid_parents.append(parent_id)
        elif parent_id:
            missing_parents.append(parent_id)
    
    print(f"[DEBUG] Parent ID analysis:")
    print(f"[DEBUG]   Valid parents: {len(valid_parents)}")
    print(f"[DEBUG]   Missing parents: {len(missing_parents)}")
    if missing_parents:
        print(f"[DEBUG] Missing parent IDs: {missing_parents[:10]}{'...' if len(missing_parents) > 10 else ''}")
    
    print(f"[DEBUG] ========== SECTION EXTRACTION COUNTS ==========")
    # Show sections with extraction counts
    sections_with_extractions = [(sid, node["metadata"]["extraction_count"], node["level"]) 
                                for sid, node in section_nodes.items() 
                                if node["metadata"]["extraction_count"] > 0]
    sections_with_extractions.sort(key=lambda x: -x[1])  # Sort by extraction count descending
    
    print(f"[DEBUG] Sections with extractions: {len(sections_with_extractions)} out of {len(section_nodes)}")
    for i, (sid, count, level) in enumerate(sections_with_extractions[:15]):  # Show top 15
        print(f"[DEBUG]   {i+1:2d}. '{sid}' (level {level}): {count} extractions")
    
    print(f"[DEBUG] ========== FINAL TREE VALIDATION ==========")
    
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
                "processing_method": "docling_toc_based_enhanced_extraction",
                "tree_build_stats": {
                    "sections_processed": len(sections),
                    "section_nodes_created": len(section_nodes),
                    "root_sections": len(root_sections),
                    "duplicates_fixed": duplicate_count,
                    "parent_child_relationships": children_added,
                    "extractions_matched": extractions_matched,
                    "extractions_orphaned": extractions_orphaned,
                    "sections_with_extractions": len(sections_with_extractions)
                }
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
    
    # Final validation and debug output
    total_extractions_in_tree = sum(node["metadata"]["extraction_count"] for node in section_nodes.values())
    
    print(f"[DEBUG] Final validation:")
    print(f"[DEBUG]   Total sections in tree: {len(section_nodes)}")
    print(f"[DEBUG]   Root sections: {len(root_sections)}")
    print(f"[DEBUG]   Total extractions placed in tree: {total_extractions_in_tree}")
    print(f"[DEBUG]   Total original extractions: {len(extractions)}")
    print(f"[DEBUG]   Extraction placement success rate: {(total_extractions_in_tree/len(extractions)*100):.1f}%" if extractions else "N/A")
    
    # Show detailed breakdown of root sections
    print(f"[DEBUG] Root section breakdown:")
    for i, root in enumerate(root_sections[:10]):  # Show first 10 roots
        child_count = len(root.get("children", []))
        extraction_count = root.get("metadata", {}).get("extraction_count", 0)
        level = root.get("level", 0)
        print(f"[DEBUG]   Root {i+1:2d}: '{root.get('id')}' (level {level}) - {child_count} children, {extraction_count} extractions")
    
    if len(root_sections) > 10:
        print(f"[DEBUG]   ... and {len(root_sections) - 10} more root sections")
    
    print(f"[DEBUG] ========== TREE BUILD COMPLETE ==========")
    
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