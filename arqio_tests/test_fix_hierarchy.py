#!/usr/bin/env python3
"""Tests for hierarchy fixing and duplicate section merging functionality."""

import json

import pytest

from postprocessing.fix_hierarchy import calculate_text_similarity
from postprocessing.fix_hierarchy import detect_orphaned_sections
from postprocessing.fix_hierarchy import find_duplicate_sections
from postprocessing.fix_hierarchy import fix_hierarchy_and_merge_duplicates
from postprocessing.fix_hierarchy import fix_orphaned_sections
from postprocessing.fix_hierarchy import merge_section_group
from postprocessing.fix_hierarchy import validate_hierarchy


def test_calculate_text_similarity():
  """Test text similarity calculation."""
  # Identical texts
  assert calculate_text_similarity("hello world", "hello world") == 1.0

  # Completely different texts
  assert calculate_text_similarity("hello world", "foo bar") == 0.0

  # Partial similarity
  similarity = calculate_text_similarity(
      "hello world test", "hello world example"
  )
  assert 0.0 < similarity < 1.0
  assert similarity >= 0.5  # Should be >= 50% similar

  # Empty strings
  assert calculate_text_similarity("", "") == 0.0
  assert calculate_text_similarity("hello", "") == 0.0
  assert calculate_text_similarity("", "world") == 0.0


def test_find_duplicate_sections():
  """Test duplicate section detection."""
  sections = [
      {
          "attributes": {"id": "section1", "section_title": "Test Section"},
          "extraction_text": "This is a test section",
      },
      {
          "attributes": {
              "id": "section2",
              "section_title": "Test Section",  # Exact duplicate title
          },
          "extraction_text": "This is another test section",
      },
      {
          "attributes": {
              "id": "section3",
              "section_title": "Different Section",
          },
          "extraction_text": "This is a test section",  # Similar content
      },
      {
          "attributes": {"id": "section4", "section_title": "Unique Section"},
          "extraction_text": "Completely different content",
      },
  ]

  duplicate_groups = find_duplicate_sections(sections)

  # Should find at least one group with the exact title match
  assert len(duplicate_groups) >= 1

  # Find the group with exact title matches
  title_duplicates = None
  for group in duplicate_groups:
    if len(group) == 2 and all(
        s["attributes"]["section_title"] == "Test Section" for s in group
    ):
      title_duplicates = group
      break

  assert title_duplicates is not None
  assert len(title_duplicates) == 2


def test_merge_section_group():
  """Test merging a group of duplicate sections."""
  section_group = [
      {
          "attributes": {"id": "section1", "section_title": "Test Section"},
          "extraction_text": "First occurrence",
          "extraction_index": 1,
      },
      {
          "attributes": {"id": "section2", "section_title": "Test Section"},
          "extraction_text": "Second occurrence",
          "extraction_index": 10,  # Later in document
      },
  ]

  merged = merge_section_group(section_group)

  # Should prefer the later occurrence as canonical
  assert merged["attributes"]["id"] == "section2"

  # Should combine extraction texts
  assert "First occurrence" in merged["extraction_text"]
  assert "Second occurrence" in merged["extraction_text"]

  # Should have merge metadata
  assert "merged_section_ids" in merged["attributes"]
  assert merged["attributes"]["merge_count"] == 2
  assert "section1" in merged["attributes"]["merged_section_ids"]


def test_detect_orphaned_sections():
  """Test detection of orphaned sections."""
  sections = [
      {"attributes": {"id": "section1", "parent_id": "valid_parent"}},
      {
          "attributes": {
              "id": "section2",
              "parent_id": "invalid_parent",  # This parent doesn't exist
          }
      },
      {
          "attributes": {
              "id": "section3",
              "parent_id": None,  # Root section, not orphaned
          }
      },
  ]

  valid_ids = {"section1", "section3", "valid_parent"}

  orphaned = detect_orphaned_sections(sections, valid_ids)

  assert len(orphaned) == 1
  assert orphaned[0]["attributes"]["id"] == "section2"


