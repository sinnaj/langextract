#!/usr/bin/env python3
"""
Investigate the position mapping issue mentioned by the user.
This test creates a scenario where the same NORM appears in multiple sections
and checks whether our "first occurrence wins" approach is placing it correctly.
"""

def simulate_deduplication_scenarios():
    """Test different scenarios where duplication and position mapping could be problematic"""
    
    print("🔍 INVESTIGATING POSITION MAPPING ISSUES")
    print("=" * 60)
    
    # Scenario 1: NORM appears first in wrong section, later in correct section
    print("\n📍 SCENARIO 1: First occurrence in wrong section")
    print("-" * 50)
    
    extractions_scenario_1 = [
        {
            "extraction_class": "NORM",
            "attributes": {"id": "norm_123"},
            "extraction_text": "Fire doors must be self-closing",
            "parent_id": "wrong_section_001",  # First appearance in wrong place
            "document_order": 5
        },
        {
            "extraction_class": "NORM", 
            "attributes": {"id": "norm_123"},  # Same ID - duplicate!
            "extraction_text": "Fire doors must be self-closing",
            "parent_id": "correct_section_002",  # Later appearance in correct place
            "document_order": 15
        },
        {
            "extraction_class": "SECTION",
            "attributes": {"id": "wrong_section_001", "section_name": "General Requirements"},
            "parent_id": None
        },
        {
            "extraction_class": "SECTION",
            "attributes": {"id": "correct_section_002", "section_name": "Fire Door Specifications"}, 
            "parent_id": None
        }
    ]
    
    # Simulate current deduplication logic
    nodes = {}
    duplicates_skipped = []
    
    for extraction in extractions_scenario_1:
        node_id = extraction["attributes"]["id"]
        parent_id = extraction.get("parent_id", None)
        
        if node_id in nodes:
            print(f"⚠️  DUPLICATE DETECTED: {node_id}")
            existing_parent = nodes[node_id].get("parent_id", "ROOT")
            print(f"   Existing location: {existing_parent}")
            print(f"   Would-be location: {parent_id}")
            print(f"   🚫 SKIPPING duplicate (first occurrence wins)")
            duplicates_skipped.append({
                "id": node_id,
                "existing_parent": existing_parent,
                "skipped_parent": parent_id,
                "extraction": extraction
            })
            continue
            
        nodes[node_id] = {
            "id": node_id,
            "type": extraction["extraction_class"],
            "parent_id": parent_id,
            "text": extraction.get("extraction_text", ""),
            "document_order": extraction.get("document_order", 0),
            "extraction": extraction
        }
        print(f"✅ ADDED: {node_id} -> parent: {parent_id}")
    
    print(f"\n📊 RESULT: {len(duplicates_skipped)} duplicates skipped")
    
    # Check if the result is problematic
    norm_node = nodes.get("norm_123")
    if norm_node and norm_node["parent_id"] == "wrong_section_001":
        print("❌ PROBLEM: NORM ended up in wrong section due to first-occurrence-wins!")
        print(f"   NORM is in: {norm_node['parent_id']} (wrong)")
        print(f"   Should be in: correct_section_002")
        return False
    elif norm_node and norm_node["parent_id"] == "correct_section_002":
        print("✅ Good: NORM is in correct section")
        return True
    else:
        print("❓ Unclear result")
        return None
        
