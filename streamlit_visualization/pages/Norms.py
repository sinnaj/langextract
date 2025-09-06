import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from collections import defaultdict, Counter

st.set_page_config(
    page_title="Norms Analytics - LangExtract",
    page_icon="📋",
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

def extract_norms_data(data):
    """Extract and process norms data from extractions."""
    extractions = data.get('extractions', [])
    sections = data.get('sections', [])
    
    # Create section mapping for easy lookup
    section_map = {s.get('section_id'): s for s in sections}
    
    norm_extractions = [e for e in extractions if e.get('extraction_class') == 'NORM']
    
    norms_data = []
    for norm in norm_extractions:
        attrs = norm.get('attributes', {})
        section_id = norm.get('section_parent_id', '')
        section_info = section_map.get(section_id, {})
        
        norms_data.append({
            'id': attrs.get('id', ''),
            'norm_statement': attrs.get('norm_statement', ''),
            'obligation_type': attrs.get('obligation_type', ''),
            'priority': attrs.get('priority', 0),
            'priority_factors': attrs.get('priority_factors', {}),
            'topics': attrs.get('topics', []),
            'relevant_tags': attrs.get('relevant_tags', []),
            'applies_if': attrs.get('applies_if', ''),
            'satisfied_if': attrs.get('satisfied_if', ''),
            'exempt_if': attrs.get('exempt_if', ''),
            'project_dimensions': attrs.get('project_dimensions', {}),
            'location_scope': attrs.get('location_scope', {}),
            'confidence': attrs.get('confidence', 0),
            'section_id': section_id,
            'section_name': section_info.get('section_name', ''),
            'section_level': section_info.get('section_level', 0),
            'extraction_text': norm.get('extraction_text', ''),
            'paragraph_number': attrs.get('paragraph_number', 0),
            'severity': attrs.get('priority_factors', {}).get('severity', 0),
            'likelihood': attrs.get('priority_factors', {}).get('likelihood', 0),
            'impact': attrs.get('priority_factors', {}).get('impact', 0),
            'tag_count': len(attrs.get('relevant_tags', [])),
            'topics_count': len(attrs.get('topics', []))
        })
    
    return pd.DataFrame(norms_data)

def display_norms_overview(df):
    """Display norms overview metrics."""
    st.header("📋 Norms Overview")
    
    if df.empty:
        st.warning("No norms data found.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Norms",
            value=len(df),
            delta=f"{len(df['id'].unique())} unique"
        )
    
    with col2:
        avg_priority = df['priority'].mean() if not df.empty else 0
        st.metric(
            label="Average Priority",
            value=f"{avg_priority:.1f}",
            delta=f"out of 5"
        )
    
    with col3:
        avg_confidence = df['confidence'].mean() if not df.empty else 0
        st.metric(
            label="Average Confidence",
            value=f"{avg_confidence:.2f}",
            delta=f"out of 1.0"
        )
    
    with col4:
        unique_sections = len(df['section_id'].unique()) if not df.empty else 0
        st.metric(
            label="Sections with Norms",
            value=unique_sections
        )

def display_norms_analysis(df):
    """Display norms analysis charts."""
    st.header("📊 Norms Analysis")
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Obligation Types Distribution")
        
        obligation_counts = df['obligation_type'].value_counts()
        if not obligation_counts.empty:
            fig_obligations = px.pie(
                values=obligation_counts.values,
                names=obligation_counts.index,
                title="Distribution of Obligation Types"
            )
            st.plotly_chart(fig_obligations, use_container_width=True)
    
    with col2:
        st.subheader("Priority Distribution")
        
        priority_counts = df['priority'].value_counts().sort_index()
        if not priority_counts.empty:
            fig_priority = px.bar(
                x=priority_counts.index,
                y=priority_counts.values,
                title="Number of Norms by Priority Level",
                labels={'x': 'Priority Level', 'y': 'Number of Norms'}
            )
            st.plotly_chart(fig_priority, use_container_width=True)
    
    # Priority factors analysis
    st.subheader("Priority Factors Analysis")
    
    col3, col4 = st.columns(2)
    
    with col3:
        # Scatter plot of severity vs likelihood
        if 'severity' in df.columns and 'likelihood' in df.columns:
            fig_factors = px.scatter(
                df,
                x='severity',
                y='likelihood',
                size='impact',
                color='priority',
                title="Severity vs Likelihood (bubble size = impact)",
                labels={'x': 'Severity', 'y': 'Likelihood'}
            )
            st.plotly_chart(fig_factors, use_container_width=True)
    
    with col4:
        # Top topics
        all_topics = []
        for topics_list in df['topics']:
            all_topics.extend(topics_list)
        
        if all_topics:
            topics_counter = Counter(all_topics)
            topics_df = pd.DataFrame(list(topics_counter.items()), columns=['Topic', 'Count'])
            topics_df = topics_df.nlargest(10, 'Count')
            
            fig_topics = px.bar(
                topics_df,
                x='Count',
                y='Topic',
                orientation='h',
                title="Top 10 Topics in Norms"
            )
            st.plotly_chart(fig_topics, use_container_width=True)

def display_norms_explorer(df, all_sections, all_tags):
    """Display interactive norms explorer."""
    st.header("🔍 Norms Explorer")
    
    if df.empty:
        return
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        selected_obligation = st.selectbox(
            "Filter by Obligation Type",
            options=['All'] + sorted(df['obligation_type'].unique().tolist()),
            index=0
        )
    
    with col2:
        selected_section = st.selectbox(
            "Filter by Section",
            options=['All'] + sorted([s.get('section_name', '') for s in all_sections if s.get('section_name')]),
            index=0
        )
    
    with col3:
        min_priority = st.slider(
            "Minimum Priority",
            min_value=int(df['priority'].min()) if not df.empty else 0,
            max_value=int(df['priority'].max()) if not df.empty else 5,
            value=int(df['priority'].min()) if not df.empty else 0
        )
    
    with col4:
        # Tag filter
        all_available_tags = set()
        for tag_list in df['relevant_tags']:
            all_available_tags.update(tag_list)
        
        selected_tag = st.selectbox(
            "Filter by Tag",
            options=['All'] + sorted(list(all_available_tags)),
            index=0
        )
    
    # Apply filters
    filtered_df = df.copy()
    
    if selected_obligation != 'All':
        filtered_df = filtered_df[filtered_df['obligation_type'] == selected_obligation]
    
    if selected_section != 'All':
        filtered_df = filtered_df[filtered_df['section_name'] == selected_section]
    
    if min_priority > df['priority'].min():
        filtered_df = filtered_df[filtered_df['priority'] >= min_priority]
    
    if selected_tag != 'All':
        filtered_df = filtered_df[filtered_df['relevant_tags'].apply(lambda x: selected_tag in x)]
    
    st.subheader(f"Filtered Norms ({len(filtered_df)} of {len(df)})")
    
    if not filtered_df.empty:
        # Display filtered results
        display_cols = ['norm_statement', 'obligation_type', 'priority', 'confidence', 'section_name', 'topics']
        display_df = filtered_df[display_cols].copy()
        display_df['norm_statement'] = display_df['norm_statement'].apply(lambda x: x[:100] + '...' if len(x) > 100 else x)
        display_df['topics'] = display_df['topics'].apply(lambda x: ', '.join(x[:3]) + ('...' if len(x) > 3 else ''))
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )
        
        # Show detailed view for selected norm
        if len(filtered_df) > 0:
            selected_norm_idx = st.selectbox(
                "Select a norm for detailed view:",
                options=range(len(filtered_df)),
                format_func=lambda x: f"Norm {x+1}: {filtered_df.iloc[x]['norm_statement'][:50]}..."
            )
            
            if selected_norm_idx is not None:
                norm_details = filtered_df.iloc[selected_norm_idx]
                
                st.subheader("Norm Details")
                
                detail_col1, detail_col2 = st.columns(2)
                
                with detail_col1:
                    st.write(f"**ID:** {norm_details['id']}")
                    st.write(f"**Obligation Type:** {norm_details['obligation_type']}")
                    st.write(f"**Priority:** {norm_details['priority']}")
                    st.write(f"**Confidence:** {norm_details['confidence']:.2f}")
                    st.write(f"**Section:** {norm_details['section_name']}")
                    st.write(f"**Topics:** {', '.join(norm_details['topics'])}")
                
                with detail_col2:
                    st.write(f"**Applies If:** {norm_details['applies_if']}")
                    st.write(f"**Satisfied If:** {norm_details['satisfied_if']}")
                    st.write(f"**Exempt If:** {norm_details['exempt_if']}")
                    st.write(f"**Relevant Tags:** {', '.join(norm_details['relevant_tags'][:5])}")
                    if len(norm_details['relevant_tags']) > 5:
                        st.write(f"... and {len(norm_details['relevant_tags']) - 5} more tags")
                
                st.write("**Full Statement:**")
                st.write(norm_details['norm_statement'])

def main():
    st.title("📋 Norms Analytics")
    st.markdown("Detailed analytics for extracted norms from LangExtract")
    
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
        
        # Extract and process norms data
        norms_df = extract_norms_data(data)
        all_sections = data.get('sections', [])
        all_extractions = data.get('extractions', [])
        all_tags = [e.get('attributes', {}).get('tag', '') for e in all_extractions if e.get('extraction_class') == 'Tag']
        
        if not norms_df.empty:
            # Display analytics sections
            display_norms_overview(norms_df)
            st.divider()
            display_norms_analysis(norms_df)
            st.divider()
            display_norms_explorer(norms_df, all_sections, all_tags)
        else:
            st.warning("No norms data found in the selected file.")
            
    else:
        st.info("👆 Please select a data source from the sidebar to view norms analytics.")
        st.markdown("""
        ### About Norms Analytics
        
        This page provides detailed analysis of extracted norms, including:
        
        - **Overview**: Key metrics about norm extraction
        - **Analysis**: Distribution of obligation types, priorities, and topics
        - **Explorer**: Interactive filtering by tags, sections, and norm attributes
        
        Norms represent regulatory requirements extracted from documents, including their conditions, priorities, and relationships to other elements.
        """)

if __name__ == "__main__":
    main()