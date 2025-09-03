"""
Hierarchy fixing and duplicate section merging for langextract output.

This module provides functionality to:
1. Detect and merge duplicate sections (e.g., sections appearing in ToC and later as actual content)
2. Fix broken hierarchical parent-child relationships in document structure
3. Validate and correct the document tree structure

The functions are designed to be non-destructive, adding quality warnings when issues are detected.
"""

from collections import defaultdict
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


def calculate_text_similarity(text1: str, text2: str) -> float:
  """Calculate simple text similarity between two strings (Jaccard similarity)."""
  if not text1 or not text2:
    return 0.0

  # Convert to lowercase and split into words
  words1 = set(text1.lower().split())
  words2 = set(text2.lower().split())

  if not words1 or not words2:
    return 0.0

  # Jaccard similarity: intersection / union
  intersection = len(words1 & words2)
  union = len(words1 | words2)

  return intersection / union if union > 0 else 0.0


def find_duplicate_sections(
    sections: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
  """
  Find groups of duplicate sections based on title similarity and content.

  Returns list of groups where each group contains potentially duplicate sections.
  """
  duplicate_groups = []
  processed_ids = set()

  # Group by exact title match first
  by_title = defaultdict(list)
  for section in sections:
    title = section.get("attributes", {}).get("section_title", "") or ""
    title = title.strip() if isinstance(title, str) else ""
    if title:
      by_title[title].append(section)

  # Find exact title duplicates
  for title, instances in by_title.items():
    if len(instances) > 1:
      duplicate_groups.append(instances)
      for instance in instances:
        processed_ids.add(instance.get("attributes", {}).get("id"))

  # Look for content similarity among remaining sections
  remaining_sections = [
      s
      for s in sections
      if s.get("attributes", {}).get("id") not in processed_ids
  ]

  for i, section1 in enumerate(remaining_sections):
    if section1.get("attributes", {}).get("id") in processed_ids:
      continue

    similar_sections = [section1]
    text1 = section1.get("extraction_text", "")

    for j, section2 in enumerate(remaining_sections[i + 1 :], i + 1):
      if section2.get("attributes", {}).get("id") in processed_ids:
        continue

      text2 = section2.get("extraction_text", "")
      similarity = calculate_text_similarity(text1, text2)

      # Consider sections similar if they have high text similarity
      if similarity > 0.7:  # 70% similarity threshold
        similar_sections.append(section2)
        processed_ids.add(section2.get("attributes", {}).get("id"))

    if len(similar_sections) > 1:
      duplicate_groups.append(similar_sections)
      for section in similar_sections:
        processed_ids.add(section.get("attributes", {}).get("id"))

  return duplicate_groups


def merge_section_group(section_group: List[Dict[str, Any]]) -> Dict[str, Any]:
  """
  Merge a group of duplicate sections into a single canonical section.

  Strategy:
  1. Keep the section with the most complete information
  2. Prefer sections that appear later in the document (actual content vs ToC)
  3. Preserve all extraction_text content
  """
  if not section_group:
    return {}

  if len(section_group) == 1:
    return section_group[0]

  # Sort by extraction_index to prefer later appearances (actual content over ToC)
  sorted_sections = sorted(
      section_group, key=lambda x: x.get("extraction_index", 0), reverse=True
  )

  # Use the highest extraction_index section as the base
  canonical = sorted_sections[0].copy()

  # Combine extraction texts from all sections
  all_texts = []
  all_ids = []

  for section in section_group:
    text = section.get("extraction_text", "") or ""
    text = text.strip() if isinstance(text, str) else ""
    if text and text not in all_texts:
      all_texts.append(text)

    section_id = section.get("attributes", {}).get("id")
    if section_id:
      all_ids.append(section_id)

  # Update the canonical section
  if all_texts:
    canonical["extraction_text"] = " | ".join(all_texts)

  # Add merge information to attributes
  if "attributes" not in canonical:
    canonical["attributes"] = {}

  # Store IDs of merged sections (excluding the canonical one)
  canonical_id = canonical.get("attributes", {}).get("id")
  merged_ids = [id for id in all_ids if id != canonical_id]
  canonical["attributes"]["merged_section_ids"] = merged_ids
  canonical["attributes"]["merge_count"] = len(section_group)

  return canonical


def detect_orphaned_sections(
    sections: List[Dict[str, Any]], all_section_ids: Set[str]
) -> List[Dict[str, Any]]:
  """Find sections that have invalid parent_id references."""
  orphaned = []

  for section in sections:
    attributes = section.get("attributes", {})
    parent_id = attributes.get("parent_id")

    # Skip root-level sections (no parent_id)
    if not parent_id:
      continue

    # Check if parent exists in our section set
    if parent_id not in all_section_ids:
      orphaned.append(section)

  return orphaned


def fix_orphaned_sections(
    orphaned_sections: List[Dict[str, Any]],
    sections: List[Dict[str, Any]],
    document_ids: Set[str],
) -> List[Dict[str, Any]]:
  """
  Attempt to fix orphaned sections by finding appropriate parents.

  Strategy:
  1. Look for sections with similar titles/content that could be parents
  2. Use section levels to maintain hierarchy
  3. Fall back to document root if no suitable parent found
  """
  fixed_sections = []
  section_by_id = {s.get("attributes", {}).get("id"): s for s in sections}

  for orphan in orphaned_sections:
    orphan_copy = orphan.copy()
    attributes = orphan_copy.setdefault("attributes", {})

    orphan_level = attributes.get("section_level", 999)
    orphan_title = attributes.get("section_title", "") or ""
    orphan_title = orphan_title.strip() if isinstance(orphan_title, str) else ""

    # Look for a suitable parent (lower level number)
    best_parent = None
    best_similarity = 0.0

    for section in sections:
      section_attrs = section.get("attributes", {})
      section_level = section_attrs.get("section_level", 999)
      section_id = section_attrs.get("id")

      # Only consider sections with lower level numbers as potential parents
      if section_level >= orphan_level or not section_id:
        continue

      section_title = section_attrs.get("section_title", "") or ""
      section_title = (
          section_title.strip() if isinstance(section_title, str) else ""
      )
      similarity = calculate_text_similarity(orphan_title, section_title)

      if similarity > best_similarity:
        best_similarity = similarity
        best_parent = section_id

    # Update parent_id
    if best_parent and best_similarity > 0.1:  # 10% minimum similarity
      attributes["parent_id"] = best_parent
      attributes["parent_fix_applied"] = True
    else:
      # Fall back to document root - use first available document ID
      if document_ids:
        attributes["parent_id"] = list(document_ids)[0]
        attributes["parent_fix_applied"] = True
        attributes["parent_fix_fallback"] = "document_root"

    fixed_sections.append(orphan_copy)

  return fixed_sections


def fix_hierarchy_and_merge_duplicates(obj: Dict[str, Any]) -> None:
  """
  Main function to fix hierarchical structure and merge duplicate sections.

  This function:
  1. Extracts all SECTION extractions
  2. Finds and merges duplicate sections
  3. Fixes orphaned sections with invalid parent references
  4. Updates the extractions list with fixed sections
  5. Adds quality warnings about changes made

  Args:
      obj: The langextract output object with 'extractions' list
  """
  if not isinstance(obj, dict) or "extractions" not in obj:
    return

  extractions = obj["extractions"]
  if not isinstance(extractions, list):
    return

  # Extract all SECTION extractions
  sections = [e for e in extractions if e.get("extraction_class") == "SECTION"]
  non_sections = [
      e for e in extractions if e.get("extraction_class") != "SECTION"
  ]

  if not sections:
    return

  logger.info(f"Processing {len(sections)} sections for hierarchy fixes")

  # Find duplicate section groups
  duplicate_groups = find_duplicate_sections(sections)
  merged_sections = []
  merged_count = 0

  # Track which sections have been processed
  processed_ids = set()

  # Merge duplicate groups
  for group in duplicate_groups:
    if len(group) > 1:
      merged_section = merge_section_group(group)
      merged_sections.append(merged_section)
      merged_count += len(group) - 1  # Count eliminated duplicates

      # Mark all sections in group as processed
      for section in group:
        section_id = section.get("attributes", {}).get("id")
        if section_id:
          processed_ids.add(section_id)

  # Add non-duplicate sections
  for section in sections:
    section_id = section.get("attributes", {}).get("id")
    if section_id not in processed_ids:
      merged_sections.append(section)

  # Build set of all valid section IDs after merging
  all_section_ids = {
      s.get("attributes", {}).get("id")
      for s in merged_sections
      if s.get("attributes", {}).get("id")
  }

  # Also include document metadata IDs as valid parents
  doc_metadata = [
      e
      for e in non_sections
      if e.get("extraction_class") == "DOCUMENT_METADATA"
  ]
  for doc in doc_metadata:
    doc_id = doc.get("attributes", {}).get("id")
    if doc_id:
      all_section_ids.add(doc_id)

  # Find orphaned sections
  orphaned_sections = detect_orphaned_sections(merged_sections, all_section_ids)

  # Fix orphaned sections
  fixed_orphans = []
  orphan_fixes = 0
  if orphaned_sections:
    # Get document metadata IDs for fallback
    doc_metadata = [
        e
        for e in non_sections
        if e.get("extraction_class") == "DOCUMENT_METADATA"
    ]
    document_ids = {
        doc.get("attributes", {}).get("id")
        for doc in doc_metadata
        if doc.get("attributes", {}).get("id")
    }

    fixed_orphans = fix_orphaned_sections(
        orphaned_sections, merged_sections, document_ids
    )
    orphan_fixes = len(fixed_orphans)

    # Replace orphaned sections with fixed versions
    orphan_ids = {s.get("attributes", {}).get("id") for s in orphaned_sections}
    final_sections = []

    for section in merged_sections:
      section_id = section.get("attributes", {}).get("id")
      if section_id in orphan_ids:
        # Find the fixed version
        fixed = next(
            (
                f
                for f in fixed_orphans
                if f.get("attributes", {}).get("id") == section_id
            ),
            section,
        )
        final_sections.append(fixed)
      else:
        final_sections.append(section)
  else:
    final_sections = merged_sections

  # Update the extractions list
  obj["extractions"] = final_sections + non_sections

  # Add quality warnings
  quality = obj.setdefault("quality", {})
  warnings = quality.setdefault("warnings", [])

  if merged_count > 0:
    warnings.append(f"DUPLICATE_SECTIONS_MERGED:{merged_count}")
    logger.info(f"Merged {merged_count} duplicate sections")

  if orphan_fixes > 0:
    warnings.append(f"ORPHANED_SECTIONS_FIXED:{orphan_fixes}")
    logger.info(f"Fixed {orphan_fixes} orphaned sections")

  logger.info(
      "Hierarchy processing complete. Final section count:"
      f" {len(final_sections)}"
  )


def validate_hierarchy(obj: Dict[str, Any]) -> List[str]:
  """
  Validate the hierarchical structure and return a list of issues found.

  This function can be used to check the quality of the hierarchy after processing.
  """
  issues = []

  if not isinstance(obj, dict) or "extractions" not in obj:
    issues.append("Invalid object structure - missing extractions")
    return issues

  extractions = obj["extractions"]
  sections = [e for e in extractions if e.get("extraction_class") == "SECTION"]

  if not sections:
    return issues

  # Build parent-child mapping
  section_by_id = {}
  parent_children = defaultdict(list)

  for section in sections:
    attributes = section.get("attributes", {})
    section_id = attributes.get("id")
    parent_id = attributes.get("parent_id")

    if section_id:
      section_by_id[section_id] = section
      if parent_id:
        parent_children[parent_id].append(section_id)

  # Check for circular references
  def has_circular_reference(node_id: str, visited: Set[str]) -> bool:
    if node_id in visited:
      return True

    visited.add(node_id)
    section = section_by_id.get(node_id)
    if section:
      parent_id = section.get("attributes", {}).get("parent_id")
      if parent_id and parent_id in section_by_id:
        return has_circular_reference(parent_id, visited.copy())

    return False

  # Validate each section
  for section in sections:
    attributes = section.get("attributes", {})
    section_id = attributes.get("id")
    parent_id = attributes.get("parent_id")
    section_title = attributes.get("section_title", "Unknown")

    # Check for circular references
    if has_circular_reference(section_id, set()):
      issues.append(
          f"Circular reference detected for section '{section_title}' (id:"
          f" {section_id})"
      )

    # Check parent exists (if not document root)
    if parent_id and parent_id not in section_by_id:
      # Check if it's a document metadata ID (acceptable)
      doc_metadata = [
          e
          for e in extractions
          if e.get("extraction_class") == "DOCUMENT_METADATA"
      ]
      valid_doc_ids = {d.get("attributes", {}).get("id") for d in doc_metadata}

      if parent_id not in valid_doc_ids:
        issues.append(
            f"Section '{section_title}' has invalid parent_id: {parent_id}"
        )

  return issues
