import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from collections import defaultdict, Counter

st.set_page_config(
    page_title="Legal Documents Analytics - LangExtract",
    page_icon="📖",
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

def extract_legal_documents_data(data):
    """Extract and process legal documents data from extractions."""
    extractions = data.get('extractions', [])
    sections = data.get('sections', [])
    
    # Create section mapping for easy lookup
    section_map = {s.get('section_id'): s for s in sections}
    
    legal_doc_extractions = [e for e in extractions if e.get('extraction_class') == 'LEGAL_DOCUMENT']
    
    legal_docs_data = []
    for doc in legal_doc_extractions:
        attrs = doc.get('attributes', {})
        section_id = doc.get('section_parent_id', '')
        section_info = section_map.get(section_id, {})
        
        # Parse year from attributes or try to extract from code/title
        year = attrs.get('year', '')
        if not year:
            # Try to extract year from code or title
            text = attrs.get('code', '') + ' ' + attrs.get('title', '')
            import re
            year_match = re.search(r'\b(19|20)\d{2}\b', text)
            year = year_match.group() if year_match else 'Unknown'
        
        legal_docs_data.append({
            'id': attrs.get('id', ''),
            'title': attrs.get('title', ''),
            'code': attrs.get('code', ''),
            'year': year,
            'article': attrs.get('article', ''),
            'section_ref': attrs.get('section', ''),
            'notes': attrs.get('notes', ''),
            'section_id': section_id,
            'section_name': section_info.get('section_name', ''),
            'section_level': section_info.get('section_level', 0),
            'extraction_text': doc.get('extraction_text', ''),
            'has_article': bool(attrs.get('article')),
            'has_section_ref': bool(attrs.get('section')),
            'has_notes': bool(attrs.get('notes')),
            'code_type': attrs.get('code', '').split()[0] if attrs.get('code') else 'Unknown',
            'year_numeric': int(year) if year.isdigit() else 0
        })
    
    return pd.DataFrame(legal_docs_data)

def display_legal_docs_overview(df):
    """Display legal documents overview metrics."""
    st.header("📖 Legal Documents Overview")
    
    if df.empty:
        st.warning("No legal documents data found.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Legal Documents",
            value=len(df),
            delta=f"{len(df['id'].unique())} unique"
        )
    
    with col2:
        unique_codes = len(df['code'].unique()) if not df.empty else 0
        st.metric(
            label="Unique Document Codes",
            value=unique_codes,
            delta="different references"
        )
    
    with col3:
        year_range = ""
        if not df.empty and df['year_numeric'].max() > 0:
            min_year = df[df['year_numeric'] > 0]['year_numeric'].min()
            max_year = df[df['year_numeric'] > 0]['year_numeric'].max()
            year_range = f"{min_year}-{max_year}"
        
        st.metric(
            label="Year Range",
            value=year_range if year_range else "Unknown",
            delta="publication years"
        )
    
    with col4:
        with_articles = df['has_article'].sum() if not df.empty else 0
        st.metric(
            label="With Article References",
            value=with_articles,
            delta=f"{(with_articles/len(df)*100):.1f}% of total" if len(df) > 0 else "0%"
        )

def display_legal_docs_analysis(df):
    """Display legal documents analysis charts."""
    st.header("📊 Legal Documents Analysis")
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Document Types Distribution")
        
        code_type_counts = df['code_type'].value_counts()
        if not code_type_counts.empty:
            fig_types = px.pie(
                values=code_type_counts.values,
                names=code_type_counts.index,
                title="Distribution by Document Type"
            )
            st.plotly_chart(fig_types, use_container_width=True)
    
    with col2:
        st.subheader("Publication Years Timeline")
        
        year_df = df[df['year_numeric'] > 0]
        if not year_df.empty:
            year_counts = year_df['year_numeric'].value_counts().sort_index()
            fig_years = px.bar(
                x=year_counts.index,
                y=year_counts.values,
                title="Documents by Publication Year",
                labels={'x': 'Publication Year', 'y': 'Number of Documents'}
            )
            st.plotly_chart(fig_years, use_container_width=True)
        else:
            st.info("No publication year data available.")
    
    # Document attributes analysis
    st.subheader("Document Attributes Analysis")
    
    col3, col4 = st.columns(2)
    
    with col3:
        # Attributes presence
        attributes_data = {
            'Has Article': df['has_article'].sum(),
            'Has Section Reference': df['has_section_ref'].sum(),
            'Has Notes': df['has_notes'].sum()
        }
        
        fig_attrs = px.bar(
            x=list(attributes_data.keys()),
            y=list(attributes_data.values()),
            title="Document Attributes Presence",
            labels={'x': 'Attribute Type', 'y': 'Number of Documents'}
        )
        st.plotly_chart(fig_attrs, use_container_width=True)
    
    with col4:
        # Documents by section
        section_counts = df['section_name'].value_counts().head(10)
        if not section_counts.empty:
            fig_sections = px.bar(
                x=section_counts.values,
                y=section_counts.index,
                orientation='h',
                title="Top 10 Sections with Legal Documents",
                labels={'x': 'Number of Documents', 'y': 'Section Name'}
            )
            st.plotly_chart(fig_sections, use_container_width=True)

def display_references_analysis(df):
    """Display legal document references analysis."""
    st.header("🔗 References Analysis")
    
    if df.empty:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Most Referenced Documents")
        
        doc_counts = df.groupby(['code', 'title']).size().reset_index(name='count')
        doc_counts = doc_counts.nlargest(10, 'count')
        
        if not doc_counts.empty:
            doc_counts['display_name'] = doc_counts.apply(
                lambda x: f"{x['code'][:30]}..." if len(x['code']) > 30 else x['code'], axis=1
            )
            
            fig_refs = px.bar(
                doc_counts,
                x='count',
                y='display_name',
                orientation='h',
                title="Top 10 Most Referenced Documents",
                labels={'x': 'Reference Count', 'y': 'Document Code'}
            )
            st.plotly_chart(fig_refs, use_container_width=True)
    
    with col2:
        st.subheader("Article vs Section References")
        
        ref_types_data = {
            'Article References': df['has_article'].sum(),
            'Section References': df['has_section_ref'].sum(),
            'No Specific Reference': len(df) - df['has_article'].sum() - df['has_section_ref'].sum()
        }
        
        fig_ref_types = px.pie(
            values=list(ref_types_data.values()),
            names=list(ref_types_data.keys()),
            title="Types of Document References"
        )
        st.plotly_chart(fig_ref_types, use_container_width=True)

def display_legal_docs_explorer(df, all_sections):
    """Display interactive legal documents explorer."""
    st.header("🔍 Legal Documents Explorer")
    
    if df.empty:
        return
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        selected_type = st.selectbox(
            "Filter by Document Type",
            options=['All'] + sorted(df['code_type'].unique().tolist()),
            index=0
        )
    
    with col2:
        selected_section = st.selectbox(
            "Filter by Section",
            options=['All'] + sorted([s.get('section_name', '') for s in all_sections if s.get('section_name')]),
            index=0
        )
    
    with col3:
        year_range = st.slider(
            "Filter by Year Range",
            min_value=int(df['year_numeric'].min()) if df['year_numeric'].max() > 0 else 1900,
            max_value=int(df['year_numeric'].max()) if df['year_numeric'].max() > 0 else 2024,
            value=(int(df['year_numeric'].min()) if df['year_numeric'].max() > 0 else 1900, 
                   int(df['year_numeric'].max()) if df['year_numeric'].max() > 0 else 2024),
            step=1
        )
    
    with col4:
        has_reference = st.selectbox(
            "Filter by Reference Type",
            options=['All', 'With Article', 'With Section', 'With Notes'],
            index=0
        )
    
    # Search functionality
    st.subheader("Search Documents")
    col5, col6 = st.columns(2)
    
    with col5:
        title_search = st.text_input("Search by Title (contains):", "")
    
    with col6:
        code_search = st.text_input("Search by Code (contains):", "")
    
    # Apply filters
    filtered_df = df.copy()
    
    if selected_type != 'All':
        filtered_df = filtered_df[filtered_df['code_type'] == selected_type]
    
    if selected_section != 'All':
        filtered_df = filtered_df[filtered_df['section_name'] == selected_section]
    
    if df['year_numeric'].max() > 0:
        filtered_df = filtered_df[
            (filtered_df['year_numeric'] >= year_range[0]) & 
            (filtered_df['year_numeric'] <= year_range[1])
        ]
    
    if has_reference == 'With Article':
        filtered_df = filtered_df[filtered_df['has_article'] == True]
    elif has_reference == 'With Section':
        filtered_df = filtered_df[filtered_df['has_section_ref'] == True]
    elif has_reference == 'With Notes':
        filtered_df = filtered_df[filtered_df['has_notes'] == True]
    
    if title_search:
        filtered_df = filtered_df[filtered_df['title'].str.contains(title_search, case=False, na=False)]
    
    if code_search:
        filtered_df = filtered_df[filtered_df['code'].str.contains(code_search, case=False, na=False)]
    
    st.subheader(f"Filtered Legal Documents ({len(filtered_df)} of {len(df)})")
    
    if not filtered_df.empty:
        # Display filtered results
        display_cols = ['title', 'code', 'year', 'article', 'section_ref', 'section_name']
        display_df = filtered_df[display_cols].copy()
        display_df['title'] = display_df['title'].apply(lambda x: x[:60] + '...' if len(x) > 60 else x)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )
        
        # Show detailed view for selected document
        if len(filtered_df) > 0:
            selected_doc_idx = st.selectbox(
                "Select a document for detailed view:",
                options=range(len(filtered_df)),
                format_func=lambda x: f"Doc {x+1}: {filtered_df.iloc[x]['code']} - {filtered_df.iloc[x]['title'][:50]}..."
            )
            
            if selected_doc_idx is not None:
                doc_details = filtered_df.iloc[selected_doc_idx]
                
                st.subheader("Legal Document Details")
                
                detail_col1, detail_col2 = st.columns(2)
                
                with detail_col1:
                    st.write(f"**ID:** {doc_details['id']}")
                    st.write(f"**Title:** {doc_details['title']}")
                    st.write(f"**Code:** {doc_details['code']}")
                    st.write(f"**Year:** {doc_details['year']}")
                    st.write(f"**Document Type:** {doc_details['code_type']}")
                
                with detail_col2:
                    st.write(f"**Article:** {doc_details['article'] if doc_details['article'] else 'Not specified'}")
                    st.write(f"**Section Reference:** {doc_details['section_ref'] if doc_details['section_ref'] else 'Not specified'}")
                    st.write(f"**Source Section:** {doc_details['section_name']}")
                    st.write(f"**Notes:** {doc_details['notes'] if doc_details['notes'] else 'No notes'}")
                
                if doc_details['extraction_text']:
                    st.write("**Full Extraction Text:**")
                    st.write(doc_details['extraction_text'])

