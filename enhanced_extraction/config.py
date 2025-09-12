"""Configuration utilities for enhanced extraction pipeline.

This module provides configuration management, provider setup,
and extraction parameter handling for the enhanced pipeline.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    def load_dotenv(): pass  # No-op fallback

import langextract as lx
from langextract import factory, providers


class ExtractionConfig:
    """Configuration manager for extraction pipeline."""
    
    def __init__(
        self,
        model_id: str = "google/gemini-2.0-flash-exp",
        temperature: float = 0.15,
        max_norms_per_5k: int = 30,
        max_char_buffer: int = 50000
    ):
        """Initialize extraction configuration.
        
        Args:
            model_id: Language model identifier
            temperature: Model temperature for extraction
            max_norms_per_5k: Maximum norms to extract per 5K characters
            max_char_buffer: Maximum character buffer size
        """
        self.model_id = model_id
        self.temperature = temperature
        self.max_norms_per_5k = max_norms_per_5k
        self.max_char_buffer = max_char_buffer
        
        # Provider configuration
        self.use_openrouter = os.getenv("USE_OPENROUTER", "1").lower() in {"1", "true", "yes"}
        self.openrouter_key = os.environ.get("OPENAI_API_KEY")
        self.google_api_key = os.environ.get("GOOGLE_API_KEY")
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration and warn about missing keys."""
        if self.use_openrouter and not self.openrouter_key:
            print("WARNING: OPENROUTER (OPENAI_API_KEY) key not set – OpenRouter call will fail.", file=sys.stderr)
        elif not self.use_openrouter and not self.google_api_key:
            print("WARNING: GOOGLE_API_KEY not set – direct Gemini call will likely fail.", file=sys.stderr)
    
    def create_langextract_config(self) -> Dict[str, Any]:
        """Create LangExtract configuration dictionary.
        
        Returns:
            Configuration dictionary for LangExtract
        """
        return lx.Config(
            model_name=self.model_id,
            temperature=self.temperature,
            cache_dir=".cache_lx",
            max_attempts=3,
        )
    
    def get_provider_info(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Get provider configuration information.
        
        Returns:
            Tuple of (use_openrouter, openrouter_key, google_api_key)
        """
        return self.use_openrouter, self.openrouter_key, self.google_api_key


def setup_langextract_providers() -> None:
    """Setup LangExtract providers and configuration."""
    if DOTENV_AVAILABLE:
        load_dotenv()
    
    try:
        # Ensure provider registry is populated
        providers.load_builtins_once()
        providers.load_plugins_once()
        
        avail = providers.list_providers()
        print(f"[DEBUG] Providers available: {sorted(list(avail.keys()))}")
    except Exception as e:
        print(f"[WARNING] Could not setup providers: {e}")


def should_skip_section_for_extraction(section_name: str) -> bool:
    """Determine if a section should be skipped for extraction.
    
    Args:
        section_name: Name of the section to check
        
    Returns:
        True if section should be skipped, False otherwise
    """
    skip_patterns = [
        # Common non-content sections
        "table of contents", "toc", "índice", "contenido",
        "bibliography", "references", "bibliografía", "referencias",
        "index", "índice alfabético",
        "appendix", "apéndice", "anexo",
        "glossary", "glosario",
        
        # Administrative sections
        "preface", "prefacio", "prólogo",
        "acknowledgments", "agradecimientos",
        "copyright", "derechos de autor",
        "license", "licencia",
        
        # Empty or minimal content indicators
        "page intentionally left blank",
        "this page is intentionally left blank",
        "página intencionalmente en blanco",
        
        # Navigation elements
        "back to top", "volver arriba",
        "next page", "previous page",
        "página siguiente", "página anterior"
    ]
    
    section_lower = section_name.lower().strip()
    
    # Check exact matches and patterns
    for pattern in skip_patterns:
        if pattern in section_lower:
            return True
    
    # Skip very short section names (likely navigation elements)
    if len(section_lower) < 3:
        return True
    
    # Skip sections that are mostly numbers/symbols
    if not any(c.isalpha() for c in section_lower):
        return True
    
    return False


def load_prompt_and_examples(
    prompt_file: Optional[Path] = None,
    examples_file: Optional[Path] = None,
    glossary_file: Optional[Path] = None,
    semantics_file: Optional[Path] = None,
    teach_file: Optional[Path] = None
) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    """Load prompt templates and examples for extraction.
    
    Args:
        prompt_file: Path to prompt template file
        examples_file: Path to examples file
        glossary_file: Path to glossary file
        semantics_file: Path to semantics file
        teach_file: Path to teaching file
        
    Returns:
        Tuple of (prompt_text, examples_list, additional_config)
    """
    prompt_text = None
    examples_list = None
    additional_config = {}
    
    # Load prompt template
    if prompt_file and prompt_file.exists():
        try:
            prompt_text = prompt_file.read_text(encoding='utf-8')
            print(f"[INFO] Loaded prompt template: {prompt_file}")
        except Exception as e:
            print(f"[WARNING] Failed to load prompt file {prompt_file}: {e}")
    
    # Load examples
    if examples_file and examples_file.exists():
        try:
            if examples_file.suffix == '.json':
                import json
                with open(examples_file, 'r', encoding='utf-8') as f:
                    examples_data = json.load(f)
                    examples_list = examples_data if isinstance(examples_data, list) else [examples_data]
            else:
                # Handle other formats as needed
                pass
            print(f"[INFO] Loaded examples: {examples_file}")
        except Exception as e:
            print(f"[WARNING] Failed to load examples file {examples_file}: {e}")
    
    # Load additional configuration files
    config_files = {
        'glossary': glossary_file,
        'semantics': semantics_file,
        'teach': teach_file
    }
    
    for config_type, file_path in config_files.items():
        if file_path and file_path.exists():
            try:
                content = file_path.read_text(encoding='utf-8')
                additional_config[config_type] = content
                print(f"[INFO] Loaded {config_type} file: {file_path}")
            except Exception as e:
                print(f"[WARNING] Failed to load {config_type} file {file_path}: {e}")
    
    return prompt_text, examples_list, additional_config


def create_extraction_schema(
    config: ExtractionConfig,
    additional_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Create extraction schema based on configuration.
    
    Args:
        config: Extraction configuration
        additional_config: Additional configuration from files
        
    Returns:
        Extraction schema dictionary
    """
    schema = {
        "model_config": {
            "model_id": config.model_id,
            "temperature": config.temperature,
            "max_tokens": 4000
        },
        "extraction_config": {
            "max_norms_per_5k": config.max_norms_per_5k,
            "max_char_buffer": config.max_char_buffer
        },
        "content_filters": {
            "skip_empty_sections": True,
            "min_section_length": 50,
            "skip_patterns": [
                "table of contents",
                "bibliography",
                "index"
            ]
        }
    }
    
    # Add additional configuration
    if additional_config.get('glossary'):
        schema['glossary'] = additional_config['glossary']
    
    if additional_config.get('semantics'):
        schema['semantics'] = additional_config['semantics']
    
    if additional_config.get('teach'):
        schema['teaching_examples'] = additional_config['teach']
    
    return schema