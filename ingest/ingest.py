"""Norm ingestion CLI script.

This script ingests norms from a JSON file and stores them in PostgreSQL
with DNF conversion for applies_if expressions.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Connection

from .dnf import optimize_dnf
from .parser import expr_to_dnf
from .sql import (
    documents,
    insert_clause_group,
    insert_norm,
    insert_requirement,
    norm_topics,
    upsert_question,
    upsert_topic,
)


def process_norm(conn: Connection, norm_data: Dict[str, Any], document_id: Optional[UUID] = None) -> None:
    """Process a single norm and insert it with its clauses.
    
    Args:
        conn: Database connection
        norm_data: Norm data from JSON
        document_id: Optional document UUID to associate with the norm
    """
    attributes = norm_data.get("attributes", {})
    
    # Prepare norm record
    norm_id = UUID(attributes.get("id", norm_data.get("id")))
    
    norm_record = {
        "id": norm_id,
        "document_id": document_id,
        "section_id": attributes.get("parent_section_id"),
        "extraction_class": norm_data.get("extraction_class", "NORM"),
        "extraction_text": norm_data.get("extraction_text", ""),
        "obligation": attributes.get("obligation_type"),
        "norm_statement": attributes.get("norm_statement"),
        "applies_if_text": attributes.get("applies_if"),
        "satisfied_if_text": attributes.get("satisfied_if"),
        "exempt_if_text": attributes.get("exempt_if"),
    }
    
    # Insert/update norm
    insert_norm(conn, norm_record)
    
    # Process topics
    topic_codes = attributes.get("topics", [])
    for topic_code in topic_codes:
        topic_id = upsert_topic(conn, topic_code)
        # Insert norm-topic relationship (ignore duplicates)
        try:
            conn.execute(
                norm_topics.insert().values(
                    norm_id=norm_id,
                    topic_id=topic_id,
                )
            )
        except Exception:
            # Already exists - skip
            pass
    
    # Process applies_if clause
    applies_if = attributes.get("applies_if")
    if applies_if and applies_if.strip() and applies_if.strip().upper() not in ["TRUE", "FALSE"]:
        process_clause(conn, norm_id, "APPLIES_IF", applies_if)
    
    # Process satisfied_if clause (optional)
    satisfied_if = attributes.get("satisfied_if")
    if satisfied_if and satisfied_if.strip() and satisfied_if.strip().upper() not in ["TRUE", "FALSE"]:
        process_clause(conn, norm_id, "SATISFIED_IF", satisfied_if)
    
    # Process exempt_if clause (optional)
    exempt_if = attributes.get("exempt_if")
    if exempt_if and exempt_if.strip() and exempt_if.strip().upper() not in ["TRUE", "FALSE"]:
        process_clause(conn, norm_id, "EXEMPT_IF", exempt_if)


def process_clause(conn: Connection, norm_id: UUID, clause_type: str, expression: str) -> None:
    """Process a clause expression and store it in DNF.
    
    Args:
        conn: Database connection
        norm_id: Norm UUID
        clause_type: Type of clause ('APPLIES_IF', 'SATISFIED_IF', 'EXEMPT_IF')
        expression: Boolean expression string
    """
    # Convert to DNF
    try:
        dnf = expr_to_dnf(expression)
    except Exception as e:
        print(f"Warning: Failed to parse {clause_type} expression: {expression}", file=sys.stderr)
        print(f"  Error: {e}", file=sys.stderr)
        return
    
    # Optimize DNF (remove contradictions, duplicates)
    dnf = optimize_dnf(dnf)
    
    # Store each disjunct as a clause group
    for conjunct in dnf:
        # Create clause group (top-level disjunct with AND logic)
        group_id = insert_clause_group(conn, norm_id, clause_type, logic="AND", parent_id=None)
        
        # Insert each atomic predicate as a requirement
        for atomic in conjunct:
            # Upsert question
            question_id = upsert_question(
                conn,
                key=atomic.key,
                value_hint=atomic.value_type.value,
            )
            
            # Insert requirement
            insert_requirement(
                conn,
                norm_id=norm_id,
                clause=clause_type,
                group_id=group_id,
                question_id=question_id,
                operator=atomic.op.value,
                expected_type=atomic.value_type.value,
                expected_value=atomic.value,
            )


def ingest_norms(dsn: str, json_path: str, document_title: Optional[str] = None, language: Optional[str] = None, jurisdiction: Optional[str] = None) -> None:
    """Main ingestion function.
    
    Args:
        dsn: PostgreSQL connection string
        json_path: Path to JSON file with norms
        document_title: Optional document title
        language: Optional language code
        jurisdiction: Optional jurisdiction code
    """
    # Create engine
    engine = create_engine(dsn)
    
    # Read JSON file
    with open(json_path, "r", encoding="utf-8") as f:
        norms_data = json.load(f)
    
    # Ensure it's a list
    if isinstance(norms_data, dict):
        norms_data = [norms_data]
    
    # Start transaction
    with engine.begin() as conn:
        document_id = None
        
        # Create document if metadata provided
        if document_title or language or jurisdiction:
            result = conn.execute(
                documents.insert().values(
                    title=document_title,
                    language=language,
                    jurisdiction=jurisdiction,
                ).returning(documents.c.id)
            )
            document_id = result.fetchone()[0]
            print(f"Created document: {document_id}")
        
        # Process each norm
        for idx, norm_data in enumerate(norms_data):
            try:
                process_norm(conn, norm_data, document_id)
                print(f"Processed norm {idx + 1}/{len(norms_data)}")
            except Exception as e:
                print(f"Error processing norm {idx + 1}: {e}", file=sys.stderr)
                raise
        
        print(f"Successfully ingested {len(norms_data)} norms")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest norms with DNF conversion into PostgreSQL"
    )
    parser.add_argument(
        "--dsn",
        required=True,
        help="PostgreSQL connection string (e.g., postgresql://user:pass@localhost:5432/mydb)",
    )
    parser.add_argument(
        "--json",
        required=True,
        help="Path to JSON file with norms",
    )
    parser.add_argument(
        "--document-title",
        help="Optional document title",
    )
    parser.add_argument(
        "--language",
        help="Optional language code (e.g., 'es')",
    )
    parser.add_argument(
        "--jurisdiction",
        help="Optional jurisdiction code (e.g., 'ES')",
    )
    
    args = parser.parse_args()
    
    try:
        ingest_norms(
            dsn=args.dsn,
            json_path=args.json,
            document_title=args.document_title,
            language=args.language,
            jurisdiction=args.jurisdiction,
        )
    except Exception as e:
        print(f"Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
