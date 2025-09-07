# Docling Hierarchical Chunking Integration

This document describes the integration of docling hierarchical chunking into the lxRunnerExtraction pipeline.

## Overview

The lxRunnerExtraction pipeline has been updated to use docling's hierarchical chunker instead of the previous manual section-based chunking. This change provides:

- **Better document structure preservation**: Docling's native understanding of document hierarchies
- **Improved metadata extraction**: Rich metadata from docling's document processing
- **Enhanced parent-child relationships**: Proper hierarchical relationships derived from document structure
- **Robust formatting handling**: Better handling of delimiters and document formatting

## Implementation Details

### Key Components

1. **`docling_integration.py`** - Main integration module that bridges docling hierarchical chunker with lxRunnerExtraction
2. **Updated `lxRunnerExtraction.py`** - Modified to use docling chunking instead of section chunking
3. **Test coverage** - Comprehensive tests for the integration

### Integration Flow

```
Input Text → DoclingDocument → Hierarchical Chunker → BaseChunk[] → SectionChunk[] → lx.extract()
```

1. **Text to DoclingDocument**: Convert plain text to DoclingDocument format
2. **Hierarchical Chunking**: Use docling's HierarchicalChunker to create BaseChunk objects
3. **Format Conversion**: Convert BaseChunk objects to SectionChunk format for compatibility
4. **Metadata Preservation**: Extract and preserve hierarchical metadata while sending only text to lx.extract
5. **Parent-Child Relationships**: Establish relationships based on document structure

### Key Functions

#### `create_docling_hierarchical_chunks(text: str) -> List[SectionChunk]`
Main entry point that replaces `create_section_chunks`. Creates hierarchical chunks from input text using docling.

#### `get_docling_hierarchical_statistics(chunks: List[SectionChunk]) -> Dict[str, Any]`
Replacement for `get_section_statistics`. Provides statistics about the hierarchical chunks.

#### `convert_docling_chunk_to_section_chunk(docling_chunk, chunk_index, text_start_pos) -> SectionChunk`
Converts docling BaseChunk objects to SectionChunk format while preserving metadata.

#### `establish_parent_child_relationships(chunks: List[SectionChunk]) -> None`
Establishes parent-child relationships based on hierarchical levels.

### Metadata Preservation

The integration preserves rich metadata from docling chunks:

- **Hierarchical structure**: Section levels and parent-child relationships
- **Document items**: References to original document elements  
- **Headings context**: All parent headings for hierarchical context
- **Origin information**: Source document metadata
- **Processing metadata**: Information about the chunking process

### Compatibility

The integration maintains full compatibility with the existing lxRunnerExtraction pipeline:

- **Same interface**: Functions have the same signatures as the original section chunker
- **Same data structures**: Uses existing SectionChunk and SectionMetadata classes
- **Backward compatibility**: Graceful fallback when docling is not available
- **Drop-in replacement**: No changes needed to calling code

## Usage

The integration is automatically used when lxRunnerExtraction.py runs. No configuration changes are required.

### Dependencies

The integration requires docling-core:
```bash
pip install docling-core
```

If docling-core is not available, the system gracefully falls back to simple paragraph-based chunking.

### Example Output

For a markdown document with headers:

```markdown
# Document Title
Content...

## Section 1
Content...

### Subsection 1.1
Content...
```

The hierarchical chunker produces:
- Chunk 1: "Document Title" (Level 1)
- Chunk 2: "Section 1" (Level 2, Parent: Chunk 1)  
- Chunk 3: "Subsection 1.1" (Level 3, Parent: Chunk 2)

## Testing

Comprehensive test coverage includes:

- **Integration tests**: Verify the integration works with various text formats
- **Metadata tests**: Ensure metadata is properly preserved and extracted
- **Hierarchy tests**: Validate parent-child relationships
- **Fallback tests**: Test graceful fallback when docling is unavailable
- **Edge case tests**: Handle empty text, malformed documents, etc.

Run tests with:
```bash
python -m pytest test_docling_integration.py -v
```

## Benefits

1. **Improved accuracy**: Better understanding of document structure
2. **Rich metadata**: More detailed chunk metadata for better processing
3. **Hierarchical awareness**: Proper parent-child relationships
4. **Format handling**: Better handling of various document formats and delimiters
5. **Extensibility**: Easy to extend with additional docling features

## Migration Notes

- No breaking changes to existing API
- Same function names and signatures
- Enhanced output with richer metadata
- Improved hierarchical structure detection
- Better handling of complex document formats

## Future Enhancements

Potential future improvements:
- Support for table chunking
- Image and figure handling
- Custom chunking strategies
- Integration with other docling features
- Performance optimizations