def test_fix_orphaned_sections():
  """Test fixing orphaned sections."""
  orphaned_sections = [{
      "attributes": {
          "id": "orphan1",
          "section_title": "Fire Safety Rules",
          "section_level": 3,
          "parent_id": "invalid_parent",
      }
  }]

  all_sections = [
      {
          "attributes": {
              "id": "section1",
              "section_title": "Fire Safety",
              "section_level": 2,
          }
      },
      {
          "attributes": {
              "id": "section2",
              "section_title": "Building Codes",
              "section_level": 1,
          }
      },
  ] + orphaned_sections

  document_ids = {"doc1"}

  fixed = fix_orphaned_sections(orphaned_sections, all_sections, document_ids)

  assert len(fixed) == 1

  # Should have found a suitable parent
  fixed_section = fixed[0]
  assert "parent_fix_applied" in fixed_section["attributes"]

  # Should prefer the Fire Safety section due to title similarity
  assert fixed_section["attributes"]["parent_id"] == "section1"


def test_fix_hierarchy_and_merge_duplicates_integration():
  """Test the main integration function."""
  test_data = {
      "extractions": [
          {
              "extraction_class": "DOCUMENT_METADATA",
              "attributes": {"id": "doc1"},
          },
          {
              "extraction_class": "SECTION",
              "attributes": {
                  "id": "section1",
                  "section_title": "Fire Safety",
                  "parent_id": "doc1",
                  "section_level": 1,
              },
              "extraction_text": "Fire safety requirements",
              "extraction_index": 5,
          },
          {
              "extraction_class": "SECTION",
              "attributes": {
                  "id": "section2",
                  "section_title": "Fire Safety",  # Duplicate
                  "parent_id": "doc1",
                  "section_level": 1,
              },
              "extraction_text": "Fire safety detailed rules",
              "extraction_index": 20,  # Later occurrence
          },
          {
              "extraction_class": "SECTION",
              "attributes": {
                  "id": "section3",
                  "section_title": "Sub Safety Rules",
                  "parent_id": "invalid_parent",  # Orphaned
                  "section_level": 2,
              },
          },
      ]
  }

  original_count = len(test_data["extractions"])
  fix_hierarchy_and_merge_duplicates(test_data)

  # Should have fewer sections due to merging
  sections_after = [
      e
      for e in test_data["extractions"]
      if e.get("extraction_class") == "SECTION"
  ]
  assert len(sections_after) == 2  # One merged, one fixed orphan

  # Should have quality warnings
  assert "quality" in test_data
  assert "warnings" in test_data["quality"]

  warnings = test_data["quality"]["warnings"]
  warning_text = " ".join(warnings)
  assert "DUPLICATE_SECTIONS_MERGED" in warning_text
  assert "ORPHANED_SECTIONS_FIXED" in warning_text


def test_validate_hierarchy():
  """Test hierarchy validation."""
  # Valid hierarchy
  valid_data = {
      "extractions": [
          {
              "extraction_class": "DOCUMENT_METADATA",
              "attributes": {"id": "doc1"},
          },
          {
              "extraction_class": "SECTION",
              "attributes": {
                  "id": "section1",
                  "section_title": "Main Section",
                  "parent_id": "doc1",
              },
          },
          {
              "extraction_class": "SECTION",
              "attributes": {
                  "id": "section2",
                  "section_title": "Sub Section",
                  "parent_id": "section1",
              },
          },
      ]
  }

  issues = validate_hierarchy(valid_data)
  assert len(issues) == 0

  # Invalid hierarchy with circular reference
  invalid_data = {
      "extractions": [
          {
              "extraction_class": "SECTION",
              "attributes": {
                  "id": "section1",
                  "section_title": "Section 1",
                  "parent_id": "section2",  # Circular reference
              },
          },
          {
              "extraction_class": "SECTION",
              "attributes": {
                  "id": "section2",
                  "section_title": "Section 2",
                  "parent_id": "section1",  # Circular reference
              },
          },
      ]
  }

  issues = validate_hierarchy(invalid_data)
  assert len(issues) > 0
  assert any("circular" in issue.lower() for issue in issues)


def test_empty_inputs():
  """Test behavior with empty or invalid inputs."""
  # Empty object
  empty_obj = {}
  fix_hierarchy_and_merge_duplicates(empty_obj)
  assert empty_obj == {}

  # Object with empty extractions
  empty_extractions = {"extractions": []}
  fix_hierarchy_and_merge_duplicates(empty_extractions)
  assert empty_extractions == {"extractions": []}

  # Object with no sections
  no_sections = {
      "extractions": [
          {"extraction_class": "NORM", "attributes": {"id": "norm1"}}
      ]
  }
  original = no_sections.copy()
  fix_hierarchy_and_merge_duplicates(no_sections)
  assert no_sections == original


if __name__ == "__main__":
  pytest.main([__file__])
