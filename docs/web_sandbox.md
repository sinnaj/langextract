# Web Sandbox Documentation

## Overview

The **Sandbox** page (`/sandbox`) is an interactive web interface for exploring and filtering extracted building code norms. It allows users to dynamically filter norms based on feature values using tri-state logic, providing real-time insights into which norms apply under different conditions.

**Key Purpose**: Enable users to:
- Browse extracted norms from completed pipeline runs
- Apply feature-based filters to see which norms are applicable
- Understand how specific building characteristics affect norm applicability
- Identify which norms are filtered out by specific conditions

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (Frontend)                      │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Norm Cards   │  │ Filter Panel│  │ State Management │  │
│  │ Display      │  │ (Features)  │  │ & API Calls      │  │
│  └──────────────┘  └─────────────┘  └──────────────────┘  │
└─────────────────────────┬───────────────────────────────────┘
                          │ AJAX Requests (JSON)
┌─────────────────────────▼───────────────────────────────────┐
│                    Flask Backend (app.py)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │ API Endpoints│  │ JSON Loading │  │ DSL Evaluation   │ │
│  │ /sandbox     │  │ from Files   │  │ (Tri-state)      │ │
│  └──────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Data Layer (Filesystem)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ output_runs/{run_id}/enhanced_output/                  │ │
│  │   └── enhanced_extraction_results.json                 │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ig_assessment/tmp/ig_results.csv                       │ │
│  │   (Feature definitions with IG scores)                 │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Frontend**: Vanilla JavaScript, Tailwind CSS (CDN), HTML5
- **Backend**: Flask (Python), Python 3.10+
- **DSL Evaluation**: Lark parser + Kleene tri-state logic (from `ig_assessment/`)
- **Data Format**: JSON (enhanced extraction results)
- **Feature Definitions**: CSV (Information Gain results)

## Data Flow: Input to Output

### 1. **Input Phase: Loading Available Runs**

**Endpoint**: `GET /api/sandbox/outputs`

**Purpose**: List all available pipeline runs that have enhanced extraction results.

**Implementation** (`web/app.py:1196-1214`):
```python
@app.get("/api/sandbox/outputs")
def list_sandbox_outputs():
    """List available output directories with timestamps."""
    outputs = []
    if OUTPUT_ROOT.exists():
        for d in OUTPUT_ROOT.iterdir():
            if d.is_dir():
                run_id = d.name
                enhanced_output_dir = d / "enhanced_output"
                extraction_file = enhanced_output_dir / "enhanced_extraction_results.json"
                if extraction_file.exists():
                    ts = d.stat().st_mtime
                    outputs.append({"run_id": run_id, "timestamp": ts})
    outputs.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify({"outputs": outputs})
```

**Process**:
1. Scans `output_runs/` directory for subdirectories
2. For each directory, checks if `enhanced_output/enhanced_extraction_results.json` exists
3. Collects `run_id` and file modification timestamp
4. Returns sorted list (latest first)

**Response Example**:
```json
{
  "outputs": [
    {
      "run_id": "1757864159",
      "timestamp": 1704987654.321
    },
    {
      "run_id": "1757850000",
      "timestamp": 1704900000.000
    }
  ]
}
```

**Frontend Handling** (`sandbox.html:134-164`):
- Populates dropdown selector with available runs
- Displays timestamp in human-readable format
- Automatically selects latest run
- Triggers norm loading for selected run

---

### 2. **Loading Feature Definitions**

**Endpoint**: `GET /api/sandbox/features`

**Purpose**: Load feature metadata from Information Gain (IG) assessment results to build filter UI.

**Implementation** (`web/app.py:1242-1313`):
```python
@app.get("/api/sandbox/features")
def get_sandbox_features():
    """Get feature definitions from ig_results.csv."""
    ig_csv_path = REPO_ROOT / "ig_assessment" / "tmp" / "ig_results.csv"
    
    features = []
    with open(ig_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        # Sort by avg_dismissal_rate descending
        rows.sort(key=lambda r: float(r.get('avg_dismissal_rate', '0.0')), reverse=True)
        
        for row in rows:
            feature_name = row.get('feature', '')
            numeric = row.get('numeric', 'False').lower() == 'true'
            categories_or_bins = row.get('categories_or_bins', '[]')
            max_dismissal_rate = row.get('max_dismissal_rate', '0.0')
            
            # Format display name with max_dismissal_rate
            display_name = f"{feature_name} ({max_dismissal_float:.2f})"
            
            # Parse categories_or_bins
            values = []
            feature_type = 'categorical'
            
            if categories_or_bins and categories_or_bins != '[]':
                parsed = ast.literal_eval(categories_or_bins)
                if isinstance(parsed, list):
                    if numeric and parsed:
                        feature_type = 'bin'
                        values = [str(b) for b in parsed]
                    else:
                        feature_type = 'categorical'
                        values = parsed
            
            if numeric and not values:
                feature_type = 'int'
            
            features.append({
                'name': feature_name,
                'display_name': display_name,
                'type': feature_type,
                'values': values,
                'numeric': numeric
            })
    
    return jsonify({"features": features, "total": len(features)})
```

