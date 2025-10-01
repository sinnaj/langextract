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

# Hardcoded tag aliases - list of lists where each sublist contains aliases of one tag
# Special rule: if an alias contains a dot, it only matches tags under that parent
TAG_ALIASES = [
    ["ACCESSIBILITY", "ACCESSIBLE"],
    ["DOOR", "PUERTA"],
    ["FIRE.SYSTEM", "FIRE_SYSTEM"],
    ["FIRE.DETECTION", "FIRE_DETECTION"],
    ["FIRE.DETECTION.SYSTEM", "FIRE_DETECTION_SYSTEM"],
    ["FIRE.ALARM", "FIRE_ALARM"],
    ["FIRE_EXTINGUISHING", "FIRE_EXTINGUISHER"],
    ["BUILDING.AREA", "AREA.BUILT"],
    ["BUILDING.HEIGHT", "HEIGHT"],
    ["EVACUATION.ROUTE", "EVACUATION_ROUTE"],
    ["SAFETY.FIRE", "FIRE.SAFETY"],
    ["EMERGENCY.EXIT", "EXIT.EMERGENCY"],
    ["REFUGE.AREA", "REFUGE_AREA"]
]

def get_canonical_tag(tag_path):
    """Get the canonical tag name for a given tag path, considering aliases."""
    # For each alias group, check if the tag matches any alias
    for alias_group in TAG_ALIASES:
        for alias in alias_group:
            if '.' in alias:
                # Special rule: dotted aliases only match if the tag sits under the same parent
                alias_parts = alias.split('.')
                tag_parts = tag_path.split('.')
                
                # Check if the tag structure matches the alias structure
                if len(tag_parts) >= len(alias_parts):
                    # Compare the relevant parts
                    if alias_parts == tag_parts[:len(alias_parts)]:
                        # Return the first alias in the group (canonical form)
                        return alias_group[0]
                    
                    # Also check if it's a direct match with underscore variant
                    alias_underscore = alias.replace('.', '_')
                    if tag_path == alias_underscore:
                        # Convert to canonical dotted form
                        return alias_group[0]
            else:
                # Simple string matching for non-dotted aliases
                if tag_path.upper() == alias.upper():
                    return alias_group[0]
                
                # Check if it's part of a larger tag path
                tag_parts = tag_path.split('.')
                for part in tag_parts:
                    if part.upper() == alias.upper():
                        # Replace this part with canonical form
                        canonical_parts = tag_parts.copy()
                        canonical_parts[tag_parts.index(part)] = alias_group[0]
                        return '.'.join(canonical_parts)
    
    # If no alias found, return original tag
    return tag_path

def find_latest_enhanced_extractions():
    """Find the latest enhanced_extraction_results.json file."""
    base_path = Path(__file__).parent.parent.parent
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

def extract_tag_data(data):
    """Extract and process tag data from the enhanced extraction structure."""
    tags = data.get('tags', [])
    
    # Use a dictionary to merge aliases
    merged_tags = defaultdict(lambda: {
        'ids': [],
        'original_paths': [],
        'used_by_norms': set(),
        'related_topics': set(),
        'section_parents': set(),
        'extraction_texts': set()
    })
    
    # Process each tag and merge aliases
    for tag in tags:
        attrs = tag.get('attributes', {})
        original_tag_path = attrs.get('tag', tag.get('extraction_text', ''))
        
        # Get the canonical tag name (handling aliases)
        canonical_tag_path = get_canonical_tag(original_tag_path)
        
        # Merge data for this canonical tag
        merged_tags[canonical_tag_path]['ids'].append(attrs.get('id', ''))
        merged_tags[canonical_tag_path]['original_paths'].append(original_tag_path)
        merged_tags[canonical_tag_path]['used_by_norms'].update(attrs.get('used_by_norm_ids', []))
        merged_tags[canonical_tag_path]['related_topics'].update(attrs.get('related_topics', []))
        merged_tags[canonical_tag_path]['section_parents'].add('')  # Not available in new format
        merged_tags[canonical_tag_path]['extraction_texts'].add(tag.get('extraction_text', ''))
    
    # Convert merged data to the expected format
    tags_data = []
    for canonical_tag_path, merged_data in merged_tags.items():
        # Parse hierarchical structure of canonical tag
        path_parts = canonical_tag_path.split('.')
        
        tags_data.append({
            'id': ', '.join(merged_data['ids']),  # Combine all IDs
            'tag_path': canonical_tag_path,
            'original_paths': list(merged_data['original_paths']),  # Keep track of original paths
            'depth': len(path_parts),
            'root_category': path_parts[0] if path_parts else '',
            'subcategory': path_parts[1] if len(path_parts) > 1 else '',
            'full_category': '.'.join(path_parts[:2]) if len(path_parts) > 1 else path_parts[0] if path_parts else '',
            'used_by_norms': list(merged_data['used_by_norms']),
            'usage_count': len(merged_data['used_by_norms']),
            'related_topics': list(merged_data['related_topics']),
            'section_parent': ', '.join(filter(None, merged_data['section_parents'])),
            'extraction_text': ', '.join(filter(None, merged_data['extraction_texts']))
        })
    
    return pd.DataFrame(tags_data)

def extract_topic_data(data):
    """Extract and process topic data from enhanced extraction structure."""
    # Collect topic information from norms and tags
    topic_info = defaultdict(lambda: {'norms': set(), 'tags': set(), 'related_topics': set()})
    
    # Process extractions to get topic-norm and topic-tag relationships
    extractions = data.get('extractions', [])
    for extraction in extractions:
        if extraction.get('extraction_class') == 'Norm':
            attrs = extraction.get('attributes', {})
            norm_id = attrs.get('id', '')
            topics = attrs.get('topics', [])
            tags = attrs.get('relevant_tags', [])
            
            for topic in topics:
                topic_info[topic]['norms'].add(norm_id)
                topic_info[topic]['tags'].update(tags)
    
    # Process tags to get additional topic relationships
    tags = data.get('tags', [])
    for tag in tags:
        attrs = tag.get('attributes', {})
        tag_name = attrs.get('tag', '')
        related_topics = attrs.get('related_topics', [])
        
        for topic in related_topics:
            topic_info[topic]['tags'].add(tag_name)
    
    # Convert to DataFrame format
    topics_data = []
    for topic_name, info in topic_info.items():
        # Parse hierarchical structure for topics (similar to tags)
        path_parts = topic_name.split('.')
        
        topics_data.append({
            'topic_name': topic_name,
            'depth': len(path_parts),
            'root_category': path_parts[0] if path_parts else '',
            'subcategory': path_parts[1] if len(path_parts) > 1 else '',
            'norms': list(info['norms']),
            'norm_count': len(info['norms']),
            'tags': list(info['tags']),
            'tag_count': len(info['tags']),
            'is_chained': len(path_parts) > 1
        })
    
    return pd.DataFrame(topics_data)

def create_tag_network_graph(df):
    """Create a network graph showing tag relationships."""
    if df.empty:
        return None
    
    # Create a graph
    G = nx.DiGraph()  # Use directed graph to show hierarchy clearly
    
    # Track parent-child relationships
    relationships = []
    tag_info = {}
    
    # First, collect all existing tags
    existing_tags = set(df['tag_path'].tolist())
    
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
    
    # Second pass: create edges for hierarchical relationships
    for _, row in df.iterrows():
        tag_path = row['tag_path']
        path_parts = tag_path.split('.')
        
        # Create edges for hierarchical relationships
        if len(path_parts) > 1:
            # Try to connect to immediate parent first
            for i in range(len(path_parts) - 1, 0, -1):
                parent_path = '.'.join(path_parts[:i])
                if parent_path in existing_tags:
                    G.add_edge(parent_path, tag_path)
                    relationships.append((parent_path, tag_path))
                    break  # Only connect to the most immediate parent found
            else:
                # If no immediate parent exists, create a virtual parent node
                parent_path = '.'.join(path_parts[:-1])
                if parent_path not in existing_tags:
                    # Add virtual parent node with minimal info
                    tag_info[parent_path] = {
                        'usage_count': 0,
                        'id': f'virtual_{parent_path}',
                        'related_topics': [],
                        'depth': len(parent_path.split('.')),
                        'is_chained': '.' in parent_path,
                        'is_virtual': True
                    }
                    G.add_node(parent_path, **tag_info[parent_path])
                    existing_tags.add(parent_path)
                
                G.add_edge(parent_path, tag_path)
                relationships.append((parent_path, tag_path))
    
    # Convert back to undirected graph for better visualization
    G_undirected = nx.Graph(G)
    
    return G_undirected, tag_info, relationships

