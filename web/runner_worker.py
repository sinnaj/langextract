from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
from time import sleep, time


def _print(msg: str):
    print(msg, flush=True)


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
    INPUT_PROMPTFILE = payload.get("INPUT_PROMPTFILE")
    INPUT_GLOSSARYFILE = payload.get("INPUT_GLOSSARYFILE")
    INPUT_EXAMPLESFILE = payload.get("INPUT_EXAMPLESFILE")
    INPUT_SEMANTCSFILE = payload.get("INPUT_SEMANTCSFILE")
    INPUT_TEACHFILE = payload.get("INPUT_TEACHFILE")

    # Attempt to import the exact file REPO_ROOT/lxRunnerExtraction.py (no other qualifies)
    makeRun = None
    ee_path = REPO_ROOT / "lxRunnerExtraction.py"
    if ee_path.exists():
        try:
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
