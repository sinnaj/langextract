#!/usr/bin/env python3
"""
Enhanced Document Tree Visualizer for LangExtract JSON Output

This script creates a hierarchical tree visualization of document structure
including SECTIONS, NORMS, TABLES, and LEGAL_DOCUMENTS with proper parent-child relationships.
"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class SectionNode:
    """Represents a node in the document tree"""
    id: str
    title: str
    sectioning_type: str
    parent_id: Optional[str]
    parent_type: Optional[str]
    children: List['SectionNode']
    section_summary: str
    extraction_text: str
    
    def __post_init__(self):
        if not self.children:
            self.children = []


class SectionTreeBuilder:
    """Builds and visualizes hierarchical document tree structures"""
    
    def __init__(self):
        self.nodes: Dict[str, SectionNode] = {}
        self.root_nodes: List[SectionNode] = []
    
    def parse_json_file(self, json_file_path: str) -> None:
        """Parse the JSON file and build the tree structure"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            extractions = data.get('extractions', [])
            # Filter relevant extraction types like the tree viewer does
            relevant_types = ['SECTION', 'NORM', 'TABLE', 'LEGAL_DOCUMENT']
            relevant_extractions = [
                ext for ext in extractions 
                if ext.get('extraction_class') in relevant_types
            ]
            
            print(f"Found {len(relevant_extractions)} relevant objects:")
            type_counts = {}
            for ext in relevant_extractions:
                ext_type = ext.get('extraction_class')
                type_counts[ext_type] = type_counts.get(ext_type, 0) + 1
            for ext_type, count in sorted(type_counts.items()):
                print(f"  {ext_type}: {count}")
            
            # Create nodes
            for extraction in relevant_extractions:
                self._create_node(extraction)
            
            # Build tree structure
            self._build_tree()
            
        except FileNotFoundError:
            print(f"Error: File {json_file_path} not found")
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
        except Exception as e:
            print(f"Error: {e}")
    
    def _create_node(self, extraction: Dict[str, Any]) -> None:
        """Create a node from extraction data (SECTION, NORM, TABLE, LEGAL_DOCUMENT)"""
        attributes = extraction.get('attributes', {})
        extraction_class = extraction.get('extraction_class', '')
        
        # Skip if no ID
        node_id = attributes.get('id')
        if not node_id:
            return
        
        # Handle different extraction types like the tree viewer
        if extraction_class == 'SECTION':
            title = attributes.get('section_title', '')
            sectioning_type = attributes.get('sectioning_type', 'Section')
            parent_id = attributes.get('parent_id')
            summary = attributes.get('section_summary', '')
            
        elif extraction_class == 'NORM':
            statement = attributes.get('norm_statement', '')
            title = statement[:100] + '...' if len(statement) > 100 else statement
            sectioning_type = 'NORM'
            parent_id = attributes.get('parent_section_id') or attributes.get('parent_id')
            summary = f"Paragraph {attributes.get('paragraph_number', 'N/A')} - {attributes.get('obligation_type', 'Unknown')}"
            
        elif extraction_class == 'TABLE':
            title = attributes.get('table_title') or extraction.get('extraction_text', '')[:50]
            sectioning_type = 'Table'
            parent_id = attributes.get('parent_section_id') or attributes.get('parent_id')
            summary = attributes.get('table_description', '')
            
        elif extraction_class == 'LEGAL_DOCUMENT':
            title = attributes.get('doc_title') or attributes.get('title', '')
            sectioning_type = 'Legal Document'
            parent_id = attributes.get('parent_id')
            summary = f"{attributes.get('doc_type', 'Document')} - {attributes.get('jurisdiction', 'Unknown jurisdiction')}"
            
        else:
            return  # Skip unsupported types
        
        node = SectionNode(
            id=node_id,
            title=title,
            sectioning_type=sectioning_type,
            parent_id=parent_id,
            parent_type=attributes.get('parent_type'),
            children=[],
            section_summary=summary,
            extraction_text=extraction.get('extraction_text', '')
        )
        
        self.nodes[node.id] = node
    
    def _build_tree(self) -> None:
        """Build the hierarchical tree structure"""
        
        # Check if we need to create a synthetic CTE.DB.SI root node
        cte_db_si_id = 'CTE.DB.SI'
        if cte_db_si_id not in self.nodes:
            # Check if any sections have CTE.DB.SI as parent_id
            has_cte_children = any(
                node.parent_id == cte_db_si_id for node in self.nodes.values()
            )
            
            if has_cte_children:
                print(f"Creating synthetic root node for {cte_db_si_id}")
                # Create synthetic root node
                synthetic_root = SectionNode(
                    id=cte_db_si_id,
                    title='CTE DB-SI - Documento Básico de Seguridad en caso de Incendio',
                    sectioning_type='Legal Document',
                    parent_id=None,
                    parent_type=None,
                    children=[],
                    section_summary='Código Técnico de la Edificación - Documento Básico de Seguridad en caso de Incendio',
                    extraction_text='Código Técnico de la Edificación - Documento Básico de Seguridad en caso de Incendio'
                )
                self.nodes[cte_db_si_id] = synthetic_root
                print(f"Added synthetic root: {cte_db_si_id}")
        
        # Find root nodes and build parent-child relationships
        for node_id, node in self.nodes.items():
            if node.parent_id is None or node.parent_id not in self.nodes:
                # Root node
                self.root_nodes.append(node)
            else:
                # Child node - add to parent
                parent_node = self.nodes[node.parent_id]
                parent_node.children.append(node)
        
        # Sort children by ID for consistent ordering
        for node in self.nodes.values():
            node.children.sort(key=lambda x: x.id)
        
        self.root_nodes.sort(key=lambda x: x.id)
    
    def print_tree(self) -> None:
        """Print the tree structure to console"""
        print("\n" + "="*80)
        print("DOCUMENT TREE STRUCTURE")
        print("="*80)
        
        for root in self.root_nodes:
            self._print_node(root, 0)
    
    def _print_node(self, node: SectionNode, indent_level: int) -> None:
        """Print a single node with proper indentation"""
        indent = "  " * indent_level
        type_indicator = f"[{node.sectioning_type}]" if node.sectioning_type else ""
        
        print(f"{indent}├─ {node.id}: {node.title} {type_indicator}")
        if node.section_summary:
            print(f"{indent}   └─ Summary: {node.section_summary}")
        
        # Print children
        for child in node.children:
            self._print_node(child, indent_level + 1)
    
    def generate_html_visualization(self, output_file: str = "section_tree_visualization.html") -> None:
        """Generate an HTML visualization of the tree"""
        html_content = self._generate_html_template()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\nHTML visualization saved to: {output_file}")
    
    def _generate_html_template(self) -> str:
        """Generate the complete HTML template with tree visualization"""
        tree_data = self._serialize_tree_for_html()
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Section Tree Visualization</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            color: #333;
            text-align: center;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        
        .tree {{
            font-family: monospace;
            line-height: 1.6;
            margin-top: 20px;
        }}
        
        .node {{
            margin: 5px 0;
            padding: 8px 12px;
            border-left: 3px solid #ddd;
            transition: all 0.3s ease;
        }}
        
        .node:hover {{
            background-color: #f0f8ff;
            border-left-color: #4CAF50;
        }}
        
        .node-id {{
            font-weight: bold;
            color: #2c5aa0;
        }}
        
        .node-title {{
            color: #333;
            margin-left: 10px;
        }}
        
        .node-type {{
            background: #e7f3ff;
            color: #1976d2;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            margin-left: 10px;
        }}
        
        .node-summary {{
            color: #666;
            font-style: italic;
            margin-left: 20px;
            font-size: 0.9em;
        }}
        
        .level-0 {{ padding-left: 0px; }}
        .level-1 {{ padding-left: 30px; }}
        .level-2 {{ padding-left: 60px; }}
        .level-3 {{ padding-left: 90px; }}
        .level-4 {{ padding-left: 120px; }}
        .level-5 {{ padding-left: 150px; }}
        
        .level-0 {{ border-left-color: #ff6b6b; }}
        .level-1 {{ border-left-color: #4ecdc4; }}
        .level-2 {{ border-left-color: #45b7d1; }}
        .level-3 {{ border-left-color: #96ceb4; }}
        .level-4 {{ border-left-color: #ffeaa7; }}
        .level-5 {{ border-left-color: #dda0dd; }}
        
        .stats {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            border: 1px solid #dee2e6;
        }}
        
        .stats h3 {{
            margin-top: 0;
            color: #495057;
        }}
        
        .toggle-btn {{
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px 5px;
            transition: background-color 0.3s;
        }}
        
        .toggle-btn:hover {{
            background: #45a049;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Section Tree Visualization</h1>
        
        <div class="stats">
            <h3>Tree Statistics</h3>
            <p><strong>Total Sections:</strong> <span id="total-sections">{len(self.nodes)}</span></p>
            <p><strong>Root Sections:</strong> <span id="root-sections">{len(self.root_nodes)}</span></p>
            <p><strong>Max Depth:</strong> <span id="max-depth">{self._calculate_max_depth()}</span></p>
        </div>
        
        <div style="text-align: center; margin: 20px 0;">
            <button class="toggle-btn" onclick="toggleSummaries()">Toggle Summaries</button>
            <button class="toggle-btn" onclick="expandAll()">Expand All</button>
            <button class="toggle-btn" onclick="collapseAll()">Collapse All</button>
        </div>
        
        <div class="tree" id="tree-container">
            {self._generate_tree_html()}
        </div>
    </div>

    <script>
        function toggleSummaries() {{
            const summaries = document.querySelectorAll('.node-summary');
            summaries.forEach(summary => {{
                summary.style.display = summary.style.display === 'none' ? 'block' : 'none';
            }});
        }}
        
        function expandAll() {{
            // Future implementation for collapsible nodes
            console.log('Expand all functionality to be implemented');
        }}
        
        function collapseAll() {{
            // Future implementation for collapsible nodes
            console.log('Collapse all functionality to be implemented');
        }}
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('Section tree visualization loaded');
        }});
    </script>
</body>
</html>"""
    
    def _generate_tree_html(self) -> str:
        """Generate HTML for the tree structure with proper node visualization"""
        html_parts = []
        
        for root in self.root_nodes:
            html_parts.append(self._generate_node_html(root, 0))
        
        return '\n'.join(html_parts)
    
    def _generate_node_html(self, node: SectionNode, level: int) -> str:
        """Generate HTML for a single node and its children with tree structure"""
        # Create collapse button if node has children
        collapse_btn = ''
        if node.children:
            collapse_btn = '<div class="collapse-btn" title="Click to expand/collapse"></div>'
        
        # Create type-specific class
        type_class = f'type-{node.sectioning_type}' if node.sectioning_type else ''
        
        # Create node type badge
        type_badge = f'<span class="node-type">{node.sectioning_type}</span>' if node.sectioning_type else ''
        
        # Create summary section
        summary = ''
        if node.section_summary:
            summary = f'<div class="node-summary">{node.section_summary}</div>'
        
        # Main node HTML
        node_html = f'''<div class="tree-node level-{level} {type_class}">
    <div class="node" data-node-id="{node.id}">
        <div class="node-content">
            <div class="node-header">
                <span class="node-id">{node.id}</span>
                <span class="node-title">{node.title}</span>
                {type_badge}
                {collapse_btn}
            </div>
            {summary}
        </div>
    </div>'''
        
        # Add children in a branch container
        if node.children:
            children_html = []
            for i, child in enumerate(node.children):
                child_html = self._generate_node_html(child, level + 1)
                children_html.append(child_html)
            
            # Add vertical line for non-last children
            branch_content = '\n'.join(children_html)
            node_html += f'\n    <div class="tree-branch">\n{branch_content}\n    </div>'
        
        node_html += '\n</div>'
        return node_html
    
    def _serialize_tree_for_html(self) -> List[Dict]:
        """Serialize tree structure for JavaScript use"""
        # For future interactive features
        return []
    
    def _calculate_max_depth(self) -> int:
        """Calculate the maximum depth of the tree"""
        max_depth = 0
        
        def calculate_depth(node: SectionNode, current_depth: int) -> int:
            nonlocal max_depth
            max_depth = max(max_depth, current_depth)
            
            for child in node.children:
                calculate_depth(child, current_depth + 1)
            
            return max_depth
        
        for root in self.root_nodes:
            calculate_depth(root, 0)
        
        return max_depth
    
    def get_tree_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the tree"""
        stats = {
            'total_sections': len(self.nodes),
            'root_sections': len(self.root_nodes),
            'max_depth': self._calculate_max_depth(),
            'sections_by_type': defaultdict(int),
            'sections_by_level': defaultdict(int)
        }
        
        # Count by type
        for node in self.nodes.values():
            if node.sectioning_type:
                stats['sections_by_type'][node.sectioning_type] += 1
        
        # Count by level
        def count_by_level(node: SectionNode, level: int):
            stats['sections_by_level'][level] += 1
            for child in node.children:
                count_by_level(child, level + 1)
        
        for root in self.root_nodes:
            count_by_level(root, 0)
        
        return stats


def main():
    """Main function to run the section tree visualizer"""
    json_file_path = r"c:\Projects\Arqio\LangExtract\langextract\output_runs\1756836143\lx output\annotated_extractions_single.json"
    
    print("Section Tree Visualizer")
    print("="*50)
    
    if not os.path.exists(json_file_path):
        print(f"Error: JSON file not found at {json_file_path}")
        return
    
    # Build the tree
    tree_builder = SectionTreeBuilder()
    tree_builder.parse_json_file(json_file_path)
    
    if not tree_builder.nodes:
        print("No relevant objects found in the JSON file")
        return
    
    # Print tree structure
    tree_builder.print_tree()
    
    # Display statistics
    stats = tree_builder.get_tree_statistics()
    print("\n" + "="*80)
    print("TREE STATISTICS")
    print("="*80)
    print(f"Total Items: {stats['total_sections']}")
    print(f"Root Items: {stats['root_sections']}")
    print(f"Maximum Depth: {stats['max_depth']}")
    print()
    
    print("Items by Type:")
    for section_type, count in sorted(stats['sections_by_type'].items()):
        print(f"  {section_type}: {count}")
    print()
    
    print("Items by Level:")
    for level, count in sorted(stats['sections_by_level'].items()):
        print(f"  Level {level}: {count}")
    
    # Generate HTML visualization
    output_file = "section_tree_visualization.html"
    tree_builder.generate_html_visualization(output_file)
    
    print(f"\n✅ Tree visualization complete!")
    print(f"📄 HTML file: {output_file}")


if __name__ == "__main__":
    main()