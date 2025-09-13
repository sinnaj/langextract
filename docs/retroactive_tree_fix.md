# Retroactive Tree View Fix Documentation

## Problem

If you ran enhanced extractions before the tree hierarchy fix was implemented, your output files may not display properly in the tree view. The sections will appear flat instead of showing nested hierarchical structure.

## Solution

Use the `retroactive_tree_fix.py` script to update existing extraction results with proper parent-child relationships.

## Usage

### Fix a Single Output Run

```bash
# Fix a specific extraction results file
python retroactive_tree_fix.py output_runs/1234567890/enhanced_output/enhanced_extraction_results.json

# Or fix an entire output run directory (will find and fix all results files)
python retroactive_tree_fix.py output_runs/1234567890/
```

### Fix Multiple Output Runs

```bash
# Fix all extraction results in all output runs
python retroactive_tree_fix.py output_runs/
```

## What the Script Does

1. **Reads** existing `enhanced_extraction_results.json` files
2. **Analyzes** section hierarchy based on `section_level` and `toc_path` 
3. **Adds** missing `parent_section_id` fields to establish parent-child relationships
4. **Regenerates** the `node_tree.json` with proper hierarchical structure
5. **Creates** backup of original files (`.json.backup`)

## Before and After

### Before (Flat Tree)
```
📁 Document Root
  📁 I Objeto
  📁 II Ámbito de aplicación  
  📁 Sección SI 1 Propagación interior
  📁 1 Compartimentación en sectores de incendio
  📁 2 Locales y zonas de riesgo especial
```

### After (Hierarchical Tree)
```
📁 Document Root
  📁 I Objeto
  📁 II Ámbito de aplicación
  📁 Sección SI 1 Propagación interior
    📁 1 Compartimentación en sectores de incendio
    📁 2 Locales y zonas de riesgo especial
```

## Safety Features

- **Automatic Backup**: Original files are backed up as `.json.backup`
- **Idempotent**: Safe to run multiple times on the same files
- **Non-destructive**: Only adds missing fields, doesn't remove existing data

## Files Modified

The script updates these files in your output directory:
- `enhanced_extraction_results.json` - Adds `parent_section_id` to sections
- `node_tree.json` - Regenerated with proper hierarchy

## Requirements

The script needs your existing extraction results to have:
- Section metadata with `section_level` field
- Properly ordered sections (parents before children)
- Valid section identifiers

Most enhanced extraction outputs from langextract should meet these requirements.