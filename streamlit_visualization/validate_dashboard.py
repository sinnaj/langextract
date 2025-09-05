#!/usr/bin/env python3
"""
Validation script for the LangExtract Streamlit Dashboard.
This script validates that the dashboard can load and process data correctly.
"""

import json
import sys
from pathlib import Path
import pandas as pd

def find_latest_combined_extractions():
    """Find the latest combined_extractions.json file."""
    base_path = Path(__file__).parent.parent
    output_runs_path = base_path / "output_runs"
    
    if not output_runs_path.exists():
        return None
    
    latest_file = None
    latest_timestamp = 0
    
    for run_dir in output_runs_path.iterdir():
        if run_dir.is_dir():
            combined_file = run_dir / "lx_output" / "combined_extractions.json"
            if combined_file.exists():
                try:
                    timestamp = int(run_dir.name)
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = combined_file
                except ValueError:
                    continue
    
    return latest_file

def validate_data_structure(data):
    """Validate the structure of the combined extractions data."""
    required_keys = ['document_metadata', 'evaluation_statistics', 'sections', 'extractions']
    
    print("🔍 Validating data structure...")
    
    for key in required_keys:
        if key not in data:
            print(f"❌ Missing required key: {key}")
            return False
        print(f"✅ Found key: {key}")
    
    # Validate extractions
    extractions = data.get('extractions', [])
    print(f"📊 Found {len(extractions)} extractions")
    
    # Count extraction types
    extraction_types = {}
    tag_count = 0
    
    for extraction in extractions:
        ext_type = extraction.get('extraction_class', 'Unknown')
        extraction_types[ext_type] = extraction_types.get(ext_type, 0) + 1
        
        if ext_type == 'Tag':
            tag_count += 1
    
    print("📈 Extraction types:")
    for ext_type, count in extraction_types.items():
        print(f"   {ext_type}: {count}")
    
    # Validate sections
    sections = data.get('sections', [])
    print(f"📁 Found {len(sections)} sections")
    
    # Validate metadata
    metadata = data.get('document_metadata', {})
    print(f"📄 Document metadata: {metadata.get('total_extractions', 0)} total extractions")
    
    return True

def main():
    print("🔍 LangExtract Dashboard Validation")
    print("===================================")
    
    # Find latest data file
    latest_file = find_latest_combined_extractions()
    
    if not latest_file:
        print("❌ No combined_extractions.json files found in output_runs")
        print("   The dashboard will still work with uploaded files")
        return 1
    
    print(f"✅ Found latest file: {latest_file}")
    
    # Load and validate data
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("✅ Successfully loaded JSON data")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return 1
    
    # Validate structure
    if not validate_data_structure(data):
        print("❌ Data validation failed")
        return 1
    
    print("\n🎉 Validation successful!")
    print("   The dashboard should work correctly with this data")
    print(f"   Run: streamlit run app.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())