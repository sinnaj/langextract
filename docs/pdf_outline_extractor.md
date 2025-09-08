# PDF Outline Extractor

This document describes how to use the PDF Outline Extractor functionality in LangExtract.

## Overview

LangExtract includes a script that extracts hierarchical structure (outline) from PDF documents using [Docling](https://github.com/DS4SD/docling) document understanding capabilities. The script identifies document titles and hierarchical headings (H1-H4) and outputs them in a structured JSON format compatible with the [PDF-Outline-Extractor](https://github.com/itshivams/PDF-Outline-Extractor/) reference implementation.

The PDF outline extractor leverages the existing PDF processing infrastructure in langextract, specifically the Docling-based document parsing and structure recognition capabilities.

## Installation

To use the PDF outline extraction feature, you need to install LangExtract with the docling optional dependency:

```bash
pip install "langextract[docling]"
```

Alternatively, if you have LangExtract already installed, you can install docling separately:

```bash
pip install docling
```

## Usage

The PDF outline extractor can be used from the command line:

```bash
python scripts/pdf_outline_extractor.py input.pdf [output.json]
```

### Basic Usage

```bash
# Extract outline and save to file
python scripts/pdf_outline_extractor.py document.pdf outline.json

# Extract outline and print to stdout
python scripts/pdf_outline_extractor.py document.pdf --stdout

# Extract from URL
python scripts/pdf_outline_extractor.py https://arxiv.org/pdf/2408.09869 paper_outline.json
```

### Advanced Options

```bash
# Enable verbose logging
python scripts/pdf_outline_extractor.py document.pdf outline.json --verbose

# Force output to stdout (ignores output file parameter)
python scripts/pdf_outline_extractor.py document.pdf output.json --stdout
```

## Output Format

The script outputs a JSON structure compatible with the PDF-Outline-Extractor format:

```json
{
  "title": "Document Title",
  "outline": [
    {
      "level": "H1",
      "text": "Introduction",
      "page": 1
    },
    {
      "level": "H2",
      "text": "Background",
      "page": 2
    },
    {
      "level": "H2",
      "text": "Methodology",
      "page": 3
    },
    {
      "level": "H3",
      "text": "Data Collection",
      "page": 4
    }
  ]
}
```

### Output Fields

- **title**: The document title (extracted from document metadata or first suitable text)
- **outline**: Array of heading objects
  - **level**: Heading level (H1, H2, H3, H4)
  - **text**: The heading text content
  - **page**: Page number (1-based) where the heading appears

## Features

The PDF outline extractor provides:

- **Advanced PDF Understanding**: Uses Docling's layout analysis and document structure recognition
- **Hierarchical Structure Detection**: Identifies title and heading levels (H1-H4)
- **Multiple Input Sources**: Support for local files and URLs
- **Compatible Output Format**: JSON structure compatible with PDF-Outline-Extractor
- **Intelligent Heading Detection**: Pattern-based and heuristic heading identification
- **Page Number Extraction**: Accurate page numbering from document provenance
- **Error Handling**: Graceful handling of processing errors with informative messages
- **Logging**: Configurable logging levels for debugging and monitoring

## How It Works

The PDF outline extractor uses a multi-step process:

1. **PDF Conversion**: Converts the PDF to a structured DoclingDocument using the existing `pdf_to_markdown.py` infrastructure
2. **Title Extraction**: Identifies the document title from:
   - Document metadata/description
   - TitleItem elements (if available)
   - First suitable text item using heuristics
3. **Outline Extraction**: Identifies headings through:
   - SectionHeaderItem elements (if available)
   - Pattern-based detection (numbered sections, common heading words)
   - Text characteristics (length, formatting, position)
4. **Level Classification**: Determines heading levels (H1-H4) based on:
   - Numbering patterns (1., 1.1, 1.1.1, etc.)
   - Common section words (Chapter, Abstract, Introduction, etc.)
   - Text characteristics and document structure
5. **Page Number Assignment**: Extracts page numbers from document provenance information

## Examples

### Converting Academic Papers

```bash
# Extract outline from arXiv paper
python scripts/pdf_outline_extractor.py https://arxiv.org/pdf/2408.09869 paper_outline.json

# Extract outline with verbose logging
python scripts/pdf_outline_extractor.py research_paper.pdf outline.json --verbose
```

### Batch Processing

You can use the script in a loop to process multiple files:

```bash
# Process multiple PDFs
for pdf in *.pdf; do
    python scripts/pdf_outline_extractor.py "$pdf" "${pdf%.pdf}_outline.json"
done
```

### Integration with LangExtract

After extracting PDF outlines, you can use the structure information with LangExtract's other capabilities:

```python
import json
import langextract as lx

# Load the extracted outline
with open('document_outline.json', 'r') as f:
    outline_data = json.load(f)

# Use outline structure for targeted extraction
for item in outline_data['outline']:
    if item['level'] == 'H1':
        print(f"Major section: {item['text']} (page {item['page']})")
```

### Working with the Python API

You can also use the outline extractor programmatically:

```python
from scripts.pdf_outline_extractor import extract_pdf_outline

# Extract outline from PDF
outline_data = extract_pdf_outline("document.pdf", verbose=True)

# Access title and outline
title = outline_data['title']
outline = outline_data['outline']

print(f"Document: {title}")
for item in outline:
    level = item['level']
    text = item['text']
    page = item['page']
    print(f"{level}: {text} (page {page})")
```

## Error Handling

The script provides comprehensive error handling:

- **Missing Dependencies**: Clear error messages when docling is not installed
- **Invalid PDFs**: Graceful handling of corrupted or unsupported PDF files
- **Network Issues**: Proper error reporting for URL-based inputs
- **File I/O Errors**: Informative messages for file access problems

## Performance Considerations

- **Processing Time**: Depends on PDF complexity and size; typically 10-30 seconds for academic papers
- **Memory Usage**: Moderate memory requirements due to Docling's document processing
- **Accuracy**: High accuracy for well-structured documents with clear heading hierarchies

## Troubleshooting

### Common Issues

1. **"No module named 'docling'"**: Install the docling dependency
   ```bash
   pip install "langextract[docling]"
   ```

2. **Empty outline results**: The PDF may lack clear hierarchical structure or use non-standard formatting

3. **Incorrect heading levels**: The heuristics may need adjustment for specific document types

### Debug Mode

Use verbose logging to diagnose issues:

```bash
python scripts/pdf_outline_extractor.py document.pdf outline.json --verbose
```

## Limitations

- **Document Types**: Optimized for structured documents (academic papers, reports, manuals)
- **Language Support**: Best performance with English documents, though other languages are supported
- **Complex Layouts**: May struggle with highly complex or non-standard document layouts
- **Graphics-heavy Documents**: Performance may vary for documents with extensive graphics or unusual formatting

## Contributing

When contributing improvements to the PDF outline extractor:

1. **Test Coverage**: Ensure comprehensive tests for new functionality
2. **Documentation**: Update this documentation for any API changes
3. **Compatibility**: Maintain compatibility with the existing PDF-Outline-Extractor JSON format
4. **Performance**: Consider impact on processing time and memory usage
5. **Error Handling**: Provide informative error messages for new failure modes

## See Also

- [PDF to Markdown Conversion](pdf_to_markdown.md) - Related PDF processing functionality
- [Docling Hierarchical Chunking](docling_hierarchical_chunking.md) - Document structure analysis
- [PDF-Outline-Extractor](https://github.com/itshivams/PDF-Outline-Extractor/) - Reference implementation