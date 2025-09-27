import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import os
from datetime import datetime

st.set_page_config(
    page_title="Enhanced Extractions - LangExtract",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

def find_latest_enhanced_extractions():
    """Find the latest enhanced_extraction_results.json file."""
    base_path = Path(__file__).parent.parent
    output_runs_path = base_path / "output_runs"
    
    if not output_runs_path.exists():
        return None
    
    latest_file = None
    latest_timestamp = 0
    
    for run_dir in output_runs_path.iterdir():
        if run_dir.is_dir():
            # Try enhanced output first
            enhanced_file = run_dir / "enhanced_output" / "enhanced_extraction_results.json"
            if enhanced_file.exists():
                try:
                    timestamp = int(run_dir.name)
                    if timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = enhanced_file
                except ValueError:
                    continue
    
    return latest_file

def load_extractions_data(file_path):
    """Load and parse the enhanced extractions JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def extract_sections_from_hierarchy(data):
    """Extract all sections from the data structure."""
    # The enhanced format has sections directly as a list
    sections = data.get('sections', [])
    
    all_sections = []
    for section in sections:
        section_info = {
            'section_id': section.get('section_id', ''),
            'section_name': section.get('section_name', ''),
            'section_type': section.get('section_type', ''),
            'section_level': section.get('section_level', 0),
            'parent_id': section.get('parent_section_id'),
            'metadata': section,
            'start_page': section.get('start_page'),
            'end_page': section.get('end_page'),
            'toc_path': section.get('toc_path', [])
        }
        all_sections.append(section_info)
    
    return all_sections

def extract_all_extractions(data):
    """Extract all extractions from the data structure."""
    # The enhanced format has extractions, tags, and parameters as separate lists
    all_extractions = []
    
    # Process extractions
    extractions = data.get('extractions', [])
    for extraction in extractions:
        extraction_data = {
            'extraction_id': extraction.get('extraction_index', ''),
            'extraction_class': extraction.get('extraction_class', 'Unknown'),
            'extraction_text': extraction.get('extraction_text', ''),
            'attributes': extraction.get('attributes', {}),
            'section_parent_id': extraction.get('attributes', {}).get('parent_section_id', ''),
            'parent_section_name': extraction.get('attributes', {}).get('section_name', ''),
            'section_level': extraction.get('attributes', {}).get('section_level', 0)
        }
        all_extractions.append(extraction_data)
    
    # Process tags
    tags = data.get('tags', [])
    for tag in tags:
        extraction_data = {
            'extraction_id': tag.get('attributes', {}).get('id', ''),
            'extraction_class': 'Tag',
            'extraction_text': tag.get('extraction_text', ''),
            'attributes': tag.get('attributes', {}),
            'section_parent_id': '',
            'parent_section_name': '',
            'section_level': 0
        }
        all_extractions.append(extraction_data)
    
    # Process parameters
    parameters = data.get('parameters', [])
    for param in parameters:
        extraction_data = {
            'extraction_id': param.get('attributes', {}).get('id', ''),
            'extraction_class': 'Parameter',
            'extraction_text': param.get('extraction_text', ''),
            'attributes': param.get('attributes', {}),
            'section_parent_id': '',
            'parent_section_name': '',
            'section_level': 0
        }
        all_extractions.append(extraction_data)
    
    return all_extractions

def display_kpi_cards(data):
    """Display KPI cards with key metrics."""
    st.header("📊 Key Performance Indicators")
    
    # Extract key metrics from new schema
    pipeline_info = data.get('pipeline_info', {})
    processing_stats = data.get('processing_stats', {})
    
    # Get sections and extractions
    all_sections = extract_sections_from_hierarchy(data)
    all_extractions = extract_all_extractions(data)
    
    # Count extractions by type
    extraction_counts = {}
    for extraction in all_extractions:
        ext_type = extraction.get('extraction_class', 'Unknown')
        extraction_counts[ext_type] = extraction_counts.get(ext_type, 0) + 1
    
    # Create columns for KPI cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Extractions",
            value=pipeline_info.get('total_extractions', len(all_extractions)),
            delta=f"from {pipeline_info.get('total_sections', len(all_sections))} sections"
        )
    
    with col2:
        st.metric(
            label="Total Sections",
            value=len(all_sections),
            delta=f"{pipeline_info.get('total_chunks', 0)} chunks processed"
        )
    
    with col3:
        st.metric(
            label="Tags Count",
            value=pipeline_info.get('total_tags', 0),
            delta=f"{pipeline_info.get('total_parameters', 0)} parameters"
        )
    
    with col4:
        # Pipeline information
        st.metric(
            label="Pipeline Version",
            value=pipeline_info.get('version', 'Unknown'),
            delta=pipeline_info.get('method', '').replace('_', ' ').title()
        )
    
    # Second row of metrics
    if extraction_counts:
        st.subheader("Extraction Types Breakdown")
        cols = st.columns(min(len(extraction_counts), 4))
        
        for i, (ext_type, count) in enumerate(list(extraction_counts.items())[:4]):
            with cols[i]:
                percentage = (count / len(all_extractions) * 100) if all_extractions else 0
                st.metric(
                    label=ext_type.replace('_', ' ').title(),
                    value=count,
                    delta=f"{percentage:.1f}% of total"
                )

def display_processing_overview(data):
    """Display processing overview charts."""
    st.header("🔄 Processing Overview")
    
    # Extract processing information from new schema
    pipeline_info = data.get('pipeline_info', {})
    processing_stats = data.get('processing_stats', {})
    
    all_sections = extract_sections_from_hierarchy(data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Pipeline Information")
        
        # Create metrics for pipeline
        pipeline_data = {
            'Total Chunks': processing_stats.get('chunks_processed', 0),
            'Successful Extractions': processing_stats.get('successful_extractions', 0),
            'Sections with Extractions': processing_stats.get('sections_with_extractions', 0)
        }
        
        if sum(pipeline_data.values()) > 0:
            fig_pipeline = px.bar(
                x=list(pipeline_data.keys()),
                y=list(pipeline_data.values()),
                title="Processing Pipeline Results",
                labels={'x': 'Metric', 'y': 'Count'},
                color=list(pipeline_data.values()),
                color_continuous_scale='viridis'
            )
            st.plotly_chart(fig_pipeline, use_container_width=True)
        else:
            st.info("No processing statistics available")
    
    with col2:
        st.subheader("Section Hierarchy")
        
        # Section level breakdown
        level_counts = {}
        type_counts = {}
        
        for section in all_sections:
            level = section.get('section_level', 0)
            level_counts[f"Level {level}"] = level_counts.get(f"Level {level}", 0) + 1
            
            section_type = section.get('section_type', 'Unknown')
            type_counts[section_type] = type_counts.get(section_type, 0) + 1
        
        if level_counts:
            fig_levels = px.pie(
                values=list(level_counts.values()),
                names=list(level_counts.keys()),
                title="Sections by Hierarchy Level",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig_levels, use_container_width=True)
        
        # Show section types
        if type_counts and len(type_counts) > 1:
            st.subheader("Section Types")
            for section_type, count in type_counts.items():
                st.metric(f"{section_type}", count)

def display_extractions_analysis(data):
    """Display detailed extractions analysis."""
    st.header("📋 Extractions Analysis")
    
    sections_data = data.get('enhanced_sections', {})
    all_extractions = extract_all_extractions(sections_data)
    
    if not all_extractions:
        st.warning("No extractions found in the data.")
        return
    
    # Create DataFrame for analysis
    extraction_data = []
    for extraction in all_extractions:
        extraction_data.append({
            'type': extraction.get('extraction_class', 'Unknown'),
            'section': extraction.get('section_parent_id', 'Unknown'),
            'section_name': extraction.get('parent_section_name', 'Unknown'),
            'section_level': extraction.get('section_level', 0),
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
            labels={'x': 'Extraction Type', 'y': 'Count'},
            color=type_counts.values,
            color_continuous_scale='viridis'
        )
        st.plotly_chart(fig_types, use_container_width=True)
    
    with col2:
        st.subheader("Text Length Distribution")
        if df['text_length'].max() > 0:
            fig_length = px.histogram(
                df,
                x='text_length',
                title="Distribution of Extraction Text Lengths",
                labels={'x': 'Text Length (characters)', 'y': 'Count'},
                nbins=20,
                color_discrete_sequence=['#1f77b4']
            )
            st.plotly_chart(fig_length, use_container_width=True)
        else:
            st.info("No text length data available")
    
    # Show sections with most extractions
    st.subheader("Sections with Most Extractions")
    section_counts = df['section_name'].value_counts().head(10)
    
    if not section_counts.empty:
        fig_sections = px.bar(
            x=section_counts.values,
            y=section_counts.index,
            orientation='h',
            title="Top 10 Sections by Extraction Count",
            labels={'x': 'Number of Extractions', 'y': 'Section Name'},
            color=section_counts.values,
            color_continuous_scale='plasma'
        )
        fig_sections.update_layout(height=400)
        st.plotly_chart(fig_sections, use_container_width=True)
    
    # Show extraction types by section level
    if 'section_level' in df.columns:
        st.subheader("Extractions by Section Level")
        level_type_data = df.groupby(['section_level', 'type']).size().reset_index(name='count')
        
        if not level_type_data.empty:
            fig_level_type = px.bar(
                level_type_data,
                x='section_level',
                y='count',
                color='type',
                title="Extraction Types by Section Hierarchy Level",
                labels={'section_level': 'Section Level', 'count': 'Number of Extractions'},
                barmode='stack'
            )
            st.plotly_chart(fig_level_type, use_container_width=True)

def main():
    st.title("📄 Enhanced Extractions")
    st.markdown("Analysis of sections and processing results from LangExtract Enhanced Pipeline")
    
    # Sidebar for file selection
    st.sidebar.title("Data Source")
    
    # Try to find latest file automatically
    latest_file = find_latest_enhanced_extractions()
    
    if latest_file:
        st.sidebar.success(f"Latest file found: {latest_file.name}")
        use_latest = st.sidebar.button("Use Latest File", type="primary")
        
        # File uploader as alternative
        st.sidebar.divider()
        st.sidebar.subheader("Or upload a file:")
        uploaded_file = st.sidebar.file_uploader(
            "Choose an enhanced_extraction_results.json file",
            type=['json'],
            help="Upload your own enhanced_extraction_results.json file"
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
        st.sidebar.warning("No enhanced_extraction_results.json files found in output_runs")
        uploaded_file = st.sidebar.file_uploader(
            "Upload an enhanced_extraction_results.json file",
            type=['json'],
            help="Upload your enhanced_extraction_results.json file"
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
        ### About this Enhanced Dashboard
        
        This dashboard visualizes the output of the Enhanced LangExtract processing pipeline. It shows:
        
        - **KPI Cards**: Key metrics about the extraction process including sections, extractions, tags, and parameters
        - **Processing Overview**: Pipeline performance and section hierarchy breakdown
        - **Extractions Analysis**: Detailed breakdown of extracted entities by type, text length, and section distribution
        - **Specialized Pages**: Analytics for Tags, Norms, Parameters, and Legal Documents
        
        The enhanced pipeline provides:
        - **Hierarchical section structure** with deterministic IDs
        - **PDF text anchoring** with highlight coordinates
        - **Parameter normalization** with SI unit conversion
        - **Comprehensive extraction metadata** and quality metrics
        
        To get started, either:
        1. Use the latest automatically detected enhanced extraction results file, or
        2. Upload your own `enhanced_extraction_results.json` file
        """)

if __name__ == "__main__":
    main()