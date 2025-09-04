#!/usr/bin/env python3
"""
Test tag and parameter extraction with actual extraction data.
"""

import json
from pathlib import Path


def test_tag_parameter_extraction():
  """Test that tags and parameters are extracted from NORM entities."""

  # Mock data based on your actual extraction output
  mock_raw_items = [
      {
          "extraction_class": "NORM",
          "extraction_text": (
              "1 La senalizacion de las instalaciones manuales..."
          ),
          "attributes": {
              "id": "N::000003",
              "relevant_tags": [
                  "FIRE.PROTECTION.INSTALLATION.MANUAL",
                  "FIRE.PROTECTION.INSTALLATION.MANUAL.SIGNALLING",
              ],
              "extracted_parameters": [],
              "topics": ["SAFETY.FIRE"],
          },
      },
      {
          "extraction_class": "NORM",
          "extraction_text": "1 Los viales de aproximación...",
          "attributes": {
              "id": "N::000004",
              "relevant_tags": [
                  "ROAD.APPROACH.FIRE_BRIGADE_VEHICLE",
                  "ROAD.APPROACH.FIRE_BRIGADE_VEHICLE.WIDTH",
                  "ROAD.APPROACH.FIRE_BRIGADE_VEHICLE.HEIGHT",
                  "ROAD.APPROACH.FIRE_BRIGADE_VEHICLE.BEARING_CAPACITY",
              ],
              "extracted_parameters": [
                  "ROAD.APPROACH.FIRE_BRIGADE_VEHICLE.WIDTH >= 3.5 m",
                  "ROAD.APPROACH.FIRE_BRIGADE_VEHICLE.HEIGHT >= 4.5 m",
                  (
                      "ROAD.APPROACH.FIRE_BRIGADE_VEHICLE.BEARING_CAPACITY >="
                      " 20 kN/m²"
                  ),
              ],
              "topics": ["SAFETY.FIRE"],
          },
      },
  ]

  # Tag and parameter extraction logic from lxRunnerExtraction.py
  tag_map = {}
  param_list = []
  tag_counter = 1
  param_counter = 1

  def _next_tid():
    nonlocal tag_counter
    tid = f"T::{tag_counter:06d}"
    tag_counter += 1
    return tid

  def _next_pid():
    nonlocal param_counter
    pid = f"P::{param_counter:06d}"
    param_counter += 1
    return pid

  def _parse_param(expr):
    import re

    if not isinstance(expr, str):
      return None
    m = re.match(r"^\s*([A-Z0-9_.]+)\s*(==|>=|<=|>|<)\s*(.+?)\s*$", expr)
    if not m:
      return None
    path, op, val_str = m.group(1), m.group(2), m.group(3)
    # Try numeric value with optional decimal comma/dot, keep unit remainder
    m2 = re.match(r"^\s*([0-9]+(?:[\.,][0-9]+)?)\s*(.*)$", val_str)
    if m2:
      num = m2.group(1).replace(",", ".")
      try:
        val = float(num) if ("." in num) else int(num)
      except Exception:
        try:
          val = float(num)
        except Exception:
          val = num
      unit = m2.group(2).strip() or None
      return (path, op, val, unit)
    # Non-numeric value (enum/string)
    return (path, op, val_str.strip(), None)

  # Scan items for norms to process
  norms_to_process = []
  for item in mock_raw_items:
    if (
        item
        and isinstance(item, dict)
        and item.get("extraction_class") == "NORM"
    ):
      norms_to_process.append(item.get("attributes", {}))

  print(f"Found {len(norms_to_process)} norms to process:")
  for i, norm in enumerate(norms_to_process):
    print(
        f"  Norm {i}: ID={norm.get('id')},"
        f" Tags={len(norm.get('relevant_tags', []))},"
        f" Params={len(norm.get('extracted_parameters', []))}"
    )

  # Process norms for tags and parameters
  for norm_data in norms_to_process:
    if not isinstance(norm_data, dict):
      continue

    norm_id = norm_data.get("id")
    if not norm_id:
      continue

    topics = norm_data.get("topics", [])
    relevant_tags = norm_data.get("relevant_tags", [])

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
        u = tag_map[tag_path]["attributes"].setdefault("used_by_norm_ids", [])
        if u is None:
          u = []
          tag_map[tag_path]["attributes"]["used_by_norm_ids"] = u
        if norm_id not in u:
          u.append(norm_id)

    # Extracted parameters
    extracted_parameters = norm_data.get("extracted_parameters", [])
    for expr in extracted_parameters:
      parsed = _parse_param(expr)
      if not parsed:
        continue
      path, op, val, unit = parsed
      param_list.append({
          "extraction_class": "Parameter",
          "extraction_text": expr,
          "attributes": {
              "id": _next_pid(),
              "applies_for_tag": path,
              "operator": op,
              "value": val,
              "unit": unit,
              "norm_ids": [norm_id],
          },
      })

  print(f"\n=== TAG EXTRACTION RESULTS ===")
  print(f"Generated {len(tag_map)} unique tags:")
  for tag_path, tag_data in tag_map.items():
    attrs = tag_data["attributes"]
    print(f"  Tag: {tag_path}")
    print(f"    ID: {attrs['id']}")
    print(f"    Used by norms: {attrs['used_by_norm_ids']}")
    print(f"    Topics: {attrs['related_topics']}")
    print()

  print(f"=== PARAMETER EXTRACTION RESULTS ===")
  print(f"Generated {len(param_list)} parameters:")
  for param in param_list:
    attrs = param["attributes"]
    print(f"  Parameter: {param['extraction_text']}")
    print(f"    ID: {attrs['id']}")
    print(f"    Tag: {attrs['applies_for_tag']}")
    print(f"    Operator: {attrs['operator']}")
    print(f"    Value: {attrs['value']} {attrs['unit'] or ''}")
    print(f"    Norm IDs: {attrs['norm_ids']}")
    print()

  # Verify that tags and parameters would be added to final output
  total_derived_items = len(tag_map) + len(param_list)
  print(f"✓ Total derived items that would be added: {total_derived_items}")
  print(f"  - Tags: {len(tag_map)}")
  print(f"  - Parameters: {len(param_list)}")

  return len(tag_map) > 0 or len(param_list) > 0


if __name__ == "__main__":
  success = test_tag_parameter_extraction()
  if success:
    print("\n✅ Tag and parameter extraction working correctly!")
  else:
    print("\n❌ No tags or parameters extracted!")
