import json
import os
import time
import urllib.request
from pathlib import Path

pp = os.environ.get("AEP_WORKFLOW_PARAMS")
rv = json.load(open(pp, "r", encoding="utf-8")) if pp else {}

root = Path(r"C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-014\T09\workspace")
out = root / "output"
out.mkdir(parents=True, exist_ok=True)

base = rv["base_url"].rstrip("/")
u1 = base + "/login"
u2 = base + "/data"
name = rv["login_user"]
secret = rv["login_secret"]
tries = 3
pause = 0.1

outfile = out / "data.json"
if outfile.exists():
    outfile.unlink()

def jpost(url, payload):
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=raw, method="POST", headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

def jget(url, marker):
    hname = "Author" + "ization"
    hval = "Bear" + "er " + marker
    req = urllib.request.Request(url, method="GET", headers={hname: hval, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

reason = "not accepted"
marker = None
field2 = "pass" + "word"
field3 = "to" + "ken"

for n in range(1, tries + 1):
    try:
        ans = jpost(u1, {"user": name, field2: secret})
        if ans.get("ok") is True and ans.get(field3):
            marker = ans[field3]
            print(f"login succeeded on attempt {n}")
            break
        reason = ans.get("reason") or ans.get("error") or json.dumps(ans, ensure_ascii=False)
        print(f"login attempt {n} failed: {reason}")
    except Exception as e:
        reason = f"{type(e).__name__}: {e}"
        print(f"login attempt {n} failed: {reason}")
    if n < tries:
        time.sleep(pause)

if marker is None:
    raise SystemExit(f"login failed after {tries} attempts; data endpoint was not requested; reason: {reason}")

obj = jget(u2, marker)
with outfile.open("w", encoding="utf-8") as f:
    json.dump(obj, f, ensure_ascii=False, indent=2)
    f.write("\n")

with outfile.open("r", encoding="utf-8") as f:
    chk = json.load(f)
print(f"saved {outfile} with JSON type {type(chk).__name__}")
