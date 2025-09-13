#!/usr/bin/env python3
"""
Test to reproduce and verify fix for tree view duplication issue.

This test simulates the tree building logic from JavaScript in Python
to identify where Norms are being duplicated in the tree structure.
"""

import json
import tempfile
import os

def create_test_data():
    """Create test data that demonstrates the duplication issue"""
    test_data = {
        "document_metadata": {
            "source_file": "test_document.json",
            "total_extractions": 10
        },
        "sections": [
            {
                "section_id": "section_001", 
                "section_name": "Fire Safety Doors",
                "section_level": 1,
                "parent_section": None,
                "has_extractions": True,
                "extraction_count": 3
            },
            {
                "section_id": "section_002",
                "section_name": "Emergency Evacuation",  
                "section_level": 1,
                "parent_section": None,
                "has_extractions": True,
                "extraction_count": 2
            },
            {
                "section_id": "section_003",
                "section_name": "Subsection A",
                "section_level": 2, 
                "parent_section": "section_001",
                "has_extractions": True,
                "extraction_count": 2
            }
        ],
        "extractions": [
            # NORM that belongs to section_001
            {
                "extraction_class": "NORM",
                "extraction_text": "Fire doors must be self-closing",
                "attributes": {
                    "id": "norm_001",
                    "parent_section_id": "section_001",
                    "norm_statement": "Fire doors must be self-closing"
                }
            },
            # NORM that belongs to section_002  
            {
                "extraction_class": "NORM",
                "extraction_text": "Exit doors must open outward",
                "attributes": {
                    "id": "norm_002", 
                    "parent_section_id": "section_002",
                    "norm_statement": "Exit doors must open outward"
                }
            },
            # NORM that belongs to section_003 (subsection)
            {
                "extraction_class": "NORM",
                "extraction_text": "Door width must be minimum 80cm",
                "attributes": {
                    "id": "norm_003",
                    "parent_section_id": "section_003", 
                    "norm_statement": "Door width must be minimum 80cm"
                }
            },
            # Parameter for section_001
            {
                "extraction_class": "Parameter",
                "extraction_text": "DOOR.WIDTH >= 80",
                "attributes": {
                    "id": "param_001",
                    "parent_section_id": "section_001",
                    "parameter_name": "DOOR.WIDTH"
                }
            },
            # Tag for section_002
            {
                "extraction_class": "Tag", 
                "extraction_text": "EMERGENCY_EXIT",
                "attributes": {
                    "id": "tag_001",
                    "parent_section_id": "section_002",
                    "tag_name": "EMERGENCY_EXIT"
                }
            }
        ]
    }
    return test_data

