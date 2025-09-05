#!/usr/bin/env python3
"""Test script for the simplified tree-based commenting system."""

import json
import tempfile
import os
import sys
from pathlib import Path

# Add the web directory to the Python path
sys.path.append(str(Path(__file__).parent))

from comments_db import CommentsDB, Comment


def test_simplified_database_operations():
    """Test basic database operations with tree_item field."""
    print("Testing simplified database operations...")
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        # Initialize database
        db = CommentsDB(db_path)
        
        # Test creating a comment with tree_item
        comment = Comment(
            file_path="test/run123/file.py",
            tree_item="extraction_456",
            author_name="test_user",
            text_body="This is a test comment on tree item"
        )
        
        created_comment = db.create_comment(comment)
        assert created_comment.id is not None
        print(f"✓ Created comment with ID: {created_comment.id}")
        
        # Test retrieving the comment
        retrieved_comment = db.get_comment(created_comment.id)
        assert retrieved_comment is not None
        assert retrieved_comment.text_body == "This is a test comment on tree item"
        assert retrieved_comment.tree_item == "extraction_456"
        print("✓ Retrieved comment successfully")
        
        # Test creating a reply
        reply = Comment(
            file_path="test/run123/file.py",
            tree_item="extraction_456",
            author_name="reply_user",
            text_body="This is a reply",
            parent_comment_id=created_comment.id
        )
        
        created_reply = db.create_comment(reply)
        assert created_reply.id is not None
        print(f"✓ Created reply with ID: {created_reply.id}")
        
        # Test getting comments for tree item
        comments = db.get_comments_for_tree_item("test/run123/file.py", "extraction_456")
        assert len(comments) == 1  # Should be one root comment with one reply
        assert len(comments[0]['replies']) == 1
        print("✓ Retrieved tree item comments with replies")
        
        # Test getting comments for file
        all_comments = db.get_comments_for_file("test/run123/file.py")
        assert len(all_comments) == 1  # Should be one root comment with one reply
        assert len(all_comments[0]['replies']) == 1
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
        
        print("All simplified database tests passed!")
        
    finally:
        # Clean up
        os.unlink(db_path)


def test_multiple_tree_items():
    """Test comments on multiple tree items."""
    print("\nTesting multiple tree items...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        db = CommentsDB(db_path)
        
        # Create comments on different tree items
        tree_items = ["extraction_1", "extraction_2", "extraction_3"]
        
        for i, tree_item in enumerate(tree_items):
            comment = Comment(
                file_path="test/run123/file.py",
                tree_item=tree_item,
                author_name=f"user_{i}",
                text_body=f"Comment on {tree_item}"
            )
            
            created_comment = db.create_comment(comment)
            print(f"✓ Created comment for {tree_item}")
            
            # Create a reply for each
            reply = Comment(
                file_path="test/run123/file.py",
                tree_item=tree_item,
                author_name=f"replier_{i}",
                text_body=f"Reply to {tree_item}",
                parent_comment_id=created_comment.id
            )
            db.create_comment(reply)
            print(f"✓ Created reply for {tree_item}")
        
        # Test getting comments for specific tree item
        comments_1 = db.get_comments_for_tree_item("test/run123/file.py", "extraction_1")
        assert len(comments_1) == 1
        assert comments_1[0]['tree_item'] == "extraction_1"
        assert len(comments_1[0]['replies']) == 1
        print("✓ Retrieved comments for specific tree item")
        
        # Test getting all comments for file
        all_comments = db.get_comments_for_file("test/run123/file.py")
        assert len(all_comments) == 3
        print("✓ Retrieved all comments for file")
        
        print("All multiple tree items tests passed!")
        
    finally:
        os.unlink(db_path)


def main():
    """Run all tests."""
    print("Running Simplified Comments System Tests")
    print("=" * 50)
    
    test_simplified_database_operations()
    test_multiple_tree_items()
    
    print("\n" + "=" * 50)
    print("All simplified tests passed! 🎉")


if __name__ == "__main__":
    main()