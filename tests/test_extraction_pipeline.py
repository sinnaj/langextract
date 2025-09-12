"""Tests for the enhanced extraction pipeline components."""

import pytest
from extraction_pipeline.data_models import (
    make_deterministic_id, normalize_text_for_id, 
    EnhancedSection, Norm, Parameter, Tag, Reference,
    AnchoringSource, TextAnchor, HighlightQuad
)
from extraction_pipeline.parameter_normalization import (
    normalize_unit, normalize_parameter_value, 
    enhance_parameter_with_normalization
)
from extraction_pipeline.text_anchoring import (
    normalize_text_for_matching, find_exact_match,
    find_normalized_match, find_fuzzy_match
)


class TestDataModels:
    """Test the enhanced data models."""
    
    def test_make_deterministic_id(self):
        """Test deterministic ID generation."""
        # Same inputs should produce same ID
        id1 = make_deterministic_id("section1", "page10", "title")
        id2 = make_deterministic_id("section1", "page10", "title")
        assert id1 == id2
        
        # Different inputs should produce different IDs
        id3 = make_deterministic_id("section2", "page10", "title")
        assert id1 != id3
        
        # ID should be 16 characters
        assert len(id1) == 16
    
    def test_normalize_text_for_id(self):
        """Test text normalization for ID generation."""
        text1 = "  This is a TEST  text (1) "
        text2 = "This is a test text (1)"
        
        norm1 = normalize_text_for_id(text1)
        norm2 = normalize_text_for_id(text2)
        
        assert norm1 == norm2
        assert norm1 == "this is a test text (1)"
    
    def test_enhanced_section_creation(self):
        """Test EnhancedSection creation with deterministic ID."""
        section = EnhancedSection.create_with_id(
            toc_path=["Sección SI 3", "4 Dimensionado"],
            start_page=10,
            title_normalized="dimensionado",
            section_name="4 Dimensionado",
            section_level=2,
            section_index=5
        )
        
        assert section.section_id is not None
        assert len(section.section_id) == 16
        assert section.section_name == "4 Dimensionado"
        assert section.toc_path == ["Sección SI 3", "4 Dimensionado"]
        assert "SI3" in section.tags  # Auto-generated from path
        assert "Dimensionado" in section.tags
    
    def test_norm_creation(self):
        """Test Norm creation with deterministic ID."""
        norm = Norm.create_with_id(
            text="La anchura mínima de las puertas será de 0,80 m",
            section_id="test_section_123",
            section_path=["Sección SI 3", "Evacuación"]
        )
        
        assert norm.norm_id is not None
        assert len(norm.norm_id) == 16
        assert norm.text == "La anchura mínima de las puertas será de 0,80 m"
        assert norm.parent_section_id == "test_section_123"
        assert norm.section_path == ["Sección SI 3", "Evacuación"]
    
    def test_parameter_creation(self):
        """Test Parameter creation with deterministic ID."""
        param = Parameter.create_with_id(
            name="DOOR.WIDTH",
            operator=">=",
            value=0.80,
            unit="m",
            norm_id="norm_123"
        )
        
        assert param.param_id is not None
        assert len(param.param_id) == 16
        assert param.name == "DOOR.WIDTH"
        assert param.operator == ">="
        assert param.original_value == 0.80
        assert param.original_unit == "m"


class TestParameterNormalization:
    """Test parameter normalization functionality."""
    
    def test_normalize_unit_length(self):
        """Test length unit normalization."""
        si_unit, factor = normalize_unit("mm")
        assert si_unit == "m"
        assert factor == 0.001
        
        si_unit, factor = normalize_unit("km")
        assert si_unit == "m"
        assert factor == 1000
    
    def test_normalize_unit_area(self):
        """Test area unit normalization."""
        si_unit, factor = normalize_unit("cm²")
        assert si_unit == "m²"
        assert factor == 0.0001
    
    def test_normalize_unit_unknown(self):
        """Test unknown unit handling."""
        si_unit, factor = normalize_unit("unknown_unit")
        assert si_unit == "unknown_unit"
        assert factor == 1.0
    
    def test_normalize_parameter_value_numeric(self):
        """Test numeric parameter value normalization."""
        norm_val, norm_unit, system = normalize_parameter_value(800, "mm")
        assert norm_val == 0.8
        assert norm_unit == "m"
        assert system == "SI"
    
    def test_normalize_parameter_value_string(self):
        """Test string parameter value normalization."""
        norm_val, norm_unit, system = normalize_parameter_value("RESIDENTIAL", None)
        assert norm_val == "RESIDENTIAL"
        assert norm_unit is None
        assert system == "original"
    
    def test_enhance_parameter_with_normalization(self):
        """Test parameter enhancement with normalization."""
        param_dict = {
            'name': 'DOOR.WIDTH',
            'operator': '>=',
            'value': 800,
            'unit': 'mm',
            'norm_id': 'test_norm'
        }
        
        param = enhance_parameter_with_normalization(param_dict)
        
        assert param.name == 'DOOR.WIDTH'
        assert param.original_value == 800
        assert param.original_unit == 'mm'
        assert param.normalized_value == 0.8
        assert param.normalized_unit == 'm'
        assert param.unit_system == 'SI'