def main():
    st.title("📖 Legal Documents Analytics")
    st.markdown("Detailed analytics for extracted legal documents from LangExtract")
    
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
        
        # Extract and process legal documents data
        legal_docs_df = extract_legal_documents_data(data)
        all_sections = data.get('sections', [])
        
        if not legal_docs_df.empty:
            # Display analytics sections
            display_legal_docs_overview(legal_docs_df)
            st.divider()
            display_legal_docs_analysis(legal_docs_df)
            st.divider()
            display_references_analysis(legal_docs_df)
            st.divider()
            display_legal_docs_explorer(legal_docs_df, all_sections)
        else:
            st.warning("No legal documents data found in the selected file.")
            
    else:
        st.info("👆 Please select a data source from the sidebar to view legal documents analytics.")
        st.markdown("""
        ### About Legal Documents Analytics
        
        This page provides detailed analysis of extracted legal documents, including:
        
        - **Overview**: Key metrics about legal document extraction
        - **Analysis**: Distribution by document types, publication years, and attributes
        - **References Analysis**: Analysis of most referenced documents and reference types
        - **Explorer**: Interactive filtering by document attributes
        
        Legal documents represent references to laws, standards, regulations, and other legal sources extracted from documents, including their codes, titles, articles, and sections.
        """)

if __name__ == "__main__":
    main()