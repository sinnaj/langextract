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

The script is designed to work with both a PDF file and a DoclingDocument JSON file to map table of contents entries to document structure:

```bash
# Basic usage: Map PDF ToC to DoclingDocument sections
python scripts/pdf_toc_extractor.py document.pdf document.json

# Enable verbose logging for debugging
python scripts/pdf_toc_extractor.py document.pdf document.json --verbose

# Require that a ToC exists (exit with error if not found)
python scripts/pdf_toc_extractor.py document.pdf document.json --require-toc
```

The script will:
1. Extract the table of contents from the PDF
2. Map ToC entries to section headers in the DoclingDocument JSON
3. Create `headline_fixed_doclingdocument.json` with corrected hierarchy
4. Generate `toc.json` with the extracted ToC structure
5. Create `report.md` with detailed mapping analysis

**Note**: If the PDF does not contain an embedded table of contents, the script will:
- Display clear warnings explaining the situation
- Continue processing using fallback logic (unless `--require-toc` is specified)
- Generate output files with limited ToC-based hierarchy information

### Python API

```python
from scripts.pdf_toc_extractor import extract_pdf_toc

# Extract ToC as structured data
toc_data = extract_pdf_toc("document.pdf")
print(f"Found {len(toc_data)} ToC entries")

# Handle PDFs without ToC
if not toc_data:
    print("Warning: This PDF does not have an embedded table of contents")
    print("Consider using alternative document structure analysis methods")
else:
    print(f"First entry: {toc_data[0]}")
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

The script includes comprehensive error handling for various scenarios:

1. **Missing Dependencies**: Clear error message if PyMuPDF is not installed
   ```
   ImportError: PyMuPDF (fitz) is required for PDF ToC extraction.
   Install with: pip install 'langextract[pymupdf]'
   ```

2. **File Not Found**: Informative error for missing input files
   ```
   Error: PDF file not found: document.pdf
   Error: DoclingDocument JSON file not found: document.json
   ```

3. **No ToC Found**: Graceful handling when PDF has no embedded table of contents
   - By default, the script continues processing with fallback logic
   - Displays detailed warnings explaining:
     - What it means (no ToC-based hierarchy mapping)
     - Possible reasons (scanned document, ToC not embedded, etc.)
     - What will happen (fallback processing methods will be used)
   - Use `--require-toc` flag to exit with error instead of continuing

4. **Large Documents**: The script handles large PDFs efficiently
   - Only extracts embedded ToC metadata (no full document scanning)
   - Processing time is typically under a second for ToC extraction

## Common Issues and Solutions

### Issue: "No table of contents found in the PDF"

**Cause**: The PDF does not have an embedded table of contents structure.

**Solutions**:
1. **Accept the limitation**: Use the `--verbose` flag to see detailed processing logs. The script will continue with fallback methods.
2. **Manually create ToC**: If you need ToC-based hierarchy, consider using a PDF editor to add bookmarks/ToC to the document.
3. **Use alternative tools**: For scanned documents, consider OCR and document structure analysis tools.
4. **Verify PDF structure**: Use a PDF viewer (like Adobe Acrobat) to check if the document has bookmarks/outlines.

### Issue: Script exits with error despite no ToC being needed

**Cause**: The `--require-toc` flag is set.

**Solution**: Remove the `--require-toc` flag to allow processing without ToC:
```bash
# Instead of this (which requires ToC):
python scripts/pdf_toc_extractor.py document.pdf document.json --require-toc

# Use this (which continues without ToC):
python scripts/pdf_toc_extractor.py document.pdf document.json
```

## Limitations

### What This Script Can Do
- Extract embedded table of contents from PDFs that have ToC structure
- Map ToC entries to DoclingDocument section headers
- Generate hierarchy corrections based on ToC structure
- Process large PDFs efficiently (278+ pages)
- Continue processing even when no ToC is found (using fallback methods)

### What This Script Cannot Do
- **Extract ToC from scanned PDFs**: Scanned documents without embedded ToC structure will return empty results
- **Create ToC from content**: The script only extracts existing embedded ToC metadata
- **OCR or content analysis**: For documents without ToC, alternative document analysis methods are needed
- **Handle corrupted PDFs**: Severely corrupted PDF files may cause extraction to fail

### When to Use This Script
✅ **Good Use Cases**:
- PDFs created from Word, LaTeX, or other authoring tools with embedded ToC
- Documents with bookmarks/outlines visible in PDF readers
- Batch processing of documents with consistent ToC structure

❌ **Not Suitable For**:
- Scanned documents or images saved as PDF
- PDFs without embedded bookmarks/outlines
- Documents where ToC needs to be inferred from content

### Checking if Your PDF Has ToC
Before using this script, check if your PDF has an embedded ToC:
1. Open the PDF in Adobe Acrobat, Preview, or another PDF reader
2. Look for a "Bookmarks" or "Outline" panel
3. If you see a hierarchical list of sections, the PDF has an embedded ToC
4. If the panel is empty or missing, the PDF likely does not have an embedded ToC

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