# PDF to Markdown Conversion

This document describes how to use the PDF to Markdown conversion functionality in LangExtract.

## Overview

LangExtract includes a script that utilizes [Docling](https://github.com/DS4SD/docling) to parse PDF files and convert them to Markdown format. Docling is a powerful document understanding library that provides advanced PDF processing capabilities including layout analysis, table structure recognition, and more.

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
# Convert a local PDF file
python scripts/pdf_to_markdown.py input.pdf output.md

# Convert a PDF from URL
python scripts/pdf_to_markdown.py https://example.com/document.pdf output.md

# Convert with verbose logging
python scripts/pdf_to_markdown.py input.pdf output.md --verbose

# Convert and print to stdout (no output file specified)
python scripts/pdf_to_markdown.py input.pdf
```

#### Command Line Options

- `input`: Path to PDF file or URL (required)
- `output`: Output Markdown file path (optional - if not specified, prints to stdout)
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
```

## Features

The PDF to Markdown converter powered by Docling provides:

- **Advanced PDF Understanding**: Layout analysis, reading order detection, table structure recognition
- **Multiple Input Sources**: Support for local files and URLs
- **High-Quality Output**: Structured Markdown with proper formatting
- **Error Handling**: Graceful handling of conversion errors with informative messages
- **Logging**: Configurable logging levels for debugging and monitoring

## Examples

### Converting Academic Papers

```bash
# Convert the Docling technical report
python scripts/pdf_to_markdown.py https://arxiv.org/pdf/2408.09869 docling_paper.md
```

### Batch Processing

You can use the script in a loop to process multiple files:

```bash
for pdf in *.pdf; do
    python scripts/pdf_to_markdown.py "$pdf" "${pdf%.pdf}.md"
done
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