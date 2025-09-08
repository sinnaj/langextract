# LangExtract Processing Pipeline Documentation

## Overview

The LangExtract processing pipeline is a sophisticated document analysis system that converts structured text (particularly regulatory and legal documents) into machine-readable extracted entities using Large Language Models (LLMs). The pipeline emphasizes hierarchical document understanding, intelligent chunking, and comprehensive extraction of norms, tags, parameters, and other entities.

## Pipeline Architecture

```
Input Document → Docling Integration → Hierarchical Chunking → Chunk Evaluation → 
LLM Extraction → Post-Processing → Combined Output
```

### Core Components

1. **Environment & Configuration**
2. **Document Input & Preprocessing** 
3. **Hierarchical Chunking (Docling Integration)**
4. **Chunk Evaluation & Filtering**
5. **LLM-Based Extraction**
6. **Post-Processing & Derivation**
7. **Output Generation & Persistence**

---

## Detailed Pipeline Stages

### 1. Environment & Configuration Setup

**Location**: `lxRunnerExtraction.py` (lines 50-110)

**Purpose**: Initialize the extraction environment and configure all parameters.

**Key Operations**:
- Load environment variables from `.env` file
- Configure LLM provider (OpenRouter vs Direct Gemini)
- Set up API keys and model parameters
- Create output directory structure (`output_runs/<RUN_ID>/`)
- Initialize provider registry

**Configuration Parameters**:
```python
- RUN_ID: Unique identifier for the extraction run
- MODEL_ID: LLM model (e.g., "google/gemini-2.5-flash")
- MODEL_TEMPERATURE: Creativity vs consistency (typically 0.15)
- MAX_NORMS_PER_5K: Extraction density limit
- MAX_CHAR_BUFFER: Maximum text chunk size (e.g., 9999)
- EXTRACTION_PASSES: Multiple passes for better recall
```

**Output Directories**:
- `chunks/`: Individual processed chunks with metadata
- `lx output/`: Final combined outputs

### 2. Document Input & Preprocessing

**Location**: `lxRunnerExtraction.py` (lines 110-170)

**Purpose**: Load and prepare the input document for processing.

**Input Discovery**:
1. Check for explicit `LE_INPUT_FILE` environment variable
2. Scan `output_runs/<RUN_ID>/input/` for text files (`.txt`, `.md`)
3. Prioritize text-like files over other formats

**Prompt Assembly**:
- Load base prompt from `INPUT_PROMPTFILE`
- Conditionally append teaching materials (`LX_TEACH_MODE=1`)
- Add entity semantics and known field paths
- Load few-shot examples from Python modules

### 3. Hierarchical Chunking (Docling Integration)

**Location**: `docling_integration.py`

**Purpose**: Convert input text into semantically meaningful chunks that preserve document structure.

#### 3.1 Document Structure Analysis
```python
Input Text → DoclingDocument → HierarchicalChunker → BaseChunk[] → SectionChunk[]
```

**Key Functions**:
- `create_docling_hierarchical_chunks(text: str) -> List[SectionChunk]`
- `perform_docling_hierarchical_chunking(text, merge_list_items, delim)`
- `convert_docling_chunk_to_section_chunk(docling_chunk, chunk_index, text_start_pos)`

#### 3.2 Hierarchical Metadata Extraction

Each chunk contains rich metadata:
```python
{
    "chunk_id": "section_001", 
    "chunk_name": "Fire Safety Requirements",
    "chunk_type": "section_header",
    "hierarchical_level": 2,
    "parent_chunk_id": "section_000", 
    "child_chunks": ["section_002", "section_003"],
    "docling_metadata": {...},
    "doc_items_info": [...]
}
```

#### 3.3 Fallback Mechanism
If Docling is unavailable, the system falls back to text-based chunking to ensure robustness.

### 4. Chunk Evaluation & Filtering

**Location**: `chunk_evaluator.py`

**Purpose**: Intelligently determine which chunks require LLM extraction vs. manual processing.

#### 4.1 Evaluation Criteria

**Extract**: Content-rich sections requiring entity extraction
- Regulatory text with specific requirements
- Technical specifications
- Detailed procedures

**Manual**: Structural elements without extractable content
- Table of contents sections
- Headline-only sections
- Navigation elements