def create_hierarchical_layout(G, tag_info):
    """Create a hierarchical layout that shows parent-child relationships clearly."""
    pos = {}
    
    # Group nodes by hierarchy depth
    depth_groups = defaultdict(list)
    for node in G.nodes():
        depth = tag_info.get(node, {}).get('depth', 1)
        depth_groups[depth].append(node)
    
    # Sort depths to ensure consistent ordering
    sorted_depths = sorted(depth_groups.keys())
    
    # Calculate positions level by level
    y_spacing = 3.0  # Vertical spacing between levels
    
    # First pass: position root nodes
    for depth_idx, depth in enumerate(sorted_depths):
        nodes_at_depth = depth_groups[depth]
        
        if depth == 1:  # Root nodes
            # Spread root nodes horizontally
            if len(nodes_at_depth) == 1:
                x_positions = [0]
            else:
                total_width = (len(nodes_at_depth) - 1) * 8.0
                x_positions = [i * 8.0 - total_width/2 for i in range(len(nodes_at_depth))]
            
            for i, node in enumerate(nodes_at_depth):
                pos[node] = (x_positions[i], 0)
    
    # Second pass: position child nodes based on their parents
    for depth in sorted_depths[1:]:  # Skip root level
        nodes_at_depth = depth_groups[depth]
        
        # Group nodes by their parents
        parent_groups = defaultdict(list)
        orphans = []
        
        for node in nodes_at_depth:
            parents = [n for n in G.neighbors(node) 
                      if tag_info.get(n, {}).get('depth', 1) < depth and n in pos]
            
            if parents:
                parent_groups[parents[0]].append(node)
            else:
                orphans.append(node)
        
        # Position children under their parents
        for parent, children in parent_groups.items():
            parent_x, parent_y = pos[parent]
            child_y = parent_y - y_spacing
            
            if len(children) == 1:
                pos[children[0]] = (parent_x, child_y)
            else:
                # Spread children around parent
                child_spacing = 2.0
                total_width = (len(children) - 1) * child_spacing
                start_x = parent_x - total_width/2
                
                for i, child in enumerate(children):
                    child_x = start_x + i * child_spacing
                    pos[child] = (child_x, child_y)
        
        # Position orphan nodes
        if orphans:
            # Find the rightmost position at this level
            max_x = max([x for x, y in pos.values() if abs(y - (-depth + 1) * y_spacing) < 0.1], default=0)
            for i, orphan in enumerate(orphans):
                pos[orphan] = (max_x + 5 + i * 2, -(depth - 1) * y_spacing)
    
    return pos

def create_topic_network_graph(df):
    """Create a network graph showing topic relationships."""
    if df.empty:
        return None
    
    # Create a graph
    G = nx.DiGraph()  # Use directed graph to show hierarchy clearly
    
    # Track parent-child relationships
    relationships = []
    topic_info = {}
    
    # First, collect all existing topics
    existing_topics = set(df['topic_name'].tolist())
    
    # Process each topic to find hierarchical relationships
    for _, row in df.iterrows():
        topic_name = row['topic_name']
        path_parts = topic_name.split('.')
        
        # Store topic information
        topic_info[topic_name] = {
            'norm_count': row['norm_count'],
            'tag_count': row['tag_count'],
            'norms': row['norms'],
            'tags': row['tags'],
            'depth': row['depth'],
            'is_chained': len(path_parts) > 1
        }
        
        # Add the topic as a node
        G.add_node(topic_name, **topic_info[topic_name])
    
    # Second pass: create edges for hierarchical relationships
    for _, row in df.iterrows():
        topic_name = row['topic_name']
        path_parts = topic_name.split('.')
        
        # Create edges for hierarchical relationships
        if len(path_parts) > 1:
            # Try to connect to immediate parent first
            for i in range(len(path_parts) - 1, 0, -1):
                parent_path = '.'.join(path_parts[:i])
                if parent_path in existing_topics:
                    G.add_edge(parent_path, topic_name)
                    relationships.append((parent_path, topic_name))
                    break  # Only connect to the most immediate parent found
            else:
                # If no immediate parent exists, create a virtual parent node
                parent_path = '.'.join(path_parts[:-1])
                if parent_path not in existing_topics:
                    # Add virtual parent node with minimal info
                    topic_info[parent_path] = {
                        'norm_count': 0,
                        'tag_count': 0,
                        'norms': [],
                        'tags': [],
                        'depth': len(parent_path.split('.')),
                        'is_chained': '.' in parent_path,
                        'is_virtual': True
                    }
                    G.add_node(parent_path, **topic_info[parent_path])
                    existing_topics.add(parent_path)
                
                G.add_edge(parent_path, topic_name)
                relationships.append((parent_path, topic_name))
    
    # Convert back to undirected graph for better visualization
    G_undirected = nx.Graph(G)
    
    return G_undirected, topic_info, relationships

def create_plotly_topic_network_graph(G, topic_info):
    """Create an interactive topic network graph using plotly."""
    if G is None or len(G.nodes()) == 0:
        return None
    
    # Calculate positions using hierarchical layout
    pos = create_topic_hierarchical_layout(G, topic_info)
    
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
        
        info = topic_info.get(node, {})
        norm_count = info.get('norm_count', 0)
        tag_count = info.get('tag_count', 0)
        depth = info.get('depth', 1)
        is_chained = info.get('is_chained', False)
        is_virtual = info.get('is_virtual', False)
        
        # Node text - show abbreviated text for better readability
        display_text = node
        if len(display_text) > 15:
            # For hierarchical topics, show only the last part if too long
            if '.' in display_text:
                parts = display_text.split('.')
                if len(parts[-1]) <= 12:
                    display_text = parts[-1]  # Show only the last part
                else:
                    display_text = parts[-1][:12] + "..."
            else:
                display_text = display_text[:12] + "..."
        node_text.append(display_text)
        
        # Node color based on depth and type
        if is_virtual:
            color = '#cccccc'  # Gray for virtual nodes
        elif depth == 1:
            color = '#ff6b6b'  # Red for root topics
        elif depth == 2:
            color = '#4ecdc4'  # Teal for second level
        elif depth == 3:
            color = '#45b7d1'  # Blue for third level
        else:
            color = '#96ceb4'  # Green for deeper levels
        node_color.append(color)
        
        # Node size based on norm count (primary) and tag count (secondary)
        if is_virtual:
            size = 8  # Smaller size for virtual nodes
        else:
            # Size primarily based on norm count, with tag count as secondary factor
            primary_size = max(10, min(40, 10 + norm_count * 2))
            secondary_bonus = min(10, tag_count // 10)  # Small bonus for many tags
            size = primary_size + secondary_bonus
        node_size.append(size)
        
        # Hover info
        hover_text = f"Topic: {node}<br>"
        if is_virtual:
            hover_text += "Type: Virtual Parent Topic<br>"
            hover_text += f"Depth: {depth}<br>"
            hover_text += "Note: This parent topic was inferred from child topics"
        else:
            hover_text += f"Norm Count: {norm_count}<br>"
            hover_text += f"Tag Count: {tag_count}<br>"
            hover_text += f"Depth: {depth}<br>"
            hover_text += f"Chained: {'Yes' if is_chained else 'No'}"
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
        line=dict(width=1.5, color='rgba(100,100,100,0.6)'),
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
            colorscale='Reds',
            color=node_size,  # Use size for color scale
            size=node_size,
            colorbar=dict(
                thickness=15,
                len=0.7,
                x=1.0,
                title="Norm Count",
                y=0.3  # Position below the tag colorbar
            ),
            line=dict(width=2)
        ),
        # Add the actual topic names for click events
        ids=[node for node in G.nodes()]  # This will be used for click events
    )
    
    # Create the figure
    fig = go.Figure(data=[edge_trace, node_trace],
                   layout=go.Layout(
                       title=dict(
                           text='Topic Hierarchy Network Graph',
                           font=dict(size=16)
                       ),
                       showlegend=False,
                       hovermode='closest',
                       margin=dict(b=20,l=5,r=5,t=40),
                       annotations=[
                           dict(
                               text="Hierarchical view of topic relationships. Node size = norm count, Colors = depth level.",
                               showarrow=False,
                               xref="paper", yref="paper",
                               x=0.005, y=-0.002,
                               xanchor='left', yanchor='bottom',
                               font=dict(size=12)
                           )
                       ],
                       xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       height=600,  # Slightly smaller than tag graph to fit on same page
                       plot_bgcolor='rgba(250,240,240,0.3)'  # Light reddish background to differentiate from tag graph
                   ))
    
    return fig

