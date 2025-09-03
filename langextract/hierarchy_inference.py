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

"""Hierarchical relationship inference for extracted data."""

from typing import Dict, List, Optional
import re
from absl import logging

from langextract.core import data


def infer_hierarchical_relationships(extractions: List[data.Extraction]) -> List[data.Extraction]:
    """Infer missing hierarchical relationships between extracted sections and norms.
    
    This function analyzes the extracted sections and norms to establish parent-child
    relationships that may have been lost during chunk-based processing.
    
    Args:
        extractions: List of extractions that may have missing hierarchical relationships.
        
    Returns:
        List of extractions with inferred parent-child relationships.
    """
    if not extractions:
        return extractions
    
    # Group extractions by type
    sections = [e for e in extractions if e.extraction_class == "SECTION"]
    norms = [e for e in extractions if e.extraction_class == "NORM"]
    other_extractions = [e for e in extractions if e.extraction_class not in ["SECTION", "NORM"]]
    
    # Process sections for hierarchy
    sections = _infer_section_hierarchy(sections)
    
    # Process norms for parent section relationships
    norms = _infer_norm_parent_relationships(norms, sections)
    
    # Combine all extractions
    result = sections + norms + other_extractions
    
    logging.info(
        "Hierarchical relationship inference complete. "
        f"Processed {len(sections)} sections, {len(norms)} norms, "
        f"{len(other_extractions)} other extractions."
    )
    
    return result


def _infer_section_hierarchy(sections: List[data.Extraction]) -> List[data.Extraction]:
    """Infer hierarchical relationships between sections.
    
    Args:
        sections: List of section extractions.
        
    Returns:
        List of sections with inferred parent-child relationships.
    """
    if not sections:
        return sections
    
    # Create section hierarchy map
    sections_by_level = {}
    sections_by_id = {}
    
    for section in sections:
        attrs = section.attributes or {}
        section_level = attrs.get("section_level", 1)
        section_id = attrs.get("id")
        
        if section_id:
            sections_by_id[section_id] = section
            
            if section_level not in sections_by_level:
                sections_by_level[section_level] = []
            sections_by_level[section_level].append(section)
    
    # Infer parent relationships for sections missing parent_id
    for section in sections:
        attrs = section.attributes or {}
        
        # Skip if already has parent_id
        if attrs.get("parent_id"):
            continue
            
        section_level = attrs.get("section_level", 1)
        section_title = attrs.get("section_title", "")
        
        # For sections without parent_id, try to infer from structure
        if section_level > 1:
            # Look for parent at higher level
            parent_section = _find_potential_parent_section(
                section, sections_by_level, section_level
            )
            
            if parent_section:
                # Update attributes to include parent reference
                new_attrs = attrs.copy()
                new_attrs["parent_id"] = parent_section.attributes.get("id")
                new_attrs["parent_type"] = parent_section.attributes.get("sectioning_type", "Section")
                
                # Create updated extraction
                section.attributes = new_attrs
                
                logging.debug(
                    f"Inferred parent relationship: {section_title} -> "
                    f"{parent_section.attributes.get('section_title', 'Unknown')}"
                )
    
    return sections


def _find_potential_parent_section(
    section: data.Extraction,
    sections_by_level: Dict[int, List[data.Extraction]],
    section_level: int
) -> Optional[data.Extraction]:
    """Find potential parent section for a given section.
    
    Args:
        section: The section to find parent for.
        sections_by_level: Dictionary mapping section levels to section lists.
        section_level: The level of the current section.
        
    Returns:
        The potential parent section, or None if not found.
    """
    # Look for parents at higher levels (lower level numbers)
    for parent_level in range(section_level - 1, 0, -1):
        if parent_level not in sections_by_level:
            continue
            
        parent_candidates = sections_by_level[parent_level]
        
        # For now, use a simple heuristic: the last parent at the higher level
        # In a more sophisticated implementation, we could use text position,
        # title similarity, or other contextual clues
        if parent_candidates:
            return parent_candidates[-1]
    
    return None


def _infer_norm_parent_relationships(
    norms: List[data.Extraction], 
    sections: List[data.Extraction]
) -> List[data.Extraction]:
    """Infer parent section relationships for norms.
    
    Args:
        norms: List of norm extractions.
        sections: List of section extractions to use as potential parents.
        
    Returns:
        List of norms with inferred parent section relationships.
    """
    if not norms or not sections:
        return norms
    
    # Create mapping of section IDs
    sections_by_id = {
        section.attributes.get("id"): section 
        for section in sections 
        if section.attributes and section.attributes.get("id")
    }
    
    for norm in norms:
        attrs = norm.attributes or {}
        
        # Skip if already has parent_section_id
        if attrs.get("parent_section_id"):
            continue
        
        # Try to infer parent section based on context or position
        parent_section_id = _infer_norm_parent_section_id(norm, sections)
        
        if parent_section_id and parent_section_id in sections_by_id:
            # Update attributes to include parent section reference
            new_attrs = attrs.copy()
            new_attrs["parent_section_id"] = parent_section_id
            
            # Create updated extraction
            norm.attributes = new_attrs
            
            logging.debug(
                f"Inferred parent section for norm: "
                f"{attrs.get('norm_statement', 'Unknown')[:50]}... -> {parent_section_id}"
            )
    
    return norms


def _infer_norm_parent_section_id(
    norm: data.Extraction,
    sections: List[data.Extraction]
) -> Optional[str]:
    """Infer the parent section ID for a norm.
    
    Args:
        norm: The norm extraction.
        sections: List of available sections.
        
    Returns:
        The inferred parent section ID, or None if not found.
    """
    # For now, use a simple heuristic: assign to the last section
    # In a more sophisticated implementation, we could use:
    # - Text position analysis
    # - Content similarity
    # - Section title matching
    # - Extraction text overlap analysis
    
    if sections:
        # Return the ID of the last section (assuming document order)
        last_section = sections[-1]
        return last_section.attributes.get("id") if last_section.attributes else None
    
    return None


def _extract_section_number_pattern(title: str) -> Optional[str]:
    """Extract section numbering pattern from title.
    
    Args:
        title: Section title.
        
    Returns:
        Extracted numbering pattern or None.
    """
    # Match patterns like "1.1", "2.1.1", "I.1", etc.
    patterns = [
        r'^(\d+(?:\.\d+)*)',  # 1.1, 1.2.3
        r'^([IVXLC]+(?:\.\d+)*)',  # I.1, II.1.2
        r'^([A-Z](?:\.\d+)*)',  # A.1, B.2.1
    ]
    
    for pattern in patterns:
        match = re.match(pattern, title.strip())
        if match:
            return match.group(1)
    
    return None