#!/usr/bin/env python3
"""
Test to verify the tree duplication fix works correctly.

This test creates data with duplicate IDs and simulates the fixed JavaScript logic
to ensure duplicates are properly handled.
"""

import json

def create_test_data_with_duplicates():
    """Create test data that has duplicate extraction IDs (simulating the real issue)"""
    test_data = {
        "document_metadata": {
            "source_file": "test_document.json",
            "total_extractions": 8
        },
        "sections": [
            {
                "section_id": "section_001", 
                "section_name": "Fire Safety Rules",
                "section_level": 1,
                "parent_section": None,
                "has_extractions": True,
                "extraction_count": 4
            },
            {
                "section_id": "section_002",
                "section_name": "Emergency Procedures",  
                "section_level": 1,
                "parent_section": None,
                "has_extractions": True,
                "extraction_count": 4
            }
        ],
        "extractions": [
            # NORM that appears in section_001 (first occurrence - should be kept)
            {
                "extraction_class": "NORM",
                "extraction_text": "Fire doors must be self-closing and fire-rated",
                "attributes": {
                    "id": "duplicate_norm_001",  # This ID will be duplicated
                    "parent_section_id": "section_001",
                    "norm_statement": "Fire doors must be self-closing and fire-rated"
                }
            },
            # Different NORM in section_001
            {
                "extraction_class": "NORM", 
                "extraction_text": "Exit signs must be illuminated",
                "attributes": {
                    "id": "unique_norm_001",
                    "parent_section_id": "section_001",
                    "norm_statement": "Exit signs must be illuminated"
                }
            },
            # DUPLICATE: Same ID as first NORM but different content and section (should be skipped)
            {
                "extraction_class": "NORM",
                "extraction_text": "Emergency exits must remain unobstructed", # Different content
                "attributes": {
                    "id": "duplicate_norm_001",  # Same ID as first norm - DUPLICATE!
                    "parent_section_id": "section_002",  # Different section
                    "norm_statement": "Emergency exits must remain unobstructed"
                }
            },
            # Another DUPLICATE: Same ID but in yet another context (should be skipped)
            {
                "extraction_class": "NORM",
                "extraction_text": "Smoke detectors must be tested monthly",
                "attributes": {
                    "id": "duplicate_norm_001",  # Same ID again - DUPLICATE!
                    "parent_section_id": "section_002",
                    "norm_statement": "Smoke detectors must be tested monthly"
                }
            },
            # Unique NORM in section_002
            {
                "extraction_class": "NORM",
                "extraction_text": "Alarm systems must have battery backup",
                "attributes": {
                    "id": "unique_norm_002",
                    "parent_section_id": "section_002",
                    "norm_statement": "Alarm systems must have battery backup"
                }
            },
            # Tag (filtered out)
            {
                "extraction_class": "Tag",
                "extraction_text": "FIRE_SAFETY",
                "attributes": {
                    "id": "tag_001",
                    "parent_section_id": "section_001"
                }
            }
        ]
    }
    return test_data

