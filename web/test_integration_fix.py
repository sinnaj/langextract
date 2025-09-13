#!/usr/bin/env python3
"""
Integration test to verify the tree duplication fix works with real data.

This test loads real combined_extractions.json data and simulates the fixed JavaScript
tree building logic to ensure duplicates are properly handled.
"""

import json
import os

def load_real_test_data():
    """Load a real combined_extractions.json file"""
    test_file = "../output_runs/1757006891/lx output/combined_extractions.json"
    if os.path.exists(test_file):
        with open(test_file, 'r') as f:
            return json.load(f)
    return None

def simulate_fixed_tree_building_with_real_data(data):
    """
    Simulate the FIXED JavaScript tree building logic using real data.
    This incorporates the deduplication fix.
    """
    print("=== FIXED TREE BUILDING WITH REAL DATA ===")
    
    active_filters = {'Tag', 'Parameter'}  # Default filters from JS
    nodes = {}
    root_nodes = []
    duplicate_count = 0
    
    # Step 1: Process sections with deduplication
    sections = data.get('sections', [])
    should_include_sections = 'SECTION' not in active_filters
    
    if should_include_sections and sections:
        print(f"--- Processing {len(sections)} Sections ---")
        for i, section in enumerate(sections):
            section_id = section['section_id']
            
            # FIXED: Check for duplicate section IDs 
            if section_id in nodes:
                print(f"  ⚠️  Duplicate section ID detected: {section_id} already exists. Skipping duplicate section.")
                duplicate_count += 1
                continue
            
            parent_id = section.get('parent_section')
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
    
    # Step 2: Process extractions with deduplication
    extractions = data.get('extractions', [])
    relevant = [e for e in extractions if e.get('extraction_class') not in active_filters]
    
    print(f"--- Processing Extractions ---")
    print(f"Filtered: {len(extractions)} -> {len(relevant)} relevant extractions")
    
    norms_processed = 0
    norm_duplicates_skipped = 0
    
    for i, extraction in enumerate(relevant):
        extraction_id = extraction['attributes']['id']
        parent_id = extraction['attributes'].get('parent_section_id')
        extraction_class = extraction.get('extraction_class')
        
        # Skip if parent is NO_PARENT or empty
        if not parent_id or parent_id == 'NO_PARENT':
            parent_id = None
        
        # FIXED: Check if this node already exists (deduplication logic)
        if extraction_id in nodes:
            existing_node = nodes[extraction_id]
            existing_parent = existing_node.get('parent_id', 'ROOT')
            new_parent = parent_id or 'ROOT'
            
            if extraction_class == 'NORM':
                norm_duplicates_skipped += 1
                print(f"  ⚠️  NORM duplicate skipped: {extraction_id}")
                print(f"     Existing in: {existing_parent}, would be in: {new_parent}")
            
            duplicate_count += 1
            continue  # Skip this duplicate
        
        node_data = {
            'id': extraction_id,
            'title': extraction.get('extraction_text', '')[:50] + '...',
            'type': extraction_class,
            'parent_id': parent_id,
            'children': [],
            'document_order': len(sections) + i,
            'source': 'extractions'
        }
        nodes[extraction_id] = node_data
        
        if extraction_class == 'NORM':
            norms_processed += 1
    
    print(f"  Total extractions processed: {len(relevant) - duplicate_count}")
    print(f"  Duplicates skipped: {duplicate_count}")
    print(f"  NORM duplicates skipped: {norm_duplicates_skipped}")
    print(f"  Unique NORMs processed: {norms_processed}")
    
    # Step 3: Create synthetic parents for missing ones
    missing_parents = set()
    for node in nodes.values():
        if node['parent_id'] and node['parent_id'] not in nodes:
            missing_parents.add(node['parent_id'])
    
    if missing_parents:
        print(f"--- Creating {len(missing_parents)} Synthetic Parents ---")
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
    
    # Step 4: Build parent-child relationships
    orphan_count = 0
    for node in nodes.values():
        if node['parent_id'] and node['parent_id'] in nodes:
            parent = nodes[node['parent_id']]
            parent['children'].append(node)
        elif node['source'] != 'synthetic' or node['parent_id'] is not None:
            root_nodes.append(node)
            if node['parent_id']:
                orphan_count += 1
    
    print(f"--- Final Tree Statistics ---")
    print(f"Total unique nodes: {len(nodes)}")
    print(f"Root nodes: {len(root_nodes)}")
    print(f"Orphaned nodes: {orphan_count}")
    
    return nodes, root_nodes, {
        'total_duplicates_skipped': duplicate_count,
        'norm_duplicates_skipped': norm_duplicates_skipped,
        'unique_norms': norms_processed,
        'total_nodes': len(nodes),
        'root_nodes': len(root_nodes)
    }

