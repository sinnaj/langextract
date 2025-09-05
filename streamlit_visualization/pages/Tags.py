import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re
from collections import defaultdict, Counter

st.set_page_config(
    page_title="Tags Analytics - LangExtract",
    page_icon="🏷️",
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

def extract_tag_data(data):
    """Extract and process tag data from extractions."""
    extractions = data.get('extractions', [])
    tag_extractions = [e for e in extractions if e.get('extraction_class') == 'Tag']
    
    tags_data = []
    for tag_extraction in tag_extractions:
        attrs = tag_extraction.get('attributes', {})
        tag_path = attrs.get('tag', tag_extraction.get('extraction_text', ''))
        
        # Parse hierarchical structure
        path_parts = tag_path.split('.')
        
        tags_data.append({
            'id': attrs.get('id', ''),
            'tag_path': tag_path,
            'depth': len(path_parts),
            'root_category': path_parts[0] if path_parts else '',
            'subcategory': path_parts[1] if len(path_parts) > 1 else '',
            'full_category': '.'.join(path_parts[:2]) if len(path_parts) > 1 else path_parts[0] if path_parts else '',
            'used_by_norms': attrs.get('used_by_norm_ids', []),
            'usage_count': len(attrs.get('used_by_norm_ids', [])),
            'related_topics': attrs.get('related_topics', []),
            'section_parent': tag_extraction.get('section_parent_id', ''),
            'extraction_text': tag_extraction.get('extraction_text', '')
        })
    
    return pd.DataFrame(tags_data)

def display_tag_overview(df):
    """Display tag overview metrics."""
    st.header("🏷️ Tags Overview")
    
    if df.empty:
        st.warning("No tag data found.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Tags",
            value=len(df),
            delta=f"{len(df.drop_duplicates('tag_path'))} unique"
        )
    
    with col2:
        avg_usage = df['usage_count'].mean() if not df.empty else 0
        st.metric(
            label="Average Usage",
            value=f"{avg_usage:.1f}",
            delta=f"per tag"
        )
    
    with col3:
        max_depth = df['depth'].max() if not df.empty else 0
        st.metric(
            label="Max Hierarchy Depth",
            value=max_depth,
            delta="levels"
        )
    
    with col4:
        unique_categories = len(df['root_category'].unique()) if not df.empty else 0
        st.metric(
            label="Root Categories",
            value=unique_categories
        )

def display_hierarchical_analysis(df):
    """Display hierarchical structure analysis."""
    st.header("🌳 Hierarchical Structure Analysis")
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Root Categories Distribution")
        
        root_counts = df['root_category'].value_counts()
        if not root_counts.empty:
            fig_roots = px.pie(
                values=root_counts.values,
                names=root_counts.index,
                title="Distribution of Root Categories"
            )
            st.plotly_chart(fig_roots, use_container_width=True)
        
        # Show top root categories table
        st.subheader("Top Root Categories")
        root_stats = df.groupby('root_category').agg({
            'tag_path': 'count',
            'usage_count': 'sum',
            'depth': 'mean'
        }).round(1)
        root_stats.columns = ['Tag Count', 'Total Usage', 'Avg Depth']
        root_stats = root_stats.sort_values('Tag Count', ascending=False)
        st.dataframe(root_stats, use_container_width=True)
    
    with col2:
        st.subheader("Hierarchy Depth Distribution")
        
        depth_counts = df['depth'].value_counts().sort_index()
        if not depth_counts.empty:
            fig_depth = px.bar(
                x=depth_counts.index,
                y=depth_counts.values,
                title="Number of Tags by Hierarchy Depth",
                labels={'x': 'Hierarchy Depth', 'y': 'Number of Tags'}
            )
            st.plotly_chart(fig_depth, use_container_width=True)
        
        # Show subcategories
        st.subheader("Top Subcategories")
        subcat_counts = df[df['subcategory'] != '']['full_category'].value_counts().head(10)
        if not subcat_counts.empty:
            fig_subcat = px.bar(
                x=subcat_counts.values,
                y=subcat_counts.index,
                orientation='h',
                title="Top 10 Full Categories",
                labels={'x': 'Count', 'y': 'Category'}
            )
            st.plotly_chart(fig_subcat, use_container_width=True)

def display_usage_analysis(df):
    """Display tag usage analysis."""
    st.header("📊 Tag Usage Analysis")
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Usage Distribution")
        
        # Create usage bins
        if df['usage_count'].max() > 0:
            fig_usage = px.histogram(
                df,
                x='usage_count',
                title="Distribution of Tag Usage Counts",
                labels={'x': 'Number of Norms Using Tag', 'y': 'Number of Tags'},
                nbins=min(20, df['usage_count'].max())
            )
            st.plotly_chart(fig_usage, use_container_width=True)
        
        # Show unused tags
        unused_tags = df[df['usage_count'] == 0]
        if not unused_tags.empty:
            st.warning(f"⚠️ {len(unused_tags)} tags are not used by any norms")
    
    with col2:
        st.subheader("Most Used Tags")
        
        top_used = df[df['usage_count'] > 0].nlargest(15, 'usage_count')
        if not top_used.empty:
            fig_top_used = px.bar(
                top_used,
                x='usage_count',
                y='tag_path',
                orientation='h',
                title="Top 15 Most Used Tags",
                labels={'x': 'Usage Count', 'y': 'Tag Path'}
            )
            fig_top_used.update_layout(height=600)
            st.plotly_chart(fig_top_used, use_container_width=True)

def display_topics_analysis(df):
    """Display related topics analysis."""
    st.header("🎯 Topics Analysis")
    
    if df.empty:
        return
    
    # Flatten related topics
    all_topics = []
    for topics_list in df['related_topics']:
        all_topics.extend(topics_list)
    
    if not all_topics:
        st.info("No topic data available for tags.")
        return
    
    topics_counter = Counter(all_topics)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Topic Distribution")
        
        if topics_counter:
            topics_df = pd.DataFrame(list(topics_counter.items()), columns=['Topic', 'Count'])
            fig_topics = px.bar(
                topics_df,
                x='Count',
                y='Topic',
                orientation='h',
                title="Distribution of Related Topics",
                labels={'x': 'Number of Tags', 'y': 'Topic'}
            )
            st.plotly_chart(fig_topics, use_container_width=True)
    
    with col2:
        st.subheader("Topic Co-occurrence")
        
        # Create topic co-occurrence matrix
        topic_combinations = defaultdict(int)
        for topics_list in df['related_topics']:
            if len(topics_list) > 1:
                topics_list = sorted(topics_list)
                for i in range(len(topics_list)):
                    for j in range(i+1, len(topics_list)):
                        topic_combinations[f"{topics_list[i]} + {topics_list[j]}"] += 1
        
        if topic_combinations:
            combo_df = pd.DataFrame(list(topic_combinations.items()), columns=['Combination', 'Count'])
            combo_df = combo_df.nlargest(10, 'Count')
            
            fig_combo = px.bar(
                combo_df,
                x='Count',
                y='Combination',
                orientation='h',
                title="Top 10 Topic Combinations",
                labels={'x': 'Co-occurrence Count', 'y': 'Topic Combination'}
            )
            st.plotly_chart(fig_combo, use_container_width=True)
        else:
            st.info("No topic co-occurrences found.")

def display_tag_explorer(df):
    """Display interactive tag explorer."""
    st.header("🔍 Tag Explorer")
    
    if df.empty:
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_category = st.selectbox(
            "Filter by Root Category",
            options=['All'] + sorted(df['root_category'].unique().tolist()),
            index=0
        )
    
    with col2:
        min_usage = st.slider(
            "Minimum Usage Count",
            min_value=0,
            max_value=int(df['usage_count'].max()) if not df.empty else 0,
            value=0
        )
    
    with col3:
        selected_depth = st.selectbox(
            "Filter by Hierarchy Depth",
            options=['All'] + sorted(df['depth'].unique().tolist()),
            index=0
        )
    
    # Apply filters
    filtered_df = df.copy()
    
    if selected_category != 'All':
        filtered_df = filtered_df[filtered_df['root_category'] == selected_category]
    
    if min_usage > 0:
        filtered_df = filtered_df[filtered_df['usage_count'] >= min_usage]
    
    if selected_depth != 'All':
        filtered_df = filtered_df[filtered_df['depth'] == selected_depth]
    
    st.subheader(f"Filtered Tags ({len(filtered_df)} of {len(df)})")
    
    if not filtered_df.empty:
        # Display filtered results
        display_cols = ['tag_path', 'usage_count', 'depth', 'root_category', 'related_topics']
        st.dataframe(
            filtered_df[display_cols].sort_values('usage_count', ascending=False),
            use_container_width=True,
            height=400
        )
        
        # Show detailed view for selected tag
        selected_tag = st.selectbox(
            "Select a tag for detailed view:",
            options=filtered_df['tag_path'].tolist(),
            index=0 if not filtered_df.empty else None
        )
        
        if selected_tag:
            tag_details = filtered_df[filtered_df['tag_path'] == selected_tag].iloc[0]
            
            st.subheader(f"Details for: {selected_tag}")
            
            detail_col1, detail_col2 = st.columns(2)
            
            with detail_col1:
                st.write(f"**ID:** {tag_details['id']}")
                st.write(f"**Usage Count:** {tag_details['usage_count']}")
                st.write(f"**Hierarchy Depth:** {tag_details['depth']}")
                st.write(f"**Root Category:** {tag_details['root_category']}")
            
            with detail_col2:
                st.write(f"**Related Topics:** {', '.join(tag_details['related_topics'])}")
                st.write(f"**Section Parent:** {tag_details['section_parent']}")
                st.write(f"**Extraction Text:** {tag_details['extraction_text']}")
                
                if tag_details['used_by_norms']:
                    st.write(f"**Used by {len(tag_details['used_by_norms'])} norms:**")
                    for norm_id in tag_details['used_by_norms'][:5]:  # Show first 5
                        st.write(f"  - {norm_id}")
                    if len(tag_details['used_by_norms']) > 5:
                        st.write(f"  ... and {len(tag_details['used_by_norms']) - 5} more")

def main():
    st.title("🏷️ Tags Analytics")
    st.markdown("Detailed analytics for extracted tags from LangExtract")
    
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
        
        # Extract and process tag data
        tags_df = extract_tag_data(data)
        
        if not tags_df.empty:
            # Display analytics sections
            display_tag_overview(tags_df)
            st.divider()
            display_hierarchical_analysis(tags_df)
            st.divider()
            display_usage_analysis(tags_df)
            st.divider()
            display_topics_analysis(tags_df)
            st.divider()
            display_tag_explorer(tags_df)
        else:
            st.warning("No tag data found in the selected file.")
            
    else:
        st.info("👆 Please select a data source from the sidebar to view tags analytics.")
        st.markdown("""
        ### About Tags Analytics
        
        This page provides detailed analysis of extracted tags, including:
        
        - **Overview**: Key metrics about tag extraction
        - **Hierarchical Structure**: Analysis of tag categorization and depth
        - **Usage Analysis**: How tags are used across norms
        - **Topics Analysis**: Related topics and their relationships
        - **Tag Explorer**: Interactive filtering and detailed views
        
        Tags represent structured metadata extracted from documents, organized in hierarchical paths like `DOOR.TYPE.EXIT` or `SAFETY.FIRE`.
        """)

if __name__ == "__main__":
    main()