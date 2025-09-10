#!/usr/bin/env python3
"""Example demonstrating the enhanced extraction pipeline features.

This example shows how to use the enhanced pipeline components to create
deterministic IDs, normalize parameters, and structure extraction results.
"""

import json
from pathlib import Path

from extraction_pipeline.data_models import (
    EnhancedSection, Norm, Parameter, Tag, QualityMetrics
)
from extraction_pipeline.parameter_normalization import (
    enhance_parameter_with_normalization, get_normalization_report
)


def create_example_sections():
    """Create example enhanced sections with deterministic IDs."""
    sections = []
    
    # Create Section 1: SI 3 - Evacuación
    section1 = EnhancedSection.create_with_id(
        toc_path=["Sección SI 3", "Evacuación"],
        start_page=25,
        title_normalized="evacuacion",
        section_name="Evacuación",
        section_level=2,
        section_index=0
    )
    sections.append(section1)
    
    # Create Section 2: Puertas
    section2 = EnhancedSection.create_with_id(
        toc_path=["Sección SI 3", "Evacuación", "Puertas"],
        start_page=27,
        title_normalized="puertas",
        section_name="Puertas",
        section_level=3,
        section_index=1,
        parent_section_id=section1.section_id
    )
    sections.append(section2)
    
    return sections


def create_example_norms(sections):
    """Create example norms with parameters and anchoring."""
    norms = []
    
    section2 = sections[1]  # Puertas section
    
    # Norm 1: Door width requirement
    norm1 = Norm.create_with_id(
        text="La anchura mínima de las puertas será de 0,80 m",
        section_id=section2.section_id,
        section_path=section2.toc_path
    )
    
    # Add parameters to norm1
    param1_data = {
        'name': 'DOOR.WIDTH',
        'operator': '>=',
        'value': 800,
        'unit': 'mm',
        'norm_id': norm1.norm_id
    }
    param1 = enhance_parameter_with_normalization(param1_data)
    norm1.parameters.append(param1)
    
    # Add tag
    tag1 = Tag.create_with_id("Puertas/Dimensiones")
    tag1.used_by_norm_ids = [norm1.norm_id]
    norm1.tags.append(tag1)
    
    norms.append(norm1)
    
    # Norm 2: Door height requirement
    norm2 = Norm.create_with_id(
        text="La altura mínima de las puertas será de 2,00 m",
        section_id=section2.section_id,
        section_path=section2.toc_path
    )
    
    # Add parameters to norm2
    param2_data = {
        'name': 'DOOR.HEIGHT',
        'operator': '>=',
        'value': 2.0,
        'unit': 'm',
        'norm_id': norm2.norm_id
    }
    param2 = enhance_parameter_with_normalization(param2_data)
    norm2.parameters.append(param2)
    
    # Add the same tag (demonstrating tag reuse)
    tag2 = Tag.create_with_id("Puertas/Dimensiones")
    tag2.used_by_norm_ids = [norm2.norm_id]
    norm2.tags.append(tag2)
    
    norms.append(norm2)
    
    # Add norms to section
    section2.norms = norms
    
    return norms


def demonstrate_parameter_normalization():
    """Demonstrate parameter normalization capabilities."""
    print("=== Parameter Normalization Example ===")
    
    test_parameters = [
        {
            'name': 'DOOR.WIDTH',
            'operator': '>=',
            'value': 800,
            'unit': 'mm'
        },
        {
            'name': 'CORRIDOR.HEIGHT',
            'operator': '>=',
            'value': 2.5,
            'unit': 'm'
        },
        {
            'name': 'TEMPERATURE.MAX',
            'operator': '<=',
            'value': 75,
            'unit': '°F'
        },
        {
            'name': 'AREA.MIN',
            'operator': '>=',
            'value': 150,
            'unit': 'cm²'
        }
    ]
    
    normalized_params = []
    for param_data in test_parameters:
        param = enhance_parameter_with_normalization(param_data)
        normalized_params.append(param)
        
        print(f"\nParameter: {param.name}")
        print(f"  Original: {param.original_value} {param.original_unit}")
        print(f"  Normalized: {param.normalized_value} {param.normalized_unit}")
        print(f"  System: {param.unit_system}")
    
    # Generate normalization report
    report = get_normalization_report(normalized_params)
    print(f"\nNormalization Report:")
    print(f"  Coverage: {report['normalization_coverage']:.1%}")
    print(f"  SI conversions: {report['unit_systems'].get('SI', 0)}")
    print(f"  Original units: {report['unit_systems'].get('original', 0)}")