**Feature Types**:

1. **Categorical Features** (`type: 'categorical'`):
   - Discrete, non-numeric values
   - Example: `BUILDING.USAGE = ['RESIDENTIAL.HOUSING', 'COMMERCIAL', 'PARKING']`
   - UI: Dropdown with "-- Any --" option

2. **Bin Features** (`type: 'bin'`):
   - Numeric ranges derived from threshold values
   - Example: `AREA.SIZE = ['(-inf, 100.0]', '(100.0, 500.0]', '(500.0, inf)']`
   - UI: Dropdown with bin range strings

3. **Integer Features** (`type: 'int'`):
   - Numeric features without predefined bins
   - Example: `FLOOR.COUNT`
   - UI: Number input field

**Sorting**: Features are sorted by **dismissal rate** (descending), which measures how many norms each feature filters out. This prioritizes the most impactful filters at the top of the panel.

**Response Example**:
```json
{
  "features": [
    {
      "name": "BUILDING.USAGE",
      "display_name": "BUILDING.USAGE (0.67)",
      "type": "categorical",
      "values": ["RESIDENTIAL.HOUSING", "COMMERCIAL", "PARKING", "STORAGE", "PUBLIC.ASSEMBLY"],
      "numeric": false
    },
    {
      "name": "AREA.SIZE",
      "display_name": "AREA.SIZE (0.33)",
      "type": "bin",
      "values": ["(-inf, 100.0]", "(100.0, 500.0]", "(500.0, inf)"],
      "numeric": true
    },
    {
      "name": "FLOOR.COUNT",
      "display_name": "FLOOR.COUNT (0.10)",
      "type": "int",
      "values": [],
      "numeric": true
    }
  ],
  "total": 3
}
```

**Frontend Handling** (`sandbox.html:167-184`):
- Stores features in global state
- Calls `renderFilters()` to generate filter UI

---

### 3. **Loading Norms Data**

**Endpoint**: `GET /api/sandbox/norms/<run_id>`

**Purpose**: Load all norms from a specific pipeline run.

**Implementation** (`web/app.py:1217-1239`):
```python
@app.get("/api/sandbox/norms/<run_id>")
def get_sandbox_norms(run_id: str):
    """Get all norms from an output run."""
    run_dir = OUTPUT_ROOT / run_id
    enhanced_output_dir = run_dir / "enhanced_output"
    extraction_file = enhanced_output_dir / "enhanced_extraction_results.json"
    
    data = json.loads(extraction_file.read_text(encoding="utf-8"))
    
    # Extract only NORM extractions
    norms = [
        e for e in data.get("extractions", [])
        if e.get("extraction_class") == "NORM"
    ]
    
    return jsonify({"norms": norms, "total": len(norms)})
```

**Data Structure** (from `enhanced_extraction_results.json`):
```json
{
  "pipeline_info": {
    "version": "2.0",
    "method": "enhanced_docling_toc_based_extraction",
    "total_extractions": 1163
  },
  "sections": [
    {
      "section_id": "fa09c7d5c06b6313",
      "section_name": "I Objeto",
      "toc_path": ["Introducción", "I Objeto"]
    }
  ],
  "extractions": [
    {
      "extraction_class": "NORM",
      "attributes": {
        "id": "N::0001",
        "norm_statement": "Las puertas de salida tendrán una anchura mínima de 0,80 m",
        "applies_if": "DOOR.TYPE == 'EXIT' AND BUILDING.USAGE IN ['RESIDENTIAL.HOUSING', 'COMMERCIAL']",
        "satisfied_if": "DOOR.WIDTH >= 0.80",
        "obligation_type": "MANDATORY",
        "priority": 3,
        "confidence": 0.95,
        "topics": ["SI3", "Evacuación", "Puertas"],
        "location_scope": {
          "COUNTRY": "ES",
          "REGION": "national"
        }
      }
    }
  ]
}
```

**Key Norm Fields**:
- `id`: Unique norm identifier (e.g., `"N::0001"`)
- `norm_statement`: Human-readable regulatory text
- `applies_if`: **DSL predicate** determining when this norm is applicable
- `satisfied_if`: DSL predicate for compliance (not used in filtering)
- `obligation_type`: `MANDATORY`, `OPTIONAL`, `PROHIBITION`, etc.
- `priority`: Importance ranking (1-5)
- `confidence`: Extraction quality score (0.0-1.0)
- `topics`: Tags/categories for organization
- `location_scope`: Geographic applicability

**Frontend Handling** (`sandbox.html:187-207`):
- Stores norms in `allNorms` global array
- Initially displays all norms (no filters)
- Renders norm cards in the main content area

---

### 4. **Filter Application: The Core Logic**

This is the heart of the Sandbox functionality. There are two filtering stages:

#### Stage 1: `applies_if` Base Filter (Client-Side)

**Purpose**: Pre-filter norms by their `applies_if` literal value.

**UI Control** (`sandbox.html:216-247`):
```javascript
// Special dropdown with 3 options:
// - "All": Show all norms (no filtering)
// - "TRUE": Show only norms with applies_if = "TRUE"
// - "!TRUE": Show only norms with applies_if != "TRUE"
```

