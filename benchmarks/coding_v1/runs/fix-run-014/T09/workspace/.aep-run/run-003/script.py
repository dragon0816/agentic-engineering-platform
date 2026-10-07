import json
from pathlib import Path

workspace = Path.cwd()
print(f"workspace={workspace}")
print("output files:")
for p in sorted((workspace / "output").glob("**/*")):
    if p.is_file():
        print(f"- {p.relative_to(workspace)} bytes={p.stat().st_size}")

out = workspace / "output" / "data.json"
checks = []
checks.append(("output/data.json exists", out.exists()))
if out.exists():
    checks.append(("output/data.json is non-empty", out.stat().st_size > 0))
    try:
        data = json.loads(out.read_text(encoding="utf-8"))
        checks.append(("output/data.json is valid JSON", True))
        checks.append(("top-level JSON value is an object", isinstance(data, dict)))
        print("data.json top-level type:", type(data).__name__)
        print("data.json keys:", sorted(data.keys()) if isinstance(data, dict) else None)
        print("data.json content:")
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as e:
        checks.append((f"output/data.json is valid JSON ({e})", False))

print("checks:")
failed = False
for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'} - {name}")
    failed = failed or not ok
if failed:
    raise SystemExit(1)
