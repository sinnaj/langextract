import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from collections import defaultdict, Counter

st.set_page_config(
    page_title="Parameters Analytics - LangExtract",
    page_icon="⚙️",
    layout="wide"
)

def find_latest_combined_extractions():
    """Find the latest combined_extractions.json file."""
    base_path = Path(__file__).parent.parent.parent
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

def extract_parameters_data(data):
    """Extract and process parameters data from extractions."""
    extractions = data.get('extractions', [])
    sections = data.get('sections', [])
    
    # Create section mapping for easy lookup
    section_map = {s.get('section_id'): s for s in sections}
    
    parameter_extractions = [e for e in extractions if e.get('extraction_class') == 'Parameter']
    
    parameters_data = []
    for param in parameter_extractions:
        attrs = param.get('attributes', {})
        section_id = param.get('section_parent_id', '')
        section_info = section_map.get(section_id, {})
        
        parameters_data.append({
            'id': attrs.get('id', ''),
            'applies_for_tag': attrs.get('applies_for_tag', ''),
            'operator': attrs.get('operator', ''),
            'value': attrs.get('value', ''),
            'unit': attrs.get('unit', ''),
            'norm_ids': attrs.get('norm_ids', []),
            'section_id': section_id,
            'section_name': section_info.get('section_name', ''),
            'section_level': section_info.get('section_level', 0),
            'extraction_text': param.get('extraction_text', ''),
            'norm_count': len(attrs.get('norm_ids', [])),
            'has_unit': bool(attrs.get('unit')),
            'value_type': type(attrs.get('value', '')).__name__,
            'tag_category': attrs.get('applies_for_tag', '').split('.')[0] if attrs.get('applies_for_tag') else ''
        })
    
    return pd.DataFrame(parameters_data)

def display_parameters_overview(df):
    """Display parameters overview metrics."""
    st.header("⚙️ Parameters Overview")
    
    if df.empty:
        st.warning("No parameters data found.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Parameters",
            value=len(df),
            delta=f"{len(df['id'].unique())} unique"
        )
    
    with col2:
        unique_tags = len(df['applies_for_tag'].unique()) if not df.empty else 0
        st.metric(
            label="Unique Tags",
            value=unique_tags,
            delta="parameters apply to"
        )
    
    with col3:
        avg_norms = df['norm_count'].mean() if not df.empty else 0
        st.metric(
            label="Avg Norms per Parameter",
            value=f"{avg_norms:.1f}",
            delta="relationships"
        )
    
    with col4:
        with_units = df['has_unit'].sum() if not df.empty else 0
        st.metric(
            label="Parameters with Units",
            value=with_units,
            delta=f"{(with_units/len(df)*100):.1f}% of total" if len(df) > 0 else "0%"
        )

def display_parameters_analysis(df):
    """Display parameters analysis charts."""
    st.header("📊 Parameters Analysis")
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Operators Distribution")
        
        operator_counts = df['operator'].value_counts()
        if not operator_counts.empty:
            fig_operators = px.pie(
                values=operator_counts.values,
                names=operator_counts.index,
                title="Distribution of Parameter Operators"
            )
            st.plotly_chart(fig_operators, use_container_width=True)
    
    with col2:
        st.subheader("Value Types Distribution")
        
        type_counts = df['value_type'].value_counts()
        if not type_counts.empty:
            fig_types = px.bar(
                x=type_counts.index,
                y=type_counts.values,
                title="Parameter Value Types",
                labels={'x': 'Value Type', 'y': 'Count'}
            )
            st.plotly_chart(fig_types, use_container_width=True)
    
    # Tag categories analysis
    st.subheader("Tag Categories Analysis")
    
    col3, col4 = st.columns(2)
    
    with col3:
        category_counts = df['tag_category'].value_counts().head(10)
        if not category_counts.empty:
            fig_categories = px.bar(
                x=category_counts.values,
                y=category_counts.index,
                orientation='h',
                title="Top 10 Tag Categories",
                labels={'x': 'Number of Parameters', 'y': 'Tag Category'}
            )
            st.plotly_chart(fig_categories, use_container_width=True)
    
    with col4:
        # Parameters with most norm relationships
        top_connected = df.nlargest(10, 'norm_count')
        if not top_connected.empty:
            fig_connected = px.bar(
                top_connected,
                x='norm_count',
                y='applies_for_tag',
                orientation='h',
                title="Parameters with Most Norm Relationships",
                labels={'x': 'Number of Related Norms', 'y': 'Parameter Tag'}
            )
            st.plotly_chart(fig_connected, use_container_width=True)

def display_value_analysis(df):
    """Display parameter value analysis."""
    st.header("🔢 Value Analysis")
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Numeric Values Distribution")
        
        # Filter numeric values
        numeric_df = df[df['value_type'].isin(['int', 'float'])].copy()
        if not numeric_df.empty:
            numeric_df['numeric_value'] = pd.to_numeric(numeric_df['value'], errors='coerce')
            numeric_df = numeric_df.dropna(subset=['numeric_value'])
            
            if not numeric_df.empty:
                fig_values = px.histogram(
                    numeric_df,
                    x='numeric_value',
                    title="Distribution of Numeric Parameter Values",
                    labels={'x': 'Value', 'y': 'Count'},
                    nbins=20
                )
                st.plotly_chart(fig_values, use_container_width=True)
        else:
            st.info("No numeric parameters found.")
    
    with col2:
        st.subheader("Units Distribution")
        
        units_df = df[df['has_unit'] == True]
        if not units_df.empty:
            unit_counts = units_df['unit'].value_counts()
            fig_units = px.bar(
                x=unit_counts.index,
                y=unit_counts.values,
                title="Distribution of Parameter Units",
                labels={'x': 'Unit', 'y': 'Count'}
            )
            st.plotly_chart(fig_units, use_container_width=True)
        else:
            st.info("No parameters with units found.")