def demonstrate_deterministic_ids():
    """Demonstrate deterministic ID generation."""
    print("\n=== Deterministic ID Example ===")
    
    # Create the same section multiple times
    sections_batch1 = []
    sections_batch2 = []
    
    for batch, batch_name in [(sections_batch1, "Batch 1"), (sections_batch2, "Batch 2")]:
        section = EnhancedSection.create_with_id(
            toc_path=["Test", "Section"],
            start_page=10,
            title_normalized="test section",
            section_name="Test Section",
            section_level=2,
            section_index=1
        )
        batch.append(section)
    
    print(f"Section ID Batch 1: {sections_batch1[0].section_id}")
    print(f"Section ID Batch 2: {sections_batch2[0].section_id}")
    print(f"IDs are identical: {sections_batch1[0].section_id == sections_batch2[0].section_id}")
    
    # Demonstrate norm ID determinism
    norm1 = Norm.create_with_id(
        text="Test norm text",
        section_id=sections_batch1[0].section_id,
        section_path=sections_batch1[0].toc_path
    )
    
    norm2 = Norm.create_with_id(
        text="Test norm text",
        section_id=sections_batch2[0].section_id,
        section_path=sections_batch2[0].toc_path
    )
    
    print(f"Norm ID 1: {norm1.norm_id}")
    print(f"Norm ID 2: {norm2.norm_id}")
    print(f"Norm IDs are identical: {norm1.norm_id == norm2.norm_id}")


def export_example_results():
    """Export example results to JSON for inspection."""
    print("\n=== Export Example ===")
    
    sections = create_example_sections()
    norms = create_example_norms(sections)
    
    # Collect all parameters
    all_parameters = []
    for norm in norms:
        all_parameters.extend(norm.parameters)
    
    # Create quality metrics
    metrics = QualityMetrics()
    metrics.total_sections = len(sections)
    metrics.total_norms = len(norms)
    metrics.parameter_normalization_coverage = len([p for p in all_parameters if p.unit_system == "SI"]) / len(all_parameters) if all_parameters else 0
    
    # Create export data
    export_data = {
        "extraction_pipeline": {
            "version": "1.0",
            "method": "enhanced_example",
            "description": "Example demonstrating enhanced pipeline features"
        },
        "sections": [
            {
                "section_id": section.section_id,
                "section_name": section.section_name,
                "toc_path": section.toc_path,
                "tags": section.tags,
                "norms": [
                    {
                        "norm_id": norm.norm_id,
                        "text": norm.text,
                        "parameters": [
                            {
                                "param_id": param.param_id,
                                "name": param.name,
                                "operator": param.operator,
                                "original_value": param.original_value,
                                "original_unit": param.original_unit,
                                "normalized_value": param.normalized_value,
                                "normalized_unit": param.normalized_unit,
                                "unit_system": param.unit_system
                            }
                            for param in norm.parameters
                        ],
                        "tags": [tag.tag_path for tag in norm.tags]
                    }
                    for norm in section.norms
                ]
            }
            for section in sections
        ],
        "quality_metrics": {
            "total_sections": metrics.total_sections,
            "total_norms": metrics.total_norms,
            "parameter_normalization_coverage": metrics.parameter_normalization_coverage
        }
    }
    
    # Save to file
    output_path = Path("example_enhanced_output.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"Example results exported to: {output_path}")
    
    # Print summary
    print("\nExample Summary:")
    print(f"  Sections: {len(sections)}")
    print(f"  Norms: {len(norms)}")
    print(f"  Parameters: {len(all_parameters)}")
    print(f"  Normalized parameters: {sum(1 for p in all_parameters if p.unit_system == 'SI')}")


def main():
    """Run the enhanced pipeline example."""
    print("Enhanced Extraction Pipeline Example")
    print("===================================")
    
    demonstrate_parameter_normalization()
    demonstrate_deterministic_ids()
    export_example_results()
    
    print("\n=== Enhanced Pipeline Features Demonstrated ===")
    print("1. ✓ Deterministic SHA1-based IDs for sections, norms, and parameters")
    print("2. ✓ Parameter normalization with SI unit conversion")
    print("3. ✓ Structured data models with comprehensive metadata")
    print("4. ✓ Tag extraction and management")
    print("5. ✓ Quality metrics and reporting")
    print("6. ✓ JSON export with enhanced structure")


if __name__ == "__main__":
    main()