**Implementation** (`sandbox.html:350-385`):
```javascript
function applyFiltersClientSide() {
  let result = allNorms;
  
  // Apply applies_if filter
  if (appliesIfFilter === 'true') {
    result = result.filter(norm => {
      const appliesIf = norm.attributes?.applies_if || 'TRUE';
      return appliesIf.trim().toUpperCase() === 'TRUE';
    });
  } else if (appliesIfFilter === 'not-true') {
    result = result.filter(norm => {
      const appliesIf = norm.attributes?.applies_if || 'TRUE';
      return appliesIf.trim().toUpperCase() !== 'TRUE';
    });
  }
  
  baseNormsAfterAppliesIf = result;
  
  // If no feature filters, we're done
  if (Object.keys(currentFilters).length === 0) {
    filteredNorms = result;
    filteredOutNorms = [];
    renderNorms();
    updateCounter();
    return;
  }
  
  // Otherwise, call API for tri-state evaluation
  applyFiltersViaAPI(result);
}
```

**Rationale**: Norms with `applies_if = "TRUE"` are universally applicable (no conditions). Users can quickly separate these from conditionally applicable norms.

#### Stage 2: Feature-Based Tri-State Filtering (API)

**Endpoint**: `POST /api/sandbox/filter`

**Purpose**: Evaluate complex `applies_if` predicates using tri-state logic to determine which norms remain applicable given partial feature assignments.

**Request Format**:
```json
{
  "run_id": "1757864159",
  "filters": {
    "BUILDING.USAGE": "RESIDENTIAL.HOUSING",
    "AREA.SIZE": "(100.0, 500.0]"
  },
  "norm_ids": ["N::0001", "N::0002", "N::0003"]
}
```

**Implementation** (`web/app.py:1316-1415`):
```python
@app.post("/api/sandbox/filter")
def filter_sandbox_norms():
    """Filter norms based on current filter selections using tri-state logic."""
    data = request.get_json()
    run_id = data.get('run_id')
    filters = data.get('filters', {})
    norm_ids = data.get('norm_ids')
    
    # Load norms from file
    result_data = json.loads(extraction_file.read_text(encoding="utf-8"))
    all_norms = [
        e for e in result_data.get("extractions", [])
        if e.get("extraction_class") == "NORM"
    ]
    
    # Filter to specific norm_ids if provided (optimization)
    norms = all_norms
    if norm_ids:
        norm_ids_set = set(norm_ids)
        norms = [n for n in all_norms if n.get('attributes', {}).get('id') in norm_ids_set]
    
    # Import tri-state evaluator
    from dsl_parser import parse_applies_if
    from evaluator import Evaluator, TristateValue
    
    # Build partial assignment from filters
    assignment = {}
    for feature_name, value in filters.items():
        assignment[feature_name] = value
    
    # Evaluate each norm
    filtered_norms = []
    for norm in norms:
        applies_if_str = norm.get('attributes', {}).get('applies_if', 'TRUE')
        
        # Parse DSL expression
        ast = parse_applies_if(applies_if_str)
        
        # Evaluate with partial assignment using Kleene logic
        evaluator = Evaluator(assignment)
        result = evaluator.evaluate(ast)
        
        # Keep norm if TRUE or UNKNOWN, exclude if FALSE
        if result != TristateValue.FALSE:
            filtered_norms.append(norm)
    
    return jsonify({
        "norms": filtered_norms,
        "total": len(filtered_norms),
        "original_total": len(norms)
    })
```

**DSL Evaluation Process**:

1. **Parse**: Convert `applies_if` string into Abstract Syntax Tree (AST)
   - Example: `"BUILDING.USAGE == 'RESIDENTIAL.HOUSING' AND AREA.SIZE > 100.0"`
   - Becomes: `AND(EQ(Identifier(BUILDING.USAGE), Literal('RESIDENTIAL.HOUSING')), GT(Identifier(AREA.SIZE), Literal(100.0)))`

2. **Evaluate**: Walk AST with tri-state evaluator
   - Features in `assignment`: Use their assigned values
   - Features NOT in `assignment`: Evaluate as `UNKNOWN`

3. **Tri-State Logic** (Kleene Logic):
   ```
   TRUE  AND TRUE    → TRUE
   TRUE  AND FALSE   → FALSE
   TRUE  AND UNKNOWN → UNKNOWN
   FALSE AND <any>   → FALSE
   
   TRUE  OR <any>    → TRUE
   FALSE OR FALSE    → FALSE
   FALSE OR UNKNOWN  → UNKNOWN
   
   NOT TRUE          → FALSE
   NOT FALSE         → TRUE
   NOT UNKNOWN       → UNKNOWN
   ```

4. **Filter Decision**:
   - `TRUE`: Norm definitely applies → **KEEP**
   - `UNKNOWN`: Norm might apply (insufficient information) → **KEEP**
   - `FALSE`: Norm definitely does NOT apply → **EXCLUDE**

**Example Evaluation**:

