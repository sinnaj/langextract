# Docling Document Section Splitter

This script uses the Docling library to parse documents and extract hierarchical sections from them.

## Features

- Parses various document formats (PDF, DOCX, Markdown, etc.) using Docling
- Extracts hierarchical section structure with intelligent level detection
- Handles content associated with each section (text, lists, tables, etc.)
- Outputs structured JSON representation of the document hierarchy
- Provides summary view of the document structure

## Usage

```bash
# Basic usage - print summary to console
python scripts/docling_section_splitter.py path/to/document.md --summary

# Save hierarchical structure to JSON file
python scripts/docling_section_splitter.py path/to/document.md -o output.json

# Get help
python scripts/docling_section_splitter.py --help
```

## Example

```bash
# Process the test document
python scripts/docling_section_splitter.py docs/test_docs/small_DBSI.md --summary
```

This will output a hierarchical breakdown of the document sections, showing:
- Section titles and levels
- Number of content items in each section
- Nested subsection structure

## Output Format

The JSON output includes:
- `document_path`: Path to the processed document
- `total_items`: Total number of items parsed from the document  
- `sections`: Array of hierarchical sections with:
  - `id`: Unique identifier for the section
  - `title`: Section title
  - `level`: Hierarchical level (1 = top level, 2 = subsection, etc.)
  - `type`: Section type ("section" or "content_group")
  - `content`: Array of content items (text, lists, etc.)
  - `subsections`: Array of nested subsections
- `metadata`: Document metadata (status, name, page count)

## Requirements

- Python 3.10+
- Docling library (automatically installs dependencies for PDF/DOCX processing)

## Installation

The Docling library is already installed in this environment. If running elsewhere:

```bash
pip install docling
```

## Hierarchical Detection

The script includes intelligent hierarchical level detection that:
- Analyzes section titles to determine proper nesting levels
- Recognizes numbered sections (11.1, 11.2, etc.) as subsections
- Handles inconsistencies in markdown heading levels
- Groups related content under appropriate sections