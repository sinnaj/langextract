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

"""Docling heading hierarchy post-processor.

Infers true outline (H1/H2/H3/…) using numbering, "anchor" phrases, and layout
heuristics from DoclingDocument objects that mark many headers as level=1 only.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from statistics import median
from typing import Any, Iterable

import yaml


GAP_THRESHOLD: float = 18.0
ANCHOR_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*Secci[oó]n\s+SI\s*\d+\b", re.I),
    re.compile(r"^\s*Secci[oó]n\s+\d+\b", re.I),
    re.compile(r"^\s*Cap[ií]tulo\s+([IVXLCDM]+|\d+)\b", re.I),
    re.compile(r"^\s*T[ií]tulo\s+([A-Z]|\d+)\b", re.I),
    re.compile(r"^\s*Anexo\s+([A-Z]|\d+)\b", re.I),
    re.compile(r"^\s*Ap[eé]ndice\s+([A-Z]|\d+)\b", re.I),
]
NUM_DEPTHS: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"^\s*(\d+(?:\.\d+)+)\b"), lambda m: m.group(1).count(".") + 2),
    (re.compile(r"^\s*(\d+)\b"), lambda m: 2),
    (re.compile(r"^\s*([A-Z])\.\s*"), lambda m: 2),
    (re.compile(r"^\s*([IVXLCDM]+)\.\s*", re.I), lambda m: 2),
]


@dataclass
class OutlineHeading:
  """Represents a heading in the document outline with inferred level."""
  level: int
  text: str
  ref: str | None
  page_no: int | None
  bbox: tuple[float, float, float, float] | None
  signals: dict  # debug info


def _is_anchor(text: str) -> bool:
  """Check if text matches anchor patterns (Level 1)."""
  for pattern in ANCHOR_PATTERNS:
    if pattern.match(text):
      return True
  return False


def _numbering_level(text: str) -> int | None:
  """Get numbering-based level from text, or None if no numbering found."""
  for pattern, level_func in NUM_DEPTHS:
    match = pattern.match(text)
    if match:
      return level_func(match)
  return None


def _bbox_height(bbox: dict | None) -> float | None:
  """Extract height from bbox dict, handling various formats."""
  if not bbox:
    return None
  
  # Handle different bbox formats
  if isinstance(bbox, dict):
    if 'l' in bbox and 't' in bbox and 'r' in bbox and 'b' in bbox:
      return abs(bbox['t'] - bbox['b'])
    elif 'left' in bbox and 'top' in bbox and 'right' in bbox and 'bottom' in bbox:
      return abs(bbox['top'] - bbox['bottom'])
  elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
    # Assuming (l, t, r, b) format
    return abs(bbox[1] - bbox[3])
  
  return None


def _vertical_gap(curr: dict | None, nxt: dict | None) -> float:
  """Calculate vertical gap between current and next header."""
  if not curr or not nxt:
    return 9999.0  # Large sentinel for missing data
  
  curr_bbox = curr.get('bbox')
  next_bbox = nxt.get('bbox')
  
  if not curr_bbox or not next_bbox:
    return 9999.0
  
  # Check if they're on different pages
  curr_page = curr.get('page_no', -1)
  next_page = nxt.get('page_no', -1)
  if curr_page != next_page and curr_page != -1 and next_page != -1:
    return 9999.0
  
  # Calculate gap: next.top - current.bottom
  curr_bottom = None
  next_top = None
  
  if isinstance(curr_bbox, dict):
    curr_bottom = curr_bbox.get('b') or curr_bbox.get('bottom')
  elif isinstance(curr_bbox, (list, tuple)) and len(curr_bbox) == 4:
    curr_bottom = curr_bbox[3]  # assuming (l, t, r, b)
  
  if isinstance(next_bbox, dict):
    next_top = next_bbox.get('t') or next_bbox.get('top')
  elif isinstance(next_bbox, (list, tuple)) and len(next_bbox) == 4:
    next_top = next_bbox[1]  # assuming (l, t, r, b)
  
  if curr_bottom is not None and next_top is not None:
    return next_top - curr_bottom
  
  return 9999.0


def _collect_headers(doc: Any) -> list[dict]:
  """Return headers in reading order.
  
  Returns:
    List of dicts with keys: 'ref', 'text', 'page_no', 'bbox', 'node'
    Only includes items with label == 'section_header' under doc.body.
  """
  headers = []
  
  if not hasattr(doc, 'body') or not doc.body:
    return headers
  
  # Get texts by reference
  texts_by_ref = {}
  if hasattr(doc, 'texts') and doc.texts:
    for text_item in doc.texts:
      if hasattr(text_item, 'self_ref'):
        texts_by_ref[text_item.self_ref] = text_item
  
  # Process body children in order
  if hasattr(doc.body, 'children') and doc.body.children:
    for child_ref in doc.body.children:
      ref_str = None
      if hasattr(child_ref, '__dict__'):
        # Handle JsonDoc objects - look for $ref converted to _ref attribute or similar
        child_dict = child_ref.__dict__
        if '$ref' in child_dict:
          ref_str = child_dict['$ref']
        elif '_ref' in child_dict:
          ref_str = child_dict['_ref']
        elif 'ref' in child_dict:
          ref_str = child_dict['ref']
      elif hasattr(child_ref, 'cref'):
        ref_str = child_ref.cref
      elif isinstance(child_ref, dict):
        ref_str = child_ref.get('$ref') or child_ref.get('ref') or child_ref.get('_ref')
      elif isinstance(child_ref, str):
        ref_str = child_ref
      
      if ref_str and ref_str in texts_by_ref:
        text_item = texts_by_ref[ref_str]
        
        # Check if this is a section header
        is_section_header = False
        if hasattr(text_item, 'label'):
          # Handle various label formats
          label = text_item.label
          if hasattr(label, 'value'):
            is_section_header = label.value == 'section_header'
          elif isinstance(label, str):
            is_section_header = label == 'section_header'
          elif str(label) == 'section_header':
            is_section_header = True
        elif hasattr(text_item, '__class__') and 'SectionHeader' in text_item.__class__.__name__:
          is_section_header = True
        
        if is_section_header:
          # Extract text
          text = ''
          if hasattr(text_item, 'text'):
            text = text_item.text
          elif hasattr(text_item, 'orig'):
            text = text_item.orig
          
          # Extract page number
          page_no = None
          if hasattr(text_item, 'prov') and text_item.prov:
            for prov_item in text_item.prov:
              if hasattr(prov_item, 'page_no'):
                page_no = prov_item.page_no
                break
              elif hasattr(prov_item, 'page'):
                page_no = prov_item.page
                break
          
          # Extract bbox
          bbox = None
          if hasattr(text_item, 'prov') and text_item.prov:
            for prov_item in text_item.prov:
              if hasattr(prov_item, 'bbox'):
                bbox_data = prov_item.bbox
                if isinstance(bbox_data, dict):
                  bbox = bbox_data
                elif hasattr(bbox_data, '__dict__'):
                  bbox = bbox_data.__dict__
                break
          
          headers.append({
            'ref': ref_str,
            'text': text,
            'page_no': page_no,
            'bbox': bbox,
            'node': text_item
          })
  
  return headers


def infer_outline(doc: Any) -> list[OutlineHeading]:
  """Infer document outline from DoclingDocument.
  
  - Rank heights among candidates to obtain size_rank (1 = largest).
  - Propose levels via (A) anchor, (B) numbering, else (C) size/gap/shortness.
  - Enforce legal outline with a (level, idx) stack.
  - Populate signals for debugging.
  """
  headers = _collect_headers(doc)
  if not headers:
    return []
  
  # Step 1: Compute height rankings among headers
  heights = []
  for header in headers:
    height = _bbox_height(header['bbox'])
    if height is not None:
      heights.append(height)
  
  # Get unique heights and rank them (descending)
  unique_heights = sorted(set(heights), reverse=True)
  height_to_rank = {height: idx + 1 for idx, height in enumerate(unique_heights)}
  
  # Step 2: Propose initial levels and collect signals
  proposed_levels = []
  for i, header in enumerate(headers):
    text = header['text']
    signals = {}
    
    # Check anchor patterns (level 1)
    is_anchor = _is_anchor(text)
    signals['anchor'] = is_anchor
    if is_anchor:
      proposed_levels.append(1)
      header['signals'] = signals  # Make sure signals are stored
      continue
    
    # Check numbering patterns
    num_level = _numbering_level(text)
    signals['num_level'] = num_level
    if num_level is not None:
      proposed_levels.append(num_level)
      header['signals'] = signals  # Make sure signals are stored
      continue
    
    # Fallback to typography/layout
    height = _bbox_height(header['bbox'])
    size_rank = height_to_rank.get(height) if height is not None else None
    signals['size_rank'] = size_rank
    
    # Calculate gap to next header
    next_header = headers[i + 1] if i + 1 < len(headers) else None
    gap_to_next = _vertical_gap(header, next_header)
    signals['gap_to_next'] = gap_to_next
    
    # Determine level based on typography
    level = 4  # default
    if size_rank == 1:
      level = 2  # largest size -> level 2
    elif size_rank == 2:
      level = 3
    elif size_rank == 3:
      level = 4
    
    # Boost to level 3 if short line or large gap
    word_count = len(text.split())
    if word_count <= 10 or gap_to_next > GAP_THRESHOLD:
      level = min(level, 3)
    
    proposed_levels.append(level)
    
    # Store additional signals
    signals['word_count'] = word_count
    header['signals'] = signals
  
  # Step 3: Enforce legal outline (no level jumps > 1)
  final_levels = []
  prev_level = 0
  
  for i, proposed_level in enumerate(proposed_levels):
    # Clamp level jumps to at most +1
    if proposed_level > prev_level + 1:
      final_level = prev_level + 1
    else:
      final_level = proposed_level
    
    final_levels.append(final_level)
    prev_level = final_level
    
    # Update signals in header
    if 'signals' not in headers[i]:
      headers[i]['signals'] = {}
    headers[i]['signals'].update({
      'proposed_level': proposed_level,
      'final_level': final_level,
      'clamped': proposed_level != final_level
    })
  
  # Step 4: Create OutlineHeading objects
  outline = []
  for i, header in enumerate(headers):
    # Convert bbox to tuple format if needed
    bbox_tuple = None
    if header['bbox']:
      bbox_data = header['bbox']
      if isinstance(bbox_data, dict):
        if 'l' in bbox_data and 't' in bbox_data and 'r' in bbox_data and 'b' in bbox_data:
          bbox_tuple = (bbox_data['l'], bbox_data['t'], bbox_data['r'], bbox_data['b'])
        elif 'left' in bbox_data and 'top' in bbox_data:
          bbox_tuple = (bbox_data['left'], bbox_data['top'], 
                       bbox_data['right'], bbox_data['bottom'])
      elif isinstance(bbox_data, (list, tuple)) and len(bbox_data) == 4:
        bbox_tuple = tuple(bbox_data)
    
    outline_heading = OutlineHeading(
      level=final_levels[i],
      text=header['text'],
      ref=header['ref'],
      page_no=header['page_no'],
      bbox=bbox_tuple,
      signals=header.get('signals', {})
    )
    outline.append(outline_heading)
  
  return outline


def infer_outline_from_json(doc_json: dict) -> list[OutlineHeading]:
  """Same as infer_outline, but input is plain dict loaded from Docling JSON."""
  # Create a simple namespace object from the JSON
  class JsonDoc:
    def __init__(self, data: dict):
      for key, value in data.items():
        if isinstance(value, dict):
          setattr(self, key, JsonDoc(value))
        elif isinstance(value, list):
          # Handle lists of dicts
          converted_list = []
          for item in value:
            if isinstance(item, dict):
              converted_list.append(JsonDoc(item))
            else:
              converted_list.append(item)
          setattr(self, key, converted_list)
        else:
          setattr(self, key, value)
  
  doc = JsonDoc(doc_json)
  return infer_outline(doc)


def to_markdown(outline: list[OutlineHeading]) -> str:
  """Render as Markdown headings (# by level)."""
  lines = []
  for heading in outline:
    prefix = "#" * heading.level
    lines.append(f"{prefix} {heading.text}")
  return "\n".join(lines)


def load_config(path: str) -> None:
  """Override ANCHOR_PATTERNS / NUM_DEPTHS / GAP_THRESHOLD from YAML/JSON."""
  global ANCHOR_PATTERNS, NUM_DEPTHS, GAP_THRESHOLD
  
  try:
    with open(path, 'r', encoding='utf-8') as f:
      if path.endswith('.json'):
        config = json.load(f)
      else:
        config = yaml.safe_load(f)
    
    if 'GAP_THRESHOLD' in config:
      GAP_THRESHOLD = float(config['GAP_THRESHOLD'])
    
    if 'ANCHOR_PATTERNS' in config:
      ANCHOR_PATTERNS = [re.compile(pattern, re.I) 
                        for pattern in config['ANCHOR_PATTERNS']]
    
    if 'NUM_DEPTHS' in config:
      NUM_DEPTHS = []
      for item in config['NUM_DEPTHS']:
        pattern = re.compile(item['pattern'])
        if item['level_func'] == 'count_dots_plus_2':
          func = lambda m: m.group(1).count('.') + 2
        elif item['level_func'] == 'level_2':
          func = lambda m: 2
        else:
          func = lambda m: 2  # default
        NUM_DEPTHS.append((pattern, func))
  
  except Exception as e:
    print(f"Warning: Could not load config from {path}: {e}")


def main():
  """CLI entry point."""
  parser = argparse.ArgumentParser(
    description="Infer document heading hierarchy from Docling JSON"
  )
  parser.add_argument("in_json", help="Input Docling JSON file")
  parser.add_argument("out_json", help="Output JSON file")
  parser.add_argument("--md", dest="out_md", help="Optional Markdown output file")
  parser.add_argument("--config", dest="config", help="Optional config file")
  
  args = parser.parse_args()
  
  if args.config:
    load_config(args.config)
  
  # Load input JSON
  with open(args.in_json, "r", encoding="utf-8") as f:
    doc_json = json.load(f)
  
  # Infer outline
  outline = infer_outline_from_json(doc_json)
  
  # Write JSON output
  with open(args.out_json, "w", encoding="utf-8") as f:
    json.dump([o.__dict__ for o in outline], f, ensure_ascii=False, indent=2)
  
  # Write optional Markdown output
  if args.out_md:
    with open(args.out_md, "w", encoding="utf-8") as f:
      f.write(to_markdown(outline))


if __name__ == "__main__":
  main()