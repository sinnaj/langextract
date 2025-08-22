from __future__ import annotations
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import Popen, PIPE, STDOUT
from threading import Thread
from typing import Optional, List

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO_ROOT / "output_runs"

@dataclass
class RunState:
    run_id: str
    status: str = "running"  # running|finished|error
    started_at: float = field(default_factory=lambda: time.time())
    ended_at: Optional[float] = None
    log_path: Optional[Path] = None
    stats: Optional[dict] = None
    buffer: List[str] = field(default_factory=list)
    exit_code: Optional[int] = None

class Runner:
    def __init__(self, run_id: str, env: dict, args: list[str], run_dir: Path):
        self.state = RunState(run_id=run_id)
        self.run_dir = run_dir
        self.env = env
        self.args = args
        self.proc: Optional[Popen] = None

    def start(self):
        log_path = self.run_dir / "run.log"
        self.state.log_path = log_path
        f = open(log_path, "a", encoding="utf-8", buffering=1)
        self.proc = Popen(self.args, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1, cwd=str(REPO_ROOT), env=self.env)

        def pump():
            assert self.proc and self.proc.stdout
            for line in self.proc.stdout:
                line = line.rstrip("\n")
                f.write(line + "\n")
                self.state.buffer.append(line)
                if line.startswith("STATS:"):
                    try:
                        payload = json.loads(line[len("STATS:"):].strip())
                        self.state.stats = payload
                    except Exception:
                        pass
            code = self.proc.wait()
            self.state.exit_code = int(code) if isinstance(code, int) else None
            self.state.ended_at = time.time()
            self.state.status = "finished" if code == 0 else "error"
            # Fallback stats
            if self.state.stats is None:
                stats_file = self.run_dir / "stats.json"
                if stats_file.exists():
                    try:
                        self.state.stats = json.loads(stats_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
            f.close()
        Thread(target=pump, daemon=True).start()

# Helper to build env and args for a worker that imports and calls makeRun

def build_worker_cmd(run_id: str, payload: dict, run_dir: Path) -> tuple[list[str], dict]:
    py = sys.executable
    worker = REPO_ROOT / "web" / "runner_worker.py"
    args = [py, "-u", str(worker), json.dumps({"run_id": run_id, **payload})]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["LE_RUN_DIR"] = str(run_dir)
    return args, env
