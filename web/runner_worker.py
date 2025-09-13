from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
from time import sleep, time


def _print(msg: str):
    print(msg, flush=True)


def _run_enhanced_extraction(run_dir: Path, payload: dict):
    """Run enhanced extraction pipeline on uploaded PDF."""
    _print("Starting enhanced extraction...")
    
    # Find uploaded PDF file in input directory
    input_dir = run_dir / "input"
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        _print("ERROR: No PDF file found in input directory")
        stats = {"ok": False, "error": "No PDF file uploaded"}
        (run_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        _print("STATS: " + json.dumps(stats))
        return
    
    pdf_path = pdf_files[0]  # Use first PDF found
    _print(f"Processing PDF: {pdf_path.name}")
    
    # Import and run enhanced extraction
    try:
        REPO_ROOT = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(REPO_ROOT))
        
        from enhanced_lx_runner import run_enhanced_extraction
        
        # Set output directory to run directory
        output_dir = run_dir / "enhanced_output"
        
        _print("Running enhanced extraction pipeline...")
        results = run_enhanced_extraction(
            pdf_path=pdf_path,
            output_dir=output_dir,
            # Pass Arqio Extraction configuration parameters from payload
            MODEL_ID=payload.get("MODEL_ID", "google/gemini-2.0-flash-exp"),
            MODEL_TEMPERATURE=float(payload.get("MODEL_TEMPERATURE", 0.15)),
            MAX_NORMS_PER_5K=int(payload.get("MAX_NORMS_PER_5K", 10)),
            MAX_CHAR_BUFFER=int(payload.get("MAX_CHAR_BUFFER", 5000)),
            EXTRACTION_PASSES=int(payload.get("EXTRACTION_PASSES", 1)),
            INPUT_PROMPTFILE=payload.get("INPUT_PROMPTFILE"),
            INPUT_GLOSSARYFILE=payload.get("INPUT_GLOSSARYFILE"),
            INPUT_EXAMPLESFILE=payload.get("INPUT_EXAMPLESFILE"),
            INPUT_SEMANTCSFILE=payload.get("INPUT_SEMANTCSFILE"),
            INPUT_TEACHFILE=payload.get("INPUT_TEACHFILE")
        )
        
        quality_metrics = results["quality_metrics"]
        _print(f"Extraction completed successfully!")
        _print(f"  - Sections processed: {quality_metrics.total_sections}")
        _print(f"  - Norms extracted: {quality_metrics.total_norms}")
        _print(f"  - Anchoring success: {quality_metrics.anchoring_success_rate():.1%}")
        _print(f"  - Parameter normalization: {quality_metrics.parameter_normalization_coverage:.1%}")
        
        # Create stats for web UI
        stats = {
            "ok": True,
            "enhanced": True,
            "total_sections": quality_metrics.total_sections,
            "total_norms": quality_metrics.total_norms,
            "anchoring_success_rate": quality_metrics.anchoring_success_rate(),
            "parameter_normalization_coverage": quality_metrics.parameter_normalization_coverage,
            "low_confidence_norms": len(quality_metrics.low_confidence_norms),
            "ts": time()
        }
        (run_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        _print("STATS: " + json.dumps(stats))
        
    except Exception as e:
        _print(f"ERROR in enhanced extraction: {e}")
        import traceback
        traceback.print_exc()
        stats = {"ok": False, "error": str(e), "enhanced": True}
        (run_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        _print("STATS: " + json.dumps(stats))


def _run_dummy(run_dir: Path, payload: dict):
    _print("Starting dummy run...")
    for i in range(5):
        _print(f"step {i+1}/5 ...")
        sleep(0.5)
    stats = {"ok": True, "dummy": True, "ts": time()}
    (run_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    _print("STATS: " + json.dumps(stats))
    _print("Dummy run complete.")


def main():
    if len(sys.argv) < 2:
        print("Usage: runner_worker.py <json-payload>", file=sys.stderr)
        sys.exit(2)
    try:
        payload = json.loads(sys.argv[1])
    except Exception as e:
        print(f"Invalid payload: {e}", file=sys.stderr)
        sys.exit(2)

    REPO_ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(REPO_ROOT))
    run_id = payload.get("run_id")
    run_dir = Path(os.environ.get("LE_RUN_DIR", str(REPO_ROOT / "output_runs" / (run_id or "unknown"))))
    run_dir.mkdir(parents=True, exist_ok=True)

    # Map payload to makeRun signature
    RUN_ID = run_id
    MODEL_ID = payload.get("MODEL_ID")
    MODEL_TEMPERATURE = payload.get("MODEL_TEMPERATURE")
    MAX_NORMS_PER_5K = payload.get("MAX_NORMS_PER_5K")
    MAX_CHAR_BUFFER = payload.get("MAX_CHAR_BUFFER")
    EXTRACTION_PASSES = payload.get("EXTRACTION_PASSES")
    INPUT_PROMPTFILE = payload.get("INPUT_PROMPTFILE")
    INPUT_GLOSSARYFILE = payload.get("INPUT_GLOSSARYFILE")
    INPUT_EXAMPLESFILE = payload.get("INPUT_EXAMPLESFILE")
    INPUT_SEMANTCSFILE = payload.get("INPUT_SEMANTCSFILE")
    INPUT_TEACHFILE = payload.get("INPUT_TEACHFILE")

    # Check for uploaded PDF files to determine which runner to use
    input_dir = run_dir / "input"
    pdf_files = list(input_dir.glob("*.pdf")) if input_dir.exists() else []
    
    # If PDF files are present, try enhanced extraction first
    if pdf_files:
        _print("PDF file detected, using enhanced extraction pipeline")
        try:
            _run_enhanced_extraction(run_dir, payload)
            return
        except Exception as e:
            _print(f"Enhanced extraction failed: {e}")
            _print("Falling back to legacy runner...")
    
    # Attempt to import the exact file REPO_ROOT/lxRunnerExtraction.py (legacy runner)
    makeRun = None
    ee_path = REPO_ROOT / "lxRunnerExtraction.py"
    if ee_path.exists():
        try:
            # Remove any cached module to ensure we load latest edits
            if "lxRunnerExtraction" in sys.modules:
                del sys.modules["lxRunnerExtraction"]
            spec = spec_from_file_location("lxRunnerExtraction", ee_path)
            if spec and spec.loader:
                lxRunnerExtraction = module_from_spec(spec)  # type: ignore
                # Ensure the module name is bound to avoid duplicate imports elsewhere
                sys.modules["lxRunnerExtraction"] = lxRunnerExtraction  # type: ignore
                spec.loader.exec_module(lxRunnerExtraction)  # type: ignore
                makeRun = getattr(lxRunnerExtraction, "makeRun", None)
        except Exception as e:
            _print(f"ERROR importing {ee_path}: {e}")
            makeRun = None
    else:
        _print(f"File not found: {ee_path}")

    if makeRun is None:
        _print("lxRunnerExtraction.makeRun not found in repository root; running dummy simulation.")
        _run_dummy(run_dir, payload)
        return

    _print(f"Starting makeRun for RUN_ID={RUN_ID}")
    try:
        # Call with exact signature order
        makeRun(
            RUN_ID,
            MODEL_ID,
            MODEL_TEMPERATURE,
            MAX_NORMS_PER_5K,
            MAX_CHAR_BUFFER,
            EXTRACTION_PASSES,
            INPUT_PROMPTFILE,
            INPUT_GLOSSARYFILE,
            INPUT_EXAMPLESFILE,
            INPUT_SEMANTCSFILE,
            INPUT_TEACHFILE,
        )
        _print("makeRun completed.")
    except Exception as e:
        _print(f"ERROR: {e}")
        # best-effort error stats
        stats = {"ok": False, "error": str(e)}
        (run_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        _print("STATS: " + json.dumps(stats))
        sys.exit(1)


if __name__ == "__main__":
    main()
