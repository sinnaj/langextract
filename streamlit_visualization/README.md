# LangExtract Streamlit Visualization Dashboard

This folder contains a Streamlit dashboard for visualizing LangExtract processing results.

## Features

### Main Dashboard (`app.py`)
- **KPI Cards**: Key metrics from combined_extractions.json
  - Total extractions count
  - Processing success rate
  - Number of sections processed
  - Last processing timestamp
  - Breakdown by extraction types (NORM, Tag, Parameter, etc.)

- **Processing Overview**: 
  - Evaluation statistics (extract/manual/drop counts)
  - Section processing breakdown
  - Visual charts showing processing results

- **Extractions Analysis**:
  - Distribution of extraction types
  - Text length analysis
  - Top sections by extraction count

### Tags Analytics Page (`pages/Tags.py`)
- **Tags Overview**: Core metrics about extracted tags
- **Hierarchical Structure Analysis**: Tag categorization and depth analysis
- **Usage Analysis**: How tags are used across norms
- **Topics Analysis**: Related topics and co-occurrence patterns
- **Tag Explorer**: Interactive filtering and detailed tag views

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

### Data Sources

The dashboard automatically looks for the latest `combined_extractions.json` file in the `output_runs` directory. You can also:

1. **Use Latest File**: Automatically detected from `output_runs/{timestamp}/lx output/combined_extractions.json`
2. **Upload File**: Upload your own `combined_extractions.json` file through the sidebar

### Navigation

- **Main Dashboard**: Overview and KPI cards
- **Tags** (sidebar page): Detailed tags analytics

## Data Structure Expected

The dashboard expects `combined_extractions.json` files with this structure:

```json
{
  "document_metadata": {
    "total_extractions": int,
    "total_processed_sections": int,
    "processing_timestamp": "ISO datetime"
  },
  "evaluation_statistics": {
    "extract_count": int,
    "manual_count": int,
    "drop_count": int,
    "extract_percentage": float
  },
  "sections": [
    {
      "section_id": "string",
      "section_name": "string",
      "processing_type": "extract|manual|drop",
      "extraction_count": int
    }
  ],
  "extractions": [
    {
      "extraction_class": "Tag|NORM|Parameter|LEGAL_DOCUMENT|PROCEDURE",
      "extraction_text": "string",
      "attributes": {
        "id": "string",
        "tag": "hierarchical.path",
        "used_by_norm_ids": ["array"],
        "related_topics": ["array"]
      }
    }
  ]
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