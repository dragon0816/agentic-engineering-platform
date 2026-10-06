import runpy
from pathlib import Path
worker = Path('output') / 't09_worker.py'
if not worker.exists():
    raise SystemExit(f'Missing worker script: {worker}')
runpy.run_path(str(worker), run_name='__main__')