**Drop**: Non-relevant content
- Empty sections
- Pure formatting elements

#### 4.2 Evaluation Process
```python
def evaluate_chunk(chunk: SectionChunk) -> ChunkEvaluation:
    if is_table_of_contents(chunk):
        return ChunkEvaluation(should_extract=False, processing_type="manual")
    elif is_headline_only(chunk):
        return ChunkEvaluation(should_extract=False, processing_type="manual") 
    else:
        return ChunkEvaluation(should_extract=True, processing_type="extract")
```

#### 4.3 Post-Processing Rules
- Drop children of dropped sections
- Handle repeating section names
- Apply hierarchical consistency rules

### 5. LLM-Based Extraction

**Location**: `lxRunnerExtraction.py` (lines 330-650)

**Purpose**: Extract structured entities from text using Large Language Models.

#### 5.1 Model Configuration
```python
cfg = factory.ModelConfig(
    model_id=MODEL_ID,
    provider="OpenAILanguageModel",  # OpenRouter compatibility
    provider_kwargs={
        "api_key": OPENROUTER_KEY,
        "base_url": "https://openrouter.ai/api/v1",
        "temperature": MODEL_TEMPERATURE,
        "format_type": lx.data.FormatType.JSON,
        "max_workers": 20,
    },
)
```

#### 5.2 Extraction Parameters
```python
extract_kwargs = {
    "text_or_documents": chunk_text,
    "prompt_description": PROMPT_DESCRIPTION,
    "examples": EXAMPLES,
    "config": cfg,
    "fence_output": False,
    "use_schema_constraints": False,
    "max_char_buffer": MAX_CHAR_BUFFER,
    "extraction_passes": EXTRACTION_PASSES,
    "resolver_params": {
        "fence_output": False,
        "format_type": lx.data.FormatType.JSON,
        "suppress_parse_errors_default": env_configurable
    }
}
```

#### 5.3 Extracted Entity Types

**NORM**: Regulatory requirements and obligations
```python
{
    "extraction_class": "NORM",
    "attributes": {
        "id": "N::000001",
        "norm_statement": "Building exits must be clearly marked",
        "obligation_type": "MUST",
        "applies_if": "BUILDING.TYPE == COMMERCIAL",
        "satisfied_if": "EXIT.SIGNAGE.VISIBLE == TRUE",
        "relevant_tags": ["BUILDING.EXIT", "SIGNAGE.SAFETY"],
        "topics": ["SAFETY.FIRE.EVACUATION"]
    }
}
```

**CLASSIFICATION**: Document categories and types
**LEGAL_DOCUMENT**: References to legal sources
**PROCEDURE**: Step-by-step processes  
**CHUNK_METADATA**: Section-level metadata

#### 5.4 Error Handling & Resilience

**Fallback Extraction**: When LLM extraction fails:
```python
def _synthesize_extraction(text, norms=None, errors=None, warnings=None):
    return {
        "schema_version": "1.0.0",
        "document_metadata": {...},
        "norms": norms or [],
        "quality": {"errors": errors or [], "warnings": warnings or []}
    }
```

**API Key Security**: Automatic redaction of sensitive information in logs

### 6. Post-Processing & Derivation

**Location**: `postprocessing/extract_tags.py`, `postprocessing/extract_params.py`

**Purpose**: Derive additional entities (Tags, Parameters) from extracted Norms.

#### 6.1 Tag Extraction

**Source**: `relevant_tags` field from NORM entities  
**Process**: Aggregate unique tags with usage tracking

```python
def extract_tags_from_norms(norms_to_process, tag_counter_start=1):
    tag_map = {}
    for norm_data in norms_to_process:
        for tag_path in norm_data.get("relevant_tags", []):
            if tag_path not in tag_map:
                tag_map[tag_path] = {
                    "extraction_class": "Tag",
                    "attributes": {
                        "id": f"T::{counter:06d}",
                        "tag": tag_path,
                        "used_by_norm_ids": [norm_id],
                        "related_topics": topics
                    }
                }
```

**Tag Hierarchy**: Support for nested tag structures (e.g., `SAFETY.FIRE.EXIT.SIGNAGE`)

#### 6.2 Parameter Extraction

