#!/usr/bin/env python3
"""Simple test script for the commenting system."""

import json
import requests
import tempfile
import os
import sys
from pathlib import Path

# Add the web directory to the Python path
sys.path.append(str(Path(__file__).parent))

from comments_db import CommentsDB, Comment


def test_database_operations():
    """Test basic database operations."""
    print("Testing database operations...")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Initialize database
        db = CommentsDB(db_path)
        
        # Test creating a comment
        comment = Comment(
            file_path="test/file.py",
            position_data={"line": 42, "column": 10},
            author_name="test_user",
            text_body="This is a test comment"
        )
        
        created_comment = db.create_comment(comment)
        assert created_comment.id is not None
        print(f"✓ Created comment with ID: {created_comment.id}")
        
        # Test retrieving the comment
        retrieved_comment = db.get_comment(created_comment.id)
        assert retrieved_comment is not None
        assert retrieved_comment.text_body == "This is a test comment"
        assert retrieved_comment.position_data == {"line": 42, "column": 10}
        print("✓ Retrieved comment successfully")
        
        # Test creating a reply
        reply = Comment(
            file_path="test/file.py",
            position_data={"line": 42, "column": 10},
            author_name="reply_user",
            text_body="This is a reply",
            parent_comment_id=created_comment.id
        )
        
        created_reply = db.create_comment(reply)
        assert created_reply.id is not None
        print(f"✓ Created reply with ID: {created_reply.id}")
        
        # Test getting comments for file
        comments = db.get_comments_for_file("test/file.py")
        assert len(comments) == 1  # Should be one root comment with one reply
        assert len(comments[0]['replies']) == 1
        print("✓ Retrieved file comments with replies")
        
        # Test updating comment
        success = db.update_comment(created_comment.id, "Updated comment text")
        assert success
        updated_comment = db.get_comment(created_comment.id)
        assert updated_comment.text_body == "Updated comment text"
        print("✓ Updated comment successfully")
        
        # Test deleting comment (should cascade to replies)
        success = db.delete_comment(created_comment.id)
        assert success
        deleted_comment = db.get_comment(created_comment.id)
        assert deleted_comment is None
        print("✓ Deleted comment successfully")
        
        print("All database tests passed!")
        
    finally:
        # Clean up
        os.unlink(db_path)


def test_position_data_flexibility():
    """Test that position data works for different file types."""
    print("\nTesting position data flexibility...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        db = CommentsDB(db_path)
        
        # Test different position data formats
        test_cases = [
            {
                "file_path": "document.txt",
                "position_data": {"line": 25, "page": 2},
                "description": "Text file with line and page"
            },
            {
                "file_path": "data.json",
                "position_data": {"path": "root.users[0].name"},
                "description": "JSON file with path"
            },
            {
                "file_path": "readme.md",
                "position_data": {"position": 1234, "section": "Installation"},
                "description": "Markdown file with position and section"
            },
            {
                "file_path": "image.png",
                "position_data": {"x": 150, "y": 200},
                "description": "Image file with coordinates"
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            comment = Comment(
                file_path=test_case["file_path"],
                position_data=test_case["position_data"],
                author_name=f"user_{i}",
                text_body=f"Comment on {test_case['description']}"
            )
            
            created_comment = db.create_comment(comment)
            retrieved_comment = db.get_comment(created_comment.id)
            
            assert retrieved_comment.position_data == test_case["position_data"]
            print(f"✓ {test_case['description']}: {test_case['position_data']}")
        
        print("All position data tests passed!")
        
    finally:
        os.unlink(db_path)


def main():
    """Run all tests."""
    print("Running Comments System Tests")
    print("=" * 40)
    
    test_database_operations()
    test_position_data_flexibility()
    
    print("\n" + "=" * 40)
    print("All tests passed! 🎉")


if __name__ == "__main__":
    main()