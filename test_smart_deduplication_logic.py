#!/usr/bin/env python3
"""
Test the smart deduplication fix with a real scenario where 
a NORM appears in multiple sections and we need to choose the best one.
"""

def create_smart_deduplication_test_data():
    """Create test data that demonstrates the smart deduplication fix"""
    return {
        "document_metadata": {
            "source_file": "smart_dedup_test.json",
            "total_extractions": 8
        },
        "sections": [
            {
                "section_id": "general_001", 
                "section_name": "General Requirements",
                "section_level": 1,
                "parent_section": None,
                "has_extractions": True,
                "extraction_count": 1
            },
            {
                "section_id": "fire_door_002",
                "section_name": "Fire Door Specifications",  
                "section_level": 2,
                "parent_section": "general_001", 
                "has_extractions": True,
                "extraction_count": 2
            },
            {
                "section_id": "emergency_003",
                "section_name": "Emergency Exit Requirements",
                "section_level": 2, 
                "parent_section": None,
                "has_extractions": True,
                "extraction_count": 1
            }
        ],
        "extractions": [
            # NORM that appears first in generic section (should be moved to specific section)
            {
                "extraction_class": "NORM",
                "extraction_text": "Fire doors must be self-closing and must remain closed at all times",
                "attributes": {
                    "id": "norm_fire_door_001",
                    "norm_statement": "Fire doors must be self-closing and must remain closed at all times",
                    "parent_id": "general_001"  # First appearance in generic section
                },
                "document_order": 5
            },
            # Same NORM appears again in specific section (should be kept here)
            {
                "extraction_class": "NORM", 
                "extraction_text": "Fire doors must be self-closing and must remain closed at all times",
                "attributes": {
                    "id": "norm_fire_door_001",  # Same ID - duplicate!
                    "norm_statement": "Fire doors must be self-closing and must remain closed at all times",
                    "parent_id": "fire_door_002"  # Later appearance in specific section
                },
                "document_order": 15
            },
            # NORM that appears first in specific section (should stay there)
            {
                "extraction_class": "NORM",
                "extraction_text": "Emergency exits must be clearly marked with illuminated signs",
                "attributes": {
                    "id": "norm_emergency_001", 
                    "norm_statement": "Emergency exits must be clearly marked with illuminated signs",
                    "parent_id": "emergency_003"  # First appearance in specific section
                },
                "document_order": 25
            },
            # Same NORM appears again in generic section (should be ignored)
            {
                "extraction_class": "NORM",
                "extraction_text": "Emergency exits must be clearly marked with illuminated signs", 
                "attributes": {
                    "id": "norm_emergency_001",  # Same ID - duplicate!
                    "norm_statement": "Emergency exits must be clearly marked with illuminated signs",
                    "parent_id": "general_001"  # Later appearance in generic section
                },
                "document_order": 35
            },
            # NORM that appears at ROOT first, then in specific section (should be moved)
            {
                "extraction_class": "NORM",
                "extraction_text": "Fire safety equipment must be inspected monthly",
                "attributes": {
                    "id": "norm_inspection_001",
                    "norm_statement": "Fire safety equipment must be inspected monthly", 
                    "parent_id": None  # First appearance at ROOT
                },
                "document_order": 45
            },
            {
                "extraction_class": "NORM",
                "extraction_text": "Fire safety equipment must be inspected monthly",
                "attributes": {
                    "id": "norm_inspection_001",  # Same ID - duplicate!
                    "norm_statement": "Fire safety equipment must be inspected monthly",
                    "parent_id": "fire_door_002"  # Later appearance in specific section
                },
                "document_order": 55
            }
        ]
    }

