#!/usr/bin/env python3
"""
Debug script to identify the tree duplication issue using real data.

This script loads real extraction data and simulates the JavaScript tree building
to identify where Norms might be appearing in wrong sections.
"""

import json
import sys
import os

def load_real_data():
    """Load real extraction data for testing"""
    file_path = "../output_runs/1757006891/lx output/combined_extractions.json"
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    else:
        print(f"Could not find test data at {file_path}")
        return None

def analyze_parenting_issues(data):
    """Analyze potential parenting issues in the tree structure"""
    
    print("=== PARENTING ANALYSIS ===")
    
    sections = {s['section_id']: s for s in data.get('sections', [])}
    extractions = data.get('extractions', [])
    
    # Group extractions by parent
    by_parent = {}
    for e in extractions:
        parent = e['attributes'].get('parent_section_id', 'NO_PARENT')
        if parent not in by_parent:
            by_parent[parent] = []
        by_parent[parent].append(e)
    
    print(f"Sections: {len(sections)}")
    print(f"Extractions: {len(extractions)}")
    print(f"Unique parents: {len(by_parent)}")
    
    # Check for problematic parenting patterns
    issues = []
    
    # 1. Check for extractions with missing parent sections
    missing_parents = set()
    for parent in by_parent.keys():
        if parent != 'NO_PARENT' and parent not in sections:
            missing_parents.add(parent)
            
    if missing_parents:
        print(f"\n⚠️  Missing parent sections: {len(missing_parents)}")
        for mp in sorted(missing_parents)[:5]:
            count = len(by_parent[mp])
            print(f"  {mp}: {count} extractions")
            issues.append(f"Missing parent section: {mp} ({count} extractions)")
    
    # 2. Check for sections with nested parent relationships
    print(f"\n--- Section Hierarchy ---")
    for section_id, section in sections.items():
        parent = section.get('parent_section', 'ROOT')
        level = section.get('section_level', 0)
        child_count = len([e for e in extractions if e['attributes'].get('parent_section_id') == section_id])
        print(f"  {section_id} (level {level}) -> parent: {parent}, children: {child_count}")
        
        # Check if parent actually exists
        if parent != 'ROOT' and parent not in sections:
            issues.append(f"Section {section_id} has non-existent parent: {parent}")
    
    # 3. Simulate synthetic parent creation (like in JS)
    synthetic_parents_needed = set()
    for e in extractions:
        parent = e['attributes'].get('parent_section_id')
        if parent and parent not in sections and parent != 'NO_PARENT':
            synthetic_parents_needed.add(parent)
            
    if synthetic_parents_needed:
        print(f"\n--- Synthetic Parents Needed ---")
        for sp in sorted(synthetic_parents_needed):
            count = len(by_parent[sp])
            print(f"  {sp}: {count} extractions")
    
    # 4. Look for specific patterns that could cause Norms to appear in wrong places
    norm_extractions = [e for e in extractions if e.get('extraction_class') == 'NORM']
    print(f"\n--- NORM Distribution ---")
    print(f"Total NORM extractions: {len(norm_extractions)}")
    
    norm_parents = {}
    for norm in norm_extractions:
        parent = norm['attributes'].get('parent_section_id', 'NO_PARENT')
        if parent not in norm_parents:
            norm_parents[parent] = []
        norm_parents[parent].append(norm)
    
    for parent, norms in sorted(norm_parents.items(), key=lambda x: len(x[1]), reverse=True):
        if parent in sections:
            section_name = sections[parent].get('section_name', parent)
            print(f"  {parent} ({section_name}): {len(norms)} norms")
        else:
            print(f"  {parent} [MISSING SECTION]: {len(norms)} norms")
    
    return issues

