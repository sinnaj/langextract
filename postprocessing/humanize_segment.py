def humanize_segment(seg: str) -> str:
    seg_clean = seg.replace('_',' ').lower()
    return seg_clean