**Source**: `extracted_parameters` field from NORM entities  
**Process**: Parse DSL expressions into structured parameters

```python
def parse_parameter(expr: str) -> Optional[Tuple[str, str, Any, Optional[str]]]:
    # Parses expressions like "BUILDING.HEIGHT >= 10 m"
    match = re.match(r"([A-Z0-9_.]+)\s*(==|>=|<=|>|<)\s*(.+)", expr)
    return (field_path, operator, value, unit)
```

**Parameter Schema**:
```python
{
    "extraction_class": "Parameter",
    "attributes": {
        "id": "P::000001",
        "applies_for_tag": "BUILDING.HEIGHT",
        "operator": ">=",
        "value": 10,
        "unit": "m",
        "norm_ids": ["N::000001"]
    }
}
```

### 7. Hierarchical Context Integration

**Location**: `lxRunnerExtraction.py` (lines 430-500)

**Purpose**: Preserve document structure throughout the extraction process.

#### 7.1 Metadata Preservation
Each extraction receives hierarchical context:
```python
def _add_docling_hierarchy_to_extractions(result_data, section_metadata):
    hierarchical_info = {
        "chunk_id": section_metadata.section_id,
        "chunk_name": section_metadata.section_name,
        "chunk_type": section_metadata.section_type,
        "hierarchical_level": section_metadata.section_level,
        "parent_chunk_id": section_metadata.parent_section_id,
        "docling_metadata": getattr(section_metadata, 'docling_metadata', {}),
        "doc_items_info": getattr(section_metadata, 'doc_items_info', [])
    }
```

#### 7.2 Parent-Child Relationships
Chunks maintain their position in the document hierarchy, enabling:
- Context-aware analysis
- Section-based filtering
- Hierarchical navigation
- Impact assessment across related sections

### 8. Output Generation & Persistence

**Location**: `lxRunnerExtraction.py` (lines 670-750)

**Purpose**: Combine all extractions into comprehensive output files.

#### 8.1 Per-Chunk Outputs
**Raw Debug Files**:
- `raw_annotated_document_XXX.json`: LangExtract object structure
- `raw_resolver_output_XXX.json`: Resolver debugging information  
- `annotated_extractions_XXX.json`: Processed extractions with metadata

#### 8.2 Combined Output
**`combined_extractions.json`**: Unified output containing:

```python
{
    "document_metadata": {
        "source_file": "input_file.md",
        "processing_method": "docling_hierarchical_with_evaluation",
        "total_original_sections": 45,
        "total_processed_sections": 42,
        "total_extractions": 618,
        "processing_timestamp": "2025-09-08T..."
    },
    "evaluation_statistics": {
        "total_chunks": 45,
        "extract_count": 35,
        "manual_count": 7,
        "drop_count": 3
    },
    "sections": [...],  # Metadata for all processed sections
    "extractions": [...],  # All extracted entities with hierarchical context
    "processing_log": [...],  # Detailed processing history
    "section_statistics": {...}  # Hierarchical structure statistics
}
```

#### 8.3 Evaluation Tracking
**`chunk_evaluations.json`**: Detailed evaluation decisions:
```python
{
    "evaluation_statistics": {...},
    "chunk_evaluations": [
        {
            "section_metadata": {...},
            "chunk_length": 1247,
            "evaluation": {
                "should_extract": true,
                "reason": "Content-rich section with regulatory requirements",
                "processing_type": "extract"
            }
        }
    ]
}
```

---

## Key Features & Capabilities

### 1. Hierarchical Document Understanding
- **Docling Integration**: Advanced document structure analysis
- **Parent-Child Relationships**: Maintain document hierarchy throughout processing
- **Context Preservation**: Section metadata travels with extractions

### 2. Intelligent Processing
- **Chunk Evaluation**: Automatic determination of processing approach
- **Selective Extraction**: Only extract from content-rich sections
- **Fallback Mechanisms**: Graceful degradation when tools are unavailable

### 3. Entity Derivation
- **Tag Extraction**: Automatic creation of taxonomy from norms
- **Parameter Extraction**: Parse complex DSL expressions
- **Relationship Mapping**: Link derived entities back to source norms

### 4. Quality & Robustness
- **Multi-Pass Extraction**: Improve recall through multiple extraction passes
- **Error Recovery**: Synthesize valid outputs even when extraction fails
- **Comprehensive Logging**: Detailed debugging and monitoring information

