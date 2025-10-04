"""DNF (Disjunctive Normal Form) helper functions.

This module provides utilities for working with DNF representations:
- Optimization (removing contradictions, deduplication)
- Validation
"""

from typing import Dict, Set

from ingest.types import Atomic, Conjunct, DNF


def is_contradiction(conjunct: Conjunct) -> bool:
    """Check if a conjunct contains contradictory atomics.
    
    A conjunct is contradictory if it requires the same key to have
    different values with EQ operators, or contains A == TRUE and A == FALSE.
    
    Args:
        conjunct: List of atomic predicates in a conjunction
        
    Returns:
        True if the conjunct is contradictory (unsatisfiable)
    """
    # Track equality constraints for each key
    eq_constraints: Dict[str, Set] = {}
    
    for atomic in conjunct:
        if atomic.op.value == "EQ":
            key = atomic.key
            value = atomic.value
            
            # Convert value to hashable type for set storage
            if isinstance(value, list):
                value = tuple(value)
            elif isinstance(value, dict):
                # For dicts, use frozenset of items
                value = frozenset(value.items())
            
            if key in eq_constraints:
                # Check if we already have a different value for this key
                if value not in eq_constraints[key]:
                    # Same key, different values -> contradiction
                    return True
                # Same key, same value -> redundant but not contradictory
            else:
                eq_constraints[key] = {value}
    
    return False


def deduplicate_atomics(conjunct: Conjunct) -> Conjunct:
    """Remove duplicate atomic predicates from a conjunct.
    
    Args:
        conjunct: List of atomic predicates
        
    Returns:
        Conjunct with duplicates removed
    """
    seen = set()
    result = []
    
    for atomic in conjunct:
        # Create a hashable representation
        value = atomic.value
        if isinstance(value, list):
            value = tuple(value)
        elif isinstance(value, dict):
            value = frozenset(value.items())
        
        key = (atomic.key, atomic.op.value, value)
        
        if key not in seen:
            seen.add(key)
            result.append(atomic)
    
    return result


def optimize_dnf(dnf: DNF) -> DNF:
    """Optimize a DNF by removing contradictions and duplicates.
    
    Args:
        dnf: DNF representation to optimize
        
    Returns:
        Optimized DNF
    """
    optimized = []
    
    for conjunct in dnf:
        # Remove duplicates within the conjunct
        deduped = deduplicate_atomics(conjunct)
        
        # Check for contradictions
        if not is_contradiction(deduped):
            optimized.append(deduped)
    
    return optimized


def dnf_to_string(dnf: DNF) -> str:
    """Convert DNF to a human-readable string.
    
    Useful for debugging and logging.
    
    Args:
        dnf: DNF representation
        
    Returns:
        String representation in the form "(A && B) || (C && D)"
    """
    if not dnf:
        return "FALSE"
    
    if len(dnf) == 1 and len(dnf[0]) == 0:
        return "TRUE"
    
    conjunct_strs = []
    for conjunct in dnf:
        if not conjunct:
            conjunct_strs.append("TRUE")
        else:
            atomic_strs = []
            for atomic in conjunct:
                value_str = str(atomic.value)
                if isinstance(atomic.value, str):
                    value_str = f"'{atomic.value}'"
                elif isinstance(atomic.value, list):
                    value_str = str(atomic.value)
                
                op_str = {
                    "EQ": "==",
                    "NEQ": "!=",
                    "GT": ">",
                    "GTE": ">=",
                    "LT": "<",
                    "LTE": "<=",
                    "IN": "IN",
                    "NOT_IN": "NOT IN",
                }.get(atomic.op.value, atomic.op.value)
                
                atomic_strs.append(f"{atomic.key} {op_str} {value_str}")
            
            conjunct_strs.append(" && ".join(atomic_strs))
    
    if len(conjunct_strs) == 1:
        return conjunct_strs[0]
    else:
        return " || ".join(f"({c})" for c in conjunct_strs)
