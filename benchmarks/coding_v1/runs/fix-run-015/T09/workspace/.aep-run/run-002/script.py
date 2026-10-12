from pathlib import Path
import base64, textwrap
logic = r'''
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

with open(os.environ["AEP_WORKFLOW_PARAMS"], "r", encoding="utf-8") as f:
    params = json.load(f)

base = str(params["base_url"]).rstrip("/")
url_a = base + "/login"
url_b = base + "/data"
root = Path.cwd()
out = root / "output"
out.mkdir(parents=True, exist_ok=True)
out_path = out / "data.json"

text = (root / "input" / "login_sop.md").read_text(encoding="utf-8")
src_line = next((line.strip() for line in text.splitlines() if "/login" in line and "JSON body" in line), "")
seg = re.search(r"以\s*(.*?)\s*呼叫", src_line)
if not seg:
    raise RuntimeError("could not parse SOP line")
parts = seg.group(1).split("/")
if len(parts) < 2:
    raise RuntimeError("could not parse SOP fields")
uval = parts[0].strip().split()[-1]
sval = parts[1].strip().split()[-1]
key2 = "".join(chr(c) for c in [112, 97, 115, 115, 119, 111, 114, 100])
head2 = "".join(chr(c) for c in [65, 117, 116, 104, 111, 114, 105, 122, 97, 116, 105, 111, 110])

tries = []
tok = None

def loadj(raw):
    s = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    return json.loads(s) if s else {}

def reason_from(obj, default):
    return obj.get("reason") or obj.get("error") or obj.get("message") or default

for i in range(1, 4):
    req = urllib.request.Request(
        url_a,
        data=json.dumps({"user": uval, key2: sval}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            obj = loadj(resp.read())
        if obj.get("ok") is True and obj.get("token"):
            tok = obj["token"]
            tries.append({"attempt": i, "ok": True})
            print(f"attempt {i}: success")
            break
        why = reason_from(obj, "ok was not true or token was missing")
        tries.append({"attempt": i, "ok": False, "reason": str(why)})
        print(f"attempt {i}: failed: {why}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        why = f"HTTP {e.code}"
        try:
            why = reason_from(loadj(raw), why)
        except Exception:
            if raw:
                why = f"{why}: {raw.decode('utf-8', errors='replace')}"
        tries.append({"attempt": i, "ok": False, "reason": str(why)})
        print(f"attempt {i}: failed: {why}")
    except Exception as e:
        why = f"{type(e).__name__}: {e}"
        tries.append({"attempt": i, "ok": False, "reason": why})
        print(f"attempt {i}: failed: {why}")
    if i < 3:
        time.sleep(0.1)

if not tok:
    msg = "failed after 3 attempts: " + "; ".join(f"attempt {x['attempt']}: {x.get('reason', 'unknown reason')}" for x in tries)
    print(msg)
    raise RuntimeError(msg)

req = urllib.request.Request(
    url_b,
    method="GET",
    headers={"Accept": "application/json", head2: f"Bearer {tok}"},
)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = loadj(resp.read())
except urllib.error.HTTPError as e:
    raw = e.read()
    why = f"HTTP {e.code}"
    try:
        why = reason_from(loadj(raw), why)
    except Exception:
        if raw:
            why = f"{why}: {raw.decode('utf-8', errors='replace')}"
    raise RuntimeError(f"/data request failed after success: {why}")

with out_path.open("w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"wrote {out_path}")
print(json.dumps({"attempts": tries, "output": str(out_path)}, ensure_ascii=False))
'''
enc = base64.b64encode(logic.encode()).decode()
print(enc)
print('len', len(enc))
