# PDF Table of Contents Extraction with pdfminer.six

This script provides functionality to extract Table of Contents (TOC) from PDF files that do not have embedded bookmarks, using the `pdfminer.six` library.

## Overview

The `extract_toc_pdfminer.py` script analyzes PDF text content to identify and extract Table of Contents sections. It recognizes various TOC patterns commonly found in academic papers, technical documents, and books.

## Features

- **PDF Text Extraction**: Uses pdfminer.six for high-quality text extraction from PDF files
- **Pattern Recognition**: Identifies TOC sections using multiple heuristics:
  - Common TOC titles in multiple languages
  - Numbered section patterns (1.2.3 format)
  - Chapter/Section patterns
  - Page number patterns with dots
  - Roman numeral patterns
- **Hierarchical Structure**: Builds proper hierarchical TOC structure from flat text
- **Multiple Input Sources**: Supports both local files and URLs
- **Multiple Output Formats**: 
  - Text format for human readability
  - JSON format for programmatic processing
- **Robust Processing**: Handles various PDF layouts and TOC formats
- **Command Line Interface**: Easy-to-use CLI with comprehensive options

## Installation

The script requires `pdfminer.six` for PDF processing:

```bash
pip install pdfminer.six
```

For URL support, `requests` is also required:

```bash
pip install requests
```

## Usage

### Command Line Interface

```bash
# Basic usage - extract TOC and save as text
python scripts/extract_toc_pdfminer.py document.pdf

# Specify output file
python scripts/extract_toc_pdfminer.py document.pdf --output toc_output.txt

# Extract from URL
python scripts/extract_toc_pdfminer.py https://example.com/document.pdf

# Output as JSON
python scripts/extract_toc_pdfminer.py document.pdf --format json --output toc.json

# Enable verbose logging
python scripts/extract_toc_pdfminer.py document.pdf --verbose
```

### Python API

```python
from scripts.extract_toc_pdfminer import PDFTOCExtractor

# Initialize extractor
extractor = PDFTOCExtractor(verbose=False)

# Extract TOC from file
toc_entries = extractor.extract_toc('document.pdf')

# Extract TOC from URL
toc_entries = extractor.extract_toc('https://example.com/document.pdf')

# Process results
for entry in toc_entries:
    print(f"Level {entry.level}: {entry.title}")
    if entry.page:
        print(f"  Page: {entry.page}")
    for child in entry.children:
        print(f"  - {child.title}")
```

## Supported TOC Patterns

The script recognizes various TOC formats:

### Numbered Sections
```
1. Introduction .................. 5
1.1 Overview .................. 6
1.2 Background .................. 8
2. Methodology .................. 15
2.1 Data Collection .................. 16
2.1.1 Sampling .................. 17
```

### Chapter Format
```
Chapter 1: Introduction .................. 5
Chapter 2: Literature Review .................. 15
Section A: Appendix .................. 50
```

### Roman Numerals
```
I. Introduction .................. 5
II. Background .................. 10
III. Methods .................. 20
```

### Mixed Formats
The script can handle documents with multiple TOC formats and will attempt to normalize them into a consistent hierarchy.

## Output Formats

### Text Format
```
Table of Contents
==================================================

Introduction .................. 5
  Overview .................. 6
  Background .................. 8
Methodology .................. 15
  Data Collection .................. 16
    Sampling .................. 17
```

### JSON Format
```json
{
  "table_of_contents": [
    {
      "title": "Introduction",
      "level": 1,
      "page": 5,
      "children": [
        {
          "title": "Overview",
          "level": 2,
          "page": 6
        },
        {
          "title": "Background", 
          "level": 2,
          "page": 8
        }
      ]
    },
    {
      "title": "Methodology",
      "level": 1,
      "page": 15,
      "children": [
        {
          "title": "Data Collection",
          "level": 2,
          "page": 16,
          "children": [
            {
              "title": "Sampling",
              "level": 3,
              "page": 17
            }
          ]
        }
      ]
    }
  ],
  "total_entries": 2
}
```

## Algorithm Details

### TOC Detection Process

1. **Text Extraction**: Extract all text from PDF using pdfminer.six with optimized layout parameters
2. **Section Identification**: Scan text for lines containing common TOC indicators
3. **Boundary Detection**: Determine start and end of TOC sections
4. **Pattern Matching**: Apply regex patterns to identify TOC entries
5. **Hierarchy Building**: Construct hierarchical structure based on numbering levels
6. **Validation**: Filter out invalid entries and normalize format