def create_topic_hierarchical_layout(G, topic_info):
    """Create a hierarchical layout for topics that shows parent-child relationships clearly."""
    pos = {}
    
    # Group nodes by hierarchy depth
    depth_groups = defaultdict(list)
    for node in G.nodes():
        depth = topic_info.get(node, {}).get('depth', 1)
        depth_groups[depth].append(node)
    
    # Sort depths to ensure consistent ordering
    sorted_depths = sorted(depth_groups.keys())
    
    # Calculate positions level by level
    y_spacing = 2.5  # Vertical spacing between levels
    
    # First pass: position root nodes
    for depth_idx, depth in enumerate(sorted_depths):
        nodes_at_depth = depth_groups[depth]
        
        if depth == 1:  # Root nodes
            # Spread root nodes horizontally
            if len(nodes_at_depth) == 1:
                x_positions = [0]
            else:
                total_width = (len(nodes_at_depth) - 1) * 6.0
                x_positions = [i * 6.0 - total_width/2 for i in range(len(nodes_at_depth))]
            
            for i, node in enumerate(nodes_at_depth):
                pos[node] = (x_positions[i], 0)
    
    # Second pass: position child nodes based on their parents
    for depth in sorted_depths[1:]:  # Skip root level
        nodes_at_depth = depth_groups[depth]
        
        # Group nodes by their parents
        parent_groups = defaultdict(list)
        orphans = []
        
        for node in nodes_at_depth:
            parents = [n for n in G.neighbors(node) 
                      if topic_info.get(n, {}).get('depth', 1) < depth and n in pos]
            
            if parents:
                parent_groups[parents[0]].append(node)
            else:
                orphans.append(node)
        
        # Position children under their parents
        for parent, children in parent_groups.items():
            parent_x, parent_y = pos[parent]
            child_y = parent_y - y_spacing
            
            if len(children) == 1:
                pos[children[0]] = (parent_x, child_y)
            else:
                # Spread children around parent
                child_spacing = 1.5
                total_width = (len(children) - 1) * child_spacing
                start_x = parent_x - total_width/2
                
                for i, child in enumerate(children):
                    child_x = start_x + i * child_spacing
                    pos[child] = (child_x, child_y)
        
        # Position orphan nodes
        if orphans:
            # Find the rightmost position at this level
            max_x = max([x for x, y in pos.values() if abs(y - (-(depth - 1) * y_spacing)) < 0.1], default=0)
            for i, orphan in enumerate(orphans):
                pos[orphan] = (max_x + 4 + i * 1.5, -(depth - 1) * y_spacing)
    
    return pos

def display_topic_usage_details(df, selected_topic, data=None):
    """Display detailed usage information for a selected topic."""
    if selected_topic and not df.empty:
        topic_data = df[df['topic_name'] == selected_topic]
        if not topic_data.empty:
            topic_info = topic_data.iloc[0]
            
            st.subheader(f"🏷️ Topic Details: {selected_topic}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Topic Name:** {selected_topic}")
                st.write(f"**Norm Count:** {topic_info['norm_count']}")
                st.write(f"**Tag Count:** {topic_info['tag_count']}")
                st.write(f"**Hierarchy Depth:** {topic_info['depth']}")
                st.write(f"**Root Category:** {topic_info['root_category']}")
                
                # Show if it's a chained topic
                if '.' in selected_topic:
                    st.info("🔗 This is a chained topic (contains dots)")
                else:
                    st.info("🏷️ This is a root-level topic")
            
            with col2:
                if topic_info['norms']:
                    st.write(f"**Related Norms ({len(topic_info['norms'])}):**")
                    
                    # Display all norm IDs without truncation, using columns for better layout
                    norm_ids = topic_info['norms']
                    
                    # Create multiple columns to display norm IDs efficiently
                    if len(norm_ids) <= 5:
                        cols = st.columns(1)
                    elif len(norm_ids) <= 10:
                        cols = st.columns(2)
                    elif len(norm_ids) <= 20:
                        cols = st.columns(3)
                    else:
                        cols = st.columns(4)
                    
                    # Display hoverable norm IDs across columns
                    for i, norm_id in enumerate(norm_ids):
                        col_idx = i % len(cols)
                        with cols[col_idx]:
                            if data:  # If we have access to the full data
                                norm_details = get_norm_details_by_id(data, norm_id)
                                display_hoverable_norm_id(norm_id, norm_details)
                            else:  # Fallback to original display if no data available
                                st.write(f"- {norm_id}")
                
                if topic_info['tags']:
                    st.write(f"**Related Tags ({len(topic_info['tags'])}):**")
                    
                    # Display all tags without truncation, using columns for better layout
                    tags = topic_info['tags']
                    
                    # Create multiple columns to display tags efficiently
                    if len(tags) <= 5:
                        tag_cols = st.columns(1)
                    elif len(tags) <= 10:
                        tag_cols = st.columns(2)
                    elif len(tags) <= 20:
                        tag_cols = st.columns(3)
                    else:
                        tag_cols = st.columns(4)
                    
                    # Display tags across columns
                    for i, tag in enumerate(tags):
                        col_idx = i % len(tag_cols)
                        with tag_cols[col_idx]:
                            st.write(f"- {tag}")

def display_topic_statistics(df, G):
    """Display statistics about the topic graph."""
    st.header("🏷️ Topic Statistics")
    
    if df.empty or G is None:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Topics", len(df))
    
    with col2:
        chained_topics = len(df[df['topic_name'].str.contains('.', regex=False)])
        st.metric("Chained Topics", chained_topics)
    
    with col3:
        root_topics = len(df[~df['topic_name'].str.contains('.', regex=False)])
        st.metric("Root Topics", root_topics)
    
    with col4:
        if G:
            connected_components = nx.number_connected_components(G)
            st.metric("Connected Components", connected_components)

def extract_parameter_data(data):
    """Extract and process parameter data from enhanced extraction structure."""
    parameters = data.get('parameters', [])
    
    # Collect parameter information
    param_info = defaultdict(lambda: {'norms': set(), 'details': []})
    
    for parameter in parameters:
        attrs = parameter.get('attributes', {})
        param_tag = attrs.get('applies_for_tag', '')
        param_id = attrs.get('id', '')
        norm_ids = attrs.get('norm_ids', [])
        value = attrs.get('value', '')
        unit = attrs.get('unit', '')
        operator = attrs.get('operator', '')
        
        if param_tag:  # Only process if we have a valid parameter tag
            param_info[param_tag]['norms'].update(norm_ids)
            param_info[param_tag]['details'].append({
                'id': param_id,
                'value': value,
                'unit': unit,
                'operator': operator,
                'norm_ids': norm_ids
            })
    
    # Convert to DataFrame format
    params_data = []
    for param_name, info in param_info.items():
        # Parse hierarchical structure for parameters (similar to tags and topics)
        path_parts = param_name.split('.')
        
        params_data.append({
            'parameter_name': param_name,
            'depth': len(path_parts),
            'root_category': path_parts[0] if path_parts else '',
            'subcategory': path_parts[1] if len(path_parts) > 1 else '',
            'norms': list(info['norms']),
            'norm_count': len(info['norms']),
            'details': info['details'],
            'instance_count': len(info['details']),
            'is_chained': len(path_parts) > 1
        })
    
    return pd.DataFrame(params_data)

def create_parameter_network_graph(df):
    """Create a network graph showing parameter relationships."""
    if df.empty:
        return None
    
    # Create a graph
    G = nx.DiGraph()  # Use directed graph to show hierarchy clearly
    
    # Track parent-child relationships
    relationships = []
    param_info = {}
    
    # First, collect all existing parameters
    existing_params = set(df['parameter_name'].tolist())
    
    # Process each parameter to find hierarchical relationships
    for _, row in df.iterrows():
        param_name = row['parameter_name']
        path_parts = param_name.split('.')
        
        # Store parameter information
        param_info[param_name] = {
            'norm_count': row['norm_count'],
            'instance_count': row['instance_count'],
            'norms': row['norms'],
            'details': row['details'],
            'depth': row['depth'],
            'is_chained': len(path_parts) > 1
        }
        
        # Add the parameter as a node
        G.add_node(param_name, **param_info[param_name])
    
    # Second pass: create edges for hierarchical relationships
    for _, row in df.iterrows():
        param_name = row['parameter_name']
        path_parts = param_name.split('.')
        
        # Create edges for hierarchical relationships
        if len(path_parts) > 1:
            # Try to connect to immediate parent first
            for i in range(len(path_parts) - 1, 0, -1):
                parent_path = '.'.join(path_parts[:i])
                if parent_path in existing_params:
                    G.add_edge(parent_path, param_name)
                    relationships.append((parent_path, param_name))
                    break  # Only connect to the most immediate parent found
            else:
                # If no immediate parent exists, create a virtual parent node
                parent_path = '.'.join(path_parts[:-1])
                if parent_path not in existing_params:
                    # Add virtual parent node with minimal info
                    param_info[parent_path] = {
                        'norm_count': 0,
                        'instance_count': 0,
                        'norms': [],
                        'details': [],
                        'depth': len(parent_path.split('.')),
                        'is_chained': '.' in parent_path,
                        'is_virtual': True
                    }
                    G.add_node(parent_path, **param_info[parent_path])
                    existing_params.add(parent_path)
                
                G.add_edge(parent_path, param_name)
                relationships.append((parent_path, param_name))
    
    # Convert back to undirected graph for better visualization
    G_undirected = nx.Graph(G)
    
    return G_undirected, param_info, relationships

