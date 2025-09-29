import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re
from collections import defaultdict, Counter
from typing import List, Tuple, Set, Any, Dict
import io

st.set_page_config(
    page_title="Applies_If Analysis - LangExtract",
    page_icon="🔍",
    layout="wide"
)

# ========== HELPER FUNCTIONS ==========

def split_path(term: str) -> List[str]:
    """Split DSL path into components.
    
    Args:
        term: DSL path like 'A.B.C'
        
    Returns:
        List of path components ['A', 'B', 'C']
    """
    if not term or not isinstance(term, str):
        return []
    return term.strip().split('.')

def all_prefixes(term: str) -> List[str]:
    """Generate all prefix paths for hierarchy building.
    
    Args:
        term: DSL path like 'A.B.C'
        
    Returns:
        List of all prefixes ['A', 'A.B', 'A.B.C']
    """
    parts = split_path(term)
    if not parts:
        return []
    
    prefixes = []
    for i in range(1, len(parts) + 1):
        prefixes.append('.'.join(parts[:i]))
    return prefixes

def build_hierarchy(terms: List[str]) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """Build hierarchy nodes and edges from parameter terms.
    
    Args:
        terms: List of DSL paths
        
    Returns:
        Tuple of (nodes_set, edges_set) where edges are (parent, child) tuples
    """
    nodes = set()
    edges = set()
    
    # Collect all nodes (including synthetic parents)
    for term in terms:
        prefixes = all_prefixes(term)
        nodes.update(prefixes)
        
        # Create parent-child relationships
        for i in range(len(prefixes) - 1):
            parent = prefixes[i]
            child = prefixes[i + 1]
            edges.add((parent, child))
    
    return nodes, edges

@st.cache_data
def aggregate_param_stats(norms_data: List[Dict]) -> pd.DataFrame:
    """Aggregate parameter-level statistics from norms data.
    
    Args:
        norms_data: List of norm dictionaries
        
    Returns:
        DataFrame with parameter statistics
    """
    param_stats = defaultdict(lambda: {
        'norms': set(),
        'conditions': [],
        'root_term': '',
        'full_path': ''
    })
    
    parser_issues = 0
    
    for norm in norms_data:
        norm_id = norm.get('id', '')
        applies_if = norm.get('applies_if', '')
        
        if not applies_if or applies_if.upper() in ['TRUE', 'FALSE']:
            continue
            
        try:
            # Extract parameter identifiers from applies_if condition
            parameters = extract_parameter_identifiers(applies_if)
            
            for param in parameters:
                param_stats[param]['norms'].add(norm_id)
                param_stats[param]['conditions'].append({
                    'norm_id': norm_id,
                    'condition': applies_if,
                    'norm_title': norm.get('norm_statement', '')[:100] + '...' if len(norm.get('norm_statement', '')) > 100 else norm.get('norm_statement', ''),
                    'section_name': norm.get('section_name', ''),
                    'details_md': f"**Norm ID:** {norm_id}\n\n**Statement:** {norm.get('norm_statement', '')}\n\n**Section:** {norm.get('section_name', '')}\n\n**Applies If:** {applies_if}"
                })
                param_stats[param]['root_term'] = split_path(param)[0] if split_path(param) else param
                param_stats[param]['full_path'] = param
                
        except Exception as e:
            parser_issues += 1
            continue
    
    # Convert to DataFrame
    param_data = []
    for param, stats in param_stats.items():
        param_data.append({
            'parameter': param,
            'root': stats['root_term'],
            'norm_count': len(stats['norms']),
            'norm_list': list(stats['norms']),
            'conditions': stats['conditions']
        })
    
    df = pd.DataFrame(param_data)
    
    # Store parser issues count for later use
    if not df.empty:
        df.attrs['parser_issues'] = parser_issues
    
    return df.sort_values('norm_count', ascending=False) if not df.empty else df