def simulate_js_tree_building(data):
    """Simulate the exact JavaScript tree building process"""
    
    print("\n=== JS TREE BUILDING SIMULATION ===")
    
    # Default filters from JS (exclude Tags and Parameters)
    active_filters = {'Tag', 'Parameter'}
    
    nodes = {}
    root_nodes = []
    
    # Step 1: Process sections (if SECTION not filtered)
    should_include_sections = 'SECTION' not in active_filters
    
    if should_include_sections:
        print("--- Processing Sections ---")
        for i, section in enumerate(data.get('sections', [])):
            section_id = section['section_id']
            parent_id = section.get('parent_section')
            
            # Create synthetic parent if needed
            if parent_id and parent_id not in data.get('sections', {}):
                print(f"  Section {section_id} needs synthetic parent: {parent_id}")
            
            node_data = {
                'id': section_id,
                'title': section.get('section_name', section_id),
                'type': 'SECTION',
                'parent_id': parent_id,
                'children': [],
                'document_order': i,
                'source': 'sections'
            }
            nodes[section_id] = node_data
            print(f"  Added: {section_id} -> parent: {parent_id or 'ROOT'}")
    
    # Step 2: Process extractions  
    extractions = data.get('extractions', [])
    relevant = [e for e in extractions if e.get('extraction_class') not in active_filters]
    
    print(f"--- Processing Extractions ---")
    print(f"Filtered: {len(extractions)} -> {len(relevant)} relevant")
    
    for i, extraction in enumerate(relevant):
        extraction_id = extraction['attributes']['id']
        parent_id = extraction['attributes'].get('parent_section_id')
        
        # Skip if parent is NO_PARENT or empty
        if not parent_id or parent_id == 'NO_PARENT':
            parent_id = None
            
        node_data = {
            'id': extraction_id,
            'title': extraction.get('extraction_text', '')[:50] + '...',
            'type': extraction['extraction_class'],
            'parent_id': parent_id, 
            'children': [],
            'document_order': len(data.get('sections', [])) + i,
            'source': 'extractions'
        }
        nodes[extraction_id] = node_data
        
        if extraction['extraction_class'] == 'NORM':
            print(f"  NORM: {extraction_id} -> parent: {parent_id or 'ROOT'}")
    
    # Step 3: Create synthetic parents for missing ones
    missing_parents = set()
    for node in nodes.values():
        if node['parent_id'] and node['parent_id'] not in nodes:
            missing_parents.add(node['parent_id'])
    
    if missing_parents:
        print(f"--- Creating Synthetic Parents ---")
        for parent_id in missing_parents:
            synthetic_node = {
                'id': parent_id,
                'title': f'[Missing] {parent_id}',
                'type': 'SECTION',
                'parent_id': None,
                'children': [],
                'document_order': -1000,
                'source': 'synthetic'
            }
            nodes[parent_id] = synthetic_node
            print(f"  Created synthetic: {parent_id}")
    
    # Step 4: Build parent-child relationships
    print(f"--- Building Relationships ---")
    orphan_count = 0
    
    for node in nodes.values():
        if node['parent_id'] and node['parent_id'] in nodes:
            parent = nodes[node['parent_id']]
            parent['children'].append(node)
        elif node['source'] != 'synthetic' or node['parent_id'] is not None:
            root_nodes.append(node)
            if node['parent_id']:
                orphan_count += 1
                print(f"  Orphan: {node['id']} (parent {node['parent_id']} missing)")
    
    print(f"Total nodes: {len(nodes)}, Roots: {len(root_nodes)}, Orphans: {orphan_count}")
    
    # Find potential issues
    issues = []
    norm_nodes = [n for n in nodes.values() if n['type'] == 'NORM']
    
    print(f"\n--- NORM Analysis ---")
    print(f"Total NORM nodes: {len(norm_nodes)}")
    
    # Group NORM nodes by their actual parent in the tree
    norm_by_parent = {}
    for norm in norm_nodes:
        parent = 'ROOT'
        if norm['parent_id'] and norm['parent_id'] in nodes:
            parent = nodes[norm['parent_id']]['title']
        elif norm in root_nodes:
            parent = 'ROOT'
        
        if parent not in norm_by_parent:
            norm_by_parent[parent] = []
        norm_by_parent[parent].append(norm)
    
    for parent, norms in sorted(norm_by_parent.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {parent}: {len(norms)} norms")
        if len(norms) > 10:  # Show details for sections with many norms
            for norm in norms[:3]:
                print(f"    - {norm['id']}")
            if len(norms) > 3:
                print(f"    ... and {len(norms) - 3} more")
    
    return nodes, root_nodes, issues

def main():
    print("🔍 Tree Duplication Issue Debugger")
    print("==================================")
    
    # Load real data
    data = load_real_data()
    if not data:
        return
    
    # Analyze parenting issues
    parenting_issues = analyze_parenting_issues(data)
    
    # Simulate JS tree building
    nodes, root_nodes, tree_issues = simulate_js_tree_building(data)
    
    # Summary
    print(f"\n=== SUMMARY ===")
    total_issues = len(parenting_issues) + len(tree_issues)
    if total_issues > 0:
        print(f"❌ Found {total_issues} potential issues:")
        for issue in (parenting_issues + tree_issues)[:10]:
            print(f"  - {issue}")
    else:
        print("✅ No obvious issues found in tree structure")
    
    print(f"\nTree stats:")
    print(f"  - Total nodes: {len(nodes)}")
    print(f"  - Root nodes: {len(root_nodes)}")
    print(f"  - NORM nodes: {len([n for n in nodes.values() if n['type'] == 'NORM'])}")

if __name__ == "__main__":
    main()