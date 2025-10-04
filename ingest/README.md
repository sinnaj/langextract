# Norm Ingestion Pipeline with DNF Conversion

This module provides a production-ready ingestion pipeline for storing extracted Norms with boolean logic (applies_if, satisfied_if, exempt_if) in PostgreSQL. It converts complex boolean expressions to Disjunctive Normal Form (DNF) for efficient querying and evaluation.

## Features

- **DNF Conversion**: Converts complex boolean expressions with AND, OR, NOT, and parentheses to Disjunctive Normal Form (OR-of-ANDs)
- **PostgreSQL Storage**: Stores norms, questions, clause groups, and requirements in a normalized schema
- **Idempotent Ingestion**: Re-running ingestion updates existing norms without duplicates
- **Expression Optimization**: Removes contradictions and deduplicates atomic predicates
- **Type Inference**: Automatically infers value types (BOOLEAN, INTEGER, STRING, ARRAY, etc.)
- **Support for Operators**: ==, !=, >, >=, <, <=, IN, NOT IN

## Installation

Install required dependencies:

```bash
pip install sqlalchemy psycopg lark
```

## Database Setup

1. Create a PostgreSQL database (14+):

```bash
createdb mydb
```

2. Run the schema creation script:

```bash
psql -d mydb -f db/schema.sql
```

This creates the necessary tables, indexes, and enums.

## Usage

### Command Line Ingestion

Basic usage:

```bash
python -m ingest.ingest \
  --dsn postgresql://user:pass@localhost:5432/mydb \
  --json ./sample_norms.json
```

With document metadata:

```bash
python -m ingest.ingest \
  --dsn postgresql://user:pass@localhost:5432/mydb \
  --json ./sample_norms.json \
  --document-title "Spain DB SI" \
  --language "es" \
  --jurisdiction "ES"
```

### Programmatic Usage

```python
from ingest import ingest_norms

ingest_norms(
    dsn="postgresql://user:pass@localhost:5432/mydb",
    json_path="./sample_norms.json",
    document_title="Building Code",
    language="en",
    jurisdiction="US"
)
```

### DNF Conversion API

Convert expressions to DNF programmatically:

```python
from ingest import expr_to_dnf, dnf_to_string

# Parse and convert to DNF
dnf = expr_to_dnf("A == TRUE AND (B == 1 OR C == 2)")

# Convert back to string for display
print(dnf_to_string(dnf))
# Output: (A == True && B == 1) || (A == True && C == 2)
```

## Input JSON Format

The ingestion script expects a JSON array of norm objects:

```json
[
  {
    "extraction_class": "NORM",
    "extraction_text": "Original norm text...",
    "attributes": {
      "id": "uuid-here",
      "parent_section_id": "section-id",
      "paragraph_number": "5.2",
      "obligation_type": "MANDATORY",
      "norm_statement": "Human-readable norm statement",
      "applies_if": "BUILDING.TYPE == 'RESIDENTIAL' AND AREA.SIZE > 100",
      "satisfied_if": "COMPLIANCE.VERIFIED == TRUE",
      "exempt_if": "FALSE",
      "topics": ["SAFETY.FIRE", "BUILDING.USE"]
    }
  }
]
```

### Boolean Expression Syntax

Supported operators:
- **Comparison**: `==`, `!=`, `>`, `>=`, `<`, `<=`
- **Logical**: `AND`, `OR`, `NOT`
- **Membership**: `IN ['value1', 'value2']`, `NOT IN [...]`
- **Grouping**: Parentheses `()`

Value types:
- **Boolean**: `TRUE`, `FALSE`
- **Numbers**: `42`, `3.14`
- **Strings**: `'RESIDENTIAL'` (single quotes)
- **Arrays**: `['value1', 'value2']`

Identifiers:
- Use uppercase dot notation: `BUILDING.TYPE`, `AREA.SIZE`
- Automatically canonicalized to uppercase

## Database Schema Overview

### Core Tables

- **norms**: Main norm records with text and metadata
- **questions**: Feature questions (canonicalized identifiers)
- **topics**: Topic codes for categorization
- **norm_topics**: Many-to-many relationship between norms and topics

### DNF Storage

- **norm_clause_groups**: Each row represents one disjunct (AND-group) in the DNF
  - `clause`: Type of clause (APPLIES_IF, SATISFIED_IF, EXEMPT_IF)
  - `logic`: Always 'AND' for DNF storage
  - `parent_id`: NULL for top-level disjuncts

- **norm_requirements**: Each row represents one atomic predicate
  - `group_id`: Links to the clause group (disjunct)
  - `question_id`: Links to the feature question
  - `operator`: Comparison operator (EQ, NEQ, GT, etc.)
  - `expected_value`: JSONB value for comparison

