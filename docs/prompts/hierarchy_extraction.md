@copilot fix misparenting by using ToC parents + interval containment

Goal: Stop unmapped/mis-read headers from attaching to the previous section. Parent mapped nodes to their real ToC parent, and parent unmapped nodes by deepest mapped ToC ancestor in the page range. Keep siblings flat (no previous_level + 1 chaining).

Build ToC parent pointers + intervals
Enhance build_toc_intervals to compute id, parent_idx, start_page, end_page.

def build_toc_intervals(toc_entries: List[Dict[str, Any]], total_pages: int = 1000) -> List[Dict[str, Any]]:
if not toc_entries:
return []
import copy
entries = copy.deepcopy(toc_entries)
entries.sort(key=lambda x: (x['page'], x['level']))

# Parent via level stack
stack = []  # (idx, level)
for i, e in enumerate(entries):
    e['id'] = i
    while stack and stack[-1][1] >= e['level']:
        stack.pop()
    e['parent_idx'] = stack[-1][0] if stack else None
    stack.append((i, e['level']))

# Intervals
for i, e in enumerate(entries):
    e['start_page'] = e['page']
    end_page = total_pages
    for j in range(i + 1, len(entries)):
        if entries[j]['level'] <= e['level']:
            end_page = entries[j]['page'] - 1
            break
    e['end_page'] = max(e['start_page'], end_page)
return entries
Remember which ToC node each section matched
In multi_pass_mapping(...), when you append a mapping, also store toc_idx:

mappings.append({
'toc_entry': toc_entry,
'toc_idx': i, # <— add this
'section_header': section,
'similarity_info': sim_result,
'pass': 1 # or 2/3
})

Rework parenting to use ToC ancestry (not “previous section”)
Replace the core of page_driven_parenting with this logic:

def page_driven_parenting(mappings, toc_entries, docling_data):
import copy
updated = copy.deepcopy(docling_data)
texts = updated.get('texts', [])

# Map: ToC idx -> doc idx (for mapped headings)
toc_idx_to_doc_idx = {m['toc_idx']: m['section_header']['index'] for m in mappings}

def nearest_mapped_toc_ancestor_doc_idx(toc_idx):
    # climb ToC parents until we find a mapped ancestor
    p = toc_entries[toc_idx].get('parent_idx')
    while p is not None:
        if p in toc_idx_to_doc_idx:
            return toc_idx_to_doc_idx[p]
        p = toc_entries[p].get('parent_idx')
    return None

# 1) For mapped nodes: parent to their true ToC parent (or #/body if none)
for m in mappings:
    doc_idx = m['section_header']['index']
    toc_idx = m['toc_idx']
    parent_doc_idx = nearest_mapped_toc_ancestor_doc_idx(toc_idx)
    parent_ref = "#/body" if parent_doc_idx is None else f"#/texts/{parent_doc_idx}"
    if texts[doc_idx].get('parent', {}).get('$ref') != parent_ref:
        texts[doc_idx]['parent'] = {'$ref': parent_ref}

# Helpers for unmapped
def containing_toc_idx(page: int):
    cand = [e for e in toc_entries if e['start_page'] <= page <= e['end_page']]
    if not cand:
        return None
    return max(cand, key=lambda e: e['level'])['id']  # deepest by level

mapped_doc_indices = {m['section_header']['index'] for m in mappings}

# 2) For unmapped headers: parent to deepest mapped ancestor by interval
for i, t in enumerate(texts):
    if t.get('label') != 'section_header' or i in mapped_doc_indices:
        continue
    page = extract_docling_element_page(t)
    ci = containing_toc_idx(page) if page > 0 else None

    parent_doc_idx = None
    # climb ToC to find nearest mapped ancestor
    while ci is not None and parent_doc_idx is None:
        parent_doc_idx = toc_idx_to_doc_idx.get(ci)
        if parent_doc_idx is None:
            ci = toc_entries[ci].get('parent_idx')

    parent_ref = "#/body" if parent_doc_idx is None else f"#/texts/{parent_doc_idx}"
    if t.get('parent', {}).get('$ref') != parent_ref:
        t['parent'] = {'$ref': parent_ref}

return updated
Keep siblings flat under the computed parent (no chaining)
Kill the “previous_level + 1” fallback. Instead, after you determine the parent doc idx for an unmapped header, set level to parent_level + 1, and keep it consistent for siblings with the same numbering prefix.

Add helpers:

RE_NUM = re.compile(r'^(?P([A-Z].)?\d+(?:.\d+){0,5})\b')

def numbering_key(text: str) -> Tuple[str, int]:
# returns (prefix, depth)
t = normalize_text(text)
m = RE_NUM.match(t)
if not m:
return ("", 0)
head = m.group('head') # e.g. "E.2.3.2.1" or "11.2.3"
depth = head.count('.') + 1
prefix = head.rsplit('.', 1)[0] if '.' in head else head.split('.')[0]
return (prefix, depth)

In Step 5 of enhanced_map_toc_to_docling_sections (unmapped processing), after you compute parent_doc_idx via intervals:

parent_level = 1 if parent_doc_idx is None else texts[parent_doc_idx].get('level', 1)
prefix, depth = numbering_key(section_text)

Choose level relative to parent; keep siblings flat:
new_level = parent_level + 1
texts[section_index]['level'] = new_level
texts[section_index]['derived'] = True

Optionally store sibling-level cache:
sibling_level_cache[(parent_doc_idx, prefix)] = new_level
Result: 11.1 … 11.6 all sit under “Artículo 11” as siblings; they don’t nest into each other.

Guardrails
Never parent under “Índice”: when building/using ToC ancestry, if normalize_text(title) equals indice, treat it as having no children for parenting purposes.

Keep Anejo/Sección families separate: when climbing ToC for unmapped parenting, don’t cross family boundaries (if header contains “anejo”, don’t attach under a “sección” ancestor, and vice versa).

Acceptance checks (quick)
“Sección SI 1 …” is not a child of “Índice”.

11.1 … 11.6 are siblings under “Artículo 11”.

1.1/1.2 go under “1 Condiciones …” if mapped, else under “Sección SI 5 …”

Implement the snippets above, wire them into:

build_toc_intervals (parent pointers),

multi_pass_mapping (store toc_idx),

page_driven_parenting (replace logic),

Step 5 unmapped-level assignment (use parent-level, not previous_level + 1),

optional ensure_synthetic_parent.

Take the code snippets as a suggestion! Review them intensely and make sure to uphold coding standards as per your instructions. Modularize parts of the toc extraction script if you see fit.