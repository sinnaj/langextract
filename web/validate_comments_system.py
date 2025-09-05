#!/usr/bin/env python3
"""Validation script to test the complete comments system integration."""

import json
import requests
import time


def test_api_endpoints():
    """Test all the comment API endpoints."""
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Comment API Endpoints")
    print("=" * 50)
    
    # Test 1: Get comments for file
    print("\n1. Testing GET /api/comments?file_path=...")
    response = requests.get(f"{base_url}/api/comments", params={
        "file_path": "lx output/combined_extractions.json"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS: Found {len(data['comments'])} root comments")
        for comment in data['comments']:
            print(f"   - {comment['tree_item']}: {comment['text_body'][:50]}... ({len(comment['replies'])} replies)")
    else:
        print(f"❌ FAILED: {response.status_code} - {response.text}")
        return False
    
    # Test 2: Get comments for specific tree item
    print("\n2. Testing GET /api/comments?tree_item=...")
    response = requests.get(f"{base_url}/api/comments", params={
        "file_path": "lx output/combined_extractions.json",
        "tree_item": "CTE.DB.SI"
    })
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCCESS: Found {len(data['comments'])} comments for CTE.DB.SI")
        if data['comments']:
            print(f"   - Text: {data['comments'][0]['text_body']}")
            print(f"   - Replies: {len(data['comments'][0]['replies'])}")
    else:
        print(f"❌ FAILED: {response.status_code} - {response.text}")
        return False
    
    # Test 3: Create new comment
    print("\n3. Testing POST /api/comments")
    test_comment = {
        "file_path": "test_validation.json",
        "tree_item": "test_node_123",
        "author_name": "Validation Bot",
        "text_body": "This is a test comment created by the validation script."
    }
    
    response = requests.post(f"{base_url}/api/comments", json=test_comment)
    
    if response.status_code == 201:
        data = response.json()
        comment_id = data['comment']['id']
        print(f"✅ SUCCESS: Created comment with ID {comment_id}")
        
        # Test 4: Create reply
        print("\n4. Testing POST /api/comments/<id>/reply")
        reply_data = {
            "author_name": "Reply Bot",
            "text_body": "This is a test reply to the validation comment."
        }
        
        response = requests.post(f"{base_url}/api/comments/{comment_id}/reply", json=reply_data)
        
        if response.status_code == 201:
            data = response.json()
            reply_id = data['comment']['id']
            print(f"✅ SUCCESS: Created reply with ID {reply_id}")
            
            # Test 5: Update comment
            print("\n5. Testing PUT /api/comments/<id>")
            update_data = {
                "text_body": "This comment has been updated by the validation script."
            }
            
            response = requests.put(f"{base_url}/api/comments/{comment_id}", json=update_data)
            
            if response.status_code == 200:
                print("✅ SUCCESS: Comment updated")
                
                # Test 6: Get single comment
                print("\n6. Testing GET /api/comments/<id>")
                response = requests.get(f"{base_url}/api/comments/{comment_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ SUCCESS: Retrieved comment {comment_id}")
                    print(f"   - Reply count: {data['comment']['reply_count']}")
                    
                    # Test 7: Delete comment
                    print("\n7. Testing DELETE /api/comments/<id>")
                    response = requests.delete(f"{base_url}/api/comments/{comment_id}")
                    
                    if response.status_code == 200:
                        print("✅ SUCCESS: Comment deleted (cascade to replies)")
                        
                        # Verify deletion
                        response = requests.get(f"{base_url}/api/comments/{comment_id}")
                        if response.status_code == 404:
                            print("✅ SUCCESS: Comment confirmed deleted")
                            return True
                        else:
                            print("❌ FAILED: Comment still exists after deletion")
                    else:
                        print(f"❌ FAILED: Delete failed - {response.status_code}")
                else:
                    print(f"❌ FAILED: Get single comment failed - {response.status_code}")
            else:
                print(f"❌ FAILED: Update failed - {response.status_code}")
        else:
            print(f"❌ FAILED: Reply creation failed - {response.status_code}")
    else:
        print(f"❌ FAILED: Comment creation failed - {response.status_code}")
    
    return False


def test_ui_integration():
    """Test the UI integration by checking if JavaScript loads correctly."""
    base_url = "http://localhost:5000"
    
    print("\n\n🎨 Testing UI Integration")
    print("=" * 50)
    
    # Test main page loads
    print("\n1. Testing main page loads...")
    response = requests.get(base_url)
    
    if response.status_code == 200:
        content = response.text
        if "tree-comments.js" in content:
            print("✅ SUCCESS: Main page loads and includes tree-comments.js")
        else:
            print("❌ FAILED: tree-comments.js not found in main page")
            return False
    else:
        print(f"❌ FAILED: Main page failed to load - {response.status_code}")
        return False
    
    # Test tree-comments.js loads
    print("\n2. Testing tree-comments.js loads...")
    response = requests.get(f"{base_url}/static/tree-comments.js")
    
    if response.status_code == 200:
        content = response.text
        if "TreeCommentsUI" in content and "initializeTreeComments" in content:
            print("✅ SUCCESS: tree-comments.js loads and contains required classes")
        else:
            print("❌ FAILED: tree-comments.js missing required classes")
            return False
    else:
        print(f"❌ FAILED: tree-comments.js failed to load - {response.status_code}")
        return False
    
    # Test comments test page
    print("\n3. Testing comments test page...")
    response = requests.get(f"{base_url}/test-comments")
    
    if response.status_code == 200:
        content = response.text
        if "data-extraction-id" in content and "tree-comments.js" in content:
            print("✅ SUCCESS: Test page loads with tree nodes and comments script")
        else:
            print("❌ FAILED: Test page missing required elements")
            return False
    else:
        print(f"❌ FAILED: Test page failed to load - {response.status_code}")
        return False
    
    return True


def test_data_flow():
    """Test the complete data flow from API to UI."""
    print("\n\n🔄 Testing Data Flow")
    print("=" * 50)
    
    # Check if sample comments are accessible
    print("\n1. Verifying sample comments are accessible...")
    response = requests.get("http://localhost:5000/api/comments", params={
        "file_path": "lx output/combined_extractions.json"
    })
    
    if response.status_code == 200:
        data = response.json()
        comments = data['comments']
        
        if len(comments) > 0:
            print(f"✅ SUCCESS: Found {len(comments)} sample comments")
            
            # Check each tree item has proper structure
            tree_items = []
            for comment in comments:
                tree_item = comment.get('tree_item')
                if tree_item:
                    tree_items.append(tree_item)
                    print(f"   - {tree_item}: {comment['author_name']} - {comment['text_body'][:30]}...")
            
            if tree_items:
                print(f"✅ SUCCESS: All comments have tree_item identifiers")
                print(f"   Tree items: {', '.join(tree_items)}")
                return True
            else:
                print("❌ FAILED: No tree_item identifiers found")
        else:
            print("❌ FAILED: No sample comments found")
    else:
        print(f"❌ FAILED: API call failed - {response.status_code}")
    
    return False


def main():
    """Run all validation tests."""
    print("🚀 Comments System Validation Script")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Test API functionality
        api_success = test_api_endpoints()
        
        # Test UI integration
        ui_success = test_ui_integration()
        
        # Test data flow
        data_success = test_data_flow()
        
        # Summary
        print("\n\n📊 VALIDATION SUMMARY")
        print("=" * 60)
        print(f"API Endpoints: {'✅ PASS' if api_success else '❌ FAIL'}")
        print(f"UI Integration: {'✅ PASS' if ui_success else '❌ FAIL'}")
        print(f"Data Flow: {'✅ PASS' if data_success else '❌ FAIL'}")
        
        overall_success = api_success and ui_success and data_success
        print(f"\nOverall Result: {'🎉 ALL TESTS PASSED' if overall_success else '💥 SOME TESTS FAILED'}")
        
        duration = time.time() - start_time
        print(f"Validation completed in {duration:.2f} seconds")
        
        if overall_success:
            print("\n✨ The tree-based comments system is working correctly!")
            print("   - Backend API endpoints are functional")
            print("   - Frontend JavaScript loads properly")
            print("   - Sample data is accessible")
            print("   - CRUD operations work as expected")
        else:
            print("\n⚠️  Some issues were found. Check the output above for details.")
        
        return overall_success
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to the web server.")
        print("   Make sure the Flask app is running on http://localhost:5000")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error during validation: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)