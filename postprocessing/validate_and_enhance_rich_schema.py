from extractionExperiment import OUTPUT_FILE
from postprocessing.enrich_parameters import enrich_parameters
from postprocessing.is_rich_schema import validate_rich_verbose


import json


def validate_and_enhance_rich_schema():
    try:
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        primary, ok, _errs = validate_rich_verbose(data, print_fn=lambda m: print(m))
        if primary is not None:
            # Apply enrichment/repairs and persist if anything changed materially
            before_params = len(primary.get("parameters", []) or [])
            enrich_parameters(primary)
            merge_duplicate_tags(primary)
            autophrase_questions(primary)
            ensure_consequence_ids(primary)
            compute_extended_metrics(primary)
            after_params = len(primary.get("parameters", []) or [])
            # If wrapped, reassign back into data
            if isinstance(data, dict) and isinstance(data.get("extractions"), list) and data["extractions"]:
                data["extractions"][0] = primary
            else:
                data = primary
            if after_params > before_params:
                OUTPUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[INFO] Wrote enriched output to {OUTPUT_FILE} (parameters: {before_params} -> {after_params})")
    except Exception as e:
        print(f"[WARN] Could not validate/enrich rich schema from {OUTPUT_FILE}: {e}", file=sys.stderr)