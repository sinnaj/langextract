#!/usr/bin/env python3
"""Demonstration script for the commenting system."""

import json
from pathlib import Path
import sys

# Add the web directory to the Python path
sys.path.append(str(Path(__file__).parent))

from comments_db import Comment
from comments_db import CommentsDB


def demo_commenting_system():
  """Demonstrate the commenting system with various file types and scenarios."""
  print("🎯 LangExtract Comments System Demo")
  print("=" * 50)

  # Initialize database
  db_path = Path(__file__).parent / "demo_comments.db"
  if db_path.exists():
    db_path.unlink()  # Clean start

  db = CommentsDB(db_path)
  print(f"✓ Initialized database at: {db_path}")

  # Demo 1: Text file commenting
  print("\n📄 Demo 1: Text File Commenting")
  print("-" * 30)

  text_comment = Comment(
      file_path="src/main.py",
      position_data={"line": 45, "column": 12},
      author_name="alice",
      text_body="This function needs better error handling",
  )

  created_comment = db.create_comment(text_comment)
  print(f"Created comment on line 45: '{text_comment.text_body}'")

  # Add reply
  reply = Comment(
      file_path="src/main.py",
      position_data={"line": 45, "column": 12},
      author_name="bob",
      text_body="Agreed! I'll add try-catch blocks.",
      parent_comment_id=created_comment.id,
  )

  db.create_comment(reply)
  print(f"Added reply from bob: '{reply.text_body}'")

  # Demo 2: JSON file commenting
  print("\n🗂️  Demo 2: JSON File Commenting")
  print("-" * 30)

  json_comment = Comment(
      file_path="config/settings.json",
      position_data={"path": "database.connection.timeout"},
      author_name="charlie",
      text_body="This timeout seems too low for production",
  )

  db.create_comment(json_comment)
  print(f"Created comment on JSON path: '{json_comment.position_data['path']}'")

  # Demo 3: Markdown file commenting
  print("\n📝 Demo 3: Markdown File Commenting")
  print("-" * 30)

  md_comment = Comment(
      file_path="docs/README.md",
      position_data={"position": 1250, "section": "Installation"},
      author_name="diana",
      text_body="We should add a Windows-specific installation section",
  )

  db.create_comment(md_comment)
  print(f"Created comment in section '{md_comment.position_data['section']}'")

  # Demo 4: Image file commenting
  print("\n🖼️  Demo 4: Image File Commenting")
  print("-" * 30)

  image_comment = Comment(
      file_path="assets/diagram.png",
      position_data={"x": 250, "y": 180},
      author_name="eve",
      text_body="This arrow is pointing to the wrong component",
  )

  db.create_comment(image_comment)
  print(
      f"Created comment at coordinates ({image_comment.position_data['x']},"
      f" {image_comment.position_data['y']})"
  )

  # Demo 5: Show all comments for each file
  print("\n📊 Demo 5: Retrieving Comments")
  print("-" * 30)

  files_with_comments = [
      "src/main.py",
      "config/settings.json",
      "docs/README.md",
      "assets/diagram.png",
  ]

  for file_path in files_with_comments:
    comments = db.get_comments_for_file(file_path)
    print(
        f"\n{file_path} ({len(comments)} comment{'s' if len(comments) != 1 else ''})"
    )

    for comment in comments:
      print(f"  💬 {comment['author_name']}: {comment['text_body']}")
      if comment["replies"]:
        for reply in comment["replies"]:
          print(f"     ↳ {reply['author_name']}: {reply['text_body']}")

  # Demo 6: Update and delete operations
  print("\n✏️  Demo 6: Update and Delete Operations")
  print("-" * 30)

  # Update a comment
  success = db.update_comment(
      created_comment.id, "This function REALLY needs better error handling!"
  )
  if success:
    print("✓ Updated comment text")

  # Get updated comment
  updated_comment = db.get_comment(created_comment.id)
  print(f"Updated text: '{updated_comment.text_body}'")

  # Show final stats
  print("\n📈 Final Statistics")
  print("-" * 30)

  total_comments = 0
  for file_path in files_with_comments:
    comments = db.get_comments_for_file(file_path)
    file_comment_count = sum(1 + len(c["replies"]) for c in comments)
    total_comments += file_comment_count

  print(f"Total files with comments: {len(files_with_comments)}")
  print(f"Total comments and replies: {total_comments}")

  print(f"\n🎉 Demo complete! Database saved at: {db_path}")
  print(
      "You can inspect the database using any SQLite browser or the Flask API."
  )


if __name__ == "__main__":
  demo_commenting_system()
