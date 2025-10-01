"""Enhanced data models for the extraction pipeline.

This module provides improved data models with deterministic IDs, PDF anchoring
support, and comprehensive metadata as specified in the pipeline guide.
"""

import hashlib
import dataclasses
from typing import Dict, Any, List, Optional, Union, Tuple
from enum import Enum


def make_deterministic_id(*parts: str) -> str:
    """Create a deterministic ID from the given parts using SHA1.
    
    Args:
        *parts: String parts to combine into the ID
        
    Returns:
        16-character hexadecimal SHA1 hash
    """
    content = "|".join(str(part) for part in parts)
    return hashlib.sha1(content.encode("utf-8")).hexdigest()[:16]


def normalize_text_for_id(text: str) -> str:
    """Normalize text for consistent ID generation.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text suitable for ID generation
    """
    # Case-fold, collapse whitespace, but keep parentheses and numbers
    normalized = " ".join(text.strip().lower().split())
    return normalized


class AnchoringSource(Enum):
    """Source type for text anchoring."""
    EXACT = "exact"
    NORMALIZED = "normalized" 
    FUZZY = "fuzzy"
    SECTION_FALLBACK = "section_fallback"


@dataclasses.dataclass
class HighlightQuad:
    """Represents a quadrilateral highlight area on a PDF page.
    
    Attributes:
        x1, y1, x2, y2, x3, y3, x4, y4: Coordinates of the four corners
    """
    x1: float
    y1: float
    x2: float
    y2: float
    x3: float
    y3: float
    x4: float
    y4: float


@dataclasses.dataclass
class TextAnchor:
    """Represents an anchor from text back to the PDF.
    
    Attributes:
        page: PDF page number (1-based)
        quads: List of highlight quadrilaterals
        source: How the anchor was found (exact, normalized, fuzzy, fallback)
        confidence: Confidence score (0.0 to 1.0)
        char_span: Character span in the page text (start, end)
    """
    page: int
    quads: List[HighlightQuad]
    source: AnchoringSource
    confidence: float
    char_span: Optional[Tuple[int, int]] = None


@dataclasses.dataclass
class PageLocator:
    """Fallback locator when text anchoring fails.
    
    Attributes:
        page_range: Tuple of (start_page, end_page)
        reason: Why anchoring failed ("not_found", "ambiguous")
    """
    page_range: Tuple[int, int]
    reason: str


@dataclasses.dataclass
class Parameter:
    """Enhanced Parameter with normalization and deterministic ID.
    
    Attributes:
        param_id: Deterministic SHA1-based ID
        name: Parameter name/path
        operator: Comparison operator (>=, <=, ==, etc.)
        original_value: Original value as extracted
        normalized_value: Normalized value (SI units when possible)
        original_unit: Original unit
        normalized_unit: Normalized unit (SI when possible)
        unit_system: "original" or "SI"
        norm_id: ID of the parent norm
        confidence: Confidence score (0.0 to 1.0)
    """
    param_id: str
    name: str
    operator: str
    original_value: Union[str, float, int]
    normalized_value: Optional[Union[str, float, int]] = None
    original_unit: Optional[str] = None
    normalized_unit: Optional[str] = None
    unit_system: str = "original"
    norm_id: Optional[str] = None
    confidence: float = 1.0

    @classmethod
    def create_with_id(
        cls,
        name: str,
        operator: str,
        value: Union[str, float, int],
        unit: Optional[str] = None,
        norm_id: Optional[str] = None,
        **kwargs
    ) -> 'Parameter':
        """Create a Parameter with deterministic ID."""
        param_id = make_deterministic_id(
            norm_id or "",
            name,
            str(value),
            unit or ""
        )
        return cls(
            param_id=param_id,
            name=name,
            operator=operator,
            original_value=value,
            original_unit=unit,
            norm_id=norm_id,
            **kwargs
        )


