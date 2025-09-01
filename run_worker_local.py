import json
import sys
from pathlib import Path

# Ensure we can import the runner module
from web import runner_worker as rw

# Default payload file; adjust as needed
payload_path = Path(__file__).with_name('payload_1756231665.json')

if not payload_path.exists():
    print(f"Payload file not found: {payload_path}", file=sys.stderr)
    sys.exit(2)

payload_text = payload_path.read_text(encoding='utf-8')
# Set argv so runner_worker.main reads our JSON as first argument
sys.argv = ['runner_worker.py', payload_text]

rw.main()