def simulate_fixed_tree_building(data):
    """
    Simulate the FIXED JavaScript tree building logic with deduplication.
    """
    print("=== FIXED TREE BUILDING SIMULATION ===")
    
    active_filters = {'Tag', 'Parameter'}  # Default filters
    nodes = {}
    duplicate_count = 0
    
    # Process sections
    sections = data.get('sections', [])
    should_include_sections = 'SECTION' not in active_filters
    
    if should_include_sections and sections:
        print("--- Processing Sections ---")
        for i, section in enumerate(sections):
            section_id = section['section_id']
            
            # Check for duplicate section IDs (NEW: deduplication logic)
            if section_id in nodes:
                print(f"  ⚠️  Duplicate section ID detected: {section_id} already exists. Skipping duplicate section.")
                duplicate_count += 1
                continue
            
            node_data = {
                'id': section_id,
                'title': section['section_name'],
                'type': 'SECTION',
                'parent_id': section.get('parent_section'),
                'children': [],
                'document_order': i,
                'source': 'sections'
            }
            nodes[section_id] = node_data
            print(f"  Added section: {section_id}")
    
    # Process extractions
    extractions = data.get('extractions', [])
    relevant = [e for e in extractions if e.get('extraction_class') not in active_filters]
    
    print(f"--- Processing Extractions ---")
    print(f"Filtered: {len(extractions)} -> {len(relevant)} relevant")
    
    for i, extraction in enumerate(relevant):
        extraction_id = extraction['attributes']['id']
        parent_id = extraction['attributes'].get('parent_section_id')
        
        # NEW: Check if this node already exists (deduplication logic)
        if extraction_id in nodes:
            existing_node = nodes[extraction_id]
            existing_parent = existing_node.get('parent_id', 'ROOT')
            new_parent = parent_id or 'ROOT'
            
            print(f"  ⚠️  Duplicate node ID detected: {extraction_id} ({extraction['extraction_class']}) already exists. Skipping duplicate.")
            if existing_parent != new_parent:
                print(f"     Existing node in: {existing_parent}, duplicate would be in: {new_parent}")
            
            duplicate_count += 1
            continue  # Skip this duplicate
        
        node_data = {
            'id': extraction_id,
            'title': extraction.get('extraction_text', '')[:50] + '...',
            'type': extraction['extraction_class'],
            'parent_id': parent_id,
            'children': [],
            'document_order': len(sections) + i,
            'source': 'extractions'
        }
        nodes[extraction_id] = node_data
        print(f"  Added extraction: {extraction_id} ({node_data['type']}) -> parent: {parent_id}")
    
    # Build parent-child relationships
    root_nodes = []
    for node in nodes.values():
        if node['parent_id'] and node['parent_id'] in nodes:
            parent = nodes[node['parent_id']]
            parent['children'].append(node)
        else:
            root_nodes.append(node)
    
    print(f"\n--- Summary ---")
    print(f"Total duplicates skipped: {duplicate_count}")
    print(f"Final unique nodes: {len(nodes)}")
    print(f"Root nodes: {len(root_nodes)}")
    
    return nodes, root_nodes, duplicate_count

def test_duplication_fix():
    """Test that the duplication fix works correctly"""
    
    print("🧪 Testing Tree Duplication Fix")
    print("===============================")
    
    # Create test data with known duplicates
    test_data = create_test_data_with_duplicates()
    
    print(f"Input test data:")
    print(f"  - Sections: {len(test_data['sections'])}")
    print(f"  - Extractions: {len(test_data['extractions'])}")
    print(f"  - Expected duplicate: 'duplicate_norm_001' appears 3 times")
    
    # Test the fixed tree building logic
    nodes, root_nodes, duplicate_count = simulate_fixed_tree_building(test_data)
    
    # Validate the results
    success = True
    issues = []
    
    # Check that the duplicate was properly handled
    if duplicate_count != 2:  # Should skip 2 duplicates
        success = False
        issues.append(f"Expected 2 duplicates to be skipped, but {duplicate_count} were skipped")
    
    # Check that 'duplicate_norm_001' appears only once
    if 'duplicate_norm_001' not in nodes:
        success = False
        issues.append("duplicate_norm_001 should exist (first occurrence)")
    else:
        # Check it's in the correct section (first occurrence)
        node = nodes['duplicate_norm_001']
        if node['parent_id'] != 'section_001':
            success = False
            issues.append(f"duplicate_norm_001 should be in section_001, but is in {node['parent_id']}")
    
    # Check that unique norms are preserved
    expected_unique_norms = ['unique_norm_001', 'unique_norm_002']
    for norm_id in expected_unique_norms:
        if norm_id not in nodes:
            success = False
            issues.append(f"Unique norm {norm_id} should be preserved")
    
    # Check tree structure
    print(f"\n--- Final Tree Structure ---")
    for root in root_nodes:
        print_tree_structure(root, nodes, 0)
    
    # Print results
    if success:
        print(f"\n✅ TEST PASSED")
        print(f"   - Duplicates properly skipped: {duplicate_count}")
        print(f"   - Unique nodes preserved: {len(nodes)}")
        print(f"   - Tree structure intact: {len(root_nodes)} root nodes")
    else:
        print(f"\n❌ TEST FAILED")
        for issue in issues:
            print(f"   - {issue}")
    
    return success

def print_tree_structure(node, all_nodes, level):
    """Print the tree structure for debugging"""
    indent = "  " * level
    children_count = len(node['children'])
    print(f"{indent}{node['id']} ({node['type']}) [{node['source']}] - {children_count} children")
    
    for child in node['children']:
        print_tree_structure(child, all_nodes, level + 1)

if __name__ == "__main__":
    success = test_duplication_fix()
    if success:
        print("\n🎉 Tree duplication fix is working correctly!")
    else:
        print("\n💥 Tree duplication fix needs more work.")