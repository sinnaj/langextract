import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import os
from datetime import datetime

st.set_page_config(
    page_title="Sections - LangExtract",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

def find_latest_combined_extractions():
    """Find the latest combined_extractions.json file."""
    base_path = Path(__file__).parent.parent
    output_runs_path = base_path / "output_runs"
    
    if not output_runs_path.exists():
        return None
    
    latest_file = None
    latest_timestamp = 0
    
    for run_dir in output_runs_path.iterdir():
        if run_dir.is_dir():
            combined_file = run_dir / "lx output" / "combined_extractions.json"
            if combined_file.exists():
                try:
                    timestamp = int(run_dir.name)
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = combined_file
                except ValueError:
                    continue
    
    return latest_file

def load_extractions_data(file_path):
    """Load and parse the combined extractions JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def display_kpi_cards(data):
    """Display KPI cards with key metrics."""
    st.header("📊 Key Performance Indicators")
    
    # Extract key metrics
    doc_metadata = data.get('document_metadata', {})
    eval_stats = data.get('evaluation_statistics', {})
    extractions = data.get('extractions', [])
    sections = data.get('sections', [])
    
    # Count extractions by type
    extraction_counts = {}
    for extraction in extractions:
        ext_type = extraction.get('extraction_class', 'Unknown')
        extraction_counts[ext_type] = extraction_counts.get(ext_type, 0) + 1
    
    # Create columns for KPI cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Extractions",
            value=len(extractions),
            delta=f"from {doc_metadata.get('total_processed_sections', 0)} sections"
        )
    
    with col2:
        st.metric(
            label="Total Sections",
            value=len(sections),
            delta=f"{doc_metadata.get('total_original_sections', 0)} original"
        )
    
    with col3:
        st.metric(
            label="Sections Processed Manually",
            value=eval_stats.get('manual_count', 0),
            delta=f"{eval_stats.get('manual_percentage', 0):.1f}% of total"
        )
    
    with col4:
        processing_time = doc_metadata.get('processing_timestamp', '')
        if processing_time:
            try:
                dt = datetime.fromisoformat(processing_time.replace('Z', '+00:00'))
                formatted_time = dt.strftime("%Y-%m-%d %H:%M")
            except:
                formatted_time = processing_time[:16] if len(processing_time) > 16 else processing_time
        else:
            formatted_time = "Unknown"
        
        st.metric(
            label="Last Processed",
            value=formatted_time
        )
    
    # Second row of metrics
    st.subheader("Extraction Types Breakdown")
    cols = st.columns(len(extraction_counts) if extraction_counts else 1)
    
    for i, (ext_type, count) in enumerate(extraction_counts.items()):
        with cols[i % len(cols)]:
            percentage = (count / len(extractions) * 100) if extractions else 0
            st.metric(
                label=ext_type.title(),
                value=count,
                delta=f"{percentage:.1f}% of total"
            )

def display_processing_overview(data):
    """Display processing overview charts."""
    st.header("🔄 Processing Overview")
    
    eval_stats = data.get('evaluation_statistics', {})
    sections = data.get('sections', [])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Evaluation Statistics")
        
        # Create pie chart for evaluation results
        eval_data = {
            'Extract': eval_stats.get('extract_count', 0),
            'Manual': eval_stats.get('manual_count', 0),
            'Drop': eval_stats.get('drop_count', 0)
        }
        
        if sum(eval_data.values()) > 0:
            fig_eval = px.pie(
                values=list(eval_data.values()),
                names=list(eval_data.keys()),
                title="Chunk Processing Results",
                color_discrete_map={
                    'Extract': '#2E8B57',
                    'Manual': '#FF8C00', 
                    'Drop': '#DC143C'
                }
            )
            st.plotly_chart(fig_eval, use_container_width=True)
        else:
            st.info("No evaluation statistics available")
    
    with col2:
        st.subheader("Section Processing")
        
        # Section processing breakdown
        processing_types = {}
        extraction_counts = {}
        
        for section in sections:
            proc_type = section.get('processing_type', 'unknown')
            processing_types[proc_type] = processing_types.get(proc_type, 0) + 1
            
            ext_count = section.get('extraction_count', 0)
            if ext_count > 0:
                extraction_counts[section.get('section_name', 'Unknown')] = ext_count
        
        if processing_types:
            fig_sections = px.bar(
                x=list(processing_types.keys()),
                y=list(processing_types.values()),
                title="Sections by Processing Type",
                labels={'x': 'Processing Type', 'y': 'Count'},
                color=list(processing_types.values()),
                color_continuous_scale='viridis'
            )
            st.plotly_chart(fig_sections, use_container_width=True)

def display_extractions_analysis(data):
    """Display detailed extractions analysis."""
    st.header("📋 Extractions Analysis")
    
    extractions = data.get('extractions', [])
    
    if not extractions:
        st.warning("No extractions found in the data.")
        return
    
    # Create DataFrame for analysis
    extraction_data = []
    for extraction in extractions:
        extraction_data.append({
            'type': extraction.get('extraction_class', 'Unknown'),
            'section': extraction.get('section_parent_id', 'Unknown'),
            'text_length': len(extraction.get('extraction_text', '')),
            'has_attributes': len(extraction.get('attributes', {})) > 0
        })
    
    df = pd.DataFrame(extraction_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Extractions by Type")
        type_counts = df['type'].value_counts()
        fig_types = px.bar(
            x=type_counts.index,
            y=type_counts.values,
            title="Number of Extractions by Type",
            labels={'x': 'Extraction Type', 'y': 'Count'}
        )
        st.plotly_chart(fig_types, use_container_width=True)
    
    with col2:
        st.subheader("Text Length Distribution")
        fig_length = px.histogram(
            df,
            x='text_length',
            title="Distribution of Extraction Text Lengths",
            labels={'x': 'Text Length (characters)', 'y': 'Count'},
            nbins=20
        )
        st.plotly_chart(fig_length, use_container_width=True)
    
    # Show sections with most extractions
    st.subheader("Sections with Most Extractions")
    section_counts = df['section'].value_counts().head(10)
    
    if not section_counts.empty:
        fig_sections = px.bar(
            x=section_counts.values,
            y=section_counts.index,
            orientation='h',
            title="Top 10 Sections by Extraction Count",
            labels={'x': 'Number of Extractions', 'y': 'Section ID'}
        )
        st.plotly_chart(fig_sections, use_container_width=True)

def main():
    st.title("📄 Sections")
    st.markdown("Analysis of sections and processing results from LangExtract")
    
    # Sidebar for file selection
    st.sidebar.title("Data Source")
    
    # Try to find latest file automatically
    latest_file = find_latest_combined_extractions()
    
    if latest_file:
        st.sidebar.success(f"Latest file found: {latest_file.name}")
        use_latest = st.sidebar.button("Use Latest File", type="primary")
        
        # File uploader as alternative
        st.sidebar.divider()
        st.sidebar.subheader("Or upload a file:")
        uploaded_file = st.sidebar.file_uploader(
            "Choose a combined_extractions.json file",
            type=['json'],
            help="Upload your own combined_extractions.json file"
        )
        
        if uploaded_file:
            data = json.load(uploaded_file)
            file_source = f"Uploaded: {uploaded_file.name}"
        elif use_latest or latest_file:
            data = load_extractions_data(latest_file)
            file_source = f"Latest: {latest_file.parent.parent.name}"
        else:
            data = None
            file_source = None
    else:
        st.sidebar.warning("No combined_extractions.json files found in output_runs")
        uploaded_file = st.sidebar.file_uploader(
            "Upload a combined_extractions.json file",
            type=['json'],
            help="Upload your combined_extractions.json file"
        )
        
        if uploaded_file:
            data = json.load(uploaded_file)
            file_source = f"Uploaded: {uploaded_file.name}"
        else:
            data = None
            file_source = None
    
    if data:
        st.sidebar.info(f"Data source: {file_source}")
        
        # Display dashboard sections
        display_kpi_cards(data)
        st.divider()
        display_processing_overview(data)
        st.divider()
        display_extractions_analysis(data)
        
    else:
        st.info("👆 Please select a data source from the sidebar to view the dashboard.")
        st.markdown("""
        ### About this Dashboard
        
        This dashboard visualizes the output of LangExtract processing runs. It shows:
        
        - **KPI Cards**: Key metrics about the extraction process
        - **Processing Overview**: How sections were processed and evaluated
        - **Extractions Analysis**: Detailed breakdown of extracted entities
        - **Tags Page**: Specialized analytics for extracted tags
        
        To get started, either:
        1. Use the latest automatically detected file, or
        2. Upload your own `combined_extractions.json` file
        """)

if __name__ == "__main__":
    main()