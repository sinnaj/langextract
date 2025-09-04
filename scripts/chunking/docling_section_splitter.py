#!/usr/bin/env python3
"""
Docling Document Section Splitter

This script uses Docling to parse documents and extract hierarchical sections.
It processes the document structure to create a nested representation of sections
with their content and metadata.
"""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from docling.document_converter import DocumentConverter


class DocumentSectionSplitter:
  """Extract hierarchical sections from documents using Docling."""

  def __init__(self):
    """Initialize the document converter."""
    self.converter = DocumentConverter()

  def extract_sections(self, document_path: str) -> Dict[str, Any]:
    """
    Extract hierarchical sections from a document.

    Args:
        document_path: Path to the document to process

    Returns:
        Dictionary containing the hierarchical section structure
    """
    # Convert document using Docling
    result = self.converter.convert(document_path)

    if not result.document:
      raise ValueError(f"Failed to convert document: {document_path}")

    # Extract items with their hierarchy levels
    items = list(result.document.iterate_items())

    # Build hierarchical structure
    sections = self._build_hierarchical_sections(items)

    return {
        "document_path": document_path,
        "total_items": len(items),
        "sections": sections,
        "metadata": {
            "converter_status": str(result.status),
            "document_name": result.document.name or Path(document_path).name,
            "num_pages": (
                result.document.num_pages()
                if callable(result.document.num_pages)
                else result.document.num_pages
            ),
        },
    }

  def _build_hierarchical_sections(
      self, items: List[tuple]
  ) -> List[Dict[str, Any]]:
    """
    Build hierarchical section structure from document items.

    Args:
        items: List of (item, level) tuples from document.iterate_items()

    Returns:
        List of hierarchical sections
    """
    sections = []
    section_stack = []  # Stack to track current hierarchy

    for item, level in items:
      item_data = self._extract_item_data(item, level)

      if item.label == "title":
        # This is a heading/title - create a new section
        # Determine actual hierarchy level based on title content
        actual_level = self._determine_section_level(item_data["text"], level)

        section = {
            "id": (
                f"section_{len(sections) + len([s for stack_item in section_stack for s in self._get_all_subsections(stack_item)])}"
            ),
            "title": item_data["text"],
            "level": actual_level,
            "docling_level": level,  # Original level from Docling
            "type": "section",
            "content": [],
            "subsections": [],
        }

        # Adjust the section stack based on actual level
        while section_stack and section_stack[-1]["level"] >= actual_level:
          section_stack.pop()

        # Add to parent section or root
        if section_stack:
          section_stack[-1]["subsections"].append(section)
        else:
          sections.append(section)

        section_stack.append(section)

      else:
        # This is content - add to the current section
        if section_stack:
          section_stack[-1]["content"].append(item_data)
        else:
          # No current section, create a root content item
          if not sections or sections[-1]["type"] != "content_group":
            content_group = {
                "id": f"content_group_{len(sections)}",
                "title": "Document Content",
                "level": 0,
                "type": "content_group",
                "content": [],
                "subsections": [],
            }
            sections.append(content_group)
          sections[-1]["content"].append(item_data)

    return sections

  def _determine_section_level(self, title: str, docling_level: int) -> int:
    """
    Determine the actual hierarchical level of a section based on its title.
    This helps correct cases where Docling doesn't properly detect markdown hierarchy.

    Args:
        title: The section title text
        docling_level: The level detected by Docling

    Returns:
        Adjusted level based on content analysis
    """
    title_lower = title.lower().strip()

    # Pattern-based level detection
    if any(pattern in title_lower for pattern in ["articulo", "artículo"]):
      return 1
    elif (
        title_lower.startswith(("11.", "12.", "13.", "14.", "15.", "16."))
        and "exigencia básica" in title_lower
    ):
      return 2
    elif title_lower.startswith("seccion") or title_lower.startswith("sección"):
      return 2
    elif any(title_lower.startswith(f"{i}.") for i in range(1, 10)) and not any(
        title_lower.startswith(f"1{i}.") for i in range(0, 10)
    ):
      return 3
    elif title_lower.startswith(
        ("i ", "ii ", "iii ", "iv ", "v ", "vi ", "vii ")
    ):
      return 1
    elif title_lower.startswith("# "):
      return 1
    elif title_lower.startswith("## "):
      return 2
    elif title_lower.startswith("### "):
      return 3

    # If no pattern matches, use the original Docling level but add some intelligence
    # If it looks like a numbered subsection, make it level 2
    if any(char.isdigit() for char in title[:10]) and "." in title[:10]:
      return min(docling_level + 1, 3)

    return docling_level

  def _extract_item_data(self, item, level: int) -> Dict[str, Any]:
    """
    Extract data from a document item.

    Args:
        item: Document item from Docling
        level: Hierarchical level of the item

    Returns:
        Dictionary containing item data
    """
    return {
        "type": item.label,
        "text": item.text if hasattr(item, "text") else "",
        "level": level,
        "item_class": type(item).__name__,
    }

  def _get_all_subsections(
      self, section: Dict[str, Any]
  ) -> List[Dict[str, Any]]:
    """Recursively get all subsections from a section."""
    all_subsections = []
    for subsection in section.get("subsections", []):
      all_subsections.append(subsection)
      all_subsections.extend(self._get_all_subsections(subsection))
    return all_subsections

  def save_sections_to_file(
      self,
      sections_data: Dict[str, Any],
      output_path: str,
      format_type: str = "json",
  ):
    """
    Save sections data to a file.

    Args:
        sections_data: The extracted sections data
        output_path: Path where to save the file
        format_type: Format to save ('json' or 'yaml')
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if format_type.lower() == "json":
      with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sections_data, f, indent=2, ensure_ascii=False)
    else:
      raise ValueError(f"Unsupported format: {format_type}")

    print(f"Sections saved to: {output_file}")

  def print_sections_summary(self, sections_data: Dict[str, Any]):
    """Print a summary of the extracted sections."""
    print(f"\n=== Document Sections Summary ===")
    print(f"Document: {sections_data['document_path']}")
    print(f"Total items: {sections_data['total_items']}")
    print(f"Document pages: {sections_data['metadata']['num_pages']}")
    print(f"Top-level sections: {len(sections_data['sections'])}")

    print(f"\n=== Section Hierarchy ===")
    for section in sections_data["sections"]:
      self._print_section_tree(section, indent=0)

  def _print_section_tree(self, section: Dict[str, Any], indent: int = 0):
    """Recursively print section tree structure."""
    prefix = "  " * indent
    print(
        f"{prefix}- [{section['type']}] {section['title']} (Level"
        f" {section['level']})"
    )
    print(f"{prefix}  Content items: {len(section['content'])}")

    for subsection in section["subsections"]:
      self._print_section_tree(subsection, indent + 1)


def main():
  """Main function to run the document section splitter."""
  parser = argparse.ArgumentParser(
      description="Extract hierarchical sections from documents using Docling"
  )
  parser.add_argument("document_path", help="Path to the document to process")
  parser.add_argument("-o", "--output", help="Output file path (optional)")
  parser.add_argument(
      "-f", "--format", choices=["json"], default="json", help="Output format"
  )
  parser.add_argument(
      "-s", "--summary", action="store_true", help="Print sections summary"
  )

  args = parser.parse_args()

  # Check if input file exists
  if not Path(args.document_path).exists():
    print(f"Error: Input file does not exist: {args.document_path}")
    sys.exit(1)

  try:
    # Initialize the splitter
    splitter = DocumentSectionSplitter()

    # Extract sections
    print(f"Processing document: {args.document_path}")
    sections_data = splitter.extract_sections(args.document_path)

    # Save to file if output specified
    if args.output:
      splitter.save_sections_to_file(sections_data, args.output, args.format)

    # Print summary if requested or no output file specified
    if args.summary or not args.output:
      splitter.print_sections_summary(sections_data)

    # If no output file, print JSON to stdout
    if not args.output and not args.summary:
      print(json.dumps(sections_data, indent=2, ensure_ascii=False))

  except Exception as e:
    print(f"Error processing document: {e}")
    sys.exit(1)


if __name__ == "__main__":
  main()
