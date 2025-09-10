#!/usr/bin/env python3
"""
Docling Hierarchical Chunking Script

This script performs chunking on a DoclingDocument using either Docling's
native HierarchicalChunker or a custom level 1 section-based chunking approach.
It can work with DoclingDocument files (JSON/YAML) or directly convert PDF files first.

Usage:
    python docling_hierarchical_chunker.py input.json [output.json]
    python docling_hierarchical_chunker.py input.yaml [output.yaml] 
    python docling_hierarchical_chunker.py input.pdf [output.json]
    python docling_hierarchical_chunker.py input.json --level1-sections [output.json]
    python docling_hierarchical_chunker.py --help

Example:
    # Standard hierarchical chunking
    python docling_hierarchical_chunker.py document.json chunks.json
    
    # Level 1 section-based chunking (each chunk starts with a level 1 section header)
    python docling_hierarchical_chunker.py document.json chunks.json --level1-sections
    
    # PDF input with level 1 section chunking
    python docling_hierarchical_chunker.py document.pdf chunks.json --level1-sections --verbose
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Dict, List, Any, Optional, Union, TYPE_CHECKING
import yaml

if TYPE_CHECKING:
  from docling_core.types.doc import DoclingDocument
  from docling_core.transforms.chunker.base import BaseChunk


def setup_logging(verbose: bool = False) -> None:
  """Set up logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  )


def create_test_document() -> 'DoclingDocument':
  """
  Create a simple test DoclingDocument for demonstration purposes.
  
  Returns:
      DoclingDocument: A simple test document
  """
  from docling_core.types.doc import DoclingDocument, TextItem, TitleItem, SectionHeaderItem, GroupItem, RefItem
  from docling_core.types.doc.labels import DocItemLabel
  
  # Create simple text items
  texts = [
      TitleItem(
          self_ref="#/texts/0",
          parent=RefItem(cref="#/body"),
          text="Introduction to Hierarchical Chunking",
          prov=[],
          orig="Introduction to Hierarchical Chunking"
      ),
      TextItem(
          self_ref="#/texts/1",
          parent=RefItem(cref="#/body"),
          text="This document demonstrates how hierarchical chunking works with Docling. Each section will be processed as a separate chunk while preserving the document structure.",
          label=DocItemLabel.TEXT,
          prov=[],
          orig="This document demonstrates how hierarchical chunking works with Docling. Each section will be processed as a separate chunk while preserving the document structure."
      ),
      SectionHeaderItem(
          self_ref="#/texts/2",
          parent=RefItem(cref="#/body"),
          text="Benefits of Hierarchical Chunking",
          prov=[],
          orig="Benefits of Hierarchical Chunking"
      ),
      TextItem(
          self_ref="#/texts/3",
          parent=RefItem(cref="#/body"),
          text="Hierarchical chunking preserves document structure, maintains context between related elements, and enables more intelligent processing of document content.",
          label=DocItemLabel.TEXT, 
          prov=[],
          orig="Hierarchical chunking preserves document structure, maintains context between related elements, and enables more intelligent processing of document content."
      ),
      SectionHeaderItem(
          self_ref="#/texts/4",
          parent=RefItem(cref="#/body"),
          text="Implementation Details",
          prov=[],
          orig="Implementation Details"
      ),
      TextItem(
          self_ref="#/texts/5",
          parent=RefItem(cref="#/body"),
          text="The implementation uses Docling's native HierarchicalChunker which operates directly on the DoclingDocument structure to create semantically meaningful chunks.",
          label=DocItemLabel.TEXT,
          prov=[],
          orig="The implementation uses Docling's native HierarchicalChunker which operates directly on the DoclingDocument structure to create semantically meaningful chunks."
      )
  ]
  
  # Create document structure
  document = DoclingDocument(
      name="hierarchical_chunking_test",
      description={"title": "Hierarchical Chunking Test Document"},
      texts=texts,
      tables=[],
      pictures=[],
      key_value_items=[],
      body=GroupItem(
          self_ref="#/body",
          children=[RefItem(cref=f"#/texts/{i}") for i in range(len(texts))]
      ),
      furniture=GroupItem(
          self_ref="#/furniture", 
          children=[]
      ),
      groups=[]
  )
  
  return document


