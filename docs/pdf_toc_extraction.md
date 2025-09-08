# PDF Table of Contents (ToC) Extraction

This document describes the PDF Table of Contents extraction functionality using PyMuPDF.

## Overview

The `pdf_toc_extractor.py` script provides a simple way to extract table of contents information from PDF documents using the PyMuPDF library. This complements the existing PDF to Markdown conversion functionality by providing focused ToC extraction.

## Installation

To use the PDF ToC extraction functionality, install the PyMuPDF optional dependency:

```bash
pip install "langextract[pymupdf]"
```

## Usage

### Command Line Interface

```bash
# Extract ToC as JSON (default)
python scripts/pdf_toc_extractor.py document.pdf

# Extract ToC as human-readable text
python scripts/pdf_toc_extractor.py document.pdf --format text

# Save to file
python scripts/pdf_toc_extractor.py document.pdf --output toc.json
python scripts/pdf_toc_extractor.py document.pdf --output toc.txt --format text

# Extract from URL
python scripts/pdf_toc_extractor.py https://example.com/document.pdf --format text --verbose
```

### Python API

```python
from scripts.pdf_toc_extractor import extract_pdf_toc

# Extract ToC as structured data
toc_data = extract_pdf_toc("document.pdf", output_format="json")
print(f"Found {len(toc_data)} ToC entries")

# Extract ToC as formatted text
toc_text = extract_pdf_toc("document.pdf", output_format="text")
print(toc_text)

# Save to file
toc_data = extract_pdf_toc(
    "document.pdf", 
    output_path="toc.json", 
    output_format="json"
)
```

## Output Formats

### JSON Format (Default)

The JSON format returns a list of ToC entries with the following structure:

```json
[
  {
    "level": 1,
    "title": "Introduction",
    "page": 1
  },
  {
    "level": 2,
    "title": "Background",
    "page": 3
  },
  {
    "level": 1,
    "title": "Methods",
    "page": 10
  }
]
```

- `level`: The hierarchical level of the ToC entry (1 = top level, 2 = subsection, etc.)
- `title`: The text of the ToC entry
- `page`: The page number where this section begins

### Text Format

The text format provides a human-readable representation:

```
Table of Contents
==================

Introduction ... 1
  Background ... 3
Methods ... 10
```

## Features

- **Multiple Input Sources**: Support for local files and URLs
- **Multiple Output Formats**: JSON for structured data, text for human readability
- **Error Handling**: Graceful handling of extraction errors with informative messages
- **Logging**: Configurable logging levels for debugging and monitoring
- **URL Support**: Direct extraction from web-hosted PDF documents

## Error Handling

The script includes comprehensive error handling:

1. **Missing Dependencies**: Clear error message if PyMuPDF is not installed
2. **File Not Found**: Informative error for missing input files
3. **Network Issues**: Proper handling of URL download failures
4. **No ToC**: Graceful handling when PDF has no table of contents

## Limitations

- Only works with PDFs that have embedded table of contents data
- Scanned PDFs without ToC structure will return empty results
- Network timeouts may occur for very large PDFs downloaded from URLs

## Integration with LangExtract

The extracted ToC data can be used with LangExtract for further processing:

```python
import langextract as lx
from scripts.pdf_toc_extractor import extract_pdf_toc

# Extract ToC structure
toc_data = extract_pdf_toc("document.pdf")

# Use ToC information to guide document analysis
section_titles = [entry['title'] for entry in toc_data]
result = lx.extract(
    text_or_documents=section_titles,
    prompt_description="Classify document sections by topic",
    model_id="gemini-2.5-flash"
)
```

## Contributing

When contributing improvements to the PDF ToC extraction:

1. Follow the existing code style and patterns
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure compatibility with the existing langextract ecosystem