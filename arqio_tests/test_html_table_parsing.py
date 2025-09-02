#!/usr/bin/env python3
"""
Test script to verify if the current JSON parsing implementation can handle 
complex HTML tables with unescaped quotes in attributes like colspan="4".

This test specifically targets the problematic pattern from the DBSI document.
"""

import json
import logging
import sys
from pathlib import Path

# Add the current directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from langextract import data
from langextract.resolver import Resolver, ResolverParsingError

# Configure logging to see debug output
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def test_html_table_parsing():
    """Test if the resolver can handle the complex HTML table from the user's example."""
    
    # The problematic HTML table content from the user's selection
    html_table_content = '''<table><tr><td rowspan="3">Elemento</td><td colspan="4">Resistencia al fuego</td></tr><tr><td rowspan="2">Plantas bajo rasante</td><td colspan="3">Plantas sobre rasante en edificio con altura de eva-cuación:</td></tr><tr><td>h ≤ 15 m</td><td>15 ≤ h ≤ 28 m</td><td>h &gt; 28 m</td></tr><tr><td>Paredes y techos(3) que separan al sector considerado del resto del edificio, sides to use provide(4)</td><td></td><td></td><td></td><td></td></tr><tr><td>- Sector de riesgo mínimo en edificio de cualquier uso</td><td>(no se admitte)</td><td>EI 120</td><td>EI 120</td><td>EI 120</td></tr><tr><td>- Residencial Vivienda, Residen-cial Público, Docente, Adminis-trativo</td><td>EI 120</td><td>EI 60</td><td>EI 90</td><td>EI 120</td></tr><tr><td>- Comercial, Pública concurren-cia, Hospitalario</td><td>EI 120(5)</td><td>EI 90</td><td>EI 120</td><td>EI 180</td></tr><tr><td>- Aparcamiento(6)</td><td>EI 120(7)</td><td>EI 120</td><td>EI 120</td><td>EI 120</td></tr><tr><td>Puertas de paso entre sectores de incendio</td><td colspan="4">EI2 t-C5 siendo t la mitad del tiempo de resistencia al fuego requerido a la pared en la que se encuentre, o bien la cuarta parte cuando el paso se reali-ce a través de un vestibulo de independencia y de dos puertas.</td></tr></table>'''
    
    # Create a mock LLM output that contains this HTML table in JSON format
    # This simulates what an LLM might generate when asked to extract information from the document
    mock_llm_output = f'''```json
{{
  "extractions": [
    {{
      "table_content": "{html_table_content}",
      "table_content_index": 1,
      "table_type": "fire_resistance_requirements",
      "table_type_index": 2
    }}
  ]
}}
```'''

    print("=== Testing HTML Table Parsing with Resolver ===")
    print(f"Input length: {len(mock_llm_output)} characters")
    print("Problematic patterns in content:")
    print("  - colspan=\"4\"")
    print("  - rowspan=\"3\"") 
    print("  - rowspan=\"2\"")
    print("  - Multiple unescaped quotes in HTML attributes")
    print()

    # Initialize the resolver with JSON format and fenced output
    resolver = Resolver(
        fence_output=True,
        format_type=data.FormatType.JSON,
        suppress_parse_errors_default=False
    )

    try:
        print("Attempting to parse with resolver...")
        extractions = resolver.resolve(mock_llm_output)
        
        print(f"✅ SUCCESS: Parsed {len(extractions)} extractions!")
        
        for i, extraction in enumerate(extractions):
            print(f"  Extraction {i+1}:")
            print(f"    Class: {extraction.extraction_class}")
            print(f"    Index: {extraction.extraction_index}")
            print(f"    Text length: {len(extraction.extraction_text)} chars")
            print(f"    Text preview: {extraction.extraction_text[:100]}...")
            print()
            
        return True
        
    except ResolverParsingError as e:
        print(f"❌ PARSING ERROR: {e}")
        print("The resolver failed to parse the HTML table content.")
        
        # Let's also try to test the sanitization directly
        print("\n=== Testing Direct JSON Parsing ===")
        try:
            # Extract just the JSON content
            start_marker = "```json"
            end_marker = "```"
            start_idx = mock_llm_output.find(start_marker) + len(start_marker)
            end_idx = mock_llm_output.rfind(end_marker)
            json_content = mock_llm_output[start_idx:end_idx].strip()
            
            print("Attempting direct JSON parsing...")
            parsed = json.loads(json_content)
            print("✅ Direct JSON parsing succeeded!")
            return True
            
        except json.JSONDecodeError as je:
            print(f"❌ Direct JSON parsing also failed: {je}")
            
            # Show the specific location of the error
            if hasattr(je, 'pos'):
                error_pos = je.pos
                context_start = max(0, error_pos - 50)
                context_end = min(len(json_content), error_pos + 50)
                context = json_content[context_start:context_end]
                print(f"Error context around position {error_pos}:")
                print(f"'{context}'")
            
        return False
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        return False

def test_simple_html_attributes():
    """Test with simpler HTML attribute patterns to isolate the issue."""
    
    print("\n=== Testing Simple HTML Attribute Patterns ===")
    
    # Test cases with progressively complex HTML patterns
    test_cases = [
        {
            "name": "Simple colspan",
            "content": '<td colspan="2">Simple cell</td>'
        },
        {
            "name": "Multiple attributes", 
            "content": '<td colspan="4" rowspan="2">Complex cell</td>'
        },
        {
            "name": "Nested quotes",
            "content": '<td title="This has "quoted" text">Cell content</td>'
        },
        {
            "name": "Mixed attributes",
            "content": '<table><tr><td colspan="4">Header</td></tr><tr><td>A</td><td>B</td><td>C</td><td>D</td></tr></table>'
        }
    ]
    
    resolver = Resolver(
        fence_output=True,
        format_type=data.FormatType.JSON,
        suppress_parse_errors_default=False
    )
    
    results = []
    
    for test_case in test_cases:
        print(f"\nTesting: {test_case['name']}")
        print(f"Content: {test_case['content']}")
        
        # Create mock JSON with this HTML content
        mock_output = f'''```json
{{
  "extractions": [
    {{
      "html_content": "{test_case['content']}",
      "html_content_index": 1
    }}
  ]
}}
```'''
        
        try:
            extractions = resolver.resolve(mock_output)
            print("✅ SUCCESS")
            results.append({"name": test_case['name'], "success": True})
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            results.append({"name": test_case['name'], "success": False, "error": str(e)})
    
    print(f"\n=== Simple HTML Test Results ===")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['name']}")
        if not result['success']:
            print(f"    Error: {result.get('error', 'Unknown')}")
    
    return results

if __name__ == "__main__":
    print("Testing HTML table parsing capabilities of the current resolver implementation.")
    print("=" * 80)
    
    # Test the main complex HTML table
    main_success = test_html_table_parsing()
    
    # Test simpler patterns to isolate issues
    simple_results = test_simple_html_attributes()
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(f"Complex HTML table parsing: {'✅ PASS' if main_success else '❌ FAIL'}")
    
    simple_success_count = sum(1 for r in simple_results if r['success'])
    simple_total = len(simple_results)
    print(f"Simple HTML patterns: {simple_success_count}/{simple_total} passed")
    
    if not main_success:
        print("\n🔧 RECOMMENDATION:")
        print("The current implementation may need additional HTML sanitization")
        print("strategies to handle complex HTML tables with multiple attributes.")
        print("Consider enhancing the _sanitize_json_string function with more")
        print("comprehensive HTML attribute escaping patterns.")