def display_parameters_explorer(df, all_sections, all_norms):
    """Display interactive parameters explorer."""
    st.header("🔍 Parameters Explorer")
    
    if df.empty:
        return
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        selected_operator = st.selectbox(
            "Filter by Operator",
            options=['All'] + sorted(df['operator'].unique().tolist()),
            index=0
        )
    
    with col2:
        selected_section = st.selectbox(
            "Filter by Section",
            options=['All'] + sorted([s.get('section_name', '') for s in all_sections if s.get('section_name')]),
            index=0
        )
    
    with col3:
        selected_category = st.selectbox(
            "Filter by Tag Category",
            options=['All'] + sorted(df['tag_category'].unique().tolist()),
            index=0
        )
    
    with col4:
        has_unit_filter = st.selectbox(
            "Filter by Unit",
            options=['All', 'With Unit', 'Without Unit'],
            index=0
        )
    
    # Explicit parameter search
    st.subheader("Search by Explicit Parameters")
    col5, col6 = st.columns(2)
    
    with col5:
        tag_search = st.text_input("Search by Tag (contains):", "")
    
    with col6:
        value_search = st.text_input("Search by Value (contains):", "")
    
    # Apply filters
    filtered_df = df.copy()
    
    if selected_operator != 'All':
        filtered_df = filtered_df[filtered_df['operator'] == selected_operator]
    
    if selected_section != 'All':
        filtered_df = filtered_df[filtered_df['section_name'] == selected_section]
    
    if selected_category != 'All':
        filtered_df = filtered_df[filtered_df['tag_category'] == selected_category]
    
    if has_unit_filter == 'With Unit':
        filtered_df = filtered_df[filtered_df['has_unit'] == True]
    elif has_unit_filter == 'Without Unit':
        filtered_df = filtered_df[filtered_df['has_unit'] == False]
    
    if tag_search:
        filtered_df = filtered_df[filtered_df['applies_for_tag'].str.contains(tag_search, case=False, na=False)]
    
    if value_search:
        filtered_df = filtered_df[filtered_df['value'].astype(str).str.contains(value_search, case=False, na=False)]
    
    st.subheader(f"Filtered Parameters ({len(filtered_df)} of {len(df)})")
    
    if not filtered_df.empty:
        # Display filtered results
        display_cols = ['applies_for_tag', 'operator', 'value', 'unit', 'norm_count', 'section_name']
        display_df = filtered_df[display_cols].copy()
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )
        
        # Show detailed view for selected parameter
        if len(filtered_df) > 0:
            selected_param_idx = st.selectbox(
                "Select a parameter for detailed view:",
                options=range(len(filtered_df)),
                format_func=lambda x: f"Parameter {x+1}: {filtered_df.iloc[x]['applies_for_tag']} {filtered_df.iloc[x]['operator']} {filtered_df.iloc[x]['value']}"
            )
            
            if selected_param_idx is not None:
                param_details = filtered_df.iloc[selected_param_idx]
                
                st.subheader("Parameter Details")
                
                detail_col1, detail_col2 = st.columns(2)
                
                with detail_col1:
                    st.write(f"**ID:** {param_details['id']}")
                    st.write(f"**Applies For Tag:** {param_details['applies_for_tag']}")
                    st.write(f"**Operator:** {param_details['operator']}")
                    st.write(f"**Value:** {param_details['value']}")
                    st.write(f"**Unit:** {param_details['unit'] if param_details['unit'] else 'No unit'}")
                    st.write(f"**Value Type:** {param_details['value_type']}")
                
                with detail_col2:
                    st.write(f"**Section:** {param_details['section_name']}")
                    st.write(f"**Tag Category:** {param_details['tag_category']}")
                    st.write(f"**Related Norms Count:** {param_details['norm_count']}")
                    
                    if param_details['norm_ids']:
                        st.write(f"**Related Norm IDs:**")
                        for norm_id in param_details['norm_ids'][:5]:
                            st.write(f"  - {norm_id}")
                        if len(param_details['norm_ids']) > 5:
                            st.write(f"  ... and {len(param_details['norm_ids']) - 5} more")
                
                st.write("**Full Extraction Text:**")
                st.write(param_details['extraction_text'])

def main():
    st.title("⚙️ Parameters Analytics")
    st.markdown("Detailed analytics for extracted parameters from LangExtract")
    
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
        
        # Extract and process parameters data
        parameters_df = extract_parameters_data(data)
        all_sections = data.get('sections', [])
        all_norms = [e for e in data.get('extractions', []) if e.get('extraction_class') == 'NORM']
        
        if not parameters_df.empty:
            # Display analytics sections
            display_parameters_overview(parameters_df)
            st.divider()
            display_parameters_analysis(parameters_df)
            st.divider()
            display_value_analysis(parameters_df)
            st.divider()
            display_parameters_explorer(parameters_df, all_sections, all_norms)
        else:
            st.warning("No parameters data found in the selected file.")
            
    else:
        st.info("👆 Please select a data source from the sidebar to view parameters analytics.")
        st.markdown("""
        ### About Parameters Analytics
        
        This page provides detailed analysis of extracted parameters, including:
        
        - **Overview**: Key metrics about parameter extraction
        - **Analysis**: Distribution of operators, value types, and tag categories
        - **Value Analysis**: Analysis of numeric values and units
        - **Explorer**: Interactive filtering by norms, sections, and parameter values
        
        Parameters represent specific values and conditions extracted from documents, including operators, values, units, and their relationships to tags and norms.
        """)

if __name__ == "__main__":
    main()