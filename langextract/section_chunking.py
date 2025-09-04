# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Library for breaking markdown documents into section-based chunks.

This module provides functionality to parse markdown documents and create
chunks based on section boundaries (headers) rather than character count.
Each chunk corresponds to a document section and includes metadata about
the section hierarchy.
"""

from collections.abc import Iterator
import dataclasses
import re
from typing import Optional

from langextract import chunking
from langextract.core import data
from langextract.core import tokenizer


@dataclasses.dataclass
class SectionMetadata:
  """Metadata for a document section.
  
  Attributes:
    section_id: Unique identifier for the section.
    section_name: Name/title of the section.
    section_level: Header level (1 for #, 2 for ##, etc.).
    parent_section_id: ID of the parent section (None for top-level).
    sub_sections: List of child section IDs.
    section_summary: Summary of the section content (to be filled by LangExtract).
  """
  section_id: str
  section_name: str
  section_level: int
  parent_section_id: Optional[str] = None
  sub_sections: list[str] = dataclasses.field(default_factory=list)
  section_summary: str = ""


@dataclasses.dataclass
class SectionChunk(chunking.TextChunk):
  """A TextChunk enhanced with section metadata.
  
  Extends the base TextChunk to include section-specific metadata
  while maintaining compatibility with existing extraction pipeline.
  """
  section_metadata: Optional[SectionMetadata] = None
  _section_text: Optional[str] = dataclasses.field(default=None, init=False, repr=False)
  
  @property
  def chunk_text(self) -> str:
    """Gets the section text directly for section chunks."""
    if self._section_text is not None:
      return self._section_text
    # Fall back to parent implementation if section text not set
    return super().chunk_text
  
  def set_section_text(self, section_text: str) -> None:
    """Sets the section text for this chunk."""
    self._section_text = section_text


def parse_markdown_sections(text: str) -> list[tuple[str, SectionMetadata, int, int]]:
  """Parse markdown text to identify sections and their boundaries.
  
  Args:
    text: The markdown text to parse.
    
  Returns:
    List of tuples (section_text, metadata, start_pos, end_pos) for each section.
  """
  lines = text.split('\n')
  sections = []
  current_section_lines = []
  current_metadata = None
  current_start_pos = 0
  section_stack = []  # Stack to track parent sections
  section_counter = 1
  
  for i, line in enumerate(lines):
    # Check if line is a header
    header_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
    
    if header_match:
      # Save previous section if exists
      if current_metadata is not None and current_section_lines:
        section_text = '\n'.join(current_section_lines)
        end_pos = current_start_pos + len(section_text)
        sections.append((section_text, current_metadata, current_start_pos, end_pos))
        current_start_pos = end_pos + 1  # +1 for newline
      
      # Parse new header
      header_level = len(header_match.group(1))
      section_title = header_match.group(2).strip()
      section_id = f"section_{section_counter:03d}"
      section_counter += 1
      
      # Update section stack for parent tracking
      # Remove sections at same or deeper level
      while section_stack and section_stack[-1][1] >= header_level:
        section_stack.pop()
      
      # Determine parent
      parent_id = section_stack[-1][0] if section_stack else None
      
      # Create metadata
      current_metadata = SectionMetadata(
          section_id=section_id,
          section_name=section_title,
          section_level=header_level,
          parent_section_id=parent_id
      )
      
      # Add to parent's sub_sections if applicable
      if parent_id:
        # Find parent in already processed sections and update its sub_sections
        for section_tuple in sections:
          _, meta, _, _ = section_tuple
          if meta.section_id == parent_id:
            meta.sub_sections.append(section_id)
            break
      
      # Add to stack
      section_stack.append((section_id, header_level))
      
      # Start new section with header line
      current_section_lines = [line]
    else:
      # Add line to current section
      if current_metadata is not None:
        current_section_lines.append(line)
      else:
        # Content before first header - create a default section
        if not sections and line.strip():
          current_metadata = SectionMetadata(
              section_id="section_000",
              section_name="Introduction",
              section_level=1
          )
          current_section_lines = [line]
        elif current_section_lines:
          current_section_lines.append(line)
  
  # Add final section
  if current_metadata is not None and current_section_lines:
    section_text = '\n'.join(current_section_lines)
    end_pos = current_start_pos + len(section_text)
    sections.append((section_text, current_metadata, current_start_pos, end_pos))
  
  return sections


class SectionChunkIterator:
  """Iterator that yields document chunks based on section boundaries."""
  
  def __init__(self, document: data.Document):
    """Initialize the section-based chunk iterator.
    
    Args:
      document: The document to chunk by sections.
    """
    self.document = document
    self.sections = parse_markdown_sections(document.text)
    self.current_index = 0
  
  def __iter__(self) -> Iterator[SectionChunk]:
    """Return iterator interface."""
    return self
  
  def __next__(self) -> SectionChunk:
    """Get the next section chunk."""
    if self.current_index >= len(self.sections):
      raise StopIteration
    
    section_text, metadata, start_pos, end_pos = self.sections[self.current_index]
    self.current_index += 1
    
    # Calculate approximate token positions for the section in the original document
    # This is used for metadata and alignment purposes
    original_text = self.document.text
    total_chars = len(original_text)
    total_tokens = len(self.document.tokenized_text.tokens)
    
    # Estimate token positions based on character positions
    # This is an approximation but sufficient for section boundaries
    if total_chars > 0:
      start_token = int((start_pos / total_chars) * total_tokens)
      end_token = int((end_pos / total_chars) * total_tokens)
    else:
      start_token = 0
      end_token = total_tokens
    
    # Ensure token positions are within bounds
    start_token = max(0, min(start_token, total_tokens))
    end_token = max(start_token, min(end_token, total_tokens))
    
    token_interval = tokenizer.TokenInterval(
        start_index=start_token,
        end_index=end_token
    )
    
    # Create SectionChunk with original document reference for ID consistency
    section_chunk = SectionChunk(
        token_interval=token_interval,
        document=self.document,  # Use original document to maintain ID consistency
        section_metadata=metadata
    )
    
    # Set the section-specific text
    section_chunk.set_section_text(section_text)
    
    return section_chunk


def section_document_chunk_iterator(
    documents: list[data.Document],
    use_section_chunking: bool = True
) -> Iterator[chunking.TextChunk]:
  """Iterate over documents yielding section-based chunks.
  
  Args:
    documents: List of documents to process.
    use_section_chunking: Whether to use section-based chunking.
    
  Yields:
    TextChunk objects for each section.
  """
  for document in documents:
    if use_section_chunking:
      # Use section-based chunking
      chunk_iter = SectionChunkIterator(document)
      yield from chunk_iter
    else:
      # Fall back to character-based chunking
      chunk_iter = chunking.ChunkIterator(
          text=document.tokenized_text,
          max_char_buffer=5000,  # Default fallback
          document=document,
      )
      yield from chunk_iter