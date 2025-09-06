"""Database models and utilities for the commenting system."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager


@dataclass
class Comment:
    """Represents a comment in the system."""
    id: Optional[int] = None
    file_path: str = ""
    tree_item: str = ""
    author_name: str = ""
    text_body: str = ""
    created_at: float = 0.0
    parent_comment_id: Optional[int] = None
    run_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert comment to dictionary for API responses."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Comment':
        """Create comment from dictionary."""
        return cls(**data)


class CommentsDB:
    """Database manager for the commenting system."""
    
    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables."""
        with self._get_connection() as conn:
            # Check if we need to migrate from old schema
            cursor = conn.execute("PRAGMA table_info(comments)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'run_id' not in columns or 'tree_item' not in columns:
                # Create new table with updated schema including run_id
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS comments_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        tree_item TEXT NOT NULL,
                        author_name TEXT NOT NULL,
                        text_body TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        parent_comment_id INTEGER NULL,
                        run_id TEXT NULL,
                        FOREIGN KEY (parent_comment_id) REFERENCES comments_new (id) ON DELETE CASCADE
                    )
                """)
                
                # Migrate existing data if old table exists
                if 'position_data' in columns:
                    # Migrating from position_data schema
                    conn.execute("""
                        INSERT INTO comments_new (id, file_path, tree_item, author_name, text_body, created_at, parent_comment_id, run_id)
                        SELECT id, file_path, 'migrated', author_name, text_body, created_at, parent_comment_id, NULL
                        FROM comments
                    """)
                elif 'tree_item' in columns:
                    # Migrating from tree_item schema without run_id
                    conn.execute("""
                        INSERT INTO comments_new (id, file_path, tree_item, author_name, text_body, created_at, parent_comment_id, run_id)
                        SELECT id, file_path, tree_item, author_name, text_body, created_at, parent_comment_id, NULL
                        FROM comments
                    """)
                
                # Drop old table and rename new one
                conn.execute("DROP TABLE IF EXISTS comments")
                conn.execute("ALTER TABLE comments_new RENAME TO comments")
            else:
                # Create table with new schema if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS comments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        tree_item TEXT NOT NULL,
                        author_name TEXT NOT NULL,
                        text_body TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        parent_comment_id INTEGER NULL,
                        run_id TEXT NULL,
                        FOREIGN KEY (parent_comment_id) REFERENCES comments (id) ON DELETE CASCADE
                    )
                """)
            
            # Create indexes for efficient querying
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_file_path 
                ON comments (file_path)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_tree_item 
                ON comments (tree_item)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_parent 
                ON comments (parent_comment_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_created_at 
                ON comments (created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_run_id 
                ON comments (run_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_file_run 
                ON comments (file_path, run_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_comments_tree_run 
                ON comments (tree_item, run_id)
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def create_comment(self, comment: Comment) -> Comment:
        """Create a new comment in the database."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO comments (file_path, tree_item, author_name, text_body, created_at, parent_comment_id, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                comment.file_path,
                comment.tree_item,
                comment.author_name,
                comment.text_body,
                comment.created_at,
                comment.parent_comment_id,
                comment.run_id
            ))
            comment.id = cursor.lastrowid
            conn.commit()
            return comment
    
    def get_comment(self, comment_id: int) -> Optional[Comment]:
        """Get a comment by ID."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM comments WHERE id = ?
            """, (comment_id,)).fetchone()
            
            if row:
                return Comment(
                    id=row['id'],
                    file_path=row['file_path'],
                    tree_item=row['tree_item'],
                    author_name=row['author_name'],
                    text_body=row['text_body'],
                    created_at=row['created_at'],
                    parent_comment_id=row['parent_comment_id'],
                    run_id=row['run_id'] if 'run_id' in row.keys() else None  # Handle cases where run_id might be NULL
                )
            return None
    
    def get_comments_for_file(self, file_path: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all comments for a file, organized with replies."""
        with self._get_connection() as conn:
            # Get all comments for the file, optionally filtered by run_id
            if run_id:
                rows = conn.execute("""
                    SELECT * FROM comments 
                    WHERE file_path = ? AND (run_id = ? OR run_id IS NULL)
                    ORDER BY created_at ASC
                """, (file_path, run_id)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM comments 
                    WHERE file_path = ? 
                    ORDER BY created_at ASC
                """, (file_path,)).fetchall()
            
            comments_dict = {}
            root_comments = []
            
            # First pass: create comment objects
            for row in rows:
                comment = Comment(
                    id=row['id'],
                    file_path=row['file_path'],
                    tree_item=row['tree_item'],
                    author_name=row['author_name'],
                    text_body=row['text_body'],
                    created_at=row['created_at'],
                    parent_comment_id=row['parent_comment_id'],
                    run_id=row['run_id'] if 'run_id' in row.keys() else None
                )
                comment_dict = comment.to_dict()
                comment_dict['replies'] = []
                comments_dict[comment.id] = comment_dict
            
            # Second pass: organize replies
            for comment_id, comment_data in comments_dict.items():
                parent_id = comment_data.get('parent_comment_id')
                if parent_id and parent_id in comments_dict:
                    # This is a reply
                    comments_dict[parent_id]['replies'].append(comment_data)
                else:
                    # This is a root comment
                    root_comments.append(comment_data)
            
            return root_comments
    
    def get_comments_for_tree_item(self, file_path: str, tree_item: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all comments for a specific tree item, organized with replies."""
        with self._get_connection() as conn:
            # Get all comments for the tree item, optionally filtered by run_id
            if run_id:
                rows = conn.execute("""
                    SELECT * FROM comments 
                    WHERE file_path = ? AND tree_item = ? AND (run_id = ? OR run_id IS NULL)
                    ORDER BY created_at ASC
                """, (file_path, tree_item, run_id)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM comments 
                    WHERE file_path = ? AND tree_item = ?
                    ORDER BY created_at ASC
                """, (file_path, tree_item)).fetchall()
            
            comments_dict = {}
            root_comments = []
            
            # First pass: create comment objects
            for row in rows:
                comment = Comment(
                    id=row['id'],
                    file_path=row['file_path'],
                    tree_item=row['tree_item'],
                    author_name=row['author_name'],
                    text_body=row['text_body'],
                    created_at=row['created_at'],
                    parent_comment_id=row['parent_comment_id'],
                    run_id=row['run_id'] if 'run_id' in row.keys() else None
                )
                comment_dict = comment.to_dict()
                comment_dict['replies'] = []
                comments_dict[comment.id] = comment_dict
            
            # Second pass: organize replies
            for comment_id, comment_data in comments_dict.items():
                parent_id = comment_data.get('parent_comment_id')
                if parent_id and parent_id in comments_dict:
                    # This is a reply
                    comments_dict[parent_id]['replies'].append(comment_data)
                else:
                    # This is a root comment
                    root_comments.append(comment_data)
            
            return root_comments
    
    def update_comment(self, comment_id: int, text_body: str) -> bool:
        """Update a comment's text body."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE comments 
                SET text_body = ?
                WHERE id = ?
            """, (text_body, comment_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_comment(self, comment_id: int) -> bool:
        """Delete a comment and its replies."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM comments WHERE id = ?
            """, (comment_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_reply_count(self, comment_id: int) -> int:
        """Get the number of direct replies to a comment."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as count FROM comments 
                WHERE parent_comment_id = ?
            """, (comment_id,)).fetchone()
            return row['count'] if row else 0