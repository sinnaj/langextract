"""SQLAlchemy Core schema and database operations."""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.engine import Connection

from .types import ComparisonOp, ValueType

# Create metadata object
metadata = MetaData()

# Define enums matching PostgreSQL types
obligation_type_enum = Enum(
    "MANDATORY", "RECOMMENDED", "OPTIONAL", name="obligation_type"
)
clause_type_enum = Enum(
    "APPLIES_IF", "SATISFIED_IF", "EXEMPT_IF", name="clause_type"
)
value_type_enum = Enum(
    "BOOLEAN",
    "INTEGER",
    "NUMERIC",
    "STRING",
    "ENUM",
    "ARRAY",
    "JSON",
    name="value_type",
)
logic_op_enum = Enum("AND", "OR", name="logic_op")
cmp_op_enum = Enum(
    "EQ",
    "NEQ",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "IN",
    "NOT_IN",
    "CONTAINS",
    "NOT_CONTAINS",
    name="cmp_op",
)

# Define tables
documents = Table(
    "documents",
    metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("title", Text),
    Column("jurisdiction", Text),
    Column("language", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

sections = Table(
    "sections",
    metadata,
    Column("id", Text, primary_key=True),
    Column("document_id", PGUUID(as_uuid=True), ForeignKey("documents.id")),
    Column("parent_section_id", Text, ForeignKey("sections.id")),
    Column("paragraph_number", Text),
)

norms = Table(
    "norms",
    metadata,
    Column("id", PGUUID(as_uuid=True), primary_key=True),
    Column("document_id", PGUUID(as_uuid=True), ForeignKey("documents.id")),
    Column("section_id", Text, ForeignKey("sections.id")),
    Column("extraction_class", Text, nullable=False),
    Column("extraction_text", Text, nullable=False),
    Column("obligation", obligation_type_enum),
    Column("norm_statement", Text),
    Column("applies_if_text", Text),
    Column("satisfied_if_text", Text),
    Column("exempt_if_text", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

topics = Table(
    "topics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", Text, unique=True, nullable=False),
)

norm_topics = Table(
    "norm_topics",
    metadata,
    Column("norm_id", PGUUID(as_uuid=True), ForeignKey("norms.id", ondelete="CASCADE")),
    Column("topic_id", Integer, ForeignKey("topics.id", ondelete="CASCADE")),
    PrimaryKeyConstraint("norm_id", "topic_id"),
)

questions = Table(
    "questions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("key", Text, unique=True, nullable=False),
    Column("label", Text),
    Column("value_hint", value_type_enum),
    Column("allowed_enum", ARRAY(Text)),
)

norm_clause_groups = Table(
    "norm_clause_groups",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("norm_id", PGUUID(as_uuid=True), ForeignKey("norms.id", ondelete="CASCADE")),
    Column("clause", clause_type_enum, nullable=False),
    Column("parent_id", BigInteger, ForeignKey("norm_clause_groups.id", ondelete="CASCADE")),
    Column("logic", logic_op_enum, nullable=False, server_default="AND"),
)

norm_requirements = Table(
    "norm_requirements",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("norm_id", PGUUID(as_uuid=True), ForeignKey("norms.id", ondelete="CASCADE")),
    Column("clause", clause_type_enum, nullable=False),
    Column("group_id", BigInteger, ForeignKey("norm_clause_groups.id", ondelete="SET NULL")),
    Column("question_id", Integer, ForeignKey("questions.id", ondelete="RESTRICT")),
    Column("operator", cmp_op_enum, nullable=False, server_default="EQ"),
    Column("expected_type", value_type_enum, nullable=False),
    Column("expected_value", JSONB, nullable=False),
)

# Indexes
Index("idx_questions_key_trgm", questions.c.key, postgresql_using="gin", postgresql_ops={"key": "gin_trgm_ops"})
Index("idx_normreq_norm_clause", norm_requirements.c.norm_id, norm_requirements.c.clause)
Index("idx_normreq_question", norm_requirements.c.question_id)
Index("idx_normreq_expected_gin", norm_requirements.c.expected_value, postgresql_using="gin", postgresql_ops={"expected_value": "jsonb_path_ops"})


# Helper functions for database operations

def upsert_question(conn: Connection, key: str, value_hint: Optional[str] = None, allowed_enum: Optional[List[str]] = None) -> int:
    """Upsert a question and return its ID.
    
    Args:
        conn: Database connection
        key: Question key (canonical identifier)
        value_hint: Optional value type hint
        allowed_enum: Optional list of allowed values for enum types
        
    Returns:
        Question ID (primary key)
    """
    from sqlalchemy import select
    
    # Try to get existing question
    result = conn.execute(
        select(questions.c.id).where(questions.c.key == key)
    ).fetchone()
    
    if result:
        return result[0]
    
    # Insert new question
    result = conn.execute(
        questions.insert().values(
            key=key,
            value_hint=value_hint,
            allowed_enum=allowed_enum,
        ).returning(questions.c.id)
    )
    return result.fetchone()[0]


def upsert_topic(conn: Connection, code: str) -> int:
    """Upsert a topic and return its ID.
    
    Args:
        conn: Database connection
        code: Topic code
        
    Returns:
        Topic ID (primary key)
    """
    from sqlalchemy import select
    
    # Try to get existing topic
    result = conn.execute(
        select(topics.c.id).where(topics.c.code == code)
    ).fetchone()
    
    if result:
        return result[0]
    
    # Insert new topic
    result = conn.execute(
        topics.insert().values(code=code).returning(topics.c.id)
    )
    return result.fetchone()[0]


def insert_norm(conn: Connection, norm_data: Dict[str, Any]) -> None:
    """Insert or update a norm record.
    
    Args:
        conn: Database connection
        norm_data: Dictionary containing norm fields
    """
    from sqlalchemy import delete, select
    
    # Handle UUID - it might already be a UUID object
    norm_id_value = norm_data["id"]
    if isinstance(norm_id_value, UUID):
        norm_id = norm_id_value
    else:
        norm_id = UUID(norm_id_value)
    
    # Check if norm exists
    result = conn.execute(
        select(norms.c.id).where(norms.c.id == norm_id)
    ).fetchone()
    
    if result:
        # Delete existing clause groups and requirements for idempotent update
        conn.execute(
            delete(norm_clause_groups).where(norm_clause_groups.c.norm_id == norm_id)
        )
        conn.execute(
            delete(norm_requirements).where(norm_requirements.c.norm_id == norm_id)
        )
        
        # Update norm
        conn.execute(
            norms.update().where(norms.c.id == norm_id).values(**norm_data)
        )
    else:
        # Insert new norm
        conn.execute(norms.insert().values(**norm_data))


def insert_clause_group(conn: Connection, norm_id: UUID, clause: str, logic: str = "AND", parent_id: Optional[int] = None) -> int:
    """Insert a clause group and return its ID.
    
    Args:
        conn: Database connection
        norm_id: Norm UUID
        clause: Clause type ('APPLIES_IF', 'SATISFIED_IF', 'EXEMPT_IF')
        logic: Logic operator ('AND' or 'OR')
        parent_id: Optional parent group ID
        
    Returns:
        Clause group ID (primary key)
    """
    result = conn.execute(
        norm_clause_groups.insert().values(
            norm_id=norm_id,
            clause=clause,
            logic=logic,
            parent_id=parent_id,
        ).returning(norm_clause_groups.c.id)
    )
    return result.fetchone()[0]


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
    global norm_requirements  # Ensure we have access to the table
    
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
        # Handle duplicate key violation gracefully
        if "duplicate key value violates unique constraint" in str(e):
            # Find and return the existing requirement ID
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
                return result[0]  # Return existing ID
            else:
                # If we somehow can't find it, re-raise
                raise e
        else:
            # Re-raise other exceptions
            raise e
