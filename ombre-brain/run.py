"""Load .env and start Ombre Brain server + auto diary sync."""
import os
import sys
import subprocess
from pathlib import Path

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
        print(f"[run] Loaded {env_path}", flush=True)
    except ImportError:
        print("[run] python-dotenv not available", flush=True)

# Start auto sync scheduler in background (polls every 30 min for new diary entries)
sync_script = Path(__file__).parent / "sync_scheduler.py"
sync_proc = subprocess.Popen(
    [sys.executable, "-u", str(sync_script)],
    stdout=open(Path(__file__).parent / "sync.log", "a", encoding="utf-8"),
    stderr=subprocess.STDOUT,
)
print(f"[run] Sync scheduler started (PID {sync_proc.pid})", flush=True)

# Start OB server (blocks)
sys.path.insert(0, str(Path(__file__).parent / "src"))
import runpy
runpy.run_module("server", run_name="__main__", alter_sys=True)