def simulate_smart_tree_building(data):
    """Simulate the JavaScript tree building logic with smart deduplication"""
    
    print("🧠 SMART DEDUPLICATION SIMULATION")
    print("=" * 60)
    
    nodes = {}
    duplicates_processed = []
    
    # Process sections first
    if data.get("sections"):
        print("\n--- Processing Sections ---")
        for section in data["sections"]:
            section_id = section["section_id"]
            nodes[section_id] = {
                "id": section_id,
                "title": section["section_name"],
                "type": "SECTION",
                "parent_id": section.get("parent_section"),
                "level": section.get("section_level", 0),
                "children": [],
                "attributes": section,
                "source": "sections_array"
            }
            print(f"  Added section: {section_id} -> parent: {section.get('parent_section', 'ROOT')}")
    
    # Process extractions with smart deduplication
    print("\n--- Processing Extractions with Smart Deduplication ---")
    extractions = data.get("extractions", [])
    
    for i, extraction in enumerate(extractions):
        node_id = extraction["attributes"]["id"]
        parent_id = extraction["attributes"].get("parent_id")
        
        if node_id in nodes:
            # Duplicate detected - apply smart logic
            existing_node = nodes[node_id]
            existing_parent = existing_node.get("parent_id", "ROOT") 
            new_parent = parent_id or "ROOT"
            
            print(f"  ⚠️  DUPLICATE: {node_id}")
            print(f"     Existing in: {existing_parent}")
            print(f"     Would be in: {new_parent}")
            
            # Apply smart parent selection logic
            should_replace = smart_parent_selection(
                existing_node, extraction, existing_parent, new_parent, data
            )
            
            if should_replace:
                print(f"     🔄 REPLACING: Moving to {new_parent} (better location)")
                nodes[node_id]["parent_id"] = new_parent
                nodes[node_id]["document_order"] = extraction.get("document_order", i)
                nodes[node_id]["extraction"] = extraction
                duplicates_processed.append({
                    "id": node_id,
                    "action": "moved",
                    "from": existing_parent,
                    "to": new_parent,
                    "reason": "more_specific"
                })
            else:
                print(f"     ✋ KEEPING: Current location {existing_parent} is better")
                duplicates_processed.append({
                    "id": node_id,
                    "action": "kept",
                    "location": existing_parent,
                    "reason": "already_optimal"
                })
            
            continue
        
        # New node - add it
        nodes[node_id] = {
            "id": node_id,
            "title": extraction.get("extraction_text", "")[:50] + "...",
            "type": extraction["extraction_class"],
            "parent_id": parent_id,
            "document_order": extraction.get("document_order", i),
            "level": 0,  # Will be calculated later
            "children": [],
            "attributes": extraction["attributes"],
            "extraction": extraction,
            "source": "extractions_array"
        }
        print(f"  ✅ ADDED: {node_id} -> parent: {parent_id or 'ROOT'}")
    
    # Build parent-child relationships
    print(f"\n--- Building Parent-Child Relationships ---")
    root_nodes = []
    
    # Clear children arrays first
    for node in nodes.values():
        node["children"] = []
    
    # Build relationships
    for node in nodes.values():
        if node["parent_id"] and node["parent_id"] in nodes:
            parent = nodes[node["parent_id"]]
            parent["children"].append(node)
            node["level"] = parent["level"] + 1
            print(f"  Linked {node['id']} as child of {parent['id']} (level {node['level']})")
        else:
            root_nodes.append(node)
            node["level"] = 0
            print(f"  Root node: {node['id']}")
    
    return nodes, root_nodes, duplicates_processed

def smart_parent_selection(existing_node, new_extraction, existing_parent, new_parent, data):
    """Simulate the smart parent selection logic"""
    
    # Same parent - no change needed
    if existing_parent == new_parent:
        return False
    
    # ROOT vs specific - prefer specific
    if existing_parent in ["ROOT", None] and new_parent not in ["ROOT", None]:
        return True
        
    if new_parent in ["ROOT", None] and existing_parent not in ["ROOT", None]:
        return False
    
    # Get section information
    existing_section = get_section_info(existing_parent, data)
    new_section = get_section_info(new_parent, data)
    
    if existing_section and new_section:
        existing_score = calculate_specificity_score(existing_section, existing_node)
        new_score = calculate_specificity_score(new_section, existing_node) 
        
        print(f"       Specificity scores: {existing_parent}={existing_score}, {new_parent}={new_score}")
        return new_score > existing_score
    
    # If only new parent has section info, prefer it
    if not existing_section and new_section:
        return True
    
    # If only existing parent has section info, keep it
    if existing_section and not new_section:
        return False
    
    # Fallback: later document order wins (assuming refinement)
    existing_order = existing_node.get("document_order", 0)
    new_order = new_extraction.get("document_order", 0)
    return new_order > existing_order

def get_section_info(parent_id, data):
    """Get section information for a parent ID"""
    if not parent_id or parent_id in ["ROOT", None]:
        return None
        
    if data.get("sections"):
        for section in data["sections"]:
            if section["section_id"] == parent_id:
                return section
    
    return None

def calculate_specificity_score(section, node):
    """Calculate section specificity score"""
    score = 0
    
    # Higher level = more specific (deeper nesting)
    level = section.get("section_level", 0)
    score += level * 10
    
    # Longer name typically more specific
    name = section.get("section_name", "")
    score += min(len(name) / 10, 5)
    
    # Keyword matching
    if node and node.get("extraction"):
        node_text = node["extraction"].get("extraction_text", "").lower()
        name_lower = name.lower()
        
        keywords = [word for word in name_lower.split() if len(word) > 3]
        matches = sum(1 for keyword in keywords if keyword in node_text)
        score += matches * 5
    
    # Bonus for specific terms
    name_lower = name.lower()
    if "fire" in name_lower: score += 3
    if "door" in name_lower: score += 3  
    if "emergency" in name_lower: score += 3
    if "safety" in name_lower: score += 3
    if "requirement" in name_lower: score += 2
    if "specification" in name_lower: score += 2
    
    # Penalty for generic terms
    if "general" in name_lower: score -= 5
    if "overview" in name_lower: score -= 3
    if "introduction" in name_lower: score -= 3
    
    return score