def load_docling_document(source: Union[str, Path]) -> 'DoclingDocument':
  """
  Load a DoclingDocument from a JSON/YAML file or convert from PDF.

  Args:
      source: Path to the DoclingDocument file (JSON/YAML) or PDF file

  Returns:
      DoclingDocument object

  Raises:
      ImportError: If docling-core is not installed
      FileNotFoundError: If the source file doesn't exist
      ValueError: If the file format is not supported or invalid
  """
  try:
    from docling_core.types.doc import DoclingDocument
  except ImportError as e:
    raise ImportError(
        'docling-core is required for hierarchical chunking. '
        "Install with: pip install 'docling-core'"
    ) from e

  source_path = Path(source)
  if not source_path.exists():
    raise FileNotFoundError(f'Source file not found: {source}')

  logger = logging.getLogger(__name__)
  logger.info('Loading DoclingDocument from: %s', source_path)

  try:
    # Handle PDF files by converting them first
    if source_path.suffix.lower() == '.pdf':
      try:
        from scripts.pdf_to_markdown import convert_pdf_to_markdown
        logger.info('Converting PDF to DoclingDocument...')
        document = convert_pdf_to_markdown(source_path, output_format='docling')
        logger.info('PDF conversion completed successfully')
        return document
      except ImportError:
        raise ImportError(
            'PDF conversion requires the full docling package. '
            "Install with: pip install 'langextract[docling]'"
        )
    
    # Read file content for JSON/YAML
    content = source_path.read_text(encoding='utf-8')
    
    # Parse based on file extension
    if source_path.suffix.lower() == '.json':
      data = json.loads(content)
    elif source_path.suffix.lower() in ['.yaml', '.yml']:
      data = yaml.safe_load(content)
    else:
      # Try JSON first, then YAML
      try:
        data = json.loads(content)
      except json.JSONDecodeError:
        try:
          data = yaml.safe_load(content)
        except yaml.YAMLError as yaml_err:
          raise ValueError(
              f'Unable to parse file as JSON or YAML: {yaml_err}'
          ) from yaml_err

    # Create DoclingDocument from parsed data
    if isinstance(data, dict):
      document = DoclingDocument.model_validate(data)
    else:
      raise ValueError(
          'File content must be a JSON object or YAML mapping'
      )

    logger.info('DoclingDocument loaded successfully')
    return document

  except Exception as e:
    logger.error('Failed to load DoclingDocument: %s', e)
    raise


def perform_hierarchical_chunking(
    document: 'DoclingDocument',
    merge_list_items: bool = True,
    delim: str = '\n\n'
) -> List['BaseChunk']:
  """
  Perform hierarchical chunking on a DoclingDocument.

  Args:
      document: The DoclingDocument to chunk
      merge_list_items: Whether to merge list items together (default: True)
      delim: Delimiter to use for chunk separation (default: '\n\n')

  Returns:
      List of BaseChunk objects

  Raises:
      ImportError: If docling-core is not installed
  """
  try:
    from docling_core.transforms.chunker.hierarchical_chunker import HierarchicalChunker
  except ImportError as e:
    raise ImportError(
        'docling-core is required for hierarchical chunking. '
        "Install with: pip install 'docling-core'"
    ) from e

  logger = logging.getLogger(__name__)
  logger.info('Performing hierarchical chunking...')

  # Initialize the hierarchical chunker
  chunker = HierarchicalChunker(
      merge_list_items=merge_list_items,
      delim=delim
  )

  # Perform chunking
  chunks = list(chunker.chunk(document))

  logger.info('Hierarchical chunking completed. Generated %d chunks', len(chunks))
  return chunks


