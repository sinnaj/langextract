#!/usr/bin/env python3
"""Test script to create sample comments for testing the UI."""

import sys
from pathlib import Path
import tempfile

# Add the web directory to the Python path
sys.path.append(str(Path(__file__).parent))

from comments_db import CommentsDB, Comment


def create_sample_comments():
    """Create sample comments for testing the UI."""
    
    # Use the same database path as the web app
    db_path = Path(__file__).parent / "comments.db"
    db = CommentsDB(db_path)
    
    # Sample file path that might exist in the output runs
    file_path = "lx output/combined_extractions.json"
    
    # Create some sample comments for different tree items
    sample_comments = [
        {
            "tree_item": "CTE.DB.SI",
            "author_name": "John Doe",
            "text_body": "This is the root node of the extraction tree. Good starting point for analysis."
        },
        {
            "tree_item": "NORM_15_1",
            "author_name": "Jane Smith", 
            "text_body": "Important normative requirement - needs careful review for compliance."
        },
        {
            "tree_item": "SECTION_intro",
            "author_name": "Bob Wilson",
            "text_body": "Introduction section could be clearer about the scope."
        },
        {
            "tree_item": "PARAMETER_temp_limit",
            "author_name": "Alice Johnson",
            "text_body": "Temperature parameter seems unusually high - verify with specifications."
        }
    ]
    
    created_comments = []
    
    for comment_data in sample_comments:
        comment = Comment(
            file_path=file_path,
            tree_item=comment_data["tree_item"],
            author_name=comment_data["author_name"],
            text_body=comment_data["text_body"]
        )
        
        created_comment = db.create_comment(comment)
        created_comments.append(created_comment)
        print(f"✓ Created comment for {comment_data['tree_item']}: {created_comment.id}")
    
    # Create some replies
    if len(created_comments) >= 2:
        reply1 = Comment(
            file_path=file_path,
            tree_item=created_comments[0].tree_item,
            author_name="Mike Chen",
            text_body="I agree, this root node structure looks well-organized.",
            parent_comment_id=created_comments[0].id
        )
        
        reply2 = Comment(
            file_path=file_path,
            tree_item=created_comments[1].tree_item,
            author_name="Sarah Davis",
            text_body="Actually, I think this requirement aligns with ISO standard XYZ-123.",
            parent_comment_id=created_comments[1].id
        )
        
        db.create_comment(reply1)
        db.create_comment(reply2)
        print(f"✓ Created reply to comment {created_comments[0].id}")
        print(f"✓ Created reply to comment {created_comments[1].id}")
    
    print(f"\nSample comments created successfully!")
    print(f"Database location: {db_path}")
    
    # Verify by listing all comments
    all_comments = db.get_comments_for_file(file_path)
    print(f"\nTotal root comments in database: {len(all_comments)}")
    for comment in all_comments:
        print(f"- {comment['tree_item']}: {comment['text_body'][:50]}... ({len(comment['replies'])} replies)")


if __name__ == "__main__":
    create_sample_comments()