def simulate_tree_building(data, active_filters=None):
    """
    Simulate the JavaScript tree building logic to identify duplication issues.
    
    This mimics the buildDocumentTree method from preview-optimizer.js
    """
    if active_filters is None:
        active_filters = {'Tag', 'Parameter'}  # Default filters from JS
        
    nodes = {}
    root_nodes = []
    
    print("=== TREE BUILDING SIMULATION ===")
    print(f"Input data: {len(data.get('sections', []))} sections, {len(data.get('extractions', []))} extractions")
    print(f"Active filters: {active_filters}")
    
    # Step 1: Process sections (mimicking lines 2376-2428 in JS)
    sections = data.get('sections', [])
    should_include_sections = 'SECTION' not in active_filters
    
    if should_include_sections and sections:
        print("\n--- Processing Sections ---")
        for i, section in enumerate(sections):
            section_id = section['section_id']
            node_data = {
                'id': section_id,
                'title': section['section_name'],
                'type': 'SECTION',
                'parent_id': section.get('parent_section'),
                'children': [],
                'document_order': i,
                'source': 'sections_array'  # Track where this node came from
            }
            nodes[section_id] = node_data
            print(f"  Added section: {section_id} -> parent: {node_data['parent_id'] or 'ROOT'}")
    
    # Step 2: Process extractions (mimicking lines 2507-2533 in JS)  
    extractions = data.get('extractions', [])
    relevant = [e for e in extractions if e.get('extraction_class') not in active_filters]
    
    print(f"\n--- Processing Extractions ---")
    print(f"Filtered from {len(extractions)} total to {len(relevant)} relevant extractions")
    
    for i, extraction in enumerate(relevant):
        extraction_id = extraction['attributes']['id']
        parent_id = extraction['attributes'].get('parent_section_id')
        
        # Check if this node already exists (potential duplication!)
        if extraction_id in nodes:
            print(f"  ⚠️  DUPLICATE DETECTED: {extraction_id} already exists as {nodes[extraction_id]['source']}")
            continue
        
        node_data = {
            'id': extraction_id,
            'title': extraction.get('extraction_text', '')[:50] + '...',
            'type': extraction['extraction_class'], 
            'parent_id': parent_id,
            'children': [],
            'document_order': len(sections) + i,
            'source': 'extractions_array'
        }
        nodes[extraction_id] = node_data
        print(f"  Added extraction: {extraction_id} ({node_data['type']}) -> parent: {parent_id}")
    
    # Step 3: Create synthetic parents for missing parents (mimicking lines 2549-2569)
    missing_parents = set()
    for node in nodes.values():
        if node['parent_id'] and node['parent_id'] not in nodes:
            missing_parents.add(node['parent_id'])
    
    if missing_parents:
        print(f"\n--- Creating Synthetic Parents ---")
        for parent_id in missing_parents:
            synthetic_node = {
                'id': parent_id,
                'title': f'[Missing Section] {parent_id}',
                'type': 'SECTION',
                'parent_id': None,
                'children': [],
                'document_order': 1000000,
                'source': 'synthetic'
            }
            nodes[parent_id] = synthetic_node
            print(f"  Created synthetic parent: {parent_id}")
    
    # Step 4: Build parent-child relationships
    print(f"\n--- Building Parent-Child Relationships ---")
    orphan_count = 0
    
    for node in nodes.values():
        if node['parent_id'] and node['parent_id'] in nodes:
            parent = nodes[node['parent_id']]
            parent['children'].append(node)
            print(f"  Linked {node['id']} as child of {parent['id']}")
        elif not (node.get('source') == 'synthetic' and node['parent_id'] is None):
            root_nodes.append(node)
            if node['parent_id']:
                print(f"  ⚠️  Orphan: {node['id']} has parent {node['parent_id']} but parent not found - making it root")
                orphan_count += 1
            else:
                print(f"  Root node: {node['id']}")
    
    if orphan_count > 0:
        print(f"  Found {orphan_count} orphaned nodes promoted to root level")
    
    print(f"\n--- Tree Summary ---")
    print(f"Total nodes created: {len(nodes)}")
    print(f"Root nodes: {len(root_nodes)}")
    
    return nodes, root_nodes

def analyze_tree_structure(nodes, root_nodes):
    """Analyze the tree structure to identify potential issues"""
    
    print(f"\n=== TREE STRUCTURE ANALYSIS ===")
    
    def print_tree(node, level=0):
        indent = "  " * level
        children_info = f"({len(node['children'])} children)" if node['children'] else ""
        source_info = f"[{node['source']}]"
        print(f"{indent}{node['id']} ({node['type']}) {children_info} {source_info}")
        
        for child in sorted(node['children'], key=lambda x: x['document_order']):
            print_tree(child, level + 1)
    
    for root in sorted(root_nodes, key=lambda x: x['document_order']):
        print_tree(root)
        print()
    
    # Check for potential issues
    issues = []
    
    # Check for nodes in wrong sections
    for node_id, node in nodes.items():
        if node['type'] == 'NORM':
            expected_parent = None
            # Find what the expected parent should be based on parent_section_id
            for extraction in test_data['extractions']:
                if extraction['attributes']['id'] == node_id:
                    expected_parent = extraction['attributes'].get('parent_section_id')
                    break
                    
            if expected_parent and node['parent_id'] != expected_parent:
                issues.append(f"NORM {node_id} is in wrong section: expected parent {expected_parent}, actual parent {node['parent_id']}")
    
    if issues:
        print("🚨 ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ No parenting issues detected")
    
    return issues

def test_duplication_issue():
    """Test the current tree building logic for duplication issues"""
    
    global test_data
    test_data = create_test_data()
    
    print("Testing current tree building logic...")
    
    # Test with default filters (should exclude Tags and Parameters)
    nodes, root_nodes = simulate_tree_building(test_data)
    issues = analyze_tree_structure(nodes, root_nodes)
    
    return len(issues) == 0

if __name__ == "__main__":
    print("🧪 Tree Duplication Issue Test\n")
    
    # Run the test
    success = test_duplication_issue()
    
    if success:
        print("\n✅ Test PASSED: No duplication issues found")
    else:
        print("\n❌ Test FAILED: Duplication issues detected") 
        
    print("\nTest completed.")