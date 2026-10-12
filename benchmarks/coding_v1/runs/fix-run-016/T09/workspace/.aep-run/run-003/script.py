import runpy
from pathlib import Path
root = Path(r"C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-016\T09\workspace")
worker = root / "output" / "t09_worker.py"
print("workspace:", root)
print("worker exists:", worker.exists(), "size:", worker.stat().st_size if worker.exists() else 0)
if not worker.exists():
    raise SystemExit("worker script missing")
runpy.run_path(str(worker), run_name="__main__")