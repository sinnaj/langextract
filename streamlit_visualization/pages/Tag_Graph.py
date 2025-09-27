import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from pathlib import Path
import re
from collections import defaultdict, Counter

st.set_page_config(
    page_title="Tag Graph - LangExtract",
    page_icon="🕸️",
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

def create_tag_network_graph(df):
    """Create a network graph showing tag relationships."""
    if df.empty:
        return None
    
    # Create a graph
    G = nx.Graph()
    
    # Track parent-child relationships
    relationships = []
    tag_info = {}
    
    # Process each tag to find hierarchical relationships
    for _, row in df.iterrows():
        tag_path = row['tag_path']
        path_parts = tag_path.split('.')
        
        # Store tag information
        tag_info[tag_path] = {
            'usage_count': row['usage_count'],
            'id': row['id'],
            'related_topics': row['related_topics'],
            'depth': row['depth'],
            'is_chained': len(path_parts) > 1
        }
        
        # Add the tag as a node
        G.add_node(tag_path, **tag_info[tag_path])
        
        # Create edges for hierarchical relationships
        if len(path_parts) > 1:
            # Connect to parent tag
            parent_path = '.'.join(path_parts[:-1])
            if parent_path in [t['tag_path'] for _, t in df.iterrows()]:
                G.add_edge(parent_path, tag_path)
                relationships.append((parent_path, tag_path))
    
    return G, tag_info, relationships

def create_plotly_network_graph(G, tag_info):
    """Create an interactive network graph using plotly."""
    if G is None or len(G.nodes()) == 0:
        return None
    
    # Calculate positions using spring layout
    pos = nx.spring_layout(G, k=3, iterations=50)
    
    # Prepare node traces
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_size = []
    node_info = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        
        info = tag_info.get(node, {})
        usage_count = info.get('usage_count', 0)
        depth = info.get('depth', 1)
        is_chained = info.get('is_chained', False)
        
        # Node text
        display_text = node
        if len(display_text) > 15:
            display_text = display_text[:12] + "..."
        node_text.append(display_text)
        
        # Node color based on depth
        if depth == 1:
            color = '#1f77b4'  # Blue for root tags
        elif depth == 2:
            color = '#ff7f0e'  # Orange for second level
        elif depth == 3:
            color = '#2ca02c'  # Green for third level
        else:
            color = '#d62728'  # Red for deeper levels
        node_color.append(color)
        
        # Node size based on usage count
        size = max(10, min(50, 10 + usage_count * 5))
        node_size.append(size)
        
        # Hover info
        hover_text = f"Tag: {node}<br>"
        hover_text += f"Usage Count: {usage_count}<br>"
        hover_text += f"Depth: {depth}<br>"
        hover_text += f"Chained: {'Yes' if is_chained else 'No'}<br>"
        if info.get('related_topics'):
            hover_text += f"Related Topics: {', '.join(info['related_topics'])}"
        node_info.append(hover_text)
    
    # Prepare edge traces
    edge_x = []
    edge_y = []
    
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    
    # Create edge trace
    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=2, color='rgba(125,125,125,0.5)'),
        hoverinfo='none',
        mode='lines'
    )
    
    # Create node trace
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        hovertemplate='%{customdata}<extra></extra>',
        customdata=node_info,
        text=node_text,
        textposition="middle center",
        textfont=dict(size=10),
        marker=dict(
            showscale=True,
            colorscale='viridis',
            color=node_size,  # Use size for color scale
            size=node_size,
            colorbar=dict(
                thickness=15,
                len=0.7,
                x=1.0,
                title="Usage Count"
            ),
            line=dict(width=2)
        )
    )
    
    # Create the figure
    fig = go.Figure(data=[edge_trace, node_trace],
                   layout=go.Layout(
                       title=dict(
                           text='Tag Relationship Network Graph',
                           font=dict(size=16)
                       ),
                       showlegend=False,
                       hovermode='closest',
                       margin=dict(b=20,l=5,r=5,t=40),
                       annotations=[
                           dict(
                               text="Node size represents usage count. Colors represent hierarchy depth.",
                               showarrow=False,
                               xref="paper", yref="paper",
                               x=0.005, y=-0.002,
                               xanchor='left', yanchor='bottom',
                               font=dict(size=12)
                           )
                       ],
                       xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       height=700
                   ))
    
    return fig

