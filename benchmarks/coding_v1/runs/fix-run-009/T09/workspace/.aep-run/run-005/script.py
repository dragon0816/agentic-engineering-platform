from pathlib import Path
import json, hashlib, os, datetime

ws = Path.cwd()
print(f"workspace={ws}")
print("input files:")
for p in sorted((ws/'input').glob('**/*')):
    if p.is_file():
        print(f"- {p.relative_to(ws)} bytes={p.stat().st_size}")

out = ws/'output'
print("output files:")
for p in sorted(out.glob('**/*')):
    if p.is_file():
        stat = p.stat()
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')
        print(f"- {p.relative_to(ws)} bytes={stat.st_size} mtime={mtime} sha256={sha}")
        if p.name == 'data.json':
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                print(f"  data.json valid_json=True root_type={type(data).__name__} keys={list(data.keys()) if isinstance(data, dict) else 'n/a'}")
                print("  data.json content=" + json.dumps(data, ensure_ascii=False, separators=(',', ':')))
            except Exception as e:
                print(f"  data.json valid_json=False error={e}")

# Check latest workflow run script path mentioned in runtime result exists without modifying it.
run_script = ws/'.aep-run'/'run-004'/'script.py'
print(f"latest_runtime_script_exists={run_script.exists()} path={run_script.relative_to(ws) if run_script.exists() else run_script}")
print("check_complete")