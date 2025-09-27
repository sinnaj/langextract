# LangExtract Enhanced Streamlit Visualization Dashboard

This folder contains a Streamlit dashboard for visualizing Enhanced LangExtract processing results.

## Features

### Main Dashboard (`app.py`)
- **KPI Cards**: Key metrics from enhanced_extraction_results.json
  - Total extractions count (including norms, tags, parameters)
  - Pipeline processing statistics
  - Number of sections processed
  - Pipeline version and method information
  - Breakdown by extraction types (Norm, Tag, Parameter, Legal_Document, etc.)

- **Processing Overview**: 
  - Enhanced pipeline processing statistics
  - Section hierarchy breakdown by level and type
  - Visual charts showing processing results and section distribution

- **Extractions Analysis**:
  - Distribution of extraction types across all categories
  - Text length analysis with improved visualization
  - Top sections by extraction count with section hierarchy context
  - Section level analysis showing extraction patterns

### Enhanced Analytics Pages
- **Tags Analytics** (`pages/Tags.py`): Hierarchical tag analysis from enhanced tag extraction
- **Norms Analytics** (`pages/Norms.py`): Comprehensive norms analysis with enhanced attributes
- **Parameters Analytics** (`pages/Parameters.py`): Parameter normalization and unit analysis
- **Legal Documents Analytics** (`pages/Legal_Documents.py`): Legal document extraction analysis

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Or install individually:
```bash
pip install streamlit plotly pandas
```

## Usage

### Running the Dashboard

From the `streamlit_visualization` directory:

```bash
streamlit run app.py
```

This will start the dashboard at `http://localhost:8501`

### Quick Test

Use the provided test script to validate and start the dashboard:

```bash
./test_dashboard.sh
```

### Validation

To validate that your data files are compatible with the dashboard:

```bash
python validate_dashboard.py
```

### Data Sources

The dashboard automatically looks for the latest `enhanced_extraction_results.json` file in the `output_runs` directory. You can also:

1. **Use Latest File**: Automatically detected from `output_runs/{timestamp}/enhanced_output/enhanced_extraction_results.json`
2. **Upload File**: Upload your own `enhanced_extraction_results.json` file through the sidebar

### Enhanced Pipeline Support

The dashboard now supports the Enhanced LangExtract Pipeline which provides:
- **Hierarchical section structure** with deterministic SHA1-based IDs
- **PDF text anchoring** with highlight coordinates and 3-stage matching
- **Parameter normalization** with SI unit conversion
- **Comprehensive extraction metadata** including positioning data
- **Quality metrics** and processing statistics
- **Enhanced data organization** separating norms, tags, parameters, and other entity types

### Navigation

- **Main Dashboard**: Overview and KPI cards
- **Tags** (sidebar page): Detailed tags analytics

## Data Structure Expected

The dashboard expects `enhanced_extraction_results.json` files with this structure:

```json
{
  "pipeline_info": {
    "version": "2.0",
    "method": "enhanced_docling_toc_based_extraction",
    "total_sections": 207,
    "total_extractions": 1231,
    "total_tags": 1357,
    "total_parameters": 542,
    "performance_metrics": {...}
  },
  "sections": [
    {
      "section_id": "fa09c7d5c06b6313",
      "section_name": "I Objeto",
      "section_type": "Headline",
      "section_level": 2,
      "start_page": 3,
      "end_page": 3,
      "toc_path": ["Introducción", "I Objeto"],
      "parent_section_id": "0ec9c0e66768fb12",
      "positioning_data": [...],
      "section_summary": "Section at level 2"
    }
  ],
  "extractions": [...],
  "tags": [...],
  "parameters": [...],
  "processing_stats": {
    "chunks_processed": 207,
    "successful_extractions": 1231,
    "sections_with_extractions": 201
  }
}
```

## Features by Page

### Main Dashboard
- Automatic file detection
- KPI metrics cards
- Processing success visualization
- Extraction type distribution
- Section analysis

### Tags Page
- Tag hierarchy visualization
- Usage pattern analysis
- Topic relationship mapping
- Interactive tag filtering
- Detailed tag information

## Development

To modify or extend the dashboard:

1. **Main Dashboard**: Edit `app.py`
2. **Tags Analytics**: Edit `pages/Tags.py`
3. **Add New Pages**: Create new files in `pages/` directory following Streamlit's page convention

## Troubleshooting

- **No data found**: Ensure `combined_extractions.json` files exist in `output_runs` directories
- **Loading errors**: Check JSON file format and structure
- **Missing visualizations**: Verify required data fields are present in the JSON

## Dependencies

- `streamlit>=1.28.0`: Web dashboard framework
- `plotly>=5.17.0`: Interactive plotting
- `pandas>=1.3.0`: Data manipulation