def analyze_results(nodes, duplicates_processed):
    """Analyze the results of smart deduplication"""
    
    print(f"\n📊 SMART DEDUPLICATION RESULTS")
    print("=" * 60)
    
    total_nodes = len(nodes)
    norm_nodes = len([n for n in nodes.values() if n["type"] == "NORM"])
    section_nodes = len([n for n in nodes.values() if n["type"] == "SECTION"])
    
    print(f"Total nodes: {total_nodes}")
    print(f"NORM nodes: {norm_nodes}")
    print(f"SECTION nodes: {section_nodes}")
    print(f"Duplicates processed: {len(duplicates_processed)}")
    
    print(f"\n🔄 DUPLICATE PROCESSING SUMMARY:")
    moved_count = len([d for d in duplicates_processed if d["action"] == "moved"])
    kept_count = len([d for d in duplicates_processed if d["action"] == "kept"])
    
    print(f"Moved to better location: {moved_count}")
    print(f"Kept in current location: {kept_count}")
    
    for dup in duplicates_processed:
        if dup["action"] == "moved":
            print(f"  ✅ {dup['id']}: {dup['from']} → {dup['to']} ({dup['reason']})")
        else:
            print(f"  ⚪ {dup['id']}: stayed in {dup['location']} ({dup['reason']})")
    
    # Specific test validations
    print(f"\n🎯 TEST VALIDATIONS:")
    
    # Check fire door norm placement
    fire_door_norm = nodes.get("norm_fire_door_001")
    if fire_door_norm:
        expected_parent = "fire_door_002"  # Should be in specific section
        actual_parent = fire_door_norm["parent_id"] 
        if actual_parent == expected_parent:
            print(f"✅ Fire door NORM correctly placed in {actual_parent}")
        else:
            print(f"❌ Fire door NORM in wrong location: {actual_parent} (expected: {expected_parent})")
    
    # Check emergency norm placement  
    emergency_norm = nodes.get("norm_emergency_001")
    if emergency_norm:
        expected_parent = "emergency_003"  # Should stay in specific section
        actual_parent = emergency_norm["parent_id"]
        if actual_parent == expected_parent:
            print(f"✅ Emergency NORM correctly kept in {actual_parent}")
        else:
            print(f"❌ Emergency NORM in wrong location: {actual_parent} (expected: {expected_parent})")
    
    # Check inspection norm placement
    inspection_norm = nodes.get("norm_inspection_001")  
    if inspection_norm:
        actual_parent = inspection_norm["parent_id"]
        if actual_parent != "ROOT" and actual_parent is not None:
            print(f"✅ Inspection NORM moved from ROOT to specific section: {actual_parent}")
        else:
            print(f"❌ Inspection NORM still at ROOT level")
    
    # Overall assessment
    issues = []
    if fire_door_norm and fire_door_norm["parent_id"] != "fire_door_002":
        issues.append("Fire door NORM placement")
    if emergency_norm and emergency_norm["parent_id"] != "emergency_003": 
        issues.append("Emergency NORM placement")
    if inspection_norm and inspection_norm["parent_id"] in ["ROOT", None]:
        issues.append("Inspection NORM still at ROOT")
        
    if not issues:
        print(f"\n🎉 SUCCESS: All NORMs are in their optimal locations!")
        return True
    else:
        print(f"\n❌ ISSUES FOUND: {', '.join(issues)}")
        return False

if __name__ == "__main__":
    print("🧠 Testing Smart Deduplication Logic")
    print("=" * 60)
    
    test_data = create_smart_deduplication_test_data()
    print(f"Input: {len(test_data['sections'])} sections, {len(test_data['extractions'])} extractions")
    
    nodes, root_nodes, duplicates_processed = simulate_smart_tree_building(test_data)
    success = analyze_results(nodes, duplicates_processed)
    
    print("\n" + "=" * 60) 
    if success:
        print("🎉 SMART DEDUPLICATION TEST PASSED!")
        print("The improved logic correctly places NORMs in their most appropriate sections.")
    else:
        print("❌ SMART DEDUPLICATION TEST FAILED!") 
        print("The logic needs further refinement.")