### DNF Example

Expression: `(A == TRUE AND (B == 1 OR C == 2)) AND D == 3`

Converts to DNF: `(A == TRUE AND B == 1 AND D == 3) OR (A == TRUE AND C == 2 AND D == 3)`

Storage:
- **Clause Group 1** (logic='AND'):
  - Requirement: A == TRUE
  - Requirement: B == 1
  - Requirement: D == 3
- **Clause Group 2** (logic='AND'):
  - Requirement: A == TRUE
  - Requirement: C == 2
  - Requirement: D == 3

## Testing

Run the test suite:

```bash
# Test DNF conversion and optimization
pytest tests/test_dnf.py -v

# Test parser and expression conversion
pytest tests/test_parser.py -v

# Run all tests
pytest tests/test_dnf.py tests/test_parser.py -v
```

### Test Coverage

- **test_dnf.py**: Tests for DNF optimization, contradiction detection, deduplication
- **test_parser.py**: Tests for expression parsing, operator mapping, DNF conversion, De Morgan's laws

## Verification

After ingestion, verify the data:

```sql
-- Check norms were created
SELECT id, extraction_class, norm_statement 
FROM norms 
LIMIT 5;

-- Check clause groups for a specific norm
SELECT ncg.id, ncg.clause, ncg.logic
FROM norm_clause_groups ncg
WHERE ncg.norm_id = 'your-norm-uuid-here';

-- Check requirements with questions
SELECT 
  q.key,
  nr.operator,
  nr.expected_value
FROM norm_requirements nr
JOIN questions q ON q.id = nr.question_id
WHERE nr.norm_id = 'your-norm-uuid-here'
  AND nr.clause = 'APPLIES_IF';

-- Verify DNF structure for complex conditions
SELECT 
  ncg.id as group_id,
  COUNT(nr.id) as num_requirements,
  string_agg(q.key, ', ' ORDER BY q.key) as features
FROM norm_clause_groups ncg
JOIN norm_requirements nr ON nr.group_id = ncg.id
JOIN questions q ON q.id = nr.question_id
WHERE ncg.norm_id = 'your-norm-uuid-here'
  AND ncg.clause = 'APPLIES_IF'
GROUP BY ncg.id;
```

## Architecture

### Module Structure

```
/db/
  schema.sql           # PostgreSQL schema definition

/ingest/
  __init__.py          # Package exports
  types.py             # Type definitions (Atomic, DNF, enums)
  parser.py            # Expression parser and DNF converter
  dnf.py               # DNF optimization utilities
  sql.py               # SQLAlchemy schema and operations
  ingest.py            # Main CLI ingestion script

/tests/
  test_dnf.py          # DNF tests
  test_parser.py       # Parser tests
```

### DNF Conversion Flow

1. **Parse**: Expression string → AST (using ig_assessment/dsl_parser.py)
2. **Normalize**: Push NOT operators down to leaves (De Morgan's laws)
3. **Convert**: Apply distributive laws to create OR-of-ANDs
4. **Optimize**: Remove contradictions and duplicates
5. **Store**: Each disjunct → clause_group, each atomic → requirement

### Design Decisions

- **DNF Storage**: Enables efficient querying - check if any disjunct is satisfied
- **Idempotent Upserts**: Safe to re-run ingestion without duplicates
- **Canonical Keys**: Uppercase dot notation for consistency
- **JSONB Values**: Flexible storage for any value type
- **Contradiction Detection**: Removes impossible conjuncts (A==TRUE AND A==FALSE)

## Limitations

- NOT IN operator is parsed but may need additional testing
- Complex nested NOT expressions are simplified via De Morgan's laws
- Geographic functions (WITHIN, OVERLAPS) from ig_assessment DSL not yet supported in ingestion
- HAS operator (existence test) not yet implemented in ingestion pipeline

## Future Enhancements

- [ ] Support for geographic functions
- [ ] Support for HAS operator (existence tests)
- [ ] Batch ingestion with progress tracking
- [ ] Schema migration tools
- [ ] Query interface for evaluating norms against feature assignments
- [ ] Integration with ig_assessment evaluator for compliance checking

## Example Workflow

1. Extract norms from documents (via langextract or manual process)
2. Save to JSON with applies_if expressions
3. Run ingestion: `python -m ingest.ingest --dsn ... --json ...`
4. Query norms: Find all norms that apply given a feature assignment
5. Evaluate compliance: Check if satisfied_if conditions are met

## License

Same as parent project (Apache 2.0)

## Contributing

Follow the coding standards in `.github/instructions`:
- Use Black formatting (line length 88)
- Type hints for all functions
- Docstrings in Google style
- Unit tests for new functionality