### 5. Scalability & Performance  
- **Configurable Chunking**: Adjust chunk sizes based on model capabilities
- **Parallel Processing**: Multi-worker LLM inference
- **Efficient Caching**: Avoid redundant processing

---

## Configuration Options

### Environment Variables
```bash
# API Configuration
USE_OPENROUTER=1                    # Use OpenRouter (1) vs Direct Gemini (0)
OPENAI_API_KEY=<openrouter_key>     # OpenRouter API key
GOOGLE_API_KEY=<gemini_key>         # Direct Gemini API key

# Processing Configuration  
LX_SUPPRESS_PARSE_ERRORS=false     # Suppress JSON parsing errors (dev/prod)
LX_TEACH_MODE=1                     # Include teaching materials in prompts
LE_INPUT_FILE=/path/to/input.md     # Override input file selection

# Optional Attribution (OpenRouter)
OPENROUTER_REFERER=https://myapp.com
OPENROUTER_TITLE="LangExtract Processing"
```

### Runtime Parameters
```python
makeRun(
    RUN_ID="1757118170",                                    # Unique run identifier
    MODEL_ID="google/gemini-2.5-flash",                    # LLM model selection
    MODEL_TEMPERATURE=0.15,                                 # Output randomness control
    MAX_NORMS_PER_5K=50,                                   # Extraction density limit
    MAX_CHAR_BUFFER=9999,                                  # Chunk size limit
    EXTRACTION_PASSES=1,                                   # Multiple extraction passes
    INPUT_PROMPTFILE="input_promptfiles/extraction_prompt.md",
    INPUT_GLOSSARYFILE="input_glossaryfiles/dsl_glossary.json",
    INPUT_EXAMPLESFILE="input_examplefiles/examples.py",
    INPUT_SEMANTCSFILE="input_semanticsfiles/entity_semantics.md",
    INPUT_TEACHFILE="input_teachfiles/teaching.md"
)
```

---

## Performance Considerations

### Chunk Size Optimization
- **Large Chunks**: Better context, higher cost, potential model limits
- **Small Chunks**: Lower cost, less context, potential fragmentation
- **Recommended**: 5000-10000 characters for Gemini 2.5 Flash

### Extraction Passes
- **Single Pass**: Faster, lower cost, potential missed entities
- **Multiple Passes**: Better recall, higher cost, more comprehensive results
- **Recommended**: 1-2 passes for most use cases

### Model Selection
- **Gemini 2.5 Flash**: Balanced speed/cost/quality (recommended)
- **Gemini 2.5 Pro**: Higher quality for complex documents
- **Custom Models**: Via OpenRouter for specialized needs

---

## Error Handling & Monitoring

### Logging Levels
- **INFO**: Normal processing progress
- **WARN**: Recoverable issues (chunk too large, API errors)
- **ERROR**: Serious problems requiring attention

### Quality Metrics
- **Extraction Success Rate**: Percentage of chunks successfully processed
- **Entity Counts**: Norms, Tags, Parameters extracted per section
- **Processing Time**: Performance monitoring per chunk
- **API Usage**: Token consumption and rate limiting

### Debugging Files
- **Raw Annotated Documents**: LangExtract internal structure
- **Resolver Outputs**: JSON parsing and resolution details
- **Processing Logs**: Step-by-step execution history
- **Evaluation Details**: Chunk processing decisions

---

## Integration Points

### Input Sources
- **Markdown Files**: Primary format for regulatory documents
- **Text Files**: Plain text processing
- **PDF Conversion**: Via Docling preprocessing (planned)

### Output Formats
- **JSON**: Primary structured output format
- **Database**: For integration with larger systems
- **Visualization**: Streamlit dashboard integration
- **API**: RESTful endpoints for programmatic access

### Downstream Processing
- **Analytics**: Statistical analysis of extracted entities
- **Compliance Checking**: Validation against regulatory requirements  
- **Search & Discovery**: Full-text and entity-based search
- **Report Generation**: Automated documentation creation

---

This processing pipeline represents a sophisticated approach to regulatory document analysis, combining state-of-the-art NLP techniques with practical engineering considerations for production deployment.