@dataclasses.dataclass
class Tag:
    """Enhanced Tag with deterministic ID and usage tracking.
    
    Attributes:
        tag_id: Deterministic SHA1-based ID
        tag_path: Tag path/hierarchy
        used_by_norm_ids: List of norm IDs that use this tag
        related_topics: Related topics from extraction
        confidence: Confidence score (0.0 to 1.0)
    """
    tag_id: str
    tag_path: str
    used_by_norm_ids: List[str] = dataclasses.field(default_factory=list)
    related_topics: List[str] = dataclasses.field(default_factory=list)
    confidence: float = 1.0

    @classmethod
    def create_with_id(cls, tag_path: str, **kwargs) -> 'Tag':
        """Create a Tag with deterministic ID."""
        tag_id = make_deterministic_id("tag", tag_path)
        return cls(tag_id=tag_id, tag_path=tag_path, **kwargs)


@dataclasses.dataclass
class Reference:
    """Cross-reference to another section or table.
    
    Attributes:
        reference_id: Deterministic ID
        reference_text: Original reference text
        target_type: Type of target ("section", "table", "figure")
        target_label: Parsed target label
        target_id: ID of the target if resolved
        confidence: Confidence of the reference resolution
    """
    reference_id: str
    reference_text: str
    target_type: str
    target_label: str
    target_id: Optional[str] = None
    confidence: float = 1.0

    @classmethod
    def create_with_id(cls, reference_text: str, target_type: str, target_label: str, **kwargs) -> 'Reference':
        """Create a Reference with deterministic ID."""
        ref_id = make_deterministic_id("ref", reference_text, target_type, target_label)
        return cls(
            reference_id=ref_id,
            reference_text=reference_text,
            target_type=target_type,
            target_label=target_label,
            **kwargs
        )


@dataclasses.dataclass
class Norm:
    """Enhanced Norm with anchoring, metadata, and deterministic ID.
    
    Attributes:
        norm_id: Deterministic SHA1-based ID
        text: The extracted norm text
        normalized_text: Text normalized for ID generation
        parent_section_id: ID of the parent section
        section_path: ToC path to the section
        page_from: Starting page number
        page_to: Ending page number
        char_from: Starting character position
        char_to: Ending character position
        anchors: List of PDF text anchors
        locator: Fallback locator if anchoring failed
        confidence: Confidence score (0.0 to 1.0)
        source_pass: Which pass extracted this norm
        parameters: List of associated parameters
        tags: List of associated tags
        references: List of cross-references
        merged: Whether this norm was merged from multiple parts
        parts: List of norm IDs that were merged (if merged=True)
    """
    norm_id: str
    text: str
    normalized_text: str
    parent_section_id: str
    section_path: List[str]
    page_from: Optional[int] = None
    page_to: Optional[int] = None
    char_from: Optional[int] = None
    char_to: Optional[int] = None
    anchors: List[TextAnchor] = dataclasses.field(default_factory=list)
    locator: Optional[PageLocator] = None
    confidence: float = 1.0
    source_pass: str = "exact"
    parameters: List[Parameter] = dataclasses.field(default_factory=list)
    tags: List[Tag] = dataclasses.field(default_factory=list)
    references: List[Reference] = dataclasses.field(default_factory=list)
    merged: bool = False
    parts: List[str] = dataclasses.field(default_factory=list)

    @classmethod
    def create_with_id(cls, text: str, section_id: str, **kwargs) -> 'Norm':
        """Create a Norm with deterministic ID."""
        normalized_text = normalize_text_for_id(text)
        norm_id = make_deterministic_id(section_id, normalized_text)
        return cls(
            norm_id=norm_id,
            text=text,
            normalized_text=normalized_text,
            parent_section_id=section_id,
            **kwargs
        )


