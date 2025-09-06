#!/usr/bin/env python3
"""Test the Flask API endpoints for the commenting system."""

import json
import requests
import threading
import time
import tempfile
import os
from pathlib import Path
import sys

# Add the web directory to the Python path
sys.path.append(str(Path(__file__).parent))

from app import app


def test_api_endpoints():
    """Test the comment API endpoints."""
    print("Testing Flask API endpoints...")
    
    # Configure app for testing
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        
        # Test creating a comment
        comment_data = {
            "file_path": "test/example.py",
            "tree_item": "example.py:line_10",
            "author_name": "api_tester",
            "text_body": "This is an API test comment"
        }
        
        response = client.post('/api/comments', 
                             data=json.dumps(comment_data), 
                             content_type='application/json')
        assert response.status_code == 201
        created_comment = response.get_json()['comment']
        comment_id = created_comment['id']
        print(f"✓ Created comment via API with ID: {comment_id}")
        
        # Test getting comments for a file
        response = client.get(f'/api/comments?file_path=test/example.py')
        assert response.status_code == 200
        comments_data = response.get_json()
        assert len(comments_data['comments']) == 1
        print("✓ Retrieved comments for file via API")
        
        # Test getting a specific comment
        response = client.get(f'/api/comments/{comment_id}')
        assert response.status_code == 200
        comment_details = response.get_json()['comment']
        assert comment_details['text_body'] == "This is an API test comment"
        print("✓ Retrieved specific comment via API")
        
        # Test creating a reply
        reply_data = {
            "author_name": "replier",
            "text_body": "This is a reply via API"
        }
        
        response = client.post(f'/api/comments/{comment_id}/reply',
                             data=json.dumps(reply_data),
                             content_type='application/json')
        assert response.status_code == 201
        reply_comment = response.get_json()['comment']
        reply_id = reply_comment['id']
        print(f"✓ Created reply via API with ID: {reply_id}")
        
        # Test updating a comment
        update_data = {
            "text_body": "Updated comment text via API"
        }
        
        response = client.put(f'/api/comments/{comment_id}',
                            data=json.dumps(update_data),
                            content_type='application/json')
        assert response.status_code == 200
        updated_comment = response.get_json()['comment']
        assert updated_comment['text_body'] == "Updated comment text via API"
        print("✓ Updated comment via API")
        
        # Test getting comments with reply
        response = client.get(f'/api/comments?file_path=test/example.py')
        assert response.status_code == 200
        comments_data = response.get_json()
        assert len(comments_data['comments']) == 1
        assert len(comments_data['comments'][0]['replies']) == 1
        print("✓ Retrieved comments with replies via API")
        
        # Test error cases
        
        # Test creating comment without required fields
        response = client.post('/api/comments',
                             data=json.dumps({}),
                             content_type='application/json')
        assert response.status_code == 400
        print("✓ Handled missing required fields error")
        
        # Test getting non-existent comment
        response = client.get('/api/comments/99999')
        assert response.status_code == 404
        print("✓ Handled non-existent comment error")
        
        # Test creating reply to non-existent comment
        response = client.post('/api/comments/99999/reply',
                             data=json.dumps(reply_data),
                             content_type='application/json')
        assert response.status_code == 404
        print("✓ Handled reply to non-existent comment error")
        
        # Test preventing nested replies (depth > 1)
        response = client.post(f'/api/comments/{reply_id}/reply',
                             data=json.dumps(reply_data),
                             content_type='application/json')
        assert response.status_code == 400
        print("✓ Prevented nested replies (depth > 1)")
        
        # Test deleting a comment
        response = client.delete(f'/api/comments/{comment_id}')
        assert response.status_code == 200
        print("✓ Deleted comment via API")
        
        # Verify comment is gone
        response = client.get(f'/api/comments/{comment_id}')
        assert response.status_code == 404
        print("✓ Verified comment deletion")
        
        print("All API tests passed!")


def main():
    """Run all API tests."""
    print("Running Comments API Tests")
    print("=" * 40)
    
    test_api_endpoints()
    
    print("\n" + "=" * 40)
    print("All API tests passed! 🎉")


if __name__ == "__main__":
    main()