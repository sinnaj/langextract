#!/usr/bin/env python3
"""
Validation script for the LangExtract Streamlit Dashboard.
This script validates that the dashboard can load and process data correctly.
"""

import json
import sys
from pathlib import Path
import pandas as pd

def find_latest_enhanced_extractions():
    """Find the latest enhanced_extraction_results.json file."""
    base_path = Path(__file__).parent.parent
    output_runs_path = base_path / "output_runs"
    
    if not output_runs_path.exists():
        return None
    
    latest_file = None
    latest_timestamp = 0
    
    for run_dir in output_runs_path.iterdir():
        if run_dir.is_dir():
            # Try enhanced output first
            enhanced_file = run_dir / "enhanced_output" / "enhanced_extraction_results.json"
            if enhanced_file.exists():
                try:
                    timestamp = int(run_dir.name)
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = enhanced_file
                except ValueError:
                    continue
    
    return latest_file

def validate_data_structure(data):
    """Validate the structure of the enhanced extractions data."""
    required_keys = ['pipeline_info', 'sections', 'extractions', 'tags', 'parameters', 'processing_stats']
    
    print("🔍 Validating enhanced data structure...")
    
    for key in required_keys:
        if key not in data:
            print(f"❌ Missing required key: {key}")
            return False
        print(f"✅ Found key: {key}")
    
    # Validate pipeline info
    pipeline_info = data.get('pipeline_info', {})
    print(f"📊 Pipeline version: {pipeline_info.get('version', 'Unknown')}")
    print(f"📊 Pipeline method: {pipeline_info.get('method', 'Unknown')}")
    
    # Validate sections
    sections = data.get('sections', [])
    print(f"📁 Found {len(sections)} sections")
    
    # Validate extractions
    extractions = data.get('extractions', [])
    print(f"📋 Found {len(extractions)} extractions")
    
    # Count extraction types
    extraction_types = {}
    for extraction in extractions:
        ext_type = extraction.get('extraction_class', 'Unknown')
        extraction_types[ext_type] = extraction_types.get(ext_type, 0) + 1
    
    # Validate tags
    tags = data.get('tags', [])
    print(f"🏷️ Found {len(tags)} tags")
    
    # Validate parameters
    parameters = data.get('parameters', [])
    print(f"⚙️ Found {len(parameters)} parameters")
    
    print("📈 Extraction types:")
    for ext_type, count in extraction_types.items():
        print(f"   {ext_type}: {count}")
    
    # Validate processing stats
    processing_stats = data.get('processing_stats', {})
    print(f"📄 Processing stats: {processing_stats}")
    
    return True

def main():
    print("🔍 LangExtract Enhanced Dashboard Validation")
    print("=============================================")
    
    # Find latest data file
    latest_file = find_latest_enhanced_extractions()
    
    if not latest_file:
        print("❌ No enhanced_extraction_results.json files found in output_runs")
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
    print("   The enhanced dashboard should work correctly with this data")
    print(f"   Run: streamlit run app.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())