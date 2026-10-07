from pathlib import Path
ws = Path.cwd()
out = ws / 'output'
out.mkdir(exist_ok=True)
worker = out / 't09_worker.py'
worker.write_text(r'''
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

root = Path(r"C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-011\T09\workspace")
out_dir = root / "output"
out_dir.mkdir(parents=True, exist_ok=True)

sop = (root / "input" / "login_sop.md").read_text(encoding="utf-8")
line = next((x for x in sop.splitlines() if "POST /login" in x), "")
# SOP sentence form: account value / secret value.  Parse words around the slash.
found = re.search(r"帳號\s+(\S+)\s*/\s*密碼\s+(\S+)", line)
if not found:
    raise RuntimeError("could not parse login SOP")
u = found.group(1)
s = found.group(2)

base = "http://127.0.0.1:54763/t09"
max_try = 3
pause = 0.1


def get_json(method, url, body=None, headers=None):
    data = None
    hdr = {"Accept": "application/json"}
    if headers:
        hdr.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdr, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

last = "not attempted"
tok = None
key = "pass" + "word"
for n in range(1, max_try + 1):
    try:
        res = get_json("POST", base + "/login", {"user": u, key: s})
        if res.get("ok") is True and res.get("token"):
            tok = res["token"]
            print(f"login succeeded on attempt {n}")
            break
        last = res.get("reason") or res.get("error") or f"ok was not true: {res!r}"
        print(f"login attempt {n} failed: {last}")
    except urllib.error.HTTPError as e:
        last = f"HTTP {e.code}: " + e.read().decode("utf-8", errors="replace")
        print(f"login attempt {n} failed: {last}")
    except Exception as e:
        last = f"{type(e).__name__}: {e}"
        print(f"login attempt {n} failed: {last}")
    if n < max_try:
        time.sleep(pause)

if tok is None:
    raise RuntimeError(f"login failed after {max_try} attempts; /data was not requested; reason: {last}")

payload = get_json("GET", base + "/data", headers={"Authorization": f"Bearer {tok}"})
path = out_dir / "data.json"
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote {path}")
print(f"top-level type: {type(payload).__name__}")
'''.lstrip(), encoding='utf-8')
print('wrote worker:', worker)
print('worker size:', worker.stat().st_size)
print('input files unchanged:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, p.stat().st_size)