def perform_level1_section_chunking(
    document: 'DoclingDocument',
    delim: str = '\n\n'
) -> List[Dict[str, Any]]:
  """
  Perform level 1 section-based chunking on a DoclingDocument.
  
  Each chunk will start with a level 1 section header and include all content
  until the next level 1 section header.

  Args:
      document: The DoclingDocument to chunk
      delim: Delimiter to use for joining content (default: '\n\n')

  Returns:
      List of chunk dictionaries

  Raises:
      ImportError: If docling-core is not installed
  """
  logger = logging.getLogger(__name__)
  logger.info('Performing level 1 section chunking...')

  texts = document.texts
  if not texts:
    logger.warning('Document has no texts to chunk')
    return []

  # Find all level 1 section headers
  level1_indices = []
  for i, text_item in enumerate(texts):
    if (hasattr(text_item, 'label') and text_item.label == 'section_header' and
        hasattr(text_item, 'level') and text_item.level == 1):
      level1_indices.append(i)

  if not level1_indices:
    logger.warning('No level 1 section headers found in document')
    return []

  logger.info('Found %d level 1 section headers', len(level1_indices))

  chunks = []
  for i, start_idx in enumerate(level1_indices):
    # Determine end index (next level 1 header or end of texts)
    end_idx = level1_indices[i + 1] if i + 1 < len(level1_indices) else len(texts)
    
    # Collect all content for this section
    section_texts = []
    section_doc_items = []
    section_header_text = ""
    
    for j in range(start_idx, end_idx):
      text_item = texts[j]
      
      # Get the text content
      if hasattr(text_item, 'text') and text_item.text:
        section_texts.append(text_item.text)
      elif hasattr(text_item, 'orig') and text_item.orig:
        section_texts.append(text_item.orig)
      
      # Store the header text for the first item (which should be the level 1 header)
      if j == start_idx and hasattr(text_item, 'text'):
        section_header_text = text_item.text
      
      # Collect doc items for metadata
      try:
        # Convert text item to dict format for doc_items
        doc_item = {}
        if hasattr(text_item, 'self_ref'):
          doc_item['self_ref'] = text_item.self_ref
        if hasattr(text_item, 'parent'):
          if hasattr(text_item.parent, 'cref'):
            doc_item['parent'] = {'cref': text_item.parent.cref}
          else:
            doc_item['parent'] = {'cref': str(text_item.parent)}
        if hasattr(text_item, 'children'):
          doc_item['children'] = []
        if hasattr(text_item, 'content_layer'):
          doc_item['content_layer'] = text_item.content_layer
        if hasattr(text_item, 'label'):
          doc_item['label'] = text_item.label
        if hasattr(text_item, 'prov'):
          # Handle prov items carefully - they may contain non-serializable objects
          prov_items = []
          if text_item.prov:
            for prov_item in text_item.prov:
              try:
                if hasattr(prov_item, 'model_dump'):
                  prov_items.append(prov_item.model_dump())
                elif hasattr(prov_item, 'dict'):
                  prov_items.append(prov_item.dict())
                else:
                  # Try to extract basic attributes
                  prov_dict = {}
                  if hasattr(prov_item, 'page_no'):
                    prov_dict['page_no'] = prov_item.page_no
                  if hasattr(prov_item, 'bbox'):
                    if hasattr(prov_item.bbox, 'model_dump'):
                      prov_dict['bbox'] = prov_item.bbox.model_dump()
                    elif hasattr(prov_item.bbox, 'dict'):
                      prov_dict['bbox'] = prov_item.bbox.dict()
                    else:
                      prov_dict['bbox'] = str(prov_item.bbox)
                  if hasattr(prov_item, 'charspan'):
                    prov_dict['charspan'] = list(prov_item.charspan)
                  prov_items.append(prov_dict)
              except Exception as e:
                logger.debug('Could not serialize prov item: %s', e)
          doc_item['prov'] = prov_items
        
        section_doc_items.append(doc_item)
      except Exception as e:
        logger.debug('Could not process doc_item for text %d: %s', j, e)
    
    # Create chunk
    if section_texts:
      chunk_text = delim.join(section_texts)
      
      # Create metadata
      metadata = {
        'schema_name': 'docling_core.transforms.chunker.DocMeta',
        'version': '1.0.0',
        'doc_items': section_doc_items,
        'headings': [section_header_text] if section_header_text else [],
        'captions': None,
        'origin': document.origin.model_dump() if hasattr(document, 'origin') and document.origin else None
      }
      
      chunk = {
        'chunk_id': len(chunks) + 1,
        'text': chunk_text,
        'metadata': metadata
      }
      
      chunks.append(chunk)
      logger.debug('Created chunk %d with %d text items (header: "%s")', 
                  len(chunks), end_idx - start_idx, section_header_text[:50])

  logger.info('Level 1 section chunking completed. Generated %d chunks', len(chunks))
  return chunks


def chunks_to_dict(chunks: List['BaseChunk']) -> List[Dict[str, Any]]:
  """
  Convert BaseChunk objects to dictionary representation.

  Args:
      chunks: List of BaseChunk objects

  Returns:
      List of dictionaries containing chunk data
  """
  chunk_dicts = []
  
  for i, chunk in enumerate(chunks):
    chunk_dict = {
        'chunk_id': i + 1,
        'text': chunk.text,
        'metadata': {}
    }
    
    # Add metadata if available
    if hasattr(chunk, 'meta') and chunk.meta:
      try:
        if hasattr(chunk.meta, 'model_dump'):
          chunk_dict['metadata'] = chunk.meta.model_dump()
        elif hasattr(chunk.meta, 'dict'):
          chunk_dict['metadata'] = chunk.meta.dict()
        else:
          chunk_dict['metadata'] = str(chunk.meta)
      except Exception:
        chunk_dict['metadata'] = str(chunk.meta)
      
    # Add page information if available
    if hasattr(chunk, 'page') and chunk.page is not None:
      chunk_dict['page'] = chunk.page
      
    # Add any other available attributes
    for attr in ['doc_items', 'headings', 'captions']:
      if hasattr(chunk, attr):
        value = getattr(chunk, attr)
        if value:
          try:
            # Try to serialize or convert to string
            if isinstance(value, (list, dict, str, int, float, bool)):
              chunk_dict[attr] = value
            elif hasattr(value, 'model_dump'):
              chunk_dict[attr] = value.model_dump()
            elif hasattr(value, 'dict'):
              chunk_dict[attr] = value.dict()
            else:
              chunk_dict[attr] = str(value)
          except Exception:
            chunk_dict[attr] = str(value)

    chunk_dicts.append(chunk_dict)

  return chunk_dicts