def create_plotly_parameter_network_graph(G, param_info):
    """Create an interactive parameter network graph using plotly."""
    if G is None or len(G.nodes()) == 0:
        return None
    
    # Calculate positions using hierarchical layout
    pos = create_parameter_hierarchical_layout(G, param_info)
    
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
        
        info = param_info.get(node, {})
        norm_count = info.get('norm_count', 0)
        instance_count = info.get('instance_count', 0)
        depth = info.get('depth', 1)
        is_chained = info.get('is_chained', False)
        is_virtual = info.get('is_virtual', False)
        
        # Node text - show abbreviated text for better readability
        display_text = node
        if len(display_text) > 15:
            # For hierarchical parameters, show only the last part if too long
            if '.' in display_text:
                parts = display_text.split('.')
                if len(parts[-1]) <= 12:
                    display_text = parts[-1]  # Show only the last part
                else:
                    display_text = parts[-1][:12] + "..."
            else:
                display_text = display_text[:12] + "..."
        node_text.append(display_text)
        
        # Node color based on depth and type (green color scheme for parameters)
        if is_virtual:
            color = '#cccccc'  # Gray for virtual nodes
        elif depth == 1:
            color = '#2e8b57'  # Dark green for root parameters
        elif depth == 2:
            color = '#3cb371'  # Medium green for second level
        elif depth == 3:
            color = '#98fb98'  # Light green for third level
        else:
            color = '#90ee90'  # Light green for deeper levels
        node_color.append(color)
        
        # Node size based on norm count (primary) and instance count (secondary)
        if is_virtual:
            size = 8  # Smaller size for virtual nodes
        else:
            # Size primarily based on norm count, with instance count as secondary factor
            primary_size = max(10, min(40, 10 + norm_count * 3))
            secondary_bonus = min(8, instance_count // 2)  # Small bonus for multiple instances
            size = primary_size + secondary_bonus
        node_size.append(size)
        
        # Hover info
        hover_text = f"Parameter: {node}<br>"
        if is_virtual:
            hover_text += "Type: Virtual Parent Parameter<br>"
            hover_text += f"Depth: {depth}<br>"
            hover_text += "Note: This parent parameter was inferred from child parameters"
        else:
            hover_text += f"Norm Count: {norm_count}<br>"
            hover_text += f"Instance Count: {instance_count}<br>"
            hover_text += f"Depth: {depth}<br>"
            hover_text += f"Chained: {'Yes' if is_chained else 'No'}"
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
        line=dict(width=1.5, color='rgba(46,139,87,0.6)'),  # Green color for parameter edges
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
            colorscale='Greens',
            color=node_size,  # Use size for color scale
            size=node_size,
            colorbar=dict(
                thickness=15,
                len=0.7,
                x=1.0,
                title="Norm Count",
                y=0.1  # Position below the topic and tag colorbars
            ),
            line=dict(width=2)
        ),
        # Add the actual parameter names for click events
        ids=[node for node in G.nodes()]  # This will be used for click events
    )
    
    # Create the figure
    fig = go.Figure(data=[edge_trace, node_trace],
                   layout=go.Layout(
                       title=dict(
                           text='Parameter Hierarchy Network Graph',
                           font=dict(size=16)
                       ),
                       showlegend=False,
                       hovermode='closest',
                       margin=dict(b=20,l=5,r=5,t=40),
                       annotations=[
                           dict(
                               text="Hierarchical view of parameter relationships. Node size = norm count, Colors = depth level.",
                               showarrow=False,
                               xref="paper", yref="paper",
                               x=0.005, y=-0.002,
                               xanchor='left', yanchor='bottom',
                               font=dict(size=12)
                           )
                       ],
                       xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       height=600,  # Slightly smaller than tag graph to fit on same page
                       plot_bgcolor='rgba(240,250,240,0.3)'  # Light greenish background to differentiate from tag and topic graphs
                   ))
    
    return fig

def create_parameter_hierarchical_layout(G, param_info):
    """Create a hierarchical layout for parameters that shows parent-child relationships clearly."""
    pos = {}
    
    # Group nodes by hierarchy depth
    depth_groups = defaultdict(list)
    for node in G.nodes():
        depth = param_info.get(node, {}).get('depth', 1)
        depth_groups[depth].append(node)
    
    # Sort depths to ensure consistent ordering
    sorted_depths = sorted(depth_groups.keys())
    
    # Calculate positions level by level
    y_spacing = 2.5  # Vertical spacing between levels
    
    # First pass: position root nodes
    for depth_idx, depth in enumerate(sorted_depths):
        nodes_at_depth = depth_groups[depth]
        
        if depth == 1:  # Root nodes
            # Spread root nodes horizontally
            if len(nodes_at_depth) == 1:
                x_positions = [0]
            else:
                total_width = (len(nodes_at_depth) - 1) * 6.0
                x_positions = [i * 6.0 - total_width/2 for i in range(len(nodes_at_depth))]
            
            for i, node in enumerate(nodes_at_depth):
                pos[node] = (x_positions[i], 0)
    
    # Second pass: position child nodes based on their parents
    for depth in sorted_depths[1:]:  # Skip root level
        nodes_at_depth = depth_groups[depth]
        
        # Group nodes by their parents
        parent_groups = defaultdict(list)
        orphans = []
        
        for node in nodes_at_depth:
            parents = [n for n in G.neighbors(node) 
                      if param_info.get(n, {}).get('depth', 1) < depth and n in pos]
            
            if parents:
                parent_groups[parents[0]].append(node)
            else:
                orphans.append(node)
        
        # Position children under their parents
        for parent, children in parent_groups.items():
            parent_x, parent_y = pos[parent]
            child_y = parent_y - y_spacing
            
            if len(children) == 1:
                pos[children[0]] = (parent_x, child_y)
            else:
                # Spread children around parent
                child_spacing = 1.5
                total_width = (len(children) - 1) * child_spacing
                start_x = parent_x - total_width/2
                
                for i, child in enumerate(children):
                    child_x = start_x + i * child_spacing
                    pos[child] = (child_x, child_y)
        
        # Position orphan nodes
        if orphans:
            # Find the rightmost position at this level
            max_x = max([x for x, y in pos.values() if abs(y - (-(depth - 1) * y_spacing)) < 0.1], default=0)
            for i, orphan in enumerate(orphans):
                pos[orphan] = (max_x + 4 + i * 1.5, -(depth - 1) * y_spacing)
    
    return pos

def display_parameter_usage_details(df, selected_param, data=None):
    """Display detailed usage information for a selected parameter."""
    if selected_param and not df.empty:
        param_data = df[df['parameter_name'] == selected_param]
        if not param_data.empty:
            param_info = param_data.iloc[0]
            
            st.subheader(f"📊 Parameter Details: {selected_param}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Parameter Name:** {selected_param}")
                st.write(f"**Norm Count:** {param_info['norm_count']}")
                st.write(f"**Instance Count:** {param_info['instance_count']}")
                st.write(f"**Hierarchy Depth:** {param_info['depth']}")
                st.write(f"**Root Category:** {param_info['root_category']}")
                
                # Show if it's a chained parameter
                if '.' in selected_param:
                    st.info("🔗 This is a chained parameter (contains dots)")
                else:
                    st.info("📊 This is a root-level parameter")
            
            with col2:
                if param_info['norms']:
                    st.write(f"**Related Norms ({len(param_info['norms'])}):**")
                    
                    # Display all norm IDs without truncation, using columns for better layout
                    norm_ids = param_info['norms']
                    
                    # Create multiple columns to display norm IDs efficiently
                    if len(norm_ids) <= 5:
                        cols = st.columns(1)
                    elif len(norm_ids) <= 10:
                        cols = st.columns(2)
                    elif len(norm_ids) <= 20:
                        cols = st.columns(3)
                    else:
                        cols = st.columns(4)
                    
                    # Display hoverable norm IDs across columns
                    for i, norm_id in enumerate(norm_ids):
                        col_idx = i % len(cols)
                        with cols[col_idx]:
                            if data:  # If we have access to the full data
                                norm_details = get_norm_details_by_id(data, norm_id)
                                display_hoverable_norm_id(norm_id, norm_details)
                            else:  # Fallback to original display if no data available
                                st.write(f"- {norm_id}")
                
                if param_info['details']:
                    st.write(f"**Parameter Instances ({len(param_info['details'])}):**")
                    # Show all instances with their details
                    for i, detail in enumerate(param_info['details']):
                        value = detail.get('value', '')
                        unit = detail.get('unit', '')
                        operator = detail.get('operator', '')
                        param_id = detail.get('id', '')
                        value_str = f"{operator} {value} {unit}".strip()
                        st.write(f"- {param_id}: {value_str}")

def display_parameter_statistics(df, G):
    """Display statistics about the parameter graph."""
    st.header("📊 Parameter Statistics")
    
    if df.empty or G is None:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Parameters", len(df))
    
    with col2:
        chained_params = len(df[df['parameter_name'].str.contains('.', regex=False)])
        st.metric("Chained Parameters", chained_params)
    
    with col3:
        root_params = len(df[~df['parameter_name'].str.contains('.', regex=False)])
        st.metric("Root Parameters", root_params)
    
    with col4:
        if G:
            connected_components = nx.number_connected_components(G)
            st.metric("Connected Components", connected_components)

