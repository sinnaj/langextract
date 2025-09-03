#!/usr/bin/env python3
"""
Standalone script to fix hierarchy and merge duplicates in langextract output files.

This script processes JSON files from langextract and applies hierarchy fixes:
1. Detects and merges duplicate sections
2. Fixes orphaned sections with broken parent references
3. Validates the final hierarchical structure

Usage:
    python fix_hierarchy_script.py <input_file.json> [output_file.json]

If output_file is not specified, writes to <input_file>_fixed.json
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict

# Add the postprocessing module to the path
sys.path.insert(0, str(Path(__file__).parent))

from postprocessing.fix_hierarchy import fix_hierarchy_and_merge_duplicates
from postprocessing.fix_hierarchy import validate_hierarchy


def setup_logging(verbose: bool = False) -> None:
  """Setup logging configuration."""
  level = logging.DEBUG if verbose else logging.INFO
  logging.basicConfig(
      level=level,
      format="%(asctime)s - %(levelname)s - %(message)s",
      handlers=[logging.StreamHandler(sys.stdout)],
  )


def load_json_file(file_path: Path) -> Dict[str, Any]:
  """Load and parse a JSON file."""
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    logging.error(f"File not found: {file_path}")
    sys.exit(1)
  except json.JSONDecodeError as e:
    logging.error(f"Invalid JSON in {file_path}: {e}")
    sys.exit(1)
  except Exception as e:
    logging.error(f"Error reading {file_path}: {e}")
    sys.exit(1)


def save_json_file(data: Dict[str, Any], file_path: Path) -> None:
  """Save data to a JSON file with pretty formatting."""
  try:
    with open(file_path, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
    logging.info(f"Fixed data saved to: {file_path}")
  except Exception as e:
    logging.error(f"Error writing to {file_path}: {e}")
    sys.exit(1)


def print_statistics(data: Dict[str, Any], phase: str) -> None:
  """Print statistics about the extraction data."""
  if not isinstance(data, dict) or "extractions" not in data:
    return

  extractions = data["extractions"]
  if not isinstance(extractions, list):
    return

  total = len(extractions)
  sections = [e for e in extractions if e.get("extraction_class") == "SECTION"]
  norms = [e for e in extractions if e.get("extraction_class") == "NORM"]
  tables = [e for e in extractions if e.get("extraction_class") == "TABLE"]

  logging.info(f"=== {phase} Statistics ===")
  logging.info(f"Total extractions: {total}")
  logging.info(f"Sections: {len(sections)}")
  logging.info(f"Norms: {len(norms)}")
  logging.info(f"Tables: {len(tables)}")

  # Show quality warnings if present
  quality = data.get("quality", {})
  warnings = quality.get("warnings", [])
  if warnings:
    logging.info(f"Quality warnings: {len(warnings)}")
    for warning in warnings:
      logging.info(f"  - {warning}")


def main():
  """Main function to process hierarchy fixes."""
  parser = argparse.ArgumentParser(
      description="Fix hierarchy and merge duplicates in langextract output",
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog="""
Examples:
  %(prog)s data.json                    # Creates data_fixed.json
  %(prog)s data.json fixed_data.json    # Creates fixed_data.json
  %(prog)s data.json --validate-only    # Only validate, don't fix
        """,
  )

  parser.add_argument(
      "input_file",
      type=Path,
      help="Path to the input JSON file from langextract",
  )

  parser.add_argument(
      "output_file",
      type=Path,
      nargs="?",
      help="Path to save the fixed JSON file (default: input_file_fixed.json)",
  )

  parser.add_argument(
      "--validate-only",
      action="store_true",
      help="Only validate the hierarchy, don't apply fixes",
  )

  parser.add_argument(
      "--verbose", "-v", action="store_true", help="Enable verbose logging"
  )

  args = parser.parse_args()

  # Setup logging
  setup_logging(args.verbose)

  # Validate input file exists
  if not args.input_file.exists():
    logging.error(f"Input file does not exist: {args.input_file}")
    sys.exit(1)

  # Determine output file path
  if not args.output_file:
    stem = args.input_file.stem
    suffix = args.input_file.suffix
    args.output_file = args.input_file.parent / f"{stem}_fixed{suffix}"

  # Load input data
  logging.info(f"Loading data from: {args.input_file}")
  data = load_json_file(args.input_file)

  # Print initial statistics
  print_statistics(data, "BEFORE")

  if args.validate_only:
    # Only validate
    logging.info("Validating hierarchy...")
    issues = validate_hierarchy(data)

    if issues:
      logging.warning(f"Found {len(issues)} hierarchy issues:")
      for issue in issues:
        logging.warning(f"  - {issue}")
      sys.exit(1)
    else:
      logging.info("Hierarchy validation passed - no issues found")
      sys.exit(0)

  # Apply fixes
  logging.info("Applying hierarchy fixes...")
  try:
    fix_hierarchy_and_merge_duplicates(data)
    logging.info("Hierarchy fixes applied successfully")
  except Exception as e:
    logging.error(f"Error applying fixes: {e}")
    if args.verbose:
      import traceback

      traceback.print_exc()
    sys.exit(1)

  # Print final statistics
  print_statistics(data, "AFTER")

  # Validate the result
  logging.info("Validating fixed hierarchy...")
  issues = validate_hierarchy(data)
  if issues:
    logging.warning(f"Validation found {len(issues)} remaining issues:")
    for issue in issues:
      logging.warning(f"  - {issue}")
  else:
    logging.info("Final validation passed - hierarchy is clean")

  # Save the fixed data
  save_json_file(data, args.output_file)

  logging.info("Processing complete!")


if __name__ == "__main__":
  main()
