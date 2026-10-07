import runpy
from pathlib import Path
root = Path(r"C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-011\T09\workspace")
runpy.run_path(str(root / "output" / "t09_worker.py"), run_name="__main__")