def extract_parameter_identifiers_from_condition(condition_text):
    """Extract parameter identifiers from a condition string (applies_if or exempt_if)."""
    if not condition_text or condition_text.upper() in ['TRUE', 'FALSE']:
        return []
    
    # Pattern to match parameter identifiers (e.g., BUILDING.USAGE, FLOOR.HEIGHT, etc.)
    # This regex looks for uppercase words with dots and underscores
    pattern = r'\b[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)*\b'
    
    # Extract all matches
    identifiers = re.findall(pattern, condition_text)
    
    # Filter out common logical operators and values
    excluded = {'TRUE', 'FALSE', 'AND', 'OR', 'NOT', 'NULL', 'NONE'}
    
    # Also filter out quoted values and numeric patterns
    filtered_identifiers = []
    for identifier in identifiers:
        # Skip if it's an excluded term
        if identifier in excluded:
            continue
        # Skip if it looks like a quoted value (all caps single word that might be a value)
        if '.' not in identifier and len(identifier) < 15:  # Allow some single words that might be parameters
            # Check if it's likely a parameter vs a value by context
            # Parameters usually have dots or are common parameter patterns
            if not any(param_pattern in identifier for param_pattern in ['BUILDING', 'FLOOR', 'AREA', 'HEIGHT', 'WIDTH', 'USAGE', 'TYPE', 'SYSTEM', 'FIRE', 'SAFETY', 'ACCESS']):
                continue
        filtered_identifiers.append(identifier)
    
    return list(set(filtered_identifiers))  # Remove duplicates

def extract_condition_parameter_data(data, condition_field='applies_if'):
    """Extract and process parameter identifiers from norm condition fields."""
    extractions = data.get('extractions', [])
    norm_extractions = [e for e in extractions if e.get('extraction_class') in ['Norm', 'NORM']]
    
    # Collect parameter identifier information from conditions
    param_info = defaultdict(lambda: {'norms': set(), 'conditions': []})
    
    for norm in norm_extractions:
        attrs = norm.get('attributes', {})
        norm_id = attrs.get('id', '')
        condition_text = attrs.get(condition_field, '')
        
        if condition_text:
            identifiers = extract_parameter_identifiers_from_condition(condition_text)
            for identifier in identifiers:
                param_info[identifier]['norms'].add(norm_id)
                param_info[identifier]['conditions'].append({
                    'norm_id': norm_id,
                    'condition': condition_text,
                    'norm_statement': attrs.get('norm_statement', ''),
                    'section_id': attrs.get('parent_section_id', '')
                })
    
    # Convert to DataFrame format
    params_data = []
    for param_name, info in param_info.items():
        # Parse hierarchical structure for parameters
        path_parts = param_name.split('.')
        
        params_data.append({
            'parameter_name': param_name,
            'depth': len(path_parts),
            'root_category': path_parts[0] if path_parts else '',
            'subcategory': path_parts[1] if len(path_parts) > 1 else '',
            'norms': list(info['norms']),
            'norm_count': len(info['norms']),
            'conditions': info['conditions'],
            'condition_count': len(info['conditions']),
            'is_chained': len(path_parts) > 1,
            'condition_field': condition_field
        })
    
    return pd.DataFrame(params_data)

def create_condition_parameter_network_graph(df):
    """Create a network graph showing condition parameter relationships."""
    if df.empty:
        return None, {}, []
    
    # Create a graph
    G = nx.DiGraph()  # Use directed graph to show hierarchy clearly
    
    # Track parent-child relationships
    relationships = []
    param_info = {}
    
    # First, collect all existing parameters
    existing_params = set(df['parameter_name'].tolist())
    
    # Process each parameter to find hierarchical relationships
    for _, row in df.iterrows():
        param_name = row['parameter_name']
        path_parts = param_name.split('.')
        
        # Store parameter info
        param_info[param_name] = {
            'usage_count': row['norm_count'],
            'depth': row['depth'],
            'is_chained': row['is_chained'],
            'is_virtual': False,
            'condition_count': row['condition_count']
        }
        
        # Add node to graph
        G.add_node(param_name)
        
        # Create parent-child relationships for chained parameters
        if len(path_parts) > 1:
            for i in range(1, len(path_parts)):
                parent = '.'.join(path_parts[:i])
                child = '.'.join(path_parts[:i+1])
                
                # Add parent as virtual node if it doesn't exist as a real parameter
                if parent not in existing_params:
                    if parent not in param_info:
                        param_info[parent] = {
                            'usage_count': 0,
                            'depth': i,
                            'is_chained': i > 1,
                            'is_virtual': True,
                            'condition_count': 0
                        }
                        G.add_node(parent)
                
                # Add relationship
                if G.has_node(parent) and G.has_node(child):
                    G.add_edge(parent, child)
                    relationships.append((parent, child))
    
    return G, param_info, relationships

def display_condition_parameter_usage_details(df, selected_param, data, condition_field='applies_if'):
    """Display detailed usage information for a selected condition parameter."""
    condition_name = "Applies If" if condition_field == 'applies_if' else "Exempt If"
    
    if selected_param and not df.empty:
        param_data = df[df['parameter_name'] == selected_param]
        if not param_data.empty:
            param_info = param_data.iloc[0]
            
            st.subheader(f"📍 {condition_name} Parameter Details: {selected_param}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Parameter Name:** {selected_param}")
                st.write(f"**Usage Count:** {param_info['norm_count']}")
                st.write(f"**Condition Count:** {param_info['condition_count']}")
                st.write(f"**Hierarchy Depth:** {param_info['depth']}")
                st.write(f"**Root Category:** {param_info['root_category']}")
                
                if param_info['is_chained']:
                    st.info("🔗 This is a chained parameter (contains dots)")
                else:
                    st.info("🏷️ This is a root-level parameter")
            
            with col2:
                if param_info['norms']:
                    st.write(f"**Used in {len(param_info['norms'])} norm(s) {condition_name.lower()} conditions:**")
                    
                    # Display all norm IDs without truncation, using columns for better layout
                    norm_ids = param_info['norms']
                    
                    # Create multiple columns to display norm IDs efficiently
                    if len(norm_ids) <= 5:
                        cols = st.columns(1)
                        col_idx = 0
                    elif len(norm_ids) <= 10:
                        cols = st.columns(2)
                    elif len(norm_ids) <= 20:
                        cols = st.columns(3)
                    else:
                        cols = st.columns(4)
                    
                    for i, norm_id in enumerate(norm_ids):
                        col_idx = i % len(cols)
                        with cols[col_idx]:
                            # Get norm details for hoverable display
                            norm_details = get_norm_details_by_id(data, norm_id)
                            if norm_details:
                                display_hoverable_norm_id(norm_id, norm_details)
                            else:
                                st.write(f"- {norm_id}")
                
                # Show sample conditions
                if param_info['conditions']:
                    st.write(f"**Sample {condition_name} Conditions:**")
                    sample_conditions = param_info['conditions'][:3]  # Show first 3 conditions
                    for i, condition_info in enumerate(sample_conditions):
                        with st.expander(f"Condition {i+1} (Norm: {condition_info['norm_id']})"):
                            st.code(condition_info['condition'], language='text')
                            if condition_info['norm_statement']:
                                st.write("**Norm Statement:**")
                                st.write(condition_info['norm_statement'][:200] + "..." if len(condition_info['norm_statement']) > 200 else condition_info['norm_statement'])

def create_plotly_network_graph(G, tag_info):
    """Create an interactive network graph using plotly."""
    if G is None or len(G.nodes()) == 0:
        return None
    
    # Calculate positions using hierarchical layout
    pos = create_hierarchical_layout(G, tag_info)
    
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
        is_virtual = info.get('is_virtual', False)
        
        # Node text - show abbreviated text for better readability
        display_text = node
        if len(display_text) > 15:
            # For hierarchical tags, show only the last part if too long
            if '.' in display_text:
                parts = display_text.split('.')
                if len(parts[-1]) <= 12:
                    display_text = parts[-1]  # Show only the last part
                else:
                    display_text = parts[-1][:12] + "..."
            else:
                display_text = display_text[:12] + "..."
        node_text.append(display_text)
        
        # Node color based on depth and type
        if is_virtual:
            color = '#cccccc'  # Gray for virtual nodes
        elif depth == 1:
            color = '#1f77b4'  # Blue for root tags
        elif depth == 2:
            color = '#ff7f0e'  # Orange for second level
        elif depth == 3:
            color = '#2ca02c'  # Green for third level
        else:
            color = '#d62728'  # Red for deeper levels
        node_color.append(color)
        
        # Node size based on usage count
        if is_virtual:
            size = 8  # Smaller size for virtual nodes
        else:
            size = max(10, min(50, 10 + usage_count * 3))
        node_size.append(size)
        
        # Hover info
        hover_text = f"Tag: {node}<br>"
        if is_virtual:
            hover_text += "Type: Virtual Parent Node<br>"
            hover_text += f"Depth: {depth}<br>"
            hover_text += "Note: This parent tag was inferred from child tags"
        else:
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
        line=dict(width=1.5, color='rgba(50,50,50,0.6)'),
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
        ),
        # Add the actual tag names for click events
        ids=[node for node in G.nodes()]  # This will be used for click events
    )
    
    # Create the figure
    fig = go.Figure(data=[edge_trace, node_trace],
                   layout=go.Layout(
                       title=dict(
                           text='Tag Hierarchy Network Graph',
                           font=dict(size=16)
                       ),
                       showlegend=False,
                       hovermode='closest',
                       margin=dict(b=20,l=5,r=5,t=40),
                       annotations=[
                           dict(
                               text="Hierarchical view showing tag relationships. Node size = usage count, Colors = depth level.",
                               showarrow=False,
                               xref="paper", yref="paper",
                               x=0.005, y=-0.002,
                               xanchor='left', yanchor='bottom',
                               font=dict(size=12)
                           )
                       ],
                       xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       height=800,  # Increased height for better hierarchy display
                       plot_bgcolor='rgba(240,240,240,0.3)'  # Light background to better show structure
                   ))
    
    return fig