### Pattern Recognition

The script uses several regex patterns to identify TOC entries:

- **Page Numbers**: `\.{3,}.*?(\d+)\s*$` - Lines ending with dots followed by page numbers
- **Numbered Lists**: `^(\d+(?:\.\d+)*\.?)\s+(.+)` - Numbered section headers
- **Chapters**: `^(chapter|ch\.?|section|sec\.?)\s+(\d+(?:\.\d+)*\.?)\s*:?\s*(.+)` - Chapter/section patterns
- **Roman Numerals**: `^([ivxlcdm]+)\.\s+(.+)` - Roman numeral patterns

### Hierarchy Construction

The algorithm builds hierarchy by:
1. Parsing numbering levels (e.g., "1.2.3" = level 3)
2. Using a stack-based approach to maintain parent-child relationships
3. Handling mixed numbering systems gracefully
4. Preserving original ordering from the document

## Configuration

### Layout Parameters

The script uses optimized pdfminer.six layout parameters:

```python
LAParams(
    word_margin=0.1,    # Tight word boundaries
    char_margin=2.0,    # Character spacing
    line_margin=0.5,    # Line spacing
    boxes_flow=0.5,     # Reading order detection
    all_texts=False     # Skip non-text elements
)
```

### TOC Title Detection

Supports titles in multiple languages:
- English: "table of contents", "contents", "index"
- Spanish: "índice", "tabla de contenidos", "contenido", "sumario"
- Italian: "sommario"
- German: "inhaltsverzeichnis"
- French: "table des matières"

## Limitations

1. **Text-based PDFs Only**: Works best with text-based PDFs; scanned PDFs require OCR preprocessing
2. **Pattern Dependency**: Relies on recognizable TOC patterns; unusual formats may not be detected
3. **Layout Sensitivity**: Complex multi-column layouts may affect extraction quality
4. **Language Support**: Optimized for documents using Latin scripts
5. **Page Number Accuracy**: Page numbers are extracted as-is from the TOC; may not correspond to actual PDF page numbers

## Error Handling

The script provides comprehensive error handling:

- **File Not Found**: Clear error messages for missing files
- **Network Issues**: Timeout and retry logic for URL downloads
- **PDF Parsing Errors**: Graceful handling of corrupted or protected PDFs
- **No TOC Found**: Warning when no TOC sections are detected
- **Invalid Patterns**: Robust parsing that skips malformed entries

## Performance Considerations

- **Memory Usage**: Loads entire PDF text into memory; may be limited by available RAM for very large documents
- **Processing Time**: Typically processes documents in seconds; time increases with document size and complexity
- **Network Timeouts**: URL downloads have reasonable timeouts to prevent hanging

## Testing

The script includes comprehensive unit tests covering:

- TOC entry creation and manipulation
- Pattern recognition and parsing
- Hierarchy construction
- File operations
- Integration tests with real PDFs

Run tests with:
```bash
python -m pytest tests/test_extract_toc_pdfminer.py -v
```

## Contributing

When contributing improvements:

1. Follow existing code style and patterns
2. Add tests for new functionality  
3. Update documentation as needed
4. Consider backward compatibility
5. Test with various PDF formats

## Examples

### Processing Academic Papers

```bash
# Extract TOC from arXiv paper
python scripts/extract_toc_pdfminer.py https://arxiv.org/pdf/2301.00001.pdf

# Save as JSON for further processing
python scripts/extract_toc_pdfminer.py paper.pdf --format json --output paper_toc.json
```

### Batch Processing

```python
import os
from scripts.extract_toc_pdfminer import PDFTOCExtractor

extractor = PDFTOCExtractor()

# Process all PDFs in a directory
for filename in os.listdir('pdfs/'):
    if filename.endswith('.pdf'):
        try:
            toc_entries = extractor.extract_toc(f'pdfs/{filename}')
            print(f"{filename}: {len(toc_entries)} TOC entries found")
        except Exception as e:
            print(f"Error processing {filename}: {e}")
```

This documentation covers the comprehensive functionality of the PDF TOC extraction script, providing users with all necessary information to effectively use and understand the tool.