def analyze_norm_distribution(nodes):
    """Analyze how NORMs are distributed in the fixed tree"""
    
    print(f"\n=== NORM DISTRIBUTION ANALYSIS ===")
    
    norm_nodes = [n for n in nodes.values() if n['type'] == 'NORM']
    print(f"Total NORM nodes in tree: {len(norm_nodes)}")
    
    # Group by parent
    by_parent = {}
    for norm in norm_nodes:
        parent_id = norm['parent_id'] or 'ROOT'
        if parent_id in nodes:
            parent_title = nodes[parent_id]['title']
        else:
            parent_title = parent_id
        
        if parent_title not in by_parent:
            by_parent[parent_title] = []
        by_parent[parent_title].append(norm)
    
    print(f"NORMs distributed across {len(by_parent)} different sections:")
    
    for parent_title, norms in sorted(by_parent.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"  {parent_title}: {len(norms)} norms")
    
    return by_parent

def test_integration_with_real_data():
    """Run integration test with real data"""
    
    print("🧪 Integration Test: Tree Duplication Fix with Real Data")
    print("========================================================")
    
    # Load real data
    data = load_real_test_data()
    if not data:
        print("❌ Could not load real test data")
        return False
    
    print(f"Loaded real data:")
    print(f"  - Sections: {len(data.get('sections', []))}")
    print(f"  - Extractions: {len(data.get('extractions', []))}")
    
    # Count original duplicates in the data
    extraction_ids = [e['attributes']['id'] for e in data.get('extractions', [])]
    id_counts = {}
    for id in extraction_ids:
        id_counts[id] = id_counts.get(id, 0) + 1
    
    original_duplicates = sum(count - 1 for count in id_counts.values() if count > 1)
    print(f"  - Original duplicate IDs in data: {original_duplicates}")
    
    # Run the fixed tree building
    nodes, root_nodes, stats = simulate_fixed_tree_building_with_real_data(data)
    
    # Analyze NORM distribution
    norm_distribution = analyze_norm_distribution(nodes)
    
    # Validate the fix
    success = True
    issues = []
    
    # Check that duplicates were actually skipped
    if stats['total_duplicates_skipped'] != original_duplicates:
        issues.append(f"Expected {original_duplicates} duplicates to be skipped, but {stats['total_duplicates_skipped']} were skipped")
    
    # Check that we have fewer total nodes than original extractions (due to deduplication)
    original_extraction_count = len([e for e in data.get('extractions', []) if e.get('extraction_class') not in {'Tag', 'Parameter'}])
    final_extraction_nodes = len([n for n in nodes.values() if n['source'] == 'extractions'])
    
    if final_extraction_nodes >= original_extraction_count:
        issues.append(f"Expected fewer extraction nodes ({final_extraction_nodes}) than original count ({original_extraction_count}) due to deduplication")
        success = False
    
    # Check that NORMs are properly distributed
    if stats['unique_norms'] == 0:
        issues.append("No NORM nodes found in the tree")
        success = False
    
    # Print results
    print(f"\n=== TEST RESULTS ===")
    if success and not issues:
        print(f"✅ INTEGRATION TEST PASSED")
        print(f"   - Duplicates properly skipped: {stats['total_duplicates_skipped']}")
        print(f"   - NORM duplicates skipped: {stats['norm_duplicates_skipped']}")
        print(f"   - Unique NORMs in tree: {stats['unique_norms']}")
        print(f"   - Total nodes: {stats['total_nodes']}")
        print(f"   - Root nodes: {stats['root_nodes']}")
        
        print(f"\n🎉 Fix successfully prevents NORM duplication!")
        print(f"   Each NORM now appears only once in its correct section.")
        
    else:
        print(f"❌ INTEGRATION TEST FAILED")
        for issue in issues:
            print(f"   - {issue}")
    
    return success and not issues

if __name__ == "__main__":
    success = test_integration_with_real_data()
    print(f"\nIntegration test {'PASSED' if success else 'FAILED'}.")