def get_norm_details_by_id(data, norm_id):
    """Get detailed norm information by norm ID."""
    extractions = data.get('extractions', [])
    sections = data.get('sections', [])
    norm_extractions = [e for e in extractions if e.get('extraction_class') in ['Norm', 'NORM']]
    
    # Create section mapping for easy lookup
    section_map = {s.get('section_id'): s for s in sections}
    
    for norm in norm_extractions:
        attrs = norm.get('attributes', {})
        if attrs.get('id') == norm_id:
            parent_section_id = attrs.get('parent_section_id', '')
            section_info = section_map.get(parent_section_id, {})
            section_name = section_info.get('section_name', parent_section_id or 'Unknown Section')
            
            return {
                'id': attrs.get('id', ''),
                'norm_statement': attrs.get('norm_statement', norm.get('extraction_text', '')),
                'obligation_type': attrs.get('obligation_type', ''),
                'priority': attrs.get('priority', 0),
                'confidence': attrs.get('confidence', 0),
                'applies_if': attrs.get('applies_if', ''),
                'satisfied_if': attrs.get('satisfied_if', ''),
                'exempt_if': attrs.get('exempt_if', ''),
                'topics': attrs.get('topics', []),
                'relevant_tags': attrs.get('relevant_tags', []),
                'parent_section_id': parent_section_id,
                'section_name': section_name,
                'paragraph_number': attrs.get('paragraph_number', 0),
                'extraction_text': norm.get('extraction_text', ''),
                'location_scope': attrs.get('location_scope', {}),
                'project_dimensions': attrs.get('project_dimensions', {})
            }
    return None

def display_hoverable_norm_id(norm_id, norm_details):
    """Display a norm ID with hoverable tooltip showing norm details."""
    if norm_details:
        # Format project dimensions for display
        project_dims_str = ""
        if norm_details['project_dimensions']:
            dim_parts = []
            for key, values in norm_details['project_dimensions'].items():
                if isinstance(values, list):
                    dim_parts.append(f"{key}: {', '.join(values)}")
                else:
                    dim_parts.append(f"{key}: {values}")
            project_dims_str = "; ".join(dim_parts)
        
        # Create tooltip content with all requested information
        tooltip_content = f"""
        **Norm ID:** {norm_details['id']}
        
        **Statement:** {norm_details['norm_statement'][:200]}{'...' if len(norm_details['norm_statement']) > 200 else ''}
        
        **Section:** {norm_details['section_name']}
        **Section ID:** {norm_details['parent_section_id']}
        
        **Type:** {norm_details['obligation_type']}
        **Priority:** {norm_details['priority']}
        **Confidence:** {norm_details['confidence']:.2f}
        
        **Applies If:** {norm_details['applies_if'][:100]}{'...' if len(norm_details['applies_if']) > 100 else ''}
        
        **Satisfied If:** {norm_details['satisfied_if'][:100]}{'...' if len(norm_details['satisfied_if']) > 100 else ''}
        
        **Exempt If:** {norm_details['exempt_if'][:100]}{'...' if len(norm_details['exempt_if']) > 100 else ''}
        
        **Project Dimensions:** {project_dims_str[:100]}{'...' if len(project_dims_str) > 100 else project_dims_str or 'None'}
        
        **Topics:** {', '.join(norm_details['topics'][:3])}{'...' if len(norm_details['topics']) > 3 else ''}
        
        **Tags:** {', '.join(norm_details['relevant_tags'][:3])}{'...' if len(norm_details['relevant_tags']) > 3 else ''}
        """
        
        # Use HTML with CSS and JavaScript for smart tooltip positioning
        tooltip_id = f"tooltip_{hash(norm_id) % 10000}"  # Create unique ID for this tooltip
        st.markdown(f"""
        <style>
        .norm-tooltip {{
            position: relative;
            display: inline-block;
            cursor: pointer;
            color: #0066cc;
            text-decoration: underline;
        }}
        .norm-tooltip .tooltiptext {{
            visibility: hidden;
            width: 480px;
            background-color: #333;
            color: #fff;
            text-align: left;
            border-radius: 6px;
            padding: 12px;
            position: fixed;
            z-index: 9999;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 12px;
            line-height: 1.4;
            white-space: pre-line;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            max-height: 400px;
            overflow-y: auto;
            pointer-events: none;
        }}
        .norm-tooltip:hover .tooltiptext {{
            visibility: visible;
            opacity: 1;
        }}
        .norm-tooltip .tooltiptext::after {{
            content: "";
            position: absolute;
            border-width: 8px;
            border-style: solid;
        }}
        /* Arrow pointing up (tooltip below element) */
        .tooltip-below::after {{
            top: -16px;
            left: 50%;
            margin-left: -8px;
            border-color: transparent transparent #333 transparent;
        }}
        /* Arrow pointing down (tooltip above element) */
        .tooltip-above::after {{
            bottom: -16px;
            left: 50%;
            margin-left: -8px;
            border-color: #333 transparent transparent transparent;
        }}
        /* Arrow pointing right (tooltip to the left) */
        .tooltip-left::after {{
            top: 50%;
            right: -16px;
            margin-top: -8px;
            border-color: transparent transparent transparent #333;
        }}
        /* Arrow pointing left (tooltip to the right) */
        .tooltip-right::after {{
            top: 50%;
            left: -16px;
            margin-top: -8px;
            border-color: transparent #333 transparent transparent;
        }}
        </style>
        <div class="norm-tooltip" onmouseenter="positionTooltip_{tooltip_id}(event)" onmouseleave="hideTooltip_{tooltip_id}()">- {norm_id}
            <span class="tooltiptext" id="{tooltip_id}">{tooltip_content.strip()}</span>
        </div>
        <script>
        function positionTooltip_{tooltip_id}(event) {{
            const tooltip = document.getElementById('{tooltip_id}');
            const trigger = event.target;
            
            // Get viewport dimensions
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            
            // Get trigger element position
            const triggerRect = trigger.getBoundingClientRect();
            
            // Tooltip dimensions
            const tooltipWidth = 480;
            const tooltipHeight = Math.min(400, tooltip.scrollHeight + 24); // Max height + padding
            
            let x, y;
            let position = 'above'; // default
            
            // Determine best position
            // Try above first
            if (triggerRect.top > tooltipHeight + 20) {{
                y = triggerRect.top - tooltipHeight - 10;
                position = 'above';
            }}
            // Try below if not enough space above
            else if (triggerRect.bottom + tooltipHeight + 20 < viewportHeight) {{
                y = triggerRect.bottom + 10;
                position = 'below';
            }}
            // Try to the left
            else if (triggerRect.left > tooltipWidth + 20) {{
                x = triggerRect.left - tooltipWidth - 10;
                y = triggerRect.top + (triggerRect.height / 2) - (tooltipHeight / 2);
                position = 'left';
            }}
            // Try to the right
            else if (triggerRect.right + tooltipWidth + 20 < viewportWidth) {{
                x = triggerRect.right + 10;
                y = triggerRect.top + (triggerRect.height / 2) - (tooltipHeight / 2);
                position = 'right';
            }}
            // Fallback: above with adjusted position
            else {{
                y = Math.max(10, triggerRect.top - tooltipHeight - 10);
                position = 'above';
            }}
            
            // Calculate x position for above/below positions
            if (position === 'above' || position === 'below') {{
                x = triggerRect.left + (triggerRect.width / 2) - (tooltipWidth / 2);
                // Ensure tooltip doesn't go off screen horizontally
                x = Math.max(10, Math.min(x, viewportWidth - tooltipWidth - 10));
            }}
            
            // Ensure tooltip doesn't go off screen vertically for left/right positions
            if (position === 'left' || position === 'right') {{
                y = Math.max(10, Math.min(y, viewportHeight - tooltipHeight - 10));
            }}
            
            // Apply position
            tooltip.style.left = x + 'px';
            tooltip.style.top = y + 'px';
            
            // Remove old arrow classes and add appropriate one
            tooltip.classList.remove('tooltip-above', 'tooltip-below', 'tooltip-left', 'tooltip-right');
            tooltip.classList.add('tooltip-' + position);
        }}
        
        function hideTooltip_{tooltip_id}() {{
            // No additional action needed, CSS handles hiding
        }}
        </script>
        """, unsafe_allow_html=True)
    else:
        # Fallback if no details found
        st.write(f"- {norm_id}")

