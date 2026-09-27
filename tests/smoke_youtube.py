"""Opt-in internet smoke test using a short public YouTube video."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import run_worker

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory() as folder:
        sys.exit(run_worker({"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                              "action": "download", "folder": folder,
                              "quality": "最高 480p", "mode": "video"}))
