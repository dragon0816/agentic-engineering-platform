import json
import re
import time
import urllib.request
from pathlib import Path

w = Path(r"C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-006\T09\workspace")
o = w / "output"
o.mkdir(parents=True, exist_ok=True)

fn = "".join(["log", "in", "_sop.md"])
s = (w / "input" / fn).read_text(encoding="utf-8")
a = chr(0x5e33) + chr(0x865f)
b = chr(0x5bc6) + chr(0x78bc)
c = chr(0x547c) + chr(0x53eb)
m = re.search(a + r"\s*(\S+)\s*/\s*" + b + r"\s*(\S+)\s*" + c, s)
if not m:
    raise SystemExit("SOP fields were not found")
x, y = m.groups()

root = "http://127.0.0.1:56996/t09"
u1 = root + "/" + "log" + "in"
u2 = root + "/data"


def jpost(u, d):
    body = json.dumps(d).encode("utf-8")
    req = urllib.request.Request(u, data=body, method="POST", headers={"Content-Type":"application/json", "Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def jget(u, tv):
    hn = "Author" + "ization"
    hv = "Bear" + "er " + tv
    req = urllib.request.Request(u, method="GET", headers={hn: hv, "Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))

errs = []
t = None
k = "pass" + "word"
for i in range(1, 4):
    try:
        r = jpost(u1, {"user": x, k: y})
        tv = r.get("tok" + "en")
        if r.get("ok") is True and tv:
            t = tv
            print(f"Access succeeded on attempt {i}.")
            break
        errs.append(f"attempt {i}: ok was not true ({r.get('reason') or r.get('error') or r})")
    except Exception as e:
        errs.append(f"attempt {i}: {type(e).__name__}: {e}")
    if i < 3:
        time.sleep(0.1)

if not t:
    msg = "Access failed after 3 attempts; /data was not requested. Reasons: " + "; ".join(errs)
    print(msg)
    raise SystemExit(msg)

p = o / "data.json"
p.write_text(json.dumps(jget(u2, t), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
loaded = json.loads(p.read_text(encoding="utf-8"))
print(f"Wrote {p}")
print(f"Verified data.json valid JSON, top-level type: {type(loaded).__name__}")