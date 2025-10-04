"""End-to-end integration test for norm ingestion (mock)."""

import json
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from ingest.ingest import process_norm
from ingest.parser import expr_to_dnf
from ingest.types import ComparisonOp


def test_expr_to_dnf_on_sample_data():
    """Test DNF conversion on sample norm data."""
    # Test the complex applies_if from sample data
    expr1 = "BUILDING.PROTECTION_LEVEL.IS_PROTECTED == TRUE AND DB.APPLICATION.IS_INCOMPATIBLE_WITH_PROTECTION_LEVEL == TRUE"
    dnf1 = expr_to_dnf(expr1)
    
    # Should have 1 disjunct with 2 atomics
    assert len(dnf1) == 1
    assert len(dnf1[0]) == 2
    
    # Test the more complex applies_if
    expr2 = "AREA.USAGE != BUILDING.USAGE AND ((AREA.USAGE == 'RESIDENTIAL.HOUSING') OR (AREA.USAGE IN ['LODGING','ADMINISTRATIVE','COMMERCIAL','EDUCATION'] AND AREA.SIZE > 500) OR (AREA.USAGE == 'PUBLIC.ASSEMBLY' AND AREA.OCCUPANCY > 500) OR (AREA.USAGE == 'PARKING' AND AREA.SIZE > 100))"
    dnf2 = expr_to_dnf(expr2)
    
    # Should have 4 disjuncts (one for each OR branch)
    assert len(dnf2) == 4
    
    # Each disjunct should start with AREA.USAGE != BUILDING.USAGE
    for conjunct in dnf2:
        keys = [atomic.key for atomic in conjunct]
        assert "AREA.USAGE" in keys


def test_process_norm_structure():
    """Test that process_norm correctly structures data for database."""
    # Mock connection
    mock_conn = MagicMock()
    
    # Sample norm data
    norm_data = {
        "extraction_class": "NORM",
        "extraction_text": "Test norm text",
        "attributes": {
            "id": "12345678-1234-1234-1234-123456789abc",
            "parent_section_id": "section123",
            "paragraph_number": "5.2",
            "obligation_type": "MANDATORY",
            "norm_statement": "Test statement",
            "applies_if": "A == TRUE AND B == 1",
            "satisfied_if": "C == TRUE",
            "exempt_if": "FALSE",
            "topics": ["TOPIC1", "TOPIC2"]
        }
    }
    
    # Mock the database functions
    with patch('ingest.ingest.insert_norm') as mock_insert_norm, \
         patch('ingest.ingest.upsert_topic') as mock_upsert_topic, \
         patch('ingest.ingest.process_clause') as mock_process_clause:
        
        mock_upsert_topic.return_value = 1
        mock_conn.execute.return_value.fetchone.return_value = None  # No existing norm-topic
        
        # Process the norm
        process_norm(mock_conn, norm_data, document_id=None)
        
        # Verify insert_norm was called
        mock_insert_norm.assert_called_once()
        call_args = mock_insert_norm.call_args[0]
        norm_record = call_args[1]
        
        # Check norm record structure
        assert norm_record["id"] == UUID("12345678-1234-1234-1234-123456789abc")
        assert norm_record["extraction_class"] == "NORM"
        assert norm_record["extraction_text"] == "Test norm text"
        assert norm_record["obligation"] == "MANDATORY"
        assert norm_record["norm_statement"] == "Test statement"
        
        # Verify topics were processed
        assert mock_upsert_topic.call_count == 2
        
        # Verify clauses were processed (applies_if and satisfied_if, but not exempt_if="FALSE")
        assert mock_process_clause.call_count == 2


def test_sample_json_structure():
    """Test that sample_norms.json has valid structure."""
    with open("sample_norms.json", "r") as f:
        norms = json.load(f)
    
    assert isinstance(norms, list)
    assert len(norms) >= 2
    
    # Check first norm
    norm1 = norms[0]
    assert "extraction_class" in norm1
    assert "extraction_text" in norm1
    assert "attributes" in norm1
    
    attrs = norm1["attributes"]
    assert "id" in attrs
    assert "obligation_type" in attrs
    assert "norm_statement" in attrs
    assert "applies_if" in attrs
    assert "topics" in attrs
    
    # Verify UUID format
    UUID(attrs["id"])  # Will raise if invalid


def test_dnf_conversion_produces_valid_output():
    """Test that DNF conversion produces queryable structure."""
    expr = "A == TRUE AND (B == 1 OR C == 2)"
    dnf = expr_to_dnf(expr)
    
    # Verify DNF structure
    assert len(dnf) == 2  # Two disjuncts
    
    for conjunct in dnf:
        # Each conjunct should be a list of Atomics
        assert isinstance(conjunct, list)
        for atomic in conjunct:
            # Each atomic should have required fields
            assert hasattr(atomic, 'key')
            assert hasattr(atomic, 'op')
            assert hasattr(atomic, 'value')
            assert hasattr(atomic, 'value_type')
            
            # Operator should be valid
            assert isinstance(atomic.op, ComparisonOp)


def test_question_key_canonicalization():
    """Test that question keys are properly canonicalized."""
    from ingest.parser import canonicalize_identifier
    
    # Test cases from sample norms
    assert canonicalize_identifier("BUILDING.PROTECTION_LEVEL.IS_PROTECTED") == "BUILDING.PROTECTION_LEVEL.IS_PROTECTED"
    assert canonicalize_identifier("DB.APPLICATION.IS_INCOMPATIBLE_WITH_PROTECTION_LEVEL") == "DB.APPLICATION.IS_INCOMPATIBLE_WITH_PROTECTION_LEVEL"
    assert canonicalize_identifier("solution.type") == "SOLUTION.TYPE"
    
    # Should handle extra spaces
    assert canonicalize_identifier(" area . usage ") == "AREA.USAGE"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
