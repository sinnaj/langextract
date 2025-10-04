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
    norm_requirements,  # Add this line
    upsert_question,
    upsert_topic,
)

import uuid


def upsert_section(conn: Connection, section_id: str, document_id: Optional[UUID] = None) -> None:
    """Create a section if it doesn't exist.
    
    Args:
        conn: Database connection
        section_id: Section ID
        document_id: Optional document UUID
    """
    from sqlalchemy import select
    from .sql import sections
    
    # Check if section exists
    result = conn.execute(
        select(sections.c.id).where(sections.c.id == section_id)
    ).fetchone()
    
    if not result:
        # Insert new section
        conn.execute(
            sections.insert().values(
                id=section_id,
                document_id=document_id,
                parent_section_id=None,  # We don't have parent info
                paragraph_number=None,   # We don't have paragraph info
            )
        )


def process_norm(conn: Connection, norm_data: Dict[str, Any], document_id: Optional[UUID] = None) -> None:
    """Process a single norm and insert it with its clauses."""
    attributes = norm_data.get("attributes", {})
    
    # Handle UUID parsing more robustly
    norm_id_value = attributes.get("id") or norm_data.get("id")
    
    if norm_id_value is None:
        # Generate a new UUID if none provided
        norm_id = uuid.uuid4()
        print(f"Warning: No ID found, generated new UUID: {norm_id}")
    else:
        try:
            # Try to parse as UUID
            if isinstance(norm_id_value, str) and len(norm_id_value) == 36:
                norm_id = UUID(norm_id_value)
            else:
                # Generate UUID from string/number
                norm_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(norm_id_value))
                print(f"Warning: Invalid UUID format '{norm_id_value}', generated: {norm_id}")
        except (ValueError, TypeError) as e:
            norm_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(norm_id_value))
            print(f"Warning: Could not parse ID '{norm_id_value}' as UUID, generated: {norm_id}")
    
    # Handle section creation
    section_id = attributes.get("parent_section_id")
    if section_id:
        upsert_section(conn, section_id, document_id)
    
    # Handle obligation type mapping
    obligation_raw = attributes.get("obligation_type")
    obligation_mapping = {
        "MANDATORY": "MANDATORY",
        "RECOMMENDED": "RECOMMENDED", 
        "OPTIONAL": "OPTIONAL",
        "PROHIBITION": "MANDATORY",  # Map PROHIBITION to MANDATORY
        # Add other mappings as needed
    }
    obligation = obligation_mapping.get(obligation_raw, "MANDATORY")  # Default to MANDATORY
    
    if obligation_raw and obligation_raw not in obligation_mapping:
        print(f"Warning: Unknown obligation type '{obligation_raw}', using 'MANDATORY'")
    
    norm_record = {
        "id": norm_id,
        "document_id": document_id,
        "section_id": section_id,
        "extraction_class": norm_data.get("extraction_class", "NORM"),
        "extraction_text": norm_data.get("extraction_text", ""),
        "obligation": obligation,  # Use mapped value
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
    """Process a clause expression and store it in DNF."""
    # Convert to DNF
    try:
        dnf = expr_to_dnf(expression)
    except Exception as e:
        print(f"Warning: Failed to parse {clause_type} expression: {expression}", file=sys.stderr)
        print(f"  Error: {e}", file=sys.stderr)
        return
    
    # Optimize DNF (remove contradictions, duplicates)
    dnf = optimize_dnf(dnf)
    
    # Track inserted requirements to avoid duplicates
    inserted_requirements = set()
    
    # Store each disjunct as a clause group
    for conjunct in dnf:
        # Create clause group (top-level disjunct with AND logic)
        group_id = insert_clause_group(conn, norm_id, clause_type, logic="AND", parent_id=None)
        
        # Insert each atomic predicate as a requirement
        for atomic in conjunct:
            # Create a key for deduplication
            req_key = (atomic.key, atomic.op.value, str(atomic.value))
            
            if req_key in inserted_requirements:
                print(f"Warning: Skipping duplicate requirement: {atomic.key} {atomic.op.value} {atomic.value}")
                continue
            
            # Upsert question
            question_id = upsert_question(
                conn,
                key=atomic.key,
                value_hint=atomic.value_type.value,
            )
            
            # Insert requirement with error handling
            try:
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
                inserted_requirements.add(req_key)
            except Exception as e:
                if "duplicate key value violates unique constraint" in str(e):
                    print(f"Warning: Duplicate requirement skipped: {atomic.key} {atomic.op.value} {atomic.value}")
                    continue
                else:
                    raise e


def insert_requirement(
    conn: Connection,
    norm_id: UUID,
    clause: str,
    group_id: Optional[int],
    question_id: int,
    operator: str,
    expected_type: str,
    expected_value: Any,
) -> int:
    """Insert a norm requirement and return its ID."""
    # Convert value to JSON-serializable format
    if not isinstance(expected_value, (str, int, float, bool, list, dict, type(None))):
        expected_value = str(expected_value)
    
    try:
        result = conn.execute(
            norm_requirements.insert().values(
                norm_id=norm_id,
                clause=clause,
                group_id=group_id,
                question_id=question_id,
                operator=operator,
                expected_type=expected_type,
                expected_value=json.dumps(expected_value),
            ).returning(norm_requirements.c.id)
        )
        return result.fetchone()[0]
    except Exception as e:
        # Handle duplicate key violation
        if "duplicate key value violates unique constraint" in str(e):
            # Find existing requirement and return its ID
            from sqlalchemy import select
            result = conn.execute(
                select(norm_requirements.c.id).where(
                    (norm_requirements.c.norm_id == norm_id) &
                    (norm_requirements.c.clause == clause) &
                    (norm_requirements.c.question_id == question_id) &
                    (norm_requirements.c.operator == operator) &
                    (norm_requirements.c.expected_value == json.dumps(expected_value))
                )
            ).fetchone()
            
            if result:
                print(f"Warning: Duplicate requirement detected, using existing ID: {result[0]}")
                return result[0]
            else:
                # If we can't find the existing record, re-raise the error
                raise e
        else:
            # Re-raise other errors
            raise e


def ingest_norms(dsn: str, json_path: str, document_title: Optional[str] = None, language: Optional[str] = None, jurisdiction: Optional[str] = None) -> None:
    """Main ingestion function."""
    # Create engine
    engine = create_engine(dsn)
    
    # Read JSON file
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, dict):
        if 'extractions' in data:
            # Standard LangExtract format
            all_extractions = data['extractions']
            norms_data = [e for e in all_extractions if e.get('extraction_class') == 'NORM']
            print(f"Found {len(norms_data)} NORM extractions out of {len(all_extractions)} total extractions")
        else:
            # Single norm object
            norms_data = [data]
    elif isinstance(data, list):
        # List format - could be all norms or mixed extractions
        norms_data = [e for e in data if e.get('extraction_class') == 'NORM']
        print(f"Found {len(norms_data)} NORM extractions out of {len(data)} total items")
    else:
        raise ValueError(f"Unsupported JSON structure: {type(data)}")
    
    if not norms_data:
        print("No NORM extractions found in the file!")
        return
    
    # Create document once (outside of norm processing loop)
    document_id = None
    if document_title or language or jurisdiction:
        with engine.begin() as conn:
            result = conn.execute(
                documents.insert().values(
                    title=document_title,
                    language=language,
                    jurisdiction=jurisdiction,
                ).returning(documents.c.id)
            )
            document_id = result.fetchone()[0]
            print(f"Created document: {document_id}")
    
    # Process each norm in its own transaction
    successful_count = 0
    failed_count = 0
    
    for idx, norm_data in enumerate(norms_data):
        try:
            # Each norm gets its own transaction
            with engine.begin() as conn:
                process_norm(conn, norm_data, document_id)
                successful_count += 1
                print(f"Processed norm {idx + 1}/{len(norms_data)}")
        except Exception as e:
            failed_count += 1
            print(f"Error processing norm {idx + 1}: {e}", file=sys.stderr)
            print(f"Skipping norm {idx + 1} and continuing...", file=sys.stderr)
            # Continue processing other norms instead of failing completely
            continue
    
    print(f"Ingestion completed: {successful_count} successful, {failed_count} failed out of {len(norms_data)} total norms")
    
    if failed_count > 0:
        print(f"Warning: {failed_count} norms failed to process", file=sys.stderr)


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
