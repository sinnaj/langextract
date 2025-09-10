# DoclingDocument to Markdown Conversion

This document describes how to use the DoclingDocument to Markdown conversion functionality in LangExtract.

## Overview

LangExtract includes a script that converts existing DoclingDocument files (in JSON or YAML format) to Markdown. This script complements the `pdf_to_markdown.py` script and is useful when you already have DoclingDocument files that were previously saved and want to convert them to Markdown format.

## Installation

To use the DoclingDocument to Markdown conversion feature, you need to install LangExtract with the docling optional dependency:

```bash
pip install "langextract[docling]"
```

Alternatively, if you have LangExtract already installed, you can install docling separately:

```bash
pip install docling
```

## Usage

### Command Line Interface

The DoclingDocument to Markdown conversion script is located at `scripts/docling_to_markdown.py` and can be used from the command line:

```bash
# Convert a DoclingDocument JSON file to Markdown
python scripts/docling_to_markdown.py document.json output.md

# Convert a DoclingDocument YAML file to Markdown
python scripts/docling_to_markdown.py document.yaml output.md

# Convert without specifying output file (prints to stdout)
python scripts/docling_to_markdown.py document.json

# Enable verbose logging
python scripts/docling_to_markdown.py document.json output.md -v
```

### File Format Support

The script automatically detects and supports:
- **JSON format**: DoclingDocument files saved as `.json`
- **YAML format**: DoclingDocument files saved as `.yaml` or `.yml`
- **Auto-detection**: For files without clear extensions, the script tries both JSON and YAML formats

### Workflow Integration

This script is designed to work seamlessly with the PDF to Markdown workflow:

```bash
# Step 1: Convert PDF to DoclingDocument
python scripts/pdf_to_markdown.py document.pdf document.json --format docling

# Step 2: Convert DoclingDocument to Markdown
python scripts/docling_to_markdown.py document.json converted.md
```

### Python API

You can also use the conversion function directly in your Python code:

```python
from scripts.docling_to_markdown import convert_docling_to_markdown

# Convert DoclingDocument file to Markdown
markdown_content = convert_docling_to_markdown(
    source="document.json",
    output_path="output.md",
    verbose=True
)

print(markdown_content)
```

## Error Handling

The script handles various error conditions:

- **Missing docling dependency**: Provides clear instructions for installation
- **File not found**: Reports when source files don't exist
- **Invalid format**: Handles files that are neither valid JSON nor YAML
- **Conversion errors**: Logs detailed error messages for troubleshooting

## Use Cases

This script is particularly useful for:

1. **Batch processing**: Converting multiple DoclingDocument files to Markdown
2. **Workflow separation**: Decoupling PDF parsing from Markdown generation
3. **Format conversion**: Converting between DoclingDocument formats (JSON/YAML) and Markdown
4. **Pipeline integration**: Using in automated document processing workflows

## Related Documentation

- [PDF to Markdown Conversion](pdf_to_markdown.md) - For converting PDFs directly to Markdown or DoclingDocument format
- [Docling Documentation](https://github.com/DS4SD/docling) - For more information about the underlying Docling library