def save_chunks(
    chunks: List[Dict[str, Any]],
    output_path: Optional[Union[str, Path]] = None,
    format_type: Optional[str] = None,
    chunking_method: str = 'hierarchical'
) -> None:
  """
  Save chunks to a file or print to stdout.

  Args:
      chunks: List of chunk dictionaries
      output_path: Optional output file path
      format_type: Output format ('json' or 'yaml'), auto-detected if None
      chunking_method: The chunking method used ('hierarchical' or 'level1_sections')
  """
  logger = logging.getLogger(__name__)

  # Prepare output data
  output_data = {
      'metadata': {
          'total_chunks': len(chunks),
          'chunking_method': chunking_method,
          'chunker': 'docling_hierarchical_chunker'
      },
      'chunks': chunks
  }

  if output_path:
    output_file = Path(output_path)
    
    # Determine format
    if format_type is None:
      if output_file.suffix.lower() == '.yaml' or output_file.suffix.lower() == '.yml':
        format_type = 'yaml'
      else:
        format_type = 'json'

    # Save to file
    if format_type == 'yaml':
      with open(output_file, 'w', encoding='utf-8') as f:
        yaml.safe_dump(output_data, f, default_flow_style=False, indent=2)
    else:
      with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    logger.info('Chunks saved to: %s', output_file)
  else:
    # Print to stdout
    if format_type == 'yaml':
      yaml.safe_dump(output_data, sys.stdout, default_flow_style=False, indent=2)
    else:
      json.dump(output_data, sys.stdout, indent=2, ensure_ascii=False)
      print()  # Add newline at end


def main() -> None:
  """Main command-line interface."""
  parser = argparse.ArgumentParser(
      description=(
          'Perform chunking on a DoclingDocument using either Docling\'s '
          'native HierarchicalChunker or level 1 section-based chunking'
      ),
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog=__doc__,
  )

  parser.add_argument(
      'input',
      nargs='?',
      help='Path to input file (DoclingDocument JSON/YAML or PDF). Not required if --test is used.'
  )

  parser.add_argument(
      'output',
      nargs='?',
      help='Output file path (optional, prints to stdout if not provided)'
  )

  parser.add_argument(
      '-v', '--verbose',
      action='store_true',
      help='Enable verbose logging'
  )

  parser.add_argument(
      '--format',
      choices=['json', 'yaml'],
      help='Output format (auto-detected from file extension if not specified)'
  )

  parser.add_argument(
      '--no-merge-lists',
      action='store_true',
      help='Do not merge list items together (default: merge list items)'
  )

  parser.add_argument(
      '--delimiter',
      default='\n\n',
      help='Delimiter to use for chunk separation (default: "\\n\\n")'
  )

  parser.add_argument(
      '--test',
      action='store_true',
      help='Run with a built-in test document instead of loading from file'
  )

  parser.add_argument(
      '--level1-sections',
      action='store_true',
      help='Chunk by level 1 section headers (each chunk starts with a level 1 header and includes all content until the next level 1 header)'
  )

  args = parser.parse_args()

  setup_logging(args.verbose)
  logger = logging.getLogger(__name__)

  try:
    # Load or create the DoclingDocument
    if args.test:
      logger.info('Creating test DoclingDocument...')
      document = create_test_document()
    else:
      if not args.input:
        print('Error: input file required when not using --test mode', file=sys.stderr)
        sys.exit(1)
      document = load_docling_document(args.input)

    # Perform chunking based on method selected
    if args.level1_sections:
      # Use level 1 section-based chunking
      chunk_dicts = perform_level1_section_chunking(
          document,
          delim=args.delimiter
      )
    else:
      # Use hierarchical chunking (default)
      chunks = perform_hierarchical_chunking(
          document,
          merge_list_items=not args.no_merge_lists,
          delim=args.delimiter
      )
      # Convert chunks to dictionary format
      chunk_dicts = chunks_to_dict(chunks)

    # Save or print results
    chunking_method = 'level1_sections' if args.level1_sections else 'hierarchical'
    save_chunks(chunk_dicts, args.output, args.format, chunking_method)

    logger.info('Chunking completed successfully')

  except ImportError as e:
    print(f'Error: {e}', file=sys.stderr)
    print('Please install docling-core: pip install docling-core', file=sys.stderr)
    sys.exit(1)
  except Exception as e:
    logger.error('Hierarchical chunking failed: %s', e)
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()