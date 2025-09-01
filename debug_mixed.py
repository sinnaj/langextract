#!/usr/bin/env python3
"""Debug the mixed LaTeX+HTML case specifically."""

import json
from langextract import resolver as resolver_lib
from langextract.core import data

def debug_mixed_case():
    """Debug the problematic mixed LaTeX and HTML case step by step."""
    resolver = resolver_lib.Resolver(
        format_type=data.FormatType.JSON,
        fence_output=False
    )
    
    # The exact failing case from comprehensive test - with unescaped quotes
    mixed_json = '{"extractions": [{"math": "$\\\\pi$", "table": "<table border="1"><tr><td colspan="2">$\\\\alpha$</td></tr></table>"}]}'
    
    print("=== Mixed LaTeX + HTML Debug ===")
    print("Original JSON:")
    print(repr(mixed_json))
    print()
    
    # Try to understand what's happening during processing
    try:
        result = resolver._extract_and_parse_content(mixed_json)
        print("✓ SUCCESS: Mixed case parsed!")
        print(f"Result: {result}")
    except Exception as e:
        print(f"✗ FAILED: {e}")
        
        # Let's manually step through the sanitization process
        print("\nManual sanitization debug:")
        
        # Step 1: Show what the sanitizer function would do
        def debug_sanitize_json_string(s: str) -> str:
            print(f"Input to sanitizer: {repr(s)}")
            
            # Let's follow the same logic as the actual function
            import re
            
            def _protect_valid_unicode(m):
                return f"§§UNICODE§§{m.group(1)}"
            
            # Protect unicode
            protected = re.sub(r"\\u([0-9a-fA-F]{4})", _protect_valid_unicode, s)
            print(f"After unicode protection: {repr(protected)}")
            
            # HTML processing would happen here...
            print("HTML processing should happen here...")
            
            # LaTeX backslash processing
            out_chars = []
            in_string = False
            escaped = False
            i = 0
            L = len(protected)
            valid_escapes = set('"\\/bfnrtu')
            
            while i < L:
                ch = protected[i]
                if ch == '"' and not escaped:
                    in_string = not in_string
                    out_chars.append(ch)
                    i += 1
                    continue

                if in_string:
                    if ch == '\\' and not escaped:
                        if i + 1 < L:
                            nxt = protected[i + 1]
                            if nxt in valid_escapes:
                                if nxt == 'u':
                                    hex_ok = (
                                        i + 6 <= L
                                        and re.match(r"^[0-9a-fA-F]{4}$", protected[i + 2 : i + 6] or "") is not None
                                    )
                                    if not hex_ok:
                                        out_chars.append('\\\\u')
                                        i += 2
                                        continue
                                out_chars.append('\\')
                                i += 1
                                continue
                            else:
                                # This should double backslashes like \p in \pi  
                                out_chars.append('\\\\')
                                i += 1
                                continue
                        else:
                            out_chars.append('\\\\')
                            i += 1
                            continue

                    out_chars.append(ch)
                    escaped = (ch == '\\') and not escaped
                    i += 1
                    continue

                out_chars.append(ch)
                escaped = False
                i += 1

            protected = "".join(out_chars)
            print(f"After backslash processing: {repr(protected)}")
            
            return protected
            
        try:
            sanitized = debug_sanitize_json_string(mixed_json)
            print(f"\nFinal sanitized: {repr(sanitized)}")
            
            # Try to parse it
            parsed = json.loads(sanitized)
            print("✓ Manually sanitized version works!")
        except Exception as e2:
            print(f"✗ Manual sanitization also failed: {e2}")

if __name__ == "__main__":
    debug_mixed_case()