def display_tag_usage_details(df, selected_tag, data=None):
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
                
                # Show alias information if this tag has merged aliases
                if 'original_paths' in tag_info and tag_info['original_paths']:
                    original_paths = tag_info['original_paths']
                    if len(original_paths) > 1 or (len(original_paths) == 1 and original_paths[0] != selected_tag):
                        st.info(f"🔄 **Merged Aliases**: This tag combines data from {len(original_paths)} tag variant(s)")
                        with st.expander("View original tag names"):
                            for path in original_paths:
                                st.write(f"- {path}")
            
            with col2:
                if tag_info['related_topics']:
                    st.write(f"**Related Topics:**")
                    for topic in tag_info['related_topics']:
                        st.write(f"- {topic}")
                
                st.write(f"**Section Parent:** {tag_info['section_parent']}")
                
                if tag_info['used_by_norms']:
                    st.write(f"**Used by {len(tag_info['used_by_norms'])} norm(s):**")
                    
                    # Display all norm IDs without truncation, using columns for better layout
                    norm_ids = tag_info['used_by_norms']
                    
                    # Create multiple columns to display norm IDs efficiently
                    if len(norm_ids) <= 5:
                        cols = st.columns(1)
                    elif len(norm_ids) <= 10:
                        cols = st.columns(2)
                    elif len(norm_ids) <= 20:
                        cols = st.columns(3)
                    else:
                        cols = st.columns(4)
                    
                    # Display hoverable norm IDs across columns
                    for i, norm_id in enumerate(norm_ids):
                        col_idx = i % len(cols)
                        with cols[col_idx]:
                            if data:  # If we have access to the full data
                                norm_details = get_norm_details_by_id(data, norm_id)
                                display_hoverable_norm_id(norm_id, norm_details)
                            else:  # Fallback to original display if no data available
                                st.write(f"- {norm_id}")

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
    
    # Initialize session state for click events
    if 'clicked_tag' not in st.session_state:
        st.session_state.clicked_tag = ""
    if 'clicked_topic' not in st.session_state:
        st.session_state.clicked_topic = ""
    if 'clicked_parameter' not in st.session_state:
        st.session_state.clicked_parameter = ""
    if 'clicked_applies_if_param' not in st.session_state:
        st.session_state.clicked_applies_if_param = ""
    if 'clicked_exempt_if_param' not in st.session_state:
        st.session_state.clicked_exempt_if_param = ""
    
    # Sidebar for file selection (same pattern as Tags.py)
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
                    # Display the interactive graph with click event handling
                    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="tag_graph")
                    
                    # Tag selection for detailed view
                    st.divider()
                    
                    # Get available tags
                    tag_options = [""] + sorted(tags_df['tag_path'].tolist())
                    
                    # Check if there's a selection from the graph
                    selected_from_graph = None
                    if hasattr(st.session_state, 'tag_graph') and st.session_state.tag_graph:
                        selection = st.session_state.tag_graph.get('selection', {})
                        if selection and 'points' in selection and selection['points']:
                            # Get the first selected point
                            point = selection['points'][0]
                            if 'id' in point:
                                selected_from_graph = point['id']
                    
                    # Determine the initial index
                    initial_index = 0
                    if selected_from_graph and selected_from_graph in tag_options:
                        initial_index = tag_options.index(selected_from_graph)
                    elif st.session_state.clicked_tag and st.session_state.clicked_tag in tag_options:
                        initial_index = tag_options.index(st.session_state.clicked_tag)
                    
                    selected_tag = st.selectbox(
                        "Select a tag to see detailed usage information:",
                        options=tag_options,
                        index=initial_index,
                        help="Choose a tag to see where it's used and its relationships. You can also click on a tag in the graph above.",
                        key="tag_selector_main"
                    )
                    
                    if selected_tag:
                        display_tag_usage_details(tags_df, selected_tag, data)
                    
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
                
            # ===== ADD TOPIC NETWORK SECTION =====
            # Extract and process topic data
            topics_df = extract_topic_data(data)
            
            if not topics_df.empty:
                st.divider()
                st.divider()  # Double divider to separate sections
                
                # Create topic network graph
                topic_G, topic_info, topic_relationships = create_topic_network_graph(topics_df)
                
                # Display topic statistics
                display_topic_statistics(topics_df, topic_G)
                st.divider()
                
                # Create and display the interactive topic graph
                st.header("🏷️ Topic Relationship Network")
                
                if topic_G and len(topic_G.nodes()) > 0:
                    topic_fig = create_plotly_topic_network_graph(topic_G, topic_info)
                    if topic_fig:
                        # Display the interactive topic graph with click event handling
                        event = st.plotly_chart(topic_fig, use_container_width=True, on_select="rerun", key="topic_graph")
                        
                        # Topic selection for detailed view
                        st.divider()
                        
                        # Get available topics
                        topic_options = [""] + sorted(topics_df['topic_name'].tolist())
                        
                        # Check if there's a selection from the graph
                        selected_from_graph = None
                        if hasattr(st.session_state, 'topic_graph') and st.session_state.topic_graph:
                            selection = st.session_state.topic_graph.get('selection', {})
                            if selection and 'points' in selection and selection['points']:
                                # Get the first selected point
                                point = selection['points'][0]
                                if 'id' in point:
                                    selected_from_graph = point['id']
                        
                        # Determine the initial index
                        initial_index = 0
                        if selected_from_graph and selected_from_graph in topic_options:
                            initial_index = topic_options.index(selected_from_graph)
                        elif st.session_state.clicked_topic and st.session_state.clicked_topic in topic_options:
                            initial_index = topic_options.index(st.session_state.clicked_topic)
                        
                        selected_topic = st.selectbox(
                            "Select a topic to see detailed usage information:",
                            options=topic_options,
                            index=initial_index,
                            help="Choose a topic to see related norms and tags. You can also click on a topic in the graph above.",
                            key="topic_selector"  # Unique key to avoid conflicts with tag selector
                        )
                        
                        if selected_topic:
                            display_topic_usage_details(topics_df, selected_topic, data)
                        
                        # Show topic relationships table
                        if topic_relationships:
                            st.divider()
                            st.header("🏷️ Topic Relationships")
                            topic_relationships_df = pd.DataFrame(topic_relationships, columns=['Parent Topic', 'Child Topic'])
                            st.dataframe(topic_relationships_df, use_container_width=True)
                    else:
                        st.warning("Could not create the topic network graph.")
                else:
                    st.warning("No topic relationships found to display in graph.")
            else:
                st.divider()
                st.info("No topic data found in the selected file.")
                
            # ===== ADD PARAMETER NETWORK SECTION =====
            # Extract and process parameter data
            params_df = extract_parameter_data(data)
            
            if not params_df.empty:
                st.divider()
                st.divider()  # Double divider to separate sections
                
                # Create parameter network graph
                param_G, param_info, param_relationships = create_parameter_network_graph(params_df)
                
                # Display parameter statistics
                display_parameter_statistics(params_df, param_G)
                st.divider()
                
                # Create and display the interactive parameter graph
                st.header("📊 Parameter Relationship Network")
                
                if param_G and len(param_G.nodes()) > 0:
                    param_fig = create_plotly_parameter_network_graph(param_G, param_info)
                    if param_fig:
                        # Display the interactive parameter graph with click event handling
                        event = st.plotly_chart(param_fig, use_container_width=True, on_select="rerun", key="param_graph")
                        
                        # Parameter selection for detailed view
                        st.divider()
                        
                        # Get available parameters
                        param_options = [""] + sorted(params_df['parameter_name'].tolist())
                        
                        # Check if there's a selection from the graph
                        selected_from_graph = None
                        if hasattr(st.session_state, 'param_graph') and st.session_state.param_graph:
                            selection = st.session_state.param_graph.get('selection', {})
                            if selection and 'points' in selection and selection['points']:
                                # Get the first selected point
                                point = selection['points'][0]
                                if 'id' in point:
                                    selected_from_graph = point['id']
                        
                        # Determine the initial index
                        initial_index = 0
                        if selected_from_graph and selected_from_graph in param_options:
                            initial_index = param_options.index(selected_from_graph)
                        elif st.session_state.clicked_parameter and st.session_state.clicked_parameter in param_options:
                            initial_index = param_options.index(st.session_state.clicked_parameter)
                        
                        selected_param = st.selectbox(
                            "Select a parameter to see detailed usage information:",
                            options=param_options,
                            index=initial_index,
                            help="Choose a parameter to see related norms and details. You can also click on a parameter in the graph above.",
                            key="param_selector"  # Unique key to avoid conflicts with tag and topic selectors
                        )
                        
                        if selected_param:
                            display_parameter_usage_details(params_df, selected_param, data)
                        
                        # Show parameter relationships table
                        if param_relationships:
                            st.divider()
                            st.header("📊 Parameter Relationships")
                            param_relationships_df = pd.DataFrame(param_relationships, columns=['Parent Parameter', 'Child Parameter'])
                            st.dataframe(param_relationships_df, use_container_width=True)
                    else:
                        st.warning("Could not create the parameter network graph.")
                else:
                    st.warning("No parameter relationships found to display in graph.")
            else:
                st.divider()
                st.info("No parameter data found in the selected file.")
            
            # ===== ADD APPLIES IF PARAMETER NETWORK SECTION =====
            # Extract and process applies_if parameter data
            applies_if_params_df = extract_condition_parameter_data(data, 'applies_if')
            
            if not applies_if_params_df.empty:
                st.divider()
                st.divider()  # Double divider to separate sections
                
                # Create applies_if parameter network graph
                applies_if_param_G, applies_if_param_info, applies_if_param_relationships = create_condition_parameter_network_graph(applies_if_params_df)
                
                # Display applies_if parameter statistics
                st.header("🔍 Applies If Parameter Statistics")
                
                if applies_if_params_df.empty or applies_if_param_G is None:
                    st.info("No applies_if parameter data found.")
                else:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total Parameters", len(applies_if_params_df))
                    
                    with col2:
                        chained_params = len(applies_if_params_df[applies_if_params_df['parameter_name'].str.contains('.', regex=False)])
                        st.metric("Chained Parameters", chained_params)
                    
                    with col3:
                        root_params = len(applies_if_params_df[~applies_if_params_df['parameter_name'].str.contains('.', regex=False)])
                        st.metric("Root Parameters", root_params)
                    
                    with col4:
                        if applies_if_param_G:
                            # Convert to undirected for connected components calculation
                            undirected_g = applies_if_param_G.to_undirected() if applies_if_param_G.is_directed() else applies_if_param_G
                            connected_components = nx.number_connected_components(undirected_g)
                            st.metric("Connected Components", connected_components)
                
                st.divider()
                
                # Create and display the interactive applies_if parameter graph
                st.header("🔍 Applies If Parameter Relationship Network")
                
                if applies_if_param_G and len(applies_if_param_G.nodes()) > 0:
                    applies_if_param_fig = create_plotly_parameter_network_graph(applies_if_param_G, applies_if_param_info)
                    if applies_if_param_fig:
                        # Display the interactive applies_if parameter graph with click event handling
                        event = st.plotly_chart(applies_if_param_fig, use_container_width=True, on_select="rerun", key="applies_if_param_graph")
                        
                        # Applies_if parameter selection for detailed view
                        st.divider()
                        
                        # Get available applies_if parameters
                        applies_if_param_options = [""] + sorted(applies_if_params_df['parameter_name'].tolist())
                        
                        # Check if there's a selection from the graph
                        selected_from_graph = None
                        if hasattr(st.session_state, 'applies_if_param_graph') and st.session_state.applies_if_param_graph:
                            selection = st.session_state.applies_if_param_graph.get('selection', {})
                            if selection and 'points' in selection and selection['points']:
                                # Get the first selected point
                                point = selection['points'][0]
                                if 'id' in point:
                                    selected_from_graph = point['id']
                        
                        # Determine the initial index
                        initial_index = 0
                        if selected_from_graph and selected_from_graph in applies_if_param_options:
                            initial_index = applies_if_param_options.index(selected_from_graph)
                        elif st.session_state.clicked_applies_if_param and st.session_state.clicked_applies_if_param in applies_if_param_options:
                            initial_index = applies_if_param_options.index(st.session_state.clicked_applies_if_param)
                        
                        selected_applies_if_param = st.selectbox(
                            "Select an applies_if parameter to see detailed usage information:",
                            options=applies_if_param_options,
                            index=initial_index,
                            help="Choose a parameter to see related norms and applies_if conditions. You can also click on a parameter in the graph above.",
                            key="applies_if_param_selector"
                        )
                        
                        if selected_applies_if_param:
                            display_condition_parameter_usage_details(applies_if_params_df, selected_applies_if_param, data, 'applies_if')
                        
                        # Show applies_if parameter relationships table
                        if applies_if_param_relationships:
                            st.divider()
                            st.header("🔍 Applies If Parameter Relationships")
                            applies_if_param_relationships_df = pd.DataFrame(applies_if_param_relationships, columns=['Parent Parameter', 'Child Parameter'])
                            st.dataframe(applies_if_param_relationships_df, use_container_width=True)
                    else:
                        st.warning("Could not create the applies_if parameter network graph.")
                else:
                    st.warning("No applies_if parameter relationships found to display in graph.")
            else:
                st.divider()
                st.info("No applies_if parameter data found in the selected file.")
            
            # ===== ADD EXEMPT IF PARAMETER NETWORK SECTION =====
            # Extract and process exempt_if parameter data
            exempt_if_params_df = extract_condition_parameter_data(data, 'exempt_if')
            
            if not exempt_if_params_df.empty:
                st.divider()
                st.divider()  # Double divider to separate sections
                
                # Create exempt_if parameter network graph
                exempt_if_param_G, exempt_if_param_info, exempt_if_param_relationships = create_condition_parameter_network_graph(exempt_if_params_df)
                
                # Display exempt_if parameter statistics
                st.header("🚫 Exempt If Parameter Statistics")
                
                if exempt_if_params_df.empty or exempt_if_param_G is None:
                    st.info("No exempt_if parameter data found.")
                else:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total Parameters", len(exempt_if_params_df))
                    
                    with col2:
                        chained_params = len(exempt_if_params_df[exempt_if_params_df['parameter_name'].str.contains('.', regex=False)])
                        st.metric("Chained Parameters", chained_params)
                    
                    with col3:
                        root_params = len(exempt_if_params_df[~exempt_if_params_df['parameter_name'].str.contains('.', regex=False)])
                        st.metric("Root Parameters", root_params)
                    
                    with col4:
                        if exempt_if_param_G:
                            # Convert to undirected for connected components calculation  
                            undirected_g = exempt_if_param_G.to_undirected() if exempt_if_param_G.is_directed() else exempt_if_param_G
                            connected_components = nx.number_connected_components(undirected_g)
                            st.metric("Connected Components", connected_components)
                
                st.divider()
                
                # Create and display the interactive exempt_if parameter graph
                st.header("🚫 Exempt If Parameter Relationship Network")
                
                if exempt_if_param_G and len(exempt_if_param_G.nodes()) > 0:
                    exempt_if_param_fig = create_plotly_parameter_network_graph(exempt_if_param_G, exempt_if_param_info)
                    if exempt_if_param_fig:
                        # Display the interactive exempt_if parameter graph with click event handling
                        event = st.plotly_chart(exempt_if_param_fig, use_container_width=True, on_select="rerun", key="exempt_if_param_graph")
                        
                        # Exempt_if parameter selection for detailed view
                        st.divider()
                        
                        # Get available exempt_if parameters
                        exempt_if_param_options = [""] + sorted(exempt_if_params_df['parameter_name'].tolist())
                        
                        # Check if there's a selection from the graph
                        selected_from_graph = None
                        if hasattr(st.session_state, 'exempt_if_param_graph') and st.session_state.exempt_if_param_graph:
                            selection = st.session_state.exempt_if_param_graph.get('selection', {})
                            if selection and 'points' in selection and selection['points']:
                                # Get the first selected point
                                point = selection['points'][0]
                                if 'id' in point:
                                    selected_from_graph = point['id']
                        
                        # Determine the initial index
                        initial_index = 0
                        if selected_from_graph and selected_from_graph in exempt_if_param_options:
                            initial_index = exempt_if_param_options.index(selected_from_graph)
                        elif st.session_state.clicked_exempt_if_param and st.session_state.clicked_exempt_if_param in exempt_if_param_options:
                            initial_index = exempt_if_param_options.index(st.session_state.clicked_exempt_if_param)
                        
                        selected_exempt_if_param = st.selectbox(
                            "Select an exempt_if parameter to see detailed usage information:",
                            options=exempt_if_param_options,
                            index=initial_index,
                            help="Choose a parameter to see related norms and exempt_if conditions. You can also click on a parameter in the graph above.",
                            key="exempt_if_param_selector"
                        )
                        
                        if selected_exempt_if_param:
                            display_condition_parameter_usage_details(exempt_if_params_df, selected_exempt_if_param, data, 'exempt_if')
                        
                        # Show exempt_if parameter relationships table
                        if exempt_if_param_relationships:
                            st.divider()
                            st.header("🚫 Exempt If Parameter Relationships")
                            exempt_if_param_relationships_df = pd.DataFrame(exempt_if_param_relationships, columns=['Parent Parameter', 'Child Parameter'])
                            st.dataframe(exempt_if_param_relationships_df, use_container_width=True)
                    else:
                        st.warning("Could not create the exempt_if parameter network graph.")
                else:
                    st.warning("No exempt_if parameter relationships found to display in graph.")
            else:
                st.divider()
                st.info("No exempt_if parameter data found in the selected file.")
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