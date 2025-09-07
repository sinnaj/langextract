# PDF to Markdown Conversion

This document describes how to use the PDF to Markdown conversion functionality in LangExtract.

## Overview

LangExtract includes a script that utilizes [Docling](https://github.com/DS4SD/docling) to parse PDF files and convert them to either Markdown format or preserve them as structured DoclingDocument objects. Docling is a powerful document understanding library that provides advanced PDF processing capabilities including layout analysis, table structure recognition, and more.

## Installation

To use the PDF to Markdown conversion feature, you need to install LangExtract with the docling optional dependency:

```bash
pip install "langextract[docling]"
```

Alternatively, if you have LangExtract already installed, you can install docling separately:

```bash
pip install docling
```

## Usage

### Command Line Interface

The PDF to Markdown conversion script is located at `scripts/pdf_to_markdown.py` and can be used from the command line:

```bash
# Convert a local PDF file to Markdown
python scripts/pdf_to_markdown.py input.pdf output.md

# Convert a PDF from URL to Markdown
python scripts/pdf_to_markdown.py https://example.com/document.pdf output.md

# Convert to DoclingDocument format (JSON)
python scripts/pdf_to_markdown.py input.pdf output.json --format docling

# Convert to DoclingDocument format (YAML)
python scripts/pdf_to_markdown.py input.pdf output.yaml --format docling

# Convert with verbose logging
python scripts/pdf_to_markdown.py input.pdf output.md --verbose

# Convert and print to stdout (no output file specified)
python scripts/pdf_to_markdown.py input.pdf

# Convert to DoclingDocument and print JSON to stdout
python scripts/pdf_to_markdown.py input.pdf --format docling
```

#### Command Line Options

- `input`: Path to PDF file or URL (required)
- `output`: Output file path (optional - if not specified, prints to stdout)
- `--format {markdown,docling}`: Output format - 'markdown' (default) or 'docling' for DoclingDocument
- `-v, --verbose`: Enable verbose logging
- `-h, --help`: Show help message

### Python API

You can also use the conversion function directly in your Python code:

```python
from scripts.pdf_to_markdown import convert_pdf_to_markdown

# Convert a PDF to Markdown
markdown_content = convert_pdf_to_markdown("document.pdf")
print(markdown_content)

# Convert and save to file
markdown_content = convert_pdf_to_markdown(
    "https://arxiv.org/pdf/2408.09869",
    "output.md",
    verbose=True
)

# Convert to DoclingDocument format
docling_document = convert_pdf_to_markdown(
    "document.pdf",
    "document.json",
    output_format="docling"
)

# Access structured data from DoclingDocument
print(f"Number of text items: {len(docling_document.texts)}")
print(f"Number of tables: {len(docling_document.tables)}")
print(f"Number of pictures: {len(docling_document.pictures)}")

# Convert DoclingDocument to other formats
markdown_content = docling_document.export_to_markdown()
html_content = docling_document.export_to_html()
plain_text = docling_document.export_to_text()
```

#### Function Parameters

```python
def convert_pdf_to_markdown(
    source: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    verbose: bool = False,
    output_format: Literal['markdown', 'docling'] = 'markdown',
) -> Union[str, DoclingDocument]:
```

- `source`: Path to PDF file or URL
- `output_path`: Optional output file path
- `verbose`: Enable verbose logging
- `output_format`: Output format - 'markdown' or 'docling'

**Returns:**
- `str`: Markdown content (when `output_format='markdown'`)
- `DoclingDocument`: Structured document object (when `output_format='docling'`)

## Features

The PDF converter powered by Docling provides:

- **Advanced PDF Understanding**: Layout analysis, reading order detection, table structure recognition
- **Multiple Output Formats**: 
  - Markdown for readable text format
  - DoclingDocument for structured data access with full document hierarchy
- **Multiple Input Sources**: Support for local files and URLs
- **High-Quality Output**: Structured content with proper formatting
- **Error Handling**: Graceful handling of conversion errors with informative messages
- **Logging**: Configurable logging levels for debugging and monitoring

## DoclingDocument Format

When using `--format docling`, the converter returns a structured `DoclingDocument` object that preserves:

- **Document Hierarchy**: Sections, groups, and reading order
- **Multiple Content Types**: Text, tables, pictures, key-value pairs
- **Layout Information**: Bounding boxes and positioning data
- **Provenance Information**: Tracking of content origins
- **Export Flexibility**: Convert to various formats (Markdown, HTML, text, JSON, YAML)

This structured format is ideal for:
- Advanced document processing pipelines
- Preserving document layout and structure
- Extracting specific content types (tables, images)
- Maintaining document hierarchy for AI processing

## Examples

### Converting Academic Papers

```bash
# Convert to Markdown
python scripts/pdf_to_markdown.py https://arxiv.org/pdf/2408.09869 docling_paper.md

# Convert to structured DoclingDocument
python scripts/pdf_to_markdown.py https://arxiv.org/pdf/2408.09869 docling_paper.json --format docling
```

### Batch Processing

You can use the script in a loop to process multiple files:

```bash
# Convert multiple PDFs to Markdown
for pdf in *.pdf; do
    python scripts/pdf_to_markdown.py "$pdf" "${pdf%.pdf}.md"
done

# Convert multiple PDFs to DoclingDocument format
for pdf in *.pdf; do
    python scripts/pdf_to_markdown.py "$pdf" "${pdf%.pdf}.json" --format docling
done
```

### Working with DoclingDocument

```python
from scripts.pdf_to_markdown import convert_pdf_to_markdown

# Convert to DoclingDocument
doc = convert_pdf_to_markdown("document.pdf", output_format="docling")

# Access structured content
print(f"Document has {len(doc.texts)} text items")
print(f"Document has {len(doc.tables)} tables")
print(f"Document has {len(doc.pictures)} pictures")

# Export to different formats
markdown = doc.export_to_markdown()
html = doc.export_to_html()
plain_text = doc.export_to_text()

# Save in different formats
doc.save_as_json("document.json")
doc.save_as_yaml("document.yaml")
doc.save_as_html("document.html")
```

### Integration with LangExtract

After converting PDFs to Markdown, you can use the resulting text with LangExtract's extraction capabilities:

```python
import langextract as lx
from scripts.pdf_to_markdown import convert_pdf_to_markdown

# Convert PDF to Markdown
markdown_content = convert_pdf_to_markdown("document.pdf")

# Use with LangExtract
result = lx.extract(
    text_or_documents=markdown_content,
    prompt_description="Extract key findings and conclusions",
    examples=[],
    model_id="gemini-2.5-flash"
)
```

## Error Handling

The script includes comprehensive error handling:

1. **Missing Dependencies**: Clear error message if docling is not installed
2. **File Not Found**: Informative error for missing input files
3. **Network Issues**: Proper handling of URL download failures
4. **Conversion Errors**: Graceful handling of PDF parsing failures

## Performance Considerations

- **First Run**: Initial model downloads may take several minutes
- **Hardware**: Runs efficiently on CPU, GPU acceleration supported if available
- **Memory**: Memory usage depends on PDF size and complexity
- **Processing Time**: Typically 30-60 seconds for academic papers

## Troubleshooting

### Common Issues

1. **ImportError: docling not found**
   - Solution: Install with `pip install "langextract[docling]"`

2. **Slow processing on first run**
   - This is expected as models are downloaded and cached

3. **Network timeout for URLs**
   - Try downloading the PDF locally first

4. **Poor quality output**
   - Some PDFs may have complex layouts that are challenging to parse
   - Try the `--verbose` flag to see detailed processing information

## Limitations

- Works best with text-based PDFs; scanned PDFs require OCR which may take longer
- Very large PDFs (>100 pages) may take significant time to process
- Complex layouts with unusual formatting may not convert perfectly

## Contributing

To contribute improvements to the PDF to Markdown conversion:

1. Follow the existing code style and patterns
2. Add tests for new functionality
3. Update documentation as needed
4. Consider backward compatibility