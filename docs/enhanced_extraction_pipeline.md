# Enhanced Extraction Pipeline

This document describes the enhanced extraction pipeline implementation based on the specifications in `docs/prompts/extraction_pipeline_guide.md`.

## Overview

The enhanced extraction pipeline provides:

- **Deterministic SHA1-based IDs** for all entities (sections, norms, parameters)
- **PDF text anchoring** with 3-stage matching and highlight quads
- **Parameter normalization** with SI unit conversion
- **Comprehensive quality metrics** and reporting
- **ToC-interval-based chunking** with stable section IDs

## Components

### 1. Data Models (`extraction_pipeline/data_models.py`)

Enhanced data models with deterministic IDs and comprehensive metadata:

- `EnhancedSection`: Sections with ToC path and auto-generated tags
- `Norm`: Norms with PDF anchoring and parameter relationships  
- `Parameter`: Parameters with original/normalized values and units
- `TextAnchor`: PDF anchoring with highlight quads
- `Tag`: Tags with usage tracking
- `Reference`: Cross-references with resolution
- `QualityMetrics`: Comprehensive extraction quality metrics

### 2. Parameter Normalization (`extraction_pipeline/parameter_normalization.py`)

Comprehensive unit conversion supporting:

- **Length**: mm, cm, m, km, inches, feet
- **Area**: mm², cm², m², km², hectares  
- **Volume**: mm³, cm³, m³, liters
- **Time**: minutes, hours, days
- **Temperature**: °C, °F, Kelvin
- **Pressure**: bar, Pa, psi, atm
- **Mass**: g, kg, tons
- **Speed**: km/h, m/s, mph

### 3. Text Anchoring (`extraction_pipeline/text_anchoring.py`)

Deterministic 3-stage text matching:

1. **Exact match**: Identity, case sensitive
2. **Normalized match**: Case-fold, whitespace collapse  
3. **Fuzzy match**: Token-set ratio ≥ 90%

Generates highlight quads for PDF visualization.

### 4. Enhanced Chunking (`extraction_pipeline/enhanced_chunking.py`)

ToC-interval-based chunking with:

- Stable path-based section IDs using SHA1
- Context headers for each chunk
- Page window splitting for large sections
- Integration with PDF ToC extraction

### 5. Pipeline Integration (`extraction_pipeline/enhanced_pipeline.py`)

Main pipeline class that orchestrates all components:

```python
from extraction_pipeline.enhanced_pipeline import EnhancedExtractionPipeline

# Create pipeline from PDF
pipeline = EnhancedExtractionPipeline(pdf_path)
pipeline.load_document_data()
pipeline.create_sections()

# Create chunks for extraction
chunks = pipeline.create_chunks_for_extraction(max_chars=5000)

# Process LangExtract results
enhanced_sections, metrics = pipeline.process_extraction_results(
    extraction_results, sections
)

# Generate report and export
report = pipeline.generate_extraction_report()
pipeline.export_enhanced_results(output_path)
```

## Usage

### Enhanced Runner

Use the enhanced runner for complete pipeline processing:

```bash
python enhanced_lx_runner.py input_document.md --pdf-path source.pdf --output-dir results/
```

### Example Usage

See `example_enhanced_pipeline.py` for a complete demonstration of:

- Creating sections with deterministic IDs
- Parameter normalization and SI conversion
- Quality metrics calculation
- JSON export with enhanced structure

## Key Features

### Deterministic IDs

All entities have stable, deterministic SHA1-based IDs:

```python
# Section ID from ToC path, page, and normalized title
section_id = sha1(f"{toc_path}|{start_page}|{title_normalized}")

# Norm ID from section ID and normalized text  
norm_id = sha1(f"{section_id}|{normalized_text}")

# Parameter ID from norm ID, name, value, and unit
param_id = sha1(f"{norm_id}|{name}|{value}|{unit}")
```

### Parameter Normalization

Automatic SI unit conversion with both original and normalized values:

```python
Parameter(
    original_value=800,
    original_unit="mm", 
    normalized_value=0.8,
    normalized_unit="m",
    unit_system="SI"
)
```

### PDF Anchoring

3-stage text matching with fallback to section-level locators:

```python
TextAnchor(
    page=25,
    source=AnchoringSource.EXACT,
    confidence=1.0,
    char_span=(150, 200),
    quads=[HighlightQuad(...)]
)
```

### Quality Metrics

Comprehensive extraction quality tracking:

```python
QualityMetrics(
    total_sections=10,
    total_norms=45,
    anchoring_success_rate=0.85,
    parameter_normalization_coverage=0.92,
    low_confidence_norms=['norm_001', 'norm_015']
)
```

## Output Format

Enhanced extraction results are exported as structured JSON:

```json
{
  "extraction_pipeline": {
    "version": "1.0",
    "method": "enhanced_toc_based"
  },
  "sections": [
    {
      "section_id": "8e797ed52eb5351a",
      "section_name": "Puertas", 
      "toc_path": ["Sección SI 3", "Evacuación", "Puertas"],
      "tags": ["SI3", "Evacuación", "Puertas"],
      "norms": [
        {
          "norm_id": "55816dd6ba50c800",
          "text": "La anchura mínima de las puertas será de 0,80 m",
          "anchors": [...],
          "parameters": [
            {
              "param_id": "a8162fbbb5a1f95d",
              "name": "DOOR.WIDTH",
              "operator": ">=",
              "original_value": 800,
              "original_unit": "mm",
              "normalized_value": 0.8,
              "normalized_unit": "m",
              "unit_system": "SI"
            }
          ]
        }
      ]
    }
  ],
  "quality_metrics": {
    "anchoring_success_rate": 0.85,
    "parameter_normalization_coverage": 0.92
  }
}
```

## Testing

Comprehensive test suite validates:

- Deterministic ID generation and stability
- Parameter normalization accuracy  
- Text matching algorithms
- Data model consistency
- End-to-end pipeline workflows

Run tests with:

```bash
pytest tests/test_extraction_pipeline.py -v
```

## Integration

The enhanced pipeline integrates with existing LangExtract infrastructure:

1. **Input**: Uses existing section chunker and chunk evaluator
2. **Processing**: Leverages LangExtract for entity extraction
3. **Output**: Provides enhanced data models and quality metrics
4. **Compatibility**: Maintains compatibility with existing workflows

## Future Enhancements

Potential improvements include:

1. **Advanced fuzzy matching** with better context disambiguation
2. **Cross-reference resolution** between sections and tables
3. **Machine learning confidence scoring** for extractions
4. **Interactive review interface** for low-confidence items
5. **Caching and incremental processing** for large documents