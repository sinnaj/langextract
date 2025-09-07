# Docling Hierarchical Chunking

This document describes how to use the Docling hierarchical chunking functionality in LangExtract.

## Overview

LangExtract includes a script that utilizes [Docling's hierarchical chunking capabilities](https://docling-project.github.io/docling/concepts/chunking/#hierarchical-chunker) to break down DoclingDocument objects into semantically meaningful chunks while preserving document structure and hierarchy.

The hierarchical chunker creates one chunk for each individual detected document element, merging list items by default, and attaches all relevant document metadata including headers and captions.

## Installation

To use the hierarchical chunking feature, you need to install LangExtract with the docling optional dependency:

```bash
pip install "langextract[docling]"
```

Alternatively, if you have LangExtract already installed, you can install docling separately:

```bash
pip install docling-core
```

For PDF processing capabilities, install the full docling package:

```bash
pip install docling
```

## Usage

The hierarchical chunking script can be used in several ways:

### Basic Usage

```bash
# Chunk a DoclingDocument JSON file
python scripts/docling_hierarchical_chunker.py document.json

# Chunk and save to file
python scripts/docling_hierarchical_chunker.py document.json chunks.json

# Chunk a YAML DoclingDocument
python scripts/docling_hierarchical_chunker.py document.yaml chunks.yaml
```

### PDF Input

The script can directly process PDF files by first converting them to DoclingDocument format:

```bash
# Process PDF directly
python scripts/docling_hierarchical_chunker.py document.pdf chunks.json

# With verbose logging
python scripts/docling_hierarchical_chunker.py document.pdf chunks.json --verbose
```

### Test Mode

For demonstration and testing purposes, the script includes a built-in test mode:

```bash
# Run with test document
python scripts/docling_hierarchical_chunker.py --test

# Save test results to file
python scripts/docling_hierarchical_chunker.py --test dummy output.json
```

### Advanced Options

```bash
# Don't merge list items (default is to merge them)
python scripts/docling_hierarchical_chunker.py document.json --no-merge-lists

# Use custom delimiter for chunk separation
python scripts/docling_hierarchical_chunker.py document.json --delimiter "\\n---\\n"

# Force output format
python scripts/docling_hierarchical_chunker.py document.json output.txt --format yaml
```

## Features

The hierarchical chunking script provides:

- **Document Structure Preservation**: Maintains hierarchical relationships between document elements
- **Multiple Input Formats**: Supports DoclingDocument JSON/YAML files and direct PDF processing
- **Flexible Output**: JSON or YAML output with comprehensive metadata
- **Configurable Options**: Control list merging behavior and chunk delimiters
- **Rich Metadata**: Each chunk includes document structure information, headings context, and provenance data
- **Error Handling**: Graceful handling of processing errors with informative messages
- **Test Mode**: Built-in test document for demonstration and validation

## Output Format

The script outputs a structured JSON/YAML format containing:

```json
{
  "metadata": {
    "total_chunks": 3,
    "chunking_method": "hierarchical",
    "chunker": "docling_hierarchical_chunker"
  },
  "chunks": [
    {
      "chunk_id": 1,
      "text": "Chunk text content...",
      "metadata": {
        "schema_name": "docling_core.transforms.chunker.DocMeta",
        "version": "1.0.0",
        "doc_items": [...],
        "headings": ["Document Title", "Section Header"],
        "captions": null,
        "origin": null
      }
    }
  ]
}
```

### Chunk Metadata

Each chunk includes rich metadata:

- **doc_items**: References to original document elements
- **headings**: Hierarchical context of all parent headings
- **captions**: Associated captions (if any)
- **origin**: Provenance information
- **chunk_id**: Sequential identifier for the chunk

## Examples

### Working with Generated Chunks

```python
import json

# Load chunked results
with open('chunks.json', 'r') as f:
    data = json.load(f)

# Access chunks
chunks = data['chunks']
print(f"Generated {data['metadata']['total_chunks']} chunks")

# Process each chunk
for chunk in chunks:
    print(f"Chunk {chunk['chunk_id']}: {chunk['text'][:50]}...")
    print(f"Headings context: {chunk['metadata'].get('headings', [])}")
    print("---")
```

### Integration with Document Processing Pipeline

```python
from scripts.pdf_to_markdown import convert_pdf_to_markdown
from scripts.docling_hierarchical_chunker import perform_hierarchical_chunking

# Convert PDF to DoclingDocument
doc = convert_pdf_to_markdown("document.pdf", output_format="docling")

# Perform hierarchical chunking
chunks = perform_hierarchical_chunking(doc)

# Process chunks
for chunk in chunks:
    # Access chunk text
    text = chunk.text
    
    # Access metadata
    headings = chunk.meta.headings if chunk.meta else []
    doc_items = chunk.meta.doc_items if chunk.meta else []
    
    # Further processing...
```

## Performance Considerations

- **Memory Usage**: Large documents may require significant memory for processing
- **Processing Time**: PDF conversion adds processing overhead compared to pre-converted DoclingDocument files
- **Chunk Size**: The number of chunks depends on document structure; heavily structured documents produce more chunks

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure docling-core is installed
   ```bash
   pip install docling-core
   ```

2. **PDF Processing Errors**: For PDF input, install the full docling package
   ```bash
   pip install docling
   ```

3. **Memory Issues**: For very large documents, consider processing in smaller sections

4. **Validation Errors**: Ensure DoclingDocument files are properly formatted according to the Docling schema

### Debug Mode

Use verbose logging to diagnose issues:

```bash
python scripts/docling_hierarchical_chunker.py document.pdf --verbose
```

## Contributing

When contributing improvements to the hierarchical chunking functionality:

1. Test with various document types and sizes
2. Ensure backward compatibility with existing DoclingDocument formats
3. Add appropriate error handling for edge cases
4. Update documentation for new features

---

> **Note**: This hierarchical chunking approach complements the existing section-based chunking in LangExtract, providing an alternative that leverages Docling's native understanding of document structure.