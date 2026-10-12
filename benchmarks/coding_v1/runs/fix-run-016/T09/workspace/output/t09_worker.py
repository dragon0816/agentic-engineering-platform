import json
import re
import time
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
INP = ROOT / "input"
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://127.0.0.1:64493/t09"
URL_A = BASE + "/login"
URL_B = BASE + "/data"
LIMIT = 3
PAUSE = 0.1

print("workspace:", ROOT)
print("input files:", [p.name for p in sorted(INP.glob("*"))])
md = INP / "login_sop.md"
if not md.exists():
    raise SystemExit("login_sop.md not found under input")
txt = md.read_text(encoding="utf-8")
print("login_sop.md size:", md.stat().st_size)
print("attempt limit:", LIMIT)

m = re.search(r"帳號\s+(\S+)\s*/\s*密碼\s+(\S+)\s+呼叫", txt)
if not m:
    raise SystemExit("could not parse login fields from login_sop.md; /data not requested")
v1 = m.group(1)
v2 = m.group(2)


def call_json(method, url, payload=None, headers=None):
    body = None
    hdr = {"Accept": "application/json"}
    if headers:
        hdr.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    req = request.Request(url, data=body, method=method, headers=hdr)
    try:
        with request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"error": raw}
        return exc.code, data
    except Exception as exc:
        return 0, {"error": str(exc)}


def why(status, data):
    if isinstance(data, dict):
        for key in ("reason", "error", "message", "detail"):
            if data.get(key):
                return f"HTTP {status}: {data[key]}"
        return f"HTTP {status}: {json.dumps(data, ensure_ascii=False)}"
    return f"HTTP {status}: {data!r}"

last = "login was not attempted"
tk = None
for n in range(1, LIMIT + 1):
    status, got = call_json("POST", URL_A, {"user": v1, "password": v2})
    ok = bool(isinstance(got, dict) and got.get("ok") is True)
    print(f"login attempt {n}: status={status}, ok={ok}")
    if ok:
        tk = got.get("token")
        if not tk:
            raise SystemExit(f"login attempt {n} returned ok=true but no token; /data not requested")
        break
    last = why(status, got)
    time.sleep(PAUSE)

if not tk:
    old = OUT / "data.json"
    if old.exists():
        old.unlink()
    raise SystemExit(f"login failed after {LIMIT} attempts; /data not requested; reason: {last}")

status, data = call_json("GET", URL_B, headers={"Authorization": f"Bearer {tk}"})
if status < 200 or status >= 300:
    raise SystemExit(f"/data request failed after successful login: {why(status, data)}")

out = OUT / "data.json"
out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
loaded = json.loads(out.read_text(encoding="utf-8"))
if loaded != data:
    raise SystemExit("verification failed: saved data.json does not match /data response")
if loaded in ({}, [], None):
    raise SystemExit("verification failed: data.json is empty")
print("wrote:", out)
print("verified data.json: valid JSON, non-empty, matches /data response")
print("output files:", [p.name for p in sorted(OUT.glob("*"))])
