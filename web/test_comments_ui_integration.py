#!/usr/bin/env python3
"""
Test script to verify TreeCommentsUI integration is working correctly.
"""

import requests
import json
import time

def test_comments_api():
    """Test that the comments API endpoints are working."""
    base_url = "http://127.0.0.1:5000"
    
    # Test GET /api/comments
    print("Testing GET /api/comments...")
    response = requests.get(f"{base_url}/api/comments", params={"file_path": "test.json"})
    if response.status_code == 200:
        print("✅ GET /api/comments endpoint is working")
        data = response.json()
        print(f"   Response: {data}")
    else:
        print(f"❌ GET /api/comments failed: {response.status_code}")
        return False
    
    # Test POST /api/comments
    print("\nTesting POST /api/comments...")
    comment_data = {
        "file_path": "test.json",
        "tree_item": "extraction_123",
        "author_name": "test_user",
        "text_body": "This is a test comment"
    }
    response = requests.post(f"{base_url}/api/comments", json=comment_data)
    if response.status_code == 201:
        print("✅ POST /api/comments endpoint is working")
        data = response.json()
        print(f"   Created comment: {data}")
        comment_id = data["comment"]["id"]
        
        # Test GET specific file comments
        print(f"\nTesting GET comments for specific file...")
        response = requests.get(f"{base_url}/api/comments", params={
            "file_path": "test.json",
            "tree_item": "extraction_123"
        })
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Found {len(data['comments'])} comments for tree item")
            print(f"   Comments: {data}")
        else:
            print(f"❌ Failed to get comments for tree item: {response.status_code}")
        
        # Clean up - delete the test comment
        print(f"\nCleaning up test comment {comment_id}...")
        response = requests.delete(f"{base_url}/api/comments/{comment_id}")
        if response.status_code == 200:
            print("✅ Successfully deleted test comment")
        else:
            print(f"❌ Failed to delete test comment: {response.status_code}")
            
        return True
    else:
        print(f"❌ POST /api/comments failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def test_file_access():
    """Test that we can access files from existing runs."""
    base_url = "http://127.0.0.1:5000"
    
    print("Testing file access...")
    
    # Try to access a file from an existing run
    run_id = "1757086211"  # From our output_runs directory
    file_path = "lx output/combined_extractions.json"
    
    response = requests.get(f"{base_url}/runs/{run_id}/file", params={"path": file_path})
    
    if response.status_code == 200:
        print(f"✅ Successfully accessed file: {file_path}")
        
        # Try to parse as JSON to see if it's valid extraction data
        try:
            data = response.json()
            if "extractions" in data:
                print(f"   Found {len(data['extractions'])} extractions in file")
                
                # Check if extractions have the expected structure for tree items
                if data["extractions"]:
                    first_extraction = data["extractions"][0]
                    if "attributes" in first_extraction and "id" in first_extraction["attributes"]:
                        print(f"   ✅ Extractions have proper ID structure for tree items")
                        print(f"      Sample extraction ID: {first_extraction['attributes']['id']}")
                        return True
                    else:
                        print(f"   ❌ Extractions missing ID structure: {first_extraction.keys()}")
                        return False
            else:
                print(f"   ❌ File does not contain extractions: {list(data.keys())}")
                return False
        except json.JSONDecodeError:
            print(f"   ❌ File is not valid JSON")
            return False
    else:
        print(f"❌ Failed to access file: {response.status_code}")
        return False

if __name__ == "__main__":
    print("🧪 Testing TreeCommentsUI Integration\n")
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    try:
        # Test API endpoints
        api_works = test_comments_api()
        
        print("\n" + "="*50 + "\n")
        
        # Test file access
        file_works = test_file_access()
        
        print("\n" + "="*50 + "\n")
        
        if api_works and file_works:
            print("🎉 All tests passed! TreeCommentsUI integration should be working.")
            print("\nThe issue may be:")
            print("1. TreeCommentsUI not being initialized properly in the browser")
            print("2. Comment indicators not being added to tree nodes")
            print("3. Tree nodes missing data-extraction-id attributes")
        else:
            print("❌ Some tests failed. Check the issues above.")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server at http://127.0.0.1:5000")
        print("   Make sure the web application is running: python web/app.py")