@dataclasses.dataclass
class EnhancedSection:
    """Enhanced Section with deterministic ID and comprehensive metadata.
    
    Attributes:
        section_id: Deterministic SHA1-based ID
        section_name: Section title/name
        section_level: Header level (1 for #, 2 for ##, etc.)
        section_index: Sequential index
        toc_path: ToC path hierarchy
        parent_section_id: Parent section ID
        sub_section_ids: List of child section IDs
        start_page: Starting page in PDF
        end_page: Ending page in PDF
        section_type: Type of section ("Headline" for regular sections, "Table" for tables)
        tags: Auto-generated tags from ToC path
        application_statement: Optional application statement
        exemption_statement: Optional exemption statement
        summary: Section summary
        norms: List of norms in this section
        confidence: Overall confidence score
    """
    section_id: str
    section_name: str
    section_level: int
    section_index: int
    toc_path: List[str]
    parent_section_id: Optional[str] = None
    sub_section_ids: List[str] = dataclasses.field(default_factory=list)
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    section_type: str = "Headline"
    tags: List[str] = dataclasses.field(default_factory=list)
    application_statement: Optional[str] = None
    exemption_statement: Optional[str] = None
    summary: str = ""
    norms: List[Norm] = dataclasses.field(default_factory=list)
    confidence: float = 1.0

    @classmethod
    def create_with_id(
        cls,
        toc_path: List[str],
        start_page: int,
        title_normalized: str,
        **kwargs
    ) -> 'EnhancedSection':
        """Create a Section with deterministic ID as per pipeline guide."""
        toc_path_str = "|".join(toc_path)
        section_id = make_deterministic_id(toc_path_str, str(start_page), title_normalized)
        
        # Auto-generate tags from ToC path
        tags = []
        for path_element in toc_path:
            # Extract meaningful tag components (e.g., "SI3", "Evacuación", "Puertas")
            tags.extend(_extract_tags_from_path_element(path_element))
        
        return cls(
            section_id=section_id,
            toc_path=toc_path,
            start_page=start_page,
            tags=tags,
            **kwargs
        )


def _extract_tags_from_path_element(element: str) -> List[str]:
    """Extract meaningful tags from a ToC path element."""
    tags = []
    
    # Match section codes like "SI3", "Sección SI 3", etc.
    import re
    
    # Extract codes like "SI 3" and convert to "SI3"
    si_match = re.search(r'\bSI\s*(\d+)', element, re.IGNORECASE)
    if si_match:
        tags.append(f"SI{si_match.group(1)}")
    
    # Extract other alphanumeric codes
    codes = re.findall(r'\b[A-Z]{2,3}\d+\b', element)
    tags.extend(codes)
    
    # Extract meaningful words (skip common words like "Sección", numbers)
    words = re.findall(r'\b[A-Za-zÀ-ÿ]{3,}\b', element)
    skip_words = {'sección', 'section', 'capítulo', 'chapter', 'anexo', 'anejo'}
    for word in words:
        if word.lower() not in skip_words and not word.isdigit():
            tags.append(word.title())
    
    return tags


@dataclasses.dataclass
class QualityMetrics:
    """Quality metrics for extraction results."""
    total_sections: int = 0
    total_norms: int = 0
    anchoring_success_exact: int = 0
    anchoring_success_normalized: int = 0
    anchoring_success_fuzzy: int = 0
    anchoring_fallback: int = 0
    low_confidence_norms: List[str] = dataclasses.field(default_factory=list)
    parameter_normalization_coverage: float = 0.0
    ambiguous_anchors: List[str] = dataclasses.field(default_factory=list)
    unmatched_tables: List[str] = dataclasses.field(default_factory=list)
    unmatched_references: List[str] = dataclasses.field(default_factory=list)

    def anchoring_success_rate(self) -> float:
        """Calculate overall anchoring success rate."""
        total_anchored = (self.anchoring_success_exact + 
                         self.anchoring_success_normalized + 
                         self.anchoring_success_fuzzy)
        total_attempts = total_anchored + self.anchoring_fallback
        return total_anchored / total_attempts if total_attempts > 0 else 0.0