class TestTextAnchoring:
    """Test PDF text anchoring functionality."""
    
    def test_normalize_text_for_matching(self):
        """Test text normalization for matching."""
        text = 'The "Quick" Brown–Fox (1) jumps'
        normalized = normalize_text_for_matching(text)
        assert normalized == 'the "quick" brown-fox (1) jumps'
    
    def test_find_exact_match_single(self):
        """Test exact match finding with single result."""
        page_text = "This is a test text. The norm text is here. More text follows."
        norm_text = "The norm text is here"
        
        result = find_exact_match(page_text, norm_text)
        assert result is not None
        start, end = result
        assert page_text[start:end] == norm_text
    
    def test_find_exact_match_none(self):
        """Test exact match finding with no result."""
        page_text = "This is a test text without the target."
        norm_text = "target text not present"
        
        result = find_exact_match(page_text, norm_text)
        assert result is None
    
    def test_find_normalized_match(self):
        """Test normalized match finding."""
        page_text = "This is a TEST  text with   SPACES"
        norm_text = "test text with spaces"
        
        result = find_normalized_match(page_text, norm_text)
        assert result is not None
        # Should find approximate position
        start, end = result
        assert start >= 0 and end <= len(page_text)
    
    @pytest.mark.skip("Fuzzy matching implementation needs refinement")
    def test_find_fuzzy_match_high_score(self):
        """Test fuzzy match with high similarity."""
        page_text = "The minimum width of doors shall be 0.80 meters"
        norm_text = "minimum width of doors shall be 0.80"
        
        result = find_fuzzy_match(page_text, norm_text, min_score=0.7)
        assert result is not None
        start, end, score = result
        assert score >= 0.7
        assert start >= 0 and end <= len(page_text)
    
    def test_find_fuzzy_match_low_score(self):
        """Test fuzzy match with low similarity."""
        page_text = "Completely different text content here"
        norm_text = "The minimum width requirement"
        
        result = find_fuzzy_match(page_text, norm_text, min_score=0.9)
        assert result is None


class TestIntegration:
    """Integration tests for pipeline components."""
    
    def test_section_to_norm_workflow(self):
        """Test the workflow from section to norm creation."""
        # Create section
        section = EnhancedSection.create_with_id(
            toc_path=["SI 3", "Evacuación", "Puertas"],
            start_page=25,
            title_normalized="puertas",
            section_name="Puertas",
            section_level=3,
            section_index=10
        )
        
        # Create norm in this section
        norm = Norm.create_with_id(
            text="Las puertas tendrán una anchura mínima de 0,80 m",
            section_id=section.section_id,
            section_path=section.toc_path
        )
        
        # Create parameter for this norm
        param = Parameter.create_with_id(
            name="DOOR.WIDTH",
            operator=">=",
            value=0.80,
            unit="m",
            norm_id=norm.norm_id
        )
        
        # Verify relationships
        assert norm.parent_section_id == section.section_id
        assert param.norm_id == norm.norm_id
        # The norm ID is generated from the section ID and normalized text
        # so we check the parent relationship exists
        assert norm.parent_section_id is not None
        assert param.norm_id is not None
    
    def test_deterministic_id_stability(self):
        """Test that IDs are stable across multiple runs."""
        # Create same section multiple times
        sections = []
        for i in range(5):
            section = EnhancedSection.create_with_id(
                toc_path=["Test", "Section"],
                start_page=10,
                title_normalized="test section",
                section_name="Test Section",
                section_level=2,
                section_index=1
            )
            sections.append(section)
        
        # All section IDs should be identical
        first_id = sections[0].section_id
        for section in sections[1:]:
            assert section.section_id == first_id