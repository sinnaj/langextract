#!/usr/bin/env python
"""
Demonstration script for the norm ingestion pipeline.

This script demonstrates the DNF conversion and storage structure
without requiring a live database connection.
"""

import json
from ingest import expr_to_dnf, dnf_to_string, optimize_dnf


def main():
    """Demonstrate the ingestion pipeline."""
    print("=" * 80)
    print("NORM INGESTION PIPELINE DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Load sample norms
    print("📄 Loading sample_norms.json...")
    with open('sample_norms.json', 'r') as f:
        norms = json.load(f)
    print(f"   Loaded {len(norms)} norms\n")
    
    # Process each norm
    for i, norm in enumerate(norms, 1):
        attrs = norm['attributes']
        
        print(f"🔍 Norm {i}: {attrs['id']}")
        print(f"   Obligation: {attrs.get('obligation_type', 'N/A')}")
        print(f"   Topics: {', '.join(attrs.get('topics', []))}")
        print()
        
        # Process applies_if
        applies_if = attrs.get('applies_if')
        if applies_if and applies_if.upper() not in ['TRUE', 'FALSE']:
            print(f"   📝 Original applies_if:")
            print(f"      {applies_if}")
            print()
            
            # Convert to DNF
            dnf = expr_to_dnf(applies_if)
            dnf = optimize_dnf(dnf)
            
            print(f"   🔄 Converted to DNF:")
            print(f"      {dnf_to_string(dnf)}")
            print()
            
            print(f"   📊 Storage Structure:")
            print(f"      - Number of clause_groups (disjuncts): {len(dnf)}")
            
            total_requirements = sum(len(conjunct) for conjunct in dnf)
            print(f"      - Total requirements (atomics): {total_requirements}")
            print()
            
            print(f"   🗂️ Detailed Breakdown:")
            for j, conjunct in enumerate(dnf, 1):
                print(f"      Clause Group {j} (logic='AND'):")
                for atomic in conjunct:
                    value_str = str(atomic.value)
                    if isinstance(atomic.value, str):
                        value_str = f"'{atomic.value}'"
                    elif isinstance(atomic.value, list):
                        value_str = str(atomic.value)
                    
                    print(f"         • Question: {atomic.key}")
                    print(f"           Operator: {atomic.op.value}")
                    print(f"           Expected: {value_str} ({atomic.value_type.value})")
            print()
        
        # Process satisfied_if
        satisfied_if = attrs.get('satisfied_if')
        if satisfied_if and satisfied_if.upper() not in ['TRUE', 'FALSE']:
            print(f"   ✅ Satisfied_if:")
            print(f"      {satisfied_if}")
            dnf = expr_to_dnf(satisfied_if)
            dnf = optimize_dnf(dnf)
            print(f"      → {len(dnf)} disjunct(s), {sum(len(c) for c in dnf)} requirement(s)")
            print()
        
        print("-" * 80)
        print()
    
    print("=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print()
    print("To ingest into PostgreSQL:")
    print("  python -m ingest.ingest \\")
    print("    --dsn postgresql://user:pass@localhost:5432/mydb \\")
    print("    --json ./sample_norms.json \\")
    print("    --document-title 'Sample Document' \\")
    print("    --language 'en' \\")
    print("    --jurisdiction 'US'")
    print()


if __name__ == "__main__":
    main()
