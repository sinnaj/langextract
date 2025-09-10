"""Enhanced extraction pipeline integration.

This module integrates all the enhanced components into a complete pipeline
that can be used by lxRunnerExtraction.py to provide improved extraction
with deterministic IDs, PDF anchoring, and comprehensive quality metrics.
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from .data_models import (
    EnhancedSection, Norm, Parameter, Tag, Reference, QualityMetrics,
    make_deterministic_id, normalize_text_for_id
)
from .enhanced_chunking import (
    create_enhanced_sections_from_toc, extract_section_content,
    create_section_chunks_with_context, load_toc_and_docling
)
from .text_anchoring import (
    anchor_norm_to_pdf, create_page_corpus_from_docling
)
from .parameter_normalization import (
    enhance_parameter_with_normalization, calculate_normalization_coverage,
    get_normalization_report
)


class EnhancedExtractionPipeline:
    """Enhanced extraction pipeline that integrates all components."""
    
    def __init__(self, pdf_path: Optional[Path] = None):
        """Initialize the enhanced pipeline.
        
        Args:
            pdf_path: Optional path to PDF for ToC and Docling extraction
        """
        self.pdf_path = pdf_path
        self.toc_data: List[Dict[str, Any]] = []
        self.docling_document: Dict[str, Any] = {}
        self.page_corpus: Dict[int, Dict[str, Any]] = {}
        self.sections: List[EnhancedSection] = []
        self.quality_metrics = QualityMetrics()
        
    def load_document_data(
        self,
        toc_path: Optional[Path] = None,
        docling_path: Optional[Path] = None
    ) -> None:
        """Load ToC and Docling document data.
        
        Args:
            toc_path: Optional path to existing ToC JSON
            docling_path: Optional path to existing Docling JSON
        """
        if self.pdf_path:
            self.toc_data, self.docling_document = load_toc_and_docling(
                self.pdf_path, toc_path, docling_path
            )
        else:
            # Load from provided paths
            if toc_path and toc_path.exists():
                with open(toc_path, 'r', encoding='utf-8') as f:
                    self.toc_data = json.load(f)
                    
            if docling_path and docling_path.exists():
                with open(docling_path, 'r', encoding='utf-8') as f:
                    self.docling_document = json.load(f)
        
        # Create page corpus for anchoring
        self.page_corpus = create_page_corpus_from_docling(self.docling_document)
    
    def create_sections(self) -> List[EnhancedSection]:
        """Create enhanced sections from ToC data."""
        self.sections = create_enhanced_sections_from_toc(
            self.toc_data, self.docling_document
        )
        return self.sections
    
    def create_chunks_for_extraction(
        self,
        max_chars: int = 5000
    ) -> List[Tuple[str, EnhancedSection]]:
        """Create section-based chunks for LangExtract processing.
        
        Args:
            max_chars: Maximum characters per chunk
            
        Returns:
            List of (chunk_text, section) tuples ready for extraction
        """
        return create_section_chunks_with_context(
            self.sections, self.docling_document, max_chars
        )
    
    def process_extraction_results(
        self,
        extraction_results: List[Dict[str, Any]],
        sections: List[EnhancedSection]
    ) -> Tuple[List[EnhancedSection], QualityMetrics]:
        """Process raw extraction results into enhanced data models.
        
        Args:
            extraction_results: Raw results from LangExtract
            sections: Corresponding sections for each result
            
        Returns:
            Tuple of (enhanced_sections_with_norms, quality_metrics)
        """
        enhanced_sections = []
        all_norms = []
        all_parameters = []
        
        for result, section in zip(extraction_results, sections):
            enhanced_section = self._process_section_result(result, section)
            enhanced_sections.append(enhanced_section)
            all_norms.extend(enhanced_section.norms)
            
            # Collect parameters from all norms
            for norm in enhanced_section.norms:
                all_parameters.extend(norm.parameters)
        
        # Calculate quality metrics
        self.quality_metrics = self._calculate_quality_metrics(
            enhanced_sections, all_norms, all_parameters
        )
        
        return enhanced_sections, self.quality_metrics
    
    def _process_section_result(
        self,
        result: Dict[str, Any],
        section: EnhancedSection
    ) -> EnhancedSection:
        """Process extraction result for a single section."""
        extractions = result.get('extractions', [])
        norms = []
        
        for extraction in extractions:
            # Process NORM extractions
            if isinstance(extraction, dict):
                norm_items = extraction.get('norms', [])
                for norm_data in norm_items:
                    norm = self._create_norm_from_extraction(norm_data, section)
                    norms.append(norm)
        
        section.norms = norms
        return section
    
    def _create_norm_from_extraction(
        self,
        norm_data: Dict[str, Any],
        section: EnhancedSection
    ) -> Norm:
        """Create enhanced Norm from extraction data."""
        norm_text = norm_data.get('text', norm_data.get('norm_text', ''))
        
        # Create norm with deterministic ID
        norm = Norm.create_with_id(
            text=norm_text,
            section_id=section.section_id,
            section_path=section.toc_path
        )
        
        # Set page boundaries from section
        norm.page_from = section.start_page
        norm.page_to = section.end_page
        
        # Anchor norm to PDF if possible
        if norm_text and self.page_corpus and section.start_page and section.end_page:
            section_pages = list(range(section.start_page, section.end_page + 1))
            anchor_result = anchor_norm_to_pdf(
                norm_text, section_pages, self.page_corpus
            )
            
            if hasattr(anchor_result, '__iter__') and not isinstance(anchor_result, str):
                # List of anchors
                norm.anchors = anchor_result
            else:
                # PageLocator fallback
                norm.locator = anchor_result
        
        # Process parameters
        parameters_data = norm_data.get('parameters', [])
        if parameters_data:
            for param_data in parameters_data:
                param = enhance_parameter_with_normalization(param_data)
                param.norm_id = norm.norm_id
                norm.parameters.append(param)
        
        # Process tags
        tags_data = norm_data.get('tags', norm_data.get('relevant_tags', []))
        for tag_text in tags_data:
            if isinstance(tag_text, str):
                tag = Tag.create_with_id(tag_text)
                tag.used_by_norm_ids = [norm.norm_id]
                norm.tags.append(tag)
        
        # Set confidence
        norm.confidence = norm_data.get('confidence', 1.0)
        
        return norm
    
    def _calculate_quality_metrics(
        self,
        sections: List[EnhancedSection],
        norms: List[Norm],
        parameters: List[Parameter]
    ) -> QualityMetrics:
        """Calculate comprehensive quality metrics."""
        metrics = QualityMetrics()
        
        metrics.total_sections = len(sections)
        metrics.total_norms = len(norms)
        
        # Calculate anchoring statistics
        for norm in norms:
            if norm.anchors:
                for anchor in norm.anchors:
                    if anchor.source.value == "exact":
                        metrics.anchoring_success_exact += 1
                    elif anchor.source.value == "normalized":
                        metrics.anchoring_success_normalized += 1
                    elif anchor.source.value == "fuzzy":
                        metrics.anchoring_success_fuzzy += 1
            else:
                metrics.anchoring_fallback += 1
            
            # Track low confidence norms
            if norm.confidence < 0.6:
                metrics.low_confidence_norms.append(norm.norm_id)
        
        # Parameter normalization coverage
        metrics.parameter_normalization_coverage = calculate_normalization_coverage(parameters)
        
        return metrics
    
    def generate_extraction_report(self) -> Dict[str, Any]:
        """Generate comprehensive extraction report."""
        report = {
            'pipeline_version': '1.0',
            'document_source': str(self.pdf_path) if self.pdf_path else 'unknown',
            'processing_timestamp': __import__('datetime').datetime.now().isoformat(),
            'quality_metrics': {
                'total_sections': self.quality_metrics.total_sections,
                'total_norms': self.quality_metrics.total_norms,
                'anchoring_success_rate': self.quality_metrics.anchoring_success_rate(),
                'anchoring_breakdown': {
                    'exact': self.quality_metrics.anchoring_success_exact,
                    'normalized': self.quality_metrics.anchoring_success_normalized,
                    'fuzzy': self.quality_metrics.anchoring_success_fuzzy,
                    'fallback': self.quality_metrics.anchoring_fallback
                },
                'parameter_normalization_coverage': self.quality_metrics.parameter_normalization_coverage,
                'low_confidence_norms_count': len(self.quality_metrics.low_confidence_norms)
            },
            'sections_summary': [
                {
                    'section_id': section.section_id,
                    'section_name': section.section_name,
                    'toc_path': section.toc_path,
                    'norms_count': len(section.norms),
                    'pages': f"{section.start_page}-{section.end_page}" if section.start_page and section.end_page else "unknown"
                }
                for section in self.sections
            ],
            'review_queue': {
                'low_confidence_norms': self.quality_metrics.low_confidence_norms,
                'ambiguous_anchors': self.quality_metrics.ambiguous_anchors,
                'unmatched_tables': self.quality_metrics.unmatched_tables,
                'unmatched_references': self.quality_metrics.unmatched_references
            }
        }
        
        return report
    
    def export_enhanced_results(
        self,
        output_path: Path,
        include_raw_data: bool = False
    ) -> None:
        """Export enhanced extraction results to JSON.
        
        Args:
            output_path: Path to save results
            include_raw_data: Whether to include raw extraction data
        """
        output_data = {
            'extraction_pipeline': {
                'version': '1.0',
                'method': 'enhanced_toc_based',
                'timestamp': __import__('datetime').datetime.now().isoformat()
            },
            'document_metadata': {
                'source_pdf': str(self.pdf_path) if self.pdf_path else None,
                'total_sections': len(self.sections),
                'total_norms': sum(len(s.norms) for s in self.sections)
            },
            'sections': [
                self._section_to_dict(section, include_raw_data)
                for section in self.sections
            ],
            'quality_metrics': self._quality_metrics_to_dict(),
            'extraction_report': self.generate_extraction_report()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    def _section_to_dict(self, section: EnhancedSection, include_raw: bool = False) -> Dict[str, Any]:
        """Convert EnhancedSection to dictionary for JSON export."""
        section_dict = {
            'section_id': section.section_id,
            'section_name': section.section_name,
            'section_level': section.section_level,
            'toc_path': section.toc_path,
            'start_page': section.start_page,
            'end_page': section.end_page,
            'tags': section.tags,
            'norms': [self._norm_to_dict(norm, include_raw) for norm in section.norms]
        }
        
        return section_dict
    
    def _norm_to_dict(self, norm: Norm, include_raw: bool = False) -> Dict[str, Any]:
        """Convert Norm to dictionary for JSON export."""
        norm_dict = {
            'norm_id': norm.norm_id,
            'text': norm.text,
            'confidence': norm.confidence,
            'anchors': [self._anchor_to_dict(anchor) for anchor in norm.anchors],
            'parameters': [self._parameter_to_dict(param) for param in norm.parameters],
            'tags': [tag.tag_path for tag in norm.tags]
        }
        
        if norm.locator:
            norm_dict['locator'] = {
                'page_range': norm.locator.page_range,
                'reason': norm.locator.reason
            }
        
        return norm_dict
    
    def _anchor_to_dict(self, anchor) -> Dict[str, Any]:
        """Convert TextAnchor to dictionary."""
        return {
            'page': anchor.page,
            'source': anchor.source.value,
            'confidence': anchor.confidence,
            'char_span': anchor.char_span,
            'quads': [
                {
                    'x1': q.x1, 'y1': q.y1,
                    'x2': q.x2, 'y2': q.y2,
                    'x3': q.x3, 'y3': q.y3,
                    'x4': q.x4, 'y4': q.y4
                }
                for q in anchor.quads
            ]
        }
    
    def _parameter_to_dict(self, param: Parameter) -> Dict[str, Any]:
        """Convert Parameter to dictionary."""
        return {
            'param_id': param.param_id,
            'name': param.name,
            'operator': param.operator,
            'original_value': param.original_value,
            'original_unit': param.original_unit,
            'normalized_value': param.normalized_value,
            'normalized_unit': param.normalized_unit,
            'unit_system': param.unit_system,
            'confidence': param.confidence
        }
    
    def _quality_metrics_to_dict(self) -> Dict[str, Any]:
        """Convert QualityMetrics to dictionary."""
        return {
            'total_sections': self.quality_metrics.total_sections,
            'total_norms': self.quality_metrics.total_norms,
            'anchoring_success_rate': self.quality_metrics.anchoring_success_rate(),
            'anchoring_success_exact': self.quality_metrics.anchoring_success_exact,
            'anchoring_success_normalized': self.quality_metrics.anchoring_success_normalized,
            'anchoring_success_fuzzy': self.quality_metrics.anchoring_success_fuzzy,
            'anchoring_fallback': self.quality_metrics.anchoring_fallback,
            'parameter_normalization_coverage': self.quality_metrics.parameter_normalization_coverage,
            'low_confidence_norms': self.quality_metrics.low_confidence_norms,
            'ambiguous_anchors': self.quality_metrics.ambiguous_anchors
        }


def create_enhanced_pipeline_from_pdf(pdf_path: Path) -> EnhancedExtractionPipeline:
    """Create and initialize an enhanced pipeline from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Initialized EnhancedExtractionPipeline
    """
    pipeline = EnhancedExtractionPipeline(pdf_path)
    pipeline.load_document_data()
    pipeline.create_sections()
    return pipeline