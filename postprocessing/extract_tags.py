"""
Tag extraction module for LangExtract.

This module handles the extraction and processing of tags from NORM entities
in the LangExtract post-processing pipeline.
"""

from typing import Any, Dict, List


def extract_tags_from_norms(
    norms_to_process: List[Dict[str, Any]], 
    tag_counter_start: int = 1
) -> List[Dict[str, Any]]:
    """
    Extract tags from NORM entities and create Tag extraction items.
    
    Args:
        norms_to_process: List of norm attribute dictionaries
        tag_counter_start: Starting counter for tag IDs
        
    Returns:
        List of Tag extraction dictionaries
    """
    # Build map to avoid duplicates and aggregate used_by_norm_ids
    tag_map: Dict[str, Dict[str, Any]] = {}
    tag_counter = tag_counter_start

    def _next_tid() -> str:
        nonlocal tag_counter
        tid = f"T::{tag_counter:06d}"
        tag_counter += 1
        return tid

    # Process norms for tags
    for norm_data in norms_to_process:
        if not isinstance(norm_data, dict):
            continue
            
        norm_id = norm_data.get("id")
        if not norm_id:
            continue
        
        topics = norm_data.get("topics")
        if topics is None:
            topics = []
        elif not isinstance(topics, list):
            topics = []

        # Relevant tags - ensure it's a list
        relevant_tags = norm_data.get("relevant_tags")
        if relevant_tags is None:
            relevant_tags = []
        elif not isinstance(relevant_tags, list):
            relevant_tags = []
        
        for tag_path in relevant_tags:
            if not isinstance(tag_path, str):
                continue
                
            if tag_path not in tag_map:
                tag_map[tag_path] = {
                    "extraction_class": "Tag",
                    "extraction_text": tag_path,
                    "attributes": {
                        "id": _next_tid(),
                        "tag": tag_path,
                        "used_by_norm_ids": [norm_id],
                        "related_topics": topics,
                    },
                }
            else:
                # Aggregate used_by_norm_ids for existing tag
                u = tag_map[tag_path]["attributes"].setdefault("used_by_norm_ids", [])
                if u is None:
                    u = []
                    tag_map[tag_path]["attributes"]["used_by_norm_ids"] = u
                if norm_id not in u:
                    u.append(norm_id)

    # Return list of tag dictionaries
    return list(tag_map.values())