def investigate_real_world_case():
    """Simulate what might be happening in the actual data"""
    
    print("\n\n🔍 INVESTIGATING REAL-WORLD CASE")
    print("=" * 60)
    
    # This simulates how a NORM might appear multiple times in extraction data
    # due to processing pipeline artifacts
    
    print("Scenario: NORM appears in multiple sections due to data processing")
    
    extractions = [
        # NORM first appears when processing section A
        {
            "extraction_class": "NORM",
            "attributes": {
                "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                "norm_statement": "Emergency exits must be clearly marked"
            },
            "parent_id": "section_general",
            "extraction_text": "Emergency exits must be clearly marked",
            "source_context": "Found during section_general processing"
        },
        # Same NORM appears again when processing section B (its actual home)
        {
            "extraction_class": "NORM", 
            "attributes": {
                "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",  # Same UUID!
                "norm_statement": "Emergency exits must be clearly marked"
            },
            "parent_id": "section_emergency_exits",
            "extraction_text": "Emergency exits must be clearly marked", 
            "source_context": "Found during section_emergency_exits processing"
        }
    ]
    
    print(f"Processing {len(extractions)} extractions...")
    
    nodes = {}
    skipped = 0
    
    for i, extraction in enumerate(extractions):
        node_id = extraction["attributes"]["id"]
        parent_id = extraction.get("parent_id")
        
        if node_id in nodes:
            skipped += 1
            existing_parent = nodes[node_id].get("parent_id", "ROOT")
            print(f"Extraction {i+1}: DUPLICATE {node_id[:8]}...")
            print(f"  Already in: {existing_parent}")
            print(f"  Would go to: {parent_id}")
            print(f"  Action: SKIP (first wins)")
            continue
            
        nodes[node_id] = {
            "id": node_id,
            "parent_id": parent_id,
            "type": extraction["extraction_class"],
            "extraction": extraction
        }
        print(f"Extraction {i+1}: ADD {node_id[:8]}... to {parent_id}")
    
    final_location = nodes[extractions[0]["attributes"]["id"]]["parent_id"]
    print(f"\n📍 FINAL RESULT: NORM ended up in '{final_location}'")
    print(f"   Was that the right place? Depends on the data!")
    
    if final_location == "section_general":
        print("❓ POTENTIAL ISSUE: NORM in generic section instead of specific one")
        return "potential_issue"
    elif final_location == "section_emergency_exits": 
        print("✅ Good: NORM in specific relevant section")
        return "correct"
    
def propose_solution():
    """Propose potential improvements to the deduplication logic"""
    
    print("\n\n💡 POTENTIAL SOLUTIONS")
    print("=" * 60)
    
    solutions = [
        {
            "name": "Smart Parent Selection", 
            "description": "When duplicates are found, choose the parent that's most specific/relevant",
            "pros": ["Better positioning", "More logical hierarchy"],
            "cons": ["Complex heuristics needed", "May be ambiguous"]
        },
        {
            "name": "Last Occurrence Wins",
            "description": "Keep the last occurrence instead of first", 
            "pros": ["May catch 'refined' versions", "Simple to implement"],
            "cons": ["May still choose wrong location", "Arbitrary"]
        },
        {
            "name": "Best Match Selection",
            "description": "Compare parent section names/types and choose best match",
            "pros": ["More intelligent selection", "Context-aware"],
            "cons": ["Complex logic", "May be slow"]
        },
        {
            "name": "Allow Controlled Duplicates",
            "description": "Allow same node in multiple places but mark as references",
            "pros": ["Shows full context", "No information loss"],  
            "cons": ["UI complexity", "Potential confusion"]
        }
    ]
    
    for i, solution in enumerate(solutions, 1):
        print(f"{i}. {solution['name']}")
        print(f"   {solution['description']}")
        print(f"   ✅ Pros: {', '.join(solution['pros'])}")
        print(f"   ❌ Cons: {', '.join(solution['cons'])}")
        print()

if __name__ == "__main__":
    # Run investigations
    scenario_1_result = simulate_deduplication_scenarios()
    investigate_real_world_case()
    propose_solution()
    
    print("\n" + "=" * 60)
    print("🎯 CONCLUSION")
    print("-" * 60)
    
    if scenario_1_result == False:
        print("❌ CONFIRMED: First-occurrence-wins can place NORMs in wrong sections!")
        print("   The user's complaint is valid - position mapping is incorrect.")
        print("   Need to implement smarter deduplication logic.")
    elif scenario_1_result == True:
        print("✅ First-occurrence-wins worked correctly in test scenario")
        print("   Issue might be in edge cases or different data patterns")
    else:
        print("❓ Results inconclusive - need more investigation")
    
    print("\n💡 RECOMMENDATION: Implement smart parent selection logic")
    print("   that considers context and section specificity when choosing")
    print("   which occurrence of a duplicate NORM to keep.")