@st.cache_data
def aggregate_root_stats(param_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate root-term statistics from parameter DataFrame.
    
    Args:
        param_df: DataFrame with parameter statistics
        
    Returns:
        DataFrame with root-term statistics
    """
    if param_df.empty:
        return pd.DataFrame(columns=['root', 'norm_count', 'parameters'])
    
    root_stats = defaultdict(lambda: {
        'norms': set(),
        'parameters': []
    })
    
    for _, row in param_df.iterrows():
        root = row['root']
        root_stats[root]['norms'].update(row['norm_list'])
        root_stats[root]['parameters'].append(row['parameter'])
    
    root_data = []
    for root, stats in root_stats.items():
        root_data.append({
            'root': root,
            'norm_count': len(stats['norms']),
            'parameters': stats['parameters']
        })
    
    return pd.DataFrame(root_data).sort_values('norm_count', ascending=False)

def extract_parameter_identifiers(condition_text: str) -> List[str]:
    """Extract parameter identifiers from applies_if condition text.
    
    Args:
        condition_text: The applies_if condition string
        
    Returns:
        List of parameter identifiers found in the condition
    """
    if not condition_text or condition_text.upper() in ['TRUE', 'FALSE']:
        return []
    
    # Pattern to match parameter identifiers (e.g., BUILDING.USAGE, FLOOR.HEIGHT, etc.)
    # This regex looks for uppercase words with dots and underscores
    pattern = r'\b[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)*\b'
    
    # Extract all matches
    identifiers = re.findall(pattern, condition_text)
    
    # Filter out common logical operators and values
    excluded = {'TRUE', 'FALSE', 'AND', 'OR', 'NOT', 'NULL', 'NONE', 'IF', 'THEN', 'ELSE'}
    
    # Filter identifiers
    filtered_identifiers = []
    for identifier in identifiers:
        # Skip if it's an excluded term
        if identifier in excluded:
            continue
        # Skip if it looks like a quoted value (all caps single word that might be a value)
        if '.' not in identifier and len(identifier) < 15:
            # Check if it's likely a parameter vs a value by context
            # Parameters usually have dots or are common parameter patterns
            common_patterns = ['BUILDING', 'FLOOR', 'AREA', 'HEIGHT', 'WIDTH', 'USAGE', 'TYPE', 
                             'SYSTEM', 'FIRE', 'SAFETY', 'ACCESS', 'DOOR', 'WINDOW', 'WALL',
                             'ROOM', 'SPACE', 'LOAD', 'PRESSURE', 'TEMPERATURE', 'MATERIAL']
            if not any(pattern in identifier for pattern in common_patterns):
                continue
        filtered_identifiers.append(identifier)
    
    return list(set(filtered_identifiers))  # Remove duplicates

def make_graph(nodes: Set[str], edges: Set[Tuple[str, str]], param_df: pd.DataFrame, 
               selected_filter: str = None, search_query: str = "", orphan_only: bool = False) -> go.Figure:
    """Create interactive hierarchical graph using Plotly.
    
    Args:
        nodes: Set of all nodes (parameters)
        edges: Set of (parent, child) tuples
        param_df: DataFrame with parameter statistics
        selected_filter: Currently selected parameter for highlighting
        search_query: Search query for filtering
        orphan_only: Whether to show only orphan leaves
        
    Returns:
        Plotly Figure object
    """
    if not nodes:
        return None
    
    # Filter nodes based on search query
    filtered_nodes = nodes
    if search_query:
        filtered_nodes = {node for node in nodes if search_query.lower() in node.lower()}
        # Also include parent nodes for hierarchy
        extended_nodes = set(filtered_nodes)
        for node in filtered_nodes:
            prefixes = all_prefixes(node)
            extended_nodes.update(prefixes)
        filtered_nodes = extended_nodes & nodes
    
    # Filter for orphan leaves only
    if orphan_only:
        children = {edge[1] for edge in edges}
        parents = {edge[0] for edge in edges}
        orphan_leaves = {node for node in filtered_nodes if node not in parents}
        filtered_nodes = orphan_leaves
    
    if not filtered_nodes:
        return None
    
    # Create a mapping of parameters to their stats
    param_stats = {}
    if not param_df.empty:
        for _, row in param_df.iterrows():
            param_stats[row['parameter']] = {
                'norm_count': row['norm_count'],
                'norm_list': row['norm_list']
            }
    
    # Filter edges to only include filtered nodes
    filtered_edges = {(p, c) for p, c in edges if p in filtered_nodes and c in filtered_nodes}
    
    # Calculate positions using a hierarchical layout
    pos = calculate_hierarchical_positions(filtered_nodes, filtered_edges)
    
    # Prepare node traces
    node_x = []
    node_y = []
    node_text = []
    node_size = []
    node_color = []
    node_info = []
    node_ids = []
    
    for node in filtered_nodes:
        if node not in pos:
            continue
            
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_ids.append(node)
        
        # Node display text (truncate long paths)
        display_text = node
        if len(display_text) > 15:
            if '.' in display_text:
                parts = display_text.split('.')
                if len(parts[-1]) <= 12:
                    display_text = parts[-1]
                else:
                    display_text = parts[-1][:12] + "..."
            else:
                display_text = display_text[:12] + "..."
        node_text.append(display_text)
        
        # Get stats for this parameter
        stats = param_stats.get(node, {'norm_count': 0, 'norm_list': []})
        norm_count = stats['norm_count']
        
        # Node size based on usage
        if node in param_stats:  # Real parameter
            size = max(15, min(50, 15 + norm_count * 3))
            color = 'rgba(31, 119, 180, 0.8)'  # Blue for real parameters
        else:  # Synthetic parameter
            size = 10
            color = 'rgba(128, 128, 128, 0.6)'  # Gray for synthetic
        
        # Highlight selected node
        if selected_filter and selected_filter == node:
            color = 'rgba(255, 0, 0, 0.8)'  # Red for selected
        
        node_size.append(size)
        node_color.append(color)
        
        # Hover info
        if node in param_stats:
            example_norms = stats['norm_list'][:3]  # Show first 3 norms
            examples_text = ', '.join(example_norms) + ('...' if len(stats['norm_list']) > 3 else '')
            hover_text = f"Parameter: {node}<br>Norm Count: {norm_count}<br>Example Norms: {examples_text}"
        else:
            hover_text = f"Parameter: {node}<br>Type: Synthetic Parent<br>Note: Inferred from child parameters"
        
        node_info.append(hover_text)
    
    # Prepare edge traces
    edge_x = []
    edge_y = []
    
    for parent, child in filtered_edges:
        if parent in pos and child in pos:
            x0, y0 = pos[parent]
            x1, y1 = pos[child]
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
            size=node_size,
            color=node_color,
            line=dict(width=2, color='rgba(50,50,50,0.8)')
        ),
        ids=node_ids  # For click events
    )
    
    # Create the figure
    fig = go.Figure(data=[edge_trace, node_trace],
                   layout=go.Layout(
                       title=dict(
                           text='Applies_If Parameters Hierarchy',
                           font=dict(size=16)
                       ),
                       showlegend=False,
                       hovermode='closest',
                       margin=dict(b=20,l=5,r=5,t=40),
                       annotations=[
                           dict(
                               text="Hierarchical view of applies_if parameters. Blue nodes = real parameters, Gray = synthetic parents. Click nodes to filter tables.",
                               showarrow=False,
                               xref="paper", yref="paper",
                               x=0.005, y=-0.002,
                               xanchor='left', yanchor='bottom',
                               font=dict(size=12)
                           )
                       ],
                       xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       height=600,
                       plot_bgcolor='rgba(248,249,250,0.8)'
                   ))
    
    return fig

def calculate_hierarchical_positions(nodes: Set[str], edges: Set[Tuple[str, str]]) -> Dict[str, Tuple[float, float]]:
    """Calculate hierarchical positions for graph layout.
    
    Args:
        nodes: Set of node names
        edges: Set of (parent, child) edges
        
    Returns:
        Dictionary mapping node names to (x, y) positions
    """
    # Group nodes by depth
    depth_groups = defaultdict(list)
    for node in nodes:
        depth = len(split_path(node))
        depth_groups[depth].append(node)
    
    pos = {}
    y_spacing = 3.0
    
    for depth in sorted(depth_groups.keys()):
        nodes_at_depth = sorted(depth_groups[depth])
        y_pos = -(depth - 1) * y_spacing
        
        if len(nodes_at_depth) == 1:
            pos[nodes_at_depth[0]] = (0, y_pos)
        else:
            total_width = (len(nodes_at_depth) - 1) * 4.0
            start_x = -total_width / 2
            for i, node in enumerate(nodes_at_depth):
                x_pos = start_x + i * 4.0
                pos[node] = (x_pos, y_pos)
    
    return pos

# ========== DATA LOADING FUNCTIONS ==========

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

def extract_norms_with_applies_if(data):
    """Extract norms that have applies_if conditions."""
    extractions = data.get('extractions', [])
    sections = data.get('sections', [])
    
    # Create section mapping
    section_map = {s.get('section_id'): s for s in sections}
    
    norm_extractions = [e for e in extractions if e.get('extraction_class') in ['Norm', 'NORM']]
    
    norms_data = []
    for norm in norm_extractions:
        attrs = norm.get('attributes', {})
        applies_if = attrs.get('applies_if', '')
        
        # Only include norms with non-trivial applies_if conditions
        if applies_if and applies_if.upper() not in ['TRUE', 'FALSE']:
            section_id = attrs.get('parent_section_id', '')
            section_info = section_map.get(section_id, {})
            
            norms_data.append({
                'id': attrs.get('id', ''),
                'norm_statement': norm.get('extraction_text', ''),
                'applies_if': applies_if,
                'section_name': section_info.get('section_name', ''),
                'section_id': section_id,
                'confidence': attrs.get('confidence', 0),
                'priority': attrs.get('priority', 0)
            })
    
    return norms_data

# ========== UI COMPONENTS ==========

def display_kpi_row(param_df: pd.DataFrame, root_df: pd.DataFrame, norms_count: int):
    """Display KPI metrics row."""
    st.header("📊 Key Performance Indicators")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Roots", len(root_df) if not root_df.empty else 0)
    
    with col2:
        st.metric("Parameters", len(param_df) if not param_df.empty else 0)
    
    with col3:
        st.metric("Norms with applies_if", norms_count)
    
    with col4:
        parser_issues = getattr(param_df, 'attrs', {}).get('parser_issues', 0) if not param_df.empty else 0
        st.metric("Parser Issues", parser_issues)

def display_norm_chip(norm_id: str, condition_info: Dict):
    """Display a clickable norm chip with hover tooltip."""
    tooltip_content = condition_info.get('details_md', '')
    tooltip_id = f"tooltip_{hash(norm_id) % 10000}"
    
    st.markdown(f"""
    <style>
    .norm-chip {{
        display: inline-block;
        background-color: #e1f5fe;
        color: #01579b;
        padding: 4px 8px;
        margin: 2px;
        border-radius: 12px;
        font-size: 12px;
        cursor: pointer;
        position: relative;
        border: 1px solid #81d4fa;
    }}
    .norm-chip:hover {{
        background-color: #b3e5fc;
    }}
    .chip-tooltip {{
        visibility: hidden;
        width: 400px;
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
        max-height: 300px;
        overflow-y: auto;
        pointer-events: none;
    }}
    .norm-chip:hover .chip-tooltip {{
        visibility: visible;
        opacity: 1;
    }}
    </style>
    <span class="norm-chip" onmouseenter="positionTooltip(event, '{tooltip_id}')">{norm_id}
        <span class="chip-tooltip" id="{tooltip_id}">{tooltip_content}</span>
    </span>
    <script>
    function positionTooltip(event, tooltipId) {{
        const tooltip = document.getElementById(tooltipId);
        const rect = event.target.getBoundingClientRect();
        tooltip.style.left = (rect.left + window.scrollX) + 'px';
        tooltip.style.top = (rect.bottom + window.scrollY + 5) + 'px';
    }}
    </script>
    """, unsafe_allow_html=True)

def create_csv_download(df: pd.DataFrame, filename: str):
    """Create CSV download button for DataFrame."""
    if df.empty:
        return
    
    # Convert to CSV
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()
    
    st.download_button(
        label=f"📥 Download {filename}",
        data=csv_data,
        file_name=filename,
        mime="text/csv"
    )

# ========== MAIN FUNCTION ==========

def main():
    st.title("🔍 Applies_If Analysis")
    st.markdown("Analyze repeating patterns in applies_if conditions of extracted norms")
    
    # Initialize session state
    if 'selected_parameter' not in st.session_state:
        st.session_state.selected_parameter = ""
    if 'selected_root' not in st.session_state:
        st.session_state.selected_root = ""
    
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
        
        # Extract norms with applies_if conditions
        norms_data = extract_norms_with_applies_if(data)
        
        if not norms_data:
            st.warning("No norms with applies_if conditions found in the data.")
            st.markdown("""
            ### About Applies_If Analysis
            
            This page analyzes the `applies_if` conditions in extracted norms to help you understand:
            
            - **Parameter Hierarchy**: Hierarchical structure of parameters used in conditions
            - **Usage Patterns**: Which parameters are most commonly used
            - **Root Categories**: High-level parameter groupings
            - **Condition Examples**: Sample conditions for each parameter
            
            The analysis requires norms with non-trivial `applies_if` conditions (not just 'TRUE' or 'FALSE').
            """)
            return
        
        # Aggregate statistics
        param_df = aggregate_param_stats(norms_data)
        root_df = aggregate_root_stats(param_df)
        
        if param_df.empty:
            st.warning("No parameters could be extracted from applies_if conditions.")
            return
        
        # Display KPI row
        display_kpi_row(param_df, root_df, len(norms_data))
        st.divider()
        
        # Build hierarchy for graph
        all_params = param_df['parameter'].tolist()
        nodes, edges = build_hierarchy(all_params)
        
        # UI Controls
        st.header("🎛️ Controls")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            search_query = st.text_input("🔍 Search Parameters", placeholder="Enter parameter name...")
        
        with col2:
            root_options = ["All"] + sorted(root_df['root'].tolist()) if not root_df.empty else ["All"]
            selected_root_filter = st.selectbox("🏷️ Filter by Root", root_options)
        
        with col3:
            orphan_only = st.checkbox("🍃 Show Orphan Leaves Only")
        
        with col4:
            if st.button("🧹 Clear Filters"):
                st.session_state.selected_parameter = ""
                st.session_state.selected_root = ""
                st.rerun()
        
        st.divider()
        
        # Create and display graph
        st.header("📊 Hierarchical Graph")
        
        # Apply root filter to search if specified
        effective_search = search_query
        if selected_root_filter != "All":
            if effective_search:
                effective_search = f"{selected_root_filter}.{effective_search}"
            else:
                effective_search = selected_root_filter
        
        fig = make_graph(nodes, edges, param_df, st.session_state.selected_parameter, 
                        effective_search, orphan_only)
        
        if fig:
            # Display graph with click handling
            event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="param_graph")
            
            # Handle graph clicks
            if hasattr(st.session_state, 'param_graph') and st.session_state.param_graph:
                selection = st.session_state.param_graph.get('selection', {})
                if selection and 'points' in selection and selection['points']:
                    point = selection['points'][0]
                    if 'id' in point:
                        st.session_state.selected_parameter = point['id']
                        st.rerun()
        else:
            st.info("No parameters to display based on current filters.")
        
        st.divider()
        
        # Tables section
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("📋 Table 1: Parameters")
            
            # Filter parameters based on search and root filter
            filtered_param_df = param_df.copy()
            
            if search_query:
                mask = filtered_param_df['parameter'].str.contains(search_query, case=False, na=False)
                filtered_param_df = filtered_param_df[mask]
            
            if selected_root_filter != "All":
                filtered_param_df = filtered_param_df[filtered_param_df['root'] == selected_root_filter]
            
            if not filtered_param_df.empty:
                # Display table with clickable rows
                for idx, row in filtered_param_df.iterrows():
                    with st.expander(f"📍 {row['parameter']} (Root: {row['root']}, Count: {row['norm_count']})", 
                                   expanded=(row['parameter'] == st.session_state.selected_parameter)):
                        
                        col_a, col_b = st.columns([1, 2])
                        
                        with col_a:
                            st.write(f"**Parameter:** {row['parameter']}")
                            st.write(f"**Root:** {row['root']}")
                            st.write(f"**Norm Count:** {row['norm_count']}")
                            
                            if st.button(f"Select {row['parameter']}", key=f"select_{idx}"):
                                st.session_state.selected_parameter = row['parameter']
                                st.rerun()
                        
                        with col_b:
                            st.write("**Norm List:**")
                            # Display norm chips
                            for condition in row['conditions'][:10]:  # Limit to first 10 for performance
                                display_norm_chip(condition['norm_id'], condition)
                            
                            if len(row['conditions']) > 10:
                                st.caption(f"... and {len(row['conditions']) - 10} more norms")
                
                # CSV download for filtered parameters
                create_csv_download(filtered_param_df[['parameter', 'root', 'norm_count']], 
                                  "parameters.csv")
            else:
                st.info("No parameters match the current filters.")
        
        with col2:
            st.header("📊 Table 2: Roots")
            
            # Filter roots
            filtered_root_df = root_df.copy()
            if selected_root_filter != "All":
                filtered_root_df = filtered_root_df[filtered_root_df['root'] == selected_root_filter]
            
            if not filtered_root_df.empty:
                # Display root selection
                for idx, row in filtered_root_df.iterrows():
                    with st.container():
                        st.write(f"**{row['root']}**")
                        st.write(f"Norms: {row['norm_count']}")
                        st.write(f"Parameters: {len(row['parameters'])}")
                        
                        if st.button(f"Select {row['root']}", key=f"root_select_{idx}"):
                            st.session_state.selected_root = row['root']
                        
                        # Show parameters and norms if selected
                        if st.session_state.selected_root == row['root']:
                            st.write("**Parameters:**")
                            for param in row['parameters'][:5]:  # Show first 5
                                st.write(f"- {param}")
                            if len(row['parameters']) > 5:
                                st.caption(f"... and {len(row['parameters']) - 5} more")
                            
                            # Show norm chips for this root
                            st.write("**Norms:**")
                            root_param_df = param_df[param_df['root'] == row['root']]
                            all_conditions = []
                            for _, param_row in root_param_df.iterrows():
                                all_conditions.extend(param_row['conditions'])
                            
                            unique_norms = {cond['norm_id']: cond for cond in all_conditions}
                            for norm_id, condition in list(unique_norms.items())[:8]:  # Limit for performance
                                display_norm_chip(norm_id, condition)
                            
                            if len(unique_norms) > 8:
                                st.caption(f"... and {len(unique_norms) - 8} more norms")
                        
                        st.divider()
                
                # CSV download for filtered roots
                create_csv_download(filtered_root_df[['root', 'norm_count']], "roots.csv")
            else:
                st.info("No roots match the current filters.")
    
    else:
        st.info("👆 Please select a data source from the sidebar to view the applies_if analysis.")
        st.markdown("""
        ### About Applies_If Analysis
        
        This page helps you understand repeating patterns in the `applies_if` conditions of your extracted norms by showing:
        
        - **📊 Hierarchical Graph**: Visual representation of all parameters used in applies_if statements
        - **📋 Parameter Details**: Table with parameter-level statistics and norm lists
        - **📊 Root Overview**: High-level view of root terms with drill-down capabilities
        
        **Key Features:**
        - 🔍 **Search & Filter**: Find specific parameters or filter by root categories
        - 🖱️ **Interactive Graph**: Click nodes to filter tables and explore relationships
        - 🍃 **Orphan Leaves**: Toggle to show only leaf parameters without children
        - 📥 **CSV Export**: Download filtered data for further analysis
        - 🏷️ **Hover Tooltips**: Rich details on norm information with markdown formatting
        
        **Graph Legend:**
        - **Blue nodes**: Real parameters extracted from conditions
        - **Gray nodes**: Synthetic parent nodes (inferred from hierarchy)
        - **Node size**: Proportional to number of norms using the parameter
        - **Connections**: Show parent-child relationships in parameter hierarchy
        
        To get started, upload an `enhanced_extraction_results.json` file or use the latest available file.
        """)

if __name__ == "__main__":
    main()