Given norm: `applies_if = "DOOR.TYPE == 'EXIT' AND BUILDING.USAGE == 'RESIDENTIAL.HOUSING'"`

| User Filters | Evaluation | Result |
|--------------|------------|--------|
| `{}` (none) | `UNKNOWN AND UNKNOWN → UNKNOWN` | **KEEP** (might apply) |
| `{DOOR.TYPE: 'EXIT'}` | `TRUE AND UNKNOWN → UNKNOWN` | **KEEP** (might apply) |
| `{DOOR.TYPE: 'INTERIOR'}` | `FALSE AND UNKNOWN → FALSE` | **EXCLUDE** (doesn't apply) |
| `{DOOR.TYPE: 'EXIT', BUILDING.USAGE: 'RESIDENTIAL.HOUSING'}` | `TRUE AND TRUE → TRUE` | **KEEP** (definitely applies) |
| `{DOOR.TYPE: 'EXIT', BUILDING.USAGE: 'COMMERCIAL'}` | `TRUE AND FALSE → FALSE` | **EXCLUDE** (doesn't apply) |

**Response Example**:
```json
{
  "norms": [
    {
      "extraction_class": "NORM",
      "attributes": {
        "id": "N::0001",
        "norm_statement": "Las puertas de salida tendrán una anchura mínima de 0,80 m",
        "applies_if": "DOOR.TYPE == 'EXIT' AND BUILDING.USAGE == 'RESIDENTIAL.HOUSING'"
      }
    }
  ],
  "total": 1,
  "original_total": 5
}
```

**Frontend Handling** (`sandbox.html:387-432`):
- Receives filtered norms from API
- Updates `filteredNorms` (norms that passed the filter)
- Calculates `filteredOutNorms` (norms that didn't pass)
- Re-renders the UI with updated counts

---

### 5. **Output Phase: UI Rendering**

#### Norm Cards Display (`sandbox.html:434-555`)

Each norm is rendered as an interactive card with:

**Header**:
- Norm ID (first 8 characters)
- Norm statement (regulatory text)
- "Details" button to expand/collapse

**Collapsed State**:
- Shows only ID and statement
- Compact view for browsing many norms

**Expanded State** (toggled by "Details" button):
- **Topics**: Tags/categories (e.g., "SI3", "Evacuación", "Puertas")
- **Priority**: Importance level (1-5)
- **Location Scope**: Geographic applicability (JSON object)
- **Applies If**: DSL predicate (syntax-highlighted)
- **Satisfied If**: Compliance condition (syntax-highlighted)

**Example Rendered Card**:
```
┌─────────────────────────────────────────────────────┐
│ ID: 55816dd6                        [Details ▼]     │
│ Las puertas de salida tendrán una anchura mínima... │
│                                                      │
│ (Expanded details)                                   │
│ Topics: SI3, Evacuación, Puertas                    │
│ Priority: 3                                          │
│ Location: {"COUNTRY": "ES", "REGION": "national"}   │
│ Applies If: DOOR.TYPE == 'EXIT' AND ...            │
│ Satisfied If: DOOR.WIDTH >= 0.80                   │
└─────────────────────────────────────────────────────┘
```

#### Tab System (`sandbox.html:56-84`)

**Two Tabs**:

1. **Current Tab** (default):
   - Shows norms that passed filters (or all norms if no filters)
   - Displays count: `"Current (X)"`

2. **Filtered Out Tab**:
   - Shows norms that were excluded by filters
   - Displays count: `"Filtered Out (Y)"`
   - Empty when no feature filters are applied

**Tab Switching** (`sandbox.html:457-475`):
- Click tab to switch views
- Updates tab styling (blue border for active tab)
- Re-renders norm list with appropriate subset

#### Counter Display (`sandbox.html:569-578`)

**Top-Right Counter**: Shows `"X/Y"` where:
- `X` = Number of norms passing filters
- `Y` = Total number of norms in the dataset

**Purpose**: Provides at-a-glance feedback on filter impact.

---

## Computation Deep Dive

### DSL (Domain-Specific Language) Syntax

The `applies_if` predicates use a formal DSL defined in `ig_assessment/dsl_parser.py`.

**Supported Operators**:
- **Comparison**: `==`, `!=`, `>`, `>=`, `<`, `<=`
- **Boolean**: `AND`, `OR`, `NOT`, `(parentheses)`
- **Membership**: `IN [...]`, `IN (...)`
- **Functions**: `HAS(feature)`, geographic scoping

**Supported Literals**:
- **Strings**: `'RESIDENTIAL.HOUSING'`, `"EXIT"`
- **Numbers**: `100`, `500.0`, `-10`
- **Booleans**: `TRUE`, `FALSE` (case-insensitive)

**Identifiers**:
- Dotted notation: `BUILDING.USAGE`, `DOOR.TYPE`, `AREA.SIZE`
- Uppercase convention

**Example Expressions**:
```
TRUE
BUILDING.USAGE == 'RESIDENTIAL.HOUSING'
AREA.SIZE > 100.0 AND AREA.SIZE <= 500.0
DOOR.TYPE IN ['EXIT', 'EMERGENCY']
NOT (BUILDING.USAGE == 'PARKING')
(AREA.SIZE > 100 OR AREA.OCCUPANCY > 50) AND BUILDING.USAGE != 'STORAGE'
```

### Tri-State Evaluation Algorithm

**Module**: `ig_assessment/evaluator.py`

**Class**: `Evaluator`

**Core Method**:
```python
def evaluate(self, node: ASTNode) -> TristateValue:
    """Evaluate an AST node with partial assignment."""
    
    if isinstance(node, Literal):
        # Concrete value → TRUE or FALSE
        return TristateValue.TRUE if node.value else TristateValue.FALSE
    
    elif isinstance(node, Identifier):
        # Look up in assignment
        if node.name in self.assignment:
            return TristateValue.TRUE  # Feature has expected value
        else:
            return TristateValue.UNKNOWN  # Feature not assigned
    
    elif isinstance(node, BinaryOp):
        # Evaluate left and right, apply comparison
        left = self.evaluate(node.left)
        right = self.evaluate(node.right)
        
        if node.operator == '==':
            if left == UNKNOWN or right == UNKNOWN:
                return TristateValue.UNKNOWN
            return TristateValue.TRUE if left == right else TristateValue.FALSE
        
        # Similar for !=, >, >=, <, <=
    
    elif isinstance(node, UnaryOp):
        # NOT operation
        operand = self.evaluate(node.operand)
        return tristate_not(operand)
    
    elif isinstance(node, LogicOp):
        # AND, OR operations
        left = self.evaluate(node.left)
        right = self.evaluate(node.right)
        
        if node.operator == 'AND':
            return tristate_and(left, right)
        elif node.operator == 'OR':
            return tristate_or(left, right)
```

**Truth Tables** (Kleene Logic):

**AND**:
|       | TRUE  | FALSE | UNKNOWN |
|-------|-------|-------|---------|
| TRUE  | TRUE  | FALSE | UNKNOWN |
| FALSE | FALSE | FALSE | FALSE   |
| UNKNOWN | UNKNOWN | FALSE | UNKNOWN |

**OR**:
|       | TRUE | FALSE | UNKNOWN |
|-------|------|-------|---------|
| TRUE  | TRUE | TRUE  | TRUE    |
| FALSE | TRUE | FALSE | UNKNOWN |
| UNKNOWN | TRUE | UNKNOWN | UNKNOWN |

**NOT**:
| Input   | Output  |
|---------|---------|
| TRUE    | FALSE   |
| FALSE   | TRUE    |
| UNKNOWN | UNKNOWN |

**Key Properties**:
1. **Monotonicity**: More information (fewer UNKNOWNs) never changes TRUE→FALSE or FALSE→TRUE
2. **Conservative**: When uncertain, evaluates to UNKNOWN (keeps norms visible)
3. **Short-Circuit**: `FALSE AND X → FALSE`, `TRUE OR X → TRUE` (even if X is UNKNOWN)

### Filtering Decision Logic

**Rule**: Keep norm if `evaluate(applies_if) != FALSE`

**Rationale**:
- `TRUE`: Norm definitely applies → User should see it
- `UNKNOWN`: Not enough information to dismiss → User should see it (conservative approach)
- `FALSE`: Norm definitely doesn't apply → Hide it (certain exclusion)

**Example Scenarios**:

1. **No Filters Applied**:
   - All features are UNKNOWN
   - All norms evaluate to UNKNOWN (or TRUE if `applies_if = "TRUE"`)
   - All norms are shown

2. **One Filter Applied** (`BUILDING.USAGE = "RESIDENTIAL.HOUSING"`):
   - Norm A: `applies_if = "BUILDING.USAGE == 'RESIDENTIAL.HOUSING'"` → TRUE → **SHOW**
   - Norm B: `applies_if = "BUILDING.USAGE == 'COMMERCIAL'"` → FALSE → **HIDE**
   - Norm C: `applies_if = "AREA.SIZE > 100 AND BUILDING.USAGE == 'RESIDENTIAL.HOUSING'"` → `UNKNOWN AND TRUE = UNKNOWN` → **SHOW**
   - Norm D: `applies_if = "TRUE"` → TRUE → **SHOW**

3. **Multiple Filters Applied** (`BUILDING.USAGE = "RESIDENTIAL.HOUSING"`, `AREA.SIZE = "(100.0, 500.0]"`):
   - Norm C (from above): `UNKNOWN AND TRUE AND TRUE = UNKNOWN` → **SHOW** (if AREA.SIZE check passes)
   - More specific filtering, fewer UNKNOWNs

**Performance Optimization**:
- Frontend sends only `norm_ids` of norms in `baseNormsAfterAppliesIf`
- Backend evaluates only those norms (not the entire dataset)
- Reduces API response size and processing time

---

## Frontend State Management

### Global State Variables (`sandbox.html:114-123`)

```javascript
let allNorms = [];                    // All norms from selected run
let filteredNorms = [];               // Norms passing current filters
let filteredOutNorms = [];            // Norms excluded by current filters
let baseNormsAfterAppliesIf = [];    // Norms after applies_if filter, before feature filters
let features = [];                    // Feature definitions from IG CSV
let currentFilters = {};              // Current feature filter values {feature: value}
let currentRunId = null;              // Selected output run ID
let appliesIfFilter = 'all';          // applies_if filter mode: 'all', 'true', 'not-true'
let currentTab = 'current';           // Active tab: 'current' or 'filtered-out'
```

### State Transitions

```
[Page Load]
    ↓
[Initialize]
    ↓
[Load Outputs] → Select Latest → [Load Norms]
    ↓                                  ↓
[Load Features] → [Render Filters]   allNorms = data
    ↓                                  ↓
[User Interaction]                  [Display All Norms]
    ↓
┌───────────────────────────┐
│ User Changes Filter       │
│ (Dropdown, Input, Button) │
└───────────┬───────────────┘
            ↓
    [handleFilterChange]
            ↓
    [Update currentFilters]
            ↓
    [applyFiltersClientSide]
            ↓
    ┌────────┴─────────┐
    │ No Feature       │ Feature Filters
    │ Filters          │ Applied
    ↓                  ↓
[Direct Display]   [applyFiltersViaAPI]
    │                  │
    │                  ↓
    │              [POST /api/sandbox/filter]
    │                  │
    │                  ↓
    │              [Backend Tri-State Eval]
    │                  │
    │                  ↓
    │              [Response with Filtered Norms]
    ↓                  ↓
    └──────┬───────────┘
           ↓
    [Update filteredNorms & filteredOutNorms]
           ↓
    [renderNorms]
           ↓
    [Update UI: Cards + Counts]
```

### Event Handlers

1. **Output Selector Change** (`sandbox.html:602-610`):
   ```javascript
   document.getElementById('output-selector').onchange = async (e) => {
     currentRunId = e.target.value;
     document.getElementById('clear-filters').click();  // Reset filters
     await loadNorms(currentRunId);                    // Reload norms
   };
   ```

2. **Filter Change** (Dropdowns/Inputs) (`sandbox.html:317-347`):
   ```javascript
   function handleFilterChange() {
     // Collect all filter values
     currentFilters = {};
     document.querySelectorAll('select[data-feature]').forEach(select => {
       if (select.value) currentFilters[select.dataset.feature] = select.value;
     });
     document.querySelectorAll('input[type="number"][data-feature]').forEach(input => {
       if (input.value) currentFilters[input.dataset.feature] = parseFloat(input.value);
     });
     
     // Apply filters
     applyFiltersClientSide();
   }
   ```

3. **Clear Filters Button** (`sandbox.html:581-600`):
   ```javascript
   document.getElementById('clear-filters').onclick = () => {
     document.getElementById('filter-applies-if').value = 'all';
     appliesIfFilter = 'all';
     
     document.querySelectorAll('select[data-feature]').forEach(select => select.value = '');
     document.querySelectorAll('input[type="number"][data-feature]').forEach(input => input.value = '');
     
     currentFilters = {};
     filteredNorms = allNorms;
     filteredOutNorms = [];
     renderNorms();
     updateCounter();
   };
   ```

4. **Tab Switch** (`sandbox.html:457-475`):
   ```javascript
   function switchTab(tab) {
     currentTab = tab;
     // Update button styles
     // Re-render norms for selected tab
     renderNorms();
   }
   ```

5. **Details Toggle** (`sandbox.html:557-567`):
   ```javascript
   function toggleDetails(idx) {
     const details = document.getElementById(`details-${idx}`);
     details.classList.toggle('details-collapsed');
     details.classList.toggle('details-expanded');
   }
   ```

---

## Filter UI Generation

### Filter Panel Layout (`sandbox.html:88-110`)

```
┌─────────────────────────────────────┐
│ Filters                             │
│ ┌─────────────────────────────────┐ │
│ │ Output Run                      │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ 1757864159 (Latest - ...)   │ │ │
│ │ └─────────────────────────────┘ │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ [Clear All Filters]             │ │
│ └─────────────────────────────────┘ │
│                                     │
│ (Dynamic Filters Below)             │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ applies_if Filter               │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ All ▼                       │ │ │
│ │ └─────────────────────────────┘ │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ BUILDING.USAGE (0.67)           │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ -- Any --                   │ │ │
│ │ └─────────────────────────────┘ │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ AREA.SIZE (0.33)                │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ -- Any --                   │ │ │
│ │ └─────────────────────────────┘ │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ FLOOR.COUNT (0.10)              │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ [Enter value...]            │ │ │
│ │ └─────────────────────────────┘ │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Filter Rendering Logic (`sandbox.html:209-315`)

**Top 20 Features**: Only the first 20 features (by dismissal rate) are rendered to avoid UI clutter and performance issues.

```javascript
function renderFilters() {
  const container = document.getElementById('filters-container');
  container.innerHTML = '';
  
  // Special applies_if filter (always first)
  const trueFilterDiv = createAppliesIfFilter();
  container.appendChild(trueFilterDiv);
  
  // Top 20 features
  const topFeatures = features.slice(0, 20);
  
  topFeatures.forEach(feature => {
    const filterDiv = document.createElement('div');
    filterDiv.className = 'border-b border-gray-200 pb-4';
    
    const label = document.createElement('label');
    label.textContent = feature.display_name || feature.name;
    filterDiv.appendChild(label);
    
    if (feature.type === 'categorical') {
      const select = createDropdown(feature.name, feature.values);
      filterDiv.appendChild(select);
    } else if (feature.type === 'bin') {
      const select = createDropdown(feature.name, feature.values);
      filterDiv.appendChild(select);
    } else if (feature.type === 'int') {
      const input = createNumberInput(feature.name);
      filterDiv.appendChild(input);
    }
    
    container.appendChild(filterDiv);
  });
}
```

**Dropdown Helper** (Categorical/Bin):
```javascript
function createDropdown(featureName, values) {
  const select = document.createElement('select');
  select.dataset.feature = featureName;
  select.onchange = () => handleFilterChange();
  
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = '-- Any --';
  select.appendChild(defaultOption);
  
  values.forEach(value => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
  
  return select;
}
```

**Number Input Helper** (Int):
```javascript
function createNumberInput(featureName) {
  const input = document.createElement('input');
  input.type = 'number';
  input.placeholder = 'Enter value...';
  input.dataset.feature = featureName;
  input.oninput = () => handleFilterChange();
  return input;
}
```

---

## Use Cases & Examples

### Use Case 1: "Show me norms for residential buildings"

**Steps**:
1. User selects latest output run (auto-selected)
2. User clicks `BUILDING.USAGE` dropdown
3. User selects `"RESIDENTIAL.HOUSING"`

**Backend Processing**:
- Evaluates all norms with `{BUILDING.USAGE: "RESIDENTIAL.HOUSING"}`
- Example results:
  - Norm A: `applies_if = "BUILDING.USAGE == 'RESIDENTIAL.HOUSING'"` → TRUE → **SHOW**
  - Norm B: `applies_if = "BUILDING.USAGE == 'COMMERCIAL'"` → FALSE → **HIDE**
  - Norm C: `applies_if = "TRUE"` → TRUE → **SHOW**

**UI Updates**:
- "Current" tab: Shows Norm A and Norm C
- "Filtered Out" tab: Shows Norm B
- Counter: `"2/3"`

### Use Case 2: "Find norms that apply to large areas"

**Steps**:
1. User selects `AREA.SIZE` dropdown
2. User selects `"(500.0, inf)"` (areas larger than 500m²)

**Backend Processing**:
- Evaluates with `{AREA.SIZE: "(500.0, inf)"}`
- Norms with `AREA.SIZE > 500` or `AREA.SIZE >= 500` → TRUE
- Norms with `AREA.SIZE <= 500` → FALSE
- Norms without `AREA.SIZE` references → UNKNOWN → **SHOW**

### Use Case 3: "Explore universally applicable norms"

**Steps**:
1. User clicks `applies_if Filter` dropdown
2. User selects `"TRUE"`

**Client-Side Processing**:
- Filters to norms where `applies_if == "TRUE"` (literal string match)
- These are norms with no conditions (always applicable)

**Result**: Shows only universal requirements (e.g., "All buildings require fire safety plan")

### Use Case 4: "Narrow down with multiple filters"

**Steps**:
1. User selects `BUILDING.USAGE = "RESIDENTIAL.HOUSING"`
2. User selects `AREA.SIZE = "(100.0, 500.0]"`
3. User enters `FLOOR.COUNT = 3`

**Backend Processing**:
- Evaluates with `{BUILDING.USAGE: "RESIDENTIAL.HOUSING", AREA.SIZE: "(100.0, 500.0]", FLOOR.COUNT: 3}`
- Very specific filtering: Most features are known, fewer UNKNOWNs
- Only highly relevant norms remain

**Result**: Refined list of norms applicable to 3-story residential buildings between 100-500m²

---

## Technical Details

### Performance Considerations

1. **Feature Limit**: Only top 20 features rendered (avoid UI clutter)
2. **Lazy API Calls**: Feature filters only trigger API calls when at least one filter is set
3. **Norm ID Filtering**: Backend only evaluates norms in `baseNormsAfterAppliesIf` (optimization)
4. **Client-Side applies_if Filter**: Simple string matching (no API call)
5. **Debouncing**: No explicit debouncing (filters are user-triggered, not auto-applied on typing)

### Error Handling

**Backend**:
- Missing `ig_results.csv`: Returns 404 error
- Missing `enhanced_extraction_results.json`: Returns 404 error
- DSL parsing errors: Skips unparseable norms (logged to console)
- Evaluation exceptions: Returns 500 with error details

**Frontend**:
- API errors: Displays error message in UI
- Empty result sets: Shows "No norms match the current filters" message
- Missing data: Gracefully handles with "Loading..." or error states

### Browser Compatibility

- **ES6+ JavaScript**: Requires modern browser (Chrome 60+, Firefox 60+, Safari 12+)
- **CSS Grid/Flexbox**: Modern layout features
- **Fetch API**: Native AJAX (no jQuery dependency)
- **Tailwind CSS**: CDN-delivered (no build step required)

### Security

- **No `eval()`**: DSL parsing uses proper Lark parser (no code execution)
- **Input Validation**: Backend validates `run_id`, `filters`, `norm_ids`
- **Path Traversal Protection**: Uses `Path` objects, checks existence before reading
- **JSON Injection**: Uses `json.loads()` (safe parsing)

---

## File Structure

```
langextract/
├── web/
│   ├── app.py                          # Flask backend with API endpoints
│   ├── templates/
│   │   └── sandbox.html                # Frontend HTML + JavaScript
│   └── test_sandbox_api.py             # API tests
├── ig_assessment/
│   ├── dsl_parser.py                   # DSL parser (Lark grammar)
│   ├── evaluator.py                    # Tri-state evaluator (Kleene logic)
│   ├── compute_ig.py                   # IG computation script
│   └── tmp/
│       └── ig_results.csv              # Feature definitions with dismissal rates
└── output_runs/
    └── {run_id}/
        └── enhanced_output/
            └── enhanced_extraction_results.json  # Norm data
```

---

## Testing

### API Tests (`web/test_sandbox_api.py`)

**Test Coverage**:
1. **IG CSV Parsing**: Validates feature extraction from CSV
2. **Tri-State Evaluator**: Tests Kleene logic truth tables
3. **Filtering Logic**: Validates norm filtering with partial assignments

**Running Tests**:
```bash
cd web
python test_sandbox_api.py
```

**Expected Output**:
```
============================================================
SANDBOX API TESTS
============================================================

1. Testing ig.csv parsing...
✓ Parsed 45 features from ig.csv
✓ BUILDING.USAGE has 7 categories

2. Testing tri-state evaluator...
✓ Tri-state evaluator: Partial AND returns UNKNOWN

3. Testing filtering logic...
✓ Filtering logic: correctly keeps/excludes norms based on tri-state evaluation

============================================================
ALL TESTS PASSED
============================================================
```

### Manual Testing Checklist

- [ ] Page loads without errors
- [ ] Output selector populates with available runs
- [ ] Latest run is auto-selected
- [ ] Norms load and display
- [ ] Features load and generate filter UI
- [ ] applies_if filter works (ALL/TRUE/!TRUE)
- [ ] Feature filters update Current tab
- [ ] Feature filters update Filtered Out tab
- [ ] Counter updates correctly
- [ ] Tab switching works
- [ ] Details expand/collapse works
- [ ] Clear Filters button resets all filters
- [ ] Changing output run resets filters and reloads norms

---

## Future Enhancements

### Potential Improvements

1. **Filter Persistence**:
   - Save filter state in URL query params
   - Allow bookmarking specific filter combinations

2. **Advanced Search**:
   - Full-text search in norm statements
   - Filter by priority, confidence, topics

3. **Export Functionality**:
   - Export filtered norms as JSON/CSV
   - Generate compliance reports

4. **Visualization**:
   - Dependency graph of norms
   - Feature importance charts

5. **Performance**:
   - Implement debouncing for rapid filter changes
   - Cache AST parsing results per run
   - Add pagination for large norm sets

6. **UX Improvements**:
   - Add tooltips explaining DSL syntax
   - Highlight matching features in norm text
   - Add "Why was this norm filtered?" explanations

7. **Collaboration**:
   - Share filter configurations with team
   - Add comments/notes to norms

---

## Glossary

**Applies If**: DSL predicate determining when a norm is applicable based on building features.

**AST (Abstract Syntax Tree)**: Tree representation of parsed DSL expression.

**Dismissal Rate**: Fraction of norms filtered out (made inapplicable) by a feature value.

**DSL (Domain-Specific Language)**: Formal language for expressing norm applicability conditions.

**Enhanced Extraction Results**: Structured JSON output from the LangExtract pipeline containing norms, sections, and metadata.

**Feature**: A building characteristic (e.g., `BUILDING.USAGE`, `AREA.SIZE`) used in norm applicability predicates.

**IG (Information Gain)**: Measure of how much a feature reduces uncertainty about norm applicability.

**Kleene Logic**: Three-valued logic system supporting TRUE, FALSE, and UNKNOWN values.

**Norm**: An atomic regulatory statement with applicability and compliance conditions.

**Run ID**: Unique identifier for a pipeline execution (timestamp-based).

**Tri-State Logic**: Logic system with three values (TRUE, FALSE, UNKNOWN) used for partial feature assignments.

---

## References

- **Enhanced Extraction Pipeline**: `docs/enhanced_extraction_pipeline.md`
- **IG Assessment Tool**: `ig_assessment/README.md`
- **DSL Parser**: `ig_assessment/dsl_parser.py`
- **Tri-State Evaluator**: `ig_assessment/evaluator.py`
- **Extraction Prompt**: `input_promptfiles/extraction_prompt_V2_removed_entstruct.md`

---

## Support

For issues or questions:
1. Check existing documentation in `/docs`
2. Review test cases in `web/test_sandbox_api.py`
3. Examine browser console logs for client-side errors
4. Check Flask logs for backend errors
5. File an issue on GitHub with reproduction steps