def display_tag_usage_details(df, selected_tag):
    """Display detailed usage information for a selected tag."""
    if selected_tag and not df.empty:
        tag_data = df[df['tag_path'] == selected_tag]
        if not tag_data.empty:
            tag_info = tag_data.iloc[0]
            
            st.subheader(f"📍 Usage Details: {selected_tag}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Tag ID:** {tag_info['id']}")
                st.write(f"**Usage Count:** {tag_info['usage_count']}")
                st.write(f"**Hierarchy Depth:** {tag_info['depth']}")
                st.write(f"**Root Category:** {tag_info['root_category']}")
                
                # Show if it's a chained tag
                if '.' in selected_tag:
                    st.info("🔗 This is a chained tag (contains dots)")
                else:
                    st.info("🏷️ This is a root-level tag")
            
            with col2:
                if tag_info['related_topics']:
                    st.write(f"**Related Topics:**")
                    for topic in tag_info['related_topics']:
                        st.write(f"- {topic}")
                
                st.write(f"**Section Parent:** {tag_info['section_parent']}")
                
                if tag_info['used_by_norms']:
                    st.write(f"**Used by {len(tag_info['used_by_norms'])} norm(s):**")
                    for norm_id in tag_info['used_by_norms'][:5]:  # Show first 5
                        st.write(f"- {norm_id}")
                    if len(tag_info['used_by_norms']) > 5:
                        st.write(f"... and {len(tag_info['used_by_norms']) - 5} more")

def display_graph_statistics(df, G):
    """Display statistics about the tag graph."""
    st.header("📊 Graph Statistics")
    
    if df.empty or G is None:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Tags", len(df))
    
    with col2:
        chained_tags = len(df[df['tag_path'].str.contains('.', regex=False)])
        st.metric("Chained Tags", chained_tags)
    
    with col3:
        root_tags = len(df[~df['tag_path'].str.contains('.', regex=False)])
        st.metric("Root Tags", root_tags)
    
    with col4:
        if G:
            connected_components = nx.number_connected_components(G)
            st.metric("Connected Components", connected_components)

def main():
    st.title("🕸️ Tag Graph")
    st.markdown("Interactive network graph showing relationships between extracted tags")
    
    # Sidebar for file selection (same pattern as Tags.py)
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
            # Create network graph
            G, tag_info, relationships = create_tag_network_graph(tags_df)
            
            # Display graph statistics
            display_graph_statistics(tags_df, G)
            st.divider()
            
            # Create and display the interactive graph
            st.header("🔗 Tag Relationship Network")
            
            if G and len(G.nodes()) > 0:
                fig = create_plotly_network_graph(G, tag_info)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Tag selection for detailed view
                    st.divider()
                    selected_tag = st.selectbox(
                        "Select a tag to see detailed usage information:",
                        options=[""] + sorted(tags_df['tag_path'].tolist()),
                        index=0,
                        help="Choose a tag to see where it's used and its relationships"
                    )
                    
                    if selected_tag:
                        display_tag_usage_details(tags_df, selected_tag)
                    
                    # Show relationships table
                    if relationships:
                        st.divider()
                        st.header("🔗 Tag Relationships")
                        relationships_df = pd.DataFrame(relationships, columns=['Parent Tag', 'Child Tag'])
                        st.dataframe(relationships_df, use_container_width=True)
                else:
                    st.warning("Could not create the network graph.")
            else:
                st.warning("No tag relationships found to display in graph.")
        else:
            st.warning("No tag data found in the selected file.")
            
    else:
        st.info("👆 Please select a data source from the sidebar to view the tag graph.")
        st.markdown("""
        ### About Tag Graph
        
        This page provides an interactive network visualization of tag relationships, including:
        
        - **Network Graph**: Visual representation of tag hierarchies and relationships
        - **Chained Tags**: Tags with dots (e.g., `DOOR.TYPE.EXIT`) are shown connected to their parent tags
        - **Interactive Exploration**: Click on tags to see detailed usage information
        - **Usage Patterns**: Node size represents usage frequency, colors represent hierarchy depth
        - **Relationship Analysis**: Understand semantic connections between extracted tags
        
        **Legend:**
        - 🔵 **Blue nodes**: Root-level tags (no dots)
        - 🟠 **Orange nodes**: Second-level tags (one dot)
        - 🟢 **Green nodes**: Third-level tags (two dots)
        - 🔴 **Red nodes**: Deeper hierarchy levels
        - **Node size**: Represents usage count (how many norms use this tag)
        - **Connections**: Lines show parent-child relationships in tag hierarchy
        """)

if __name__ == "__main__":
    main()