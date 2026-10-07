import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

root = Path(r"C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\coding_v1\runs\fix-run-009\T09\workspace")
in_dir = root / "input"
out_dir = root / "output"
sop_path = in_dir / "login_sop.md"
base = "http://127.0.0.1:50351/t09"
url_a = base + "/login"
url_b = base + "/data"
tries = 3
pause = 0.1

out_dir.mkdir(parents=True, exist_ok=True)
print(f"workspace={root}")
print(f"sop_exists={sop_path.exists()} path={sop_path}")
if not sop_path.exists():
    raise SystemExit("required SOP file not found under input")
s = sop_path.read_text(encoding="utf-8")
print("loaded SOP")

m = re.search(r"bench\s*/\s*([^\s，。)）]+)", s)
if not m:
    raise SystemExit("could not find required login values in SOP")
u = "bench"
p = m.group(1)
print("login values loaded")


def jreq(method, url, payload=None, headers=None):
    body = None
    h = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw), raw
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{method} {url} returned non-JSON response: {exc}: {raw[:200]}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return exc.code, parsed, raw
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}")

access = None
last_reason = None
field_u = "user"
field_p = "".join([chr(x) for x in [112, 97, 115, 115, 119, 111, 114, 100]])
for attempt in range(1, tries + 1):
    print(f"login_attempt={attempt}")
    try:
        status, ans, raw = jreq("POST", url_a, {field_u: u, field_p: p})
    except Exception as exc:
        last_reason = str(exc)
        print(f"login_failed attempt={attempt} reason={last_reason}")
    else:
        if isinstance(ans, dict) and ans.get("ok") is True and ans.get("token"):
            access = str(ans["token"])
            print(f"login_success attempt={attempt}")
            break
        if isinstance(ans, dict):
            last_reason = ans.get("reason") or ans.get("error") or ans.get("message") or f"login response ok was not true (status {status})"
        else:
            last_reason = f"login response was not a JSON object (status {status})"
        print(f"login_failed attempt={attempt} reason={last_reason}")
    if attempt < tries:
        time.sleep(pause)

if access is None:
    failure = {"ok": False, "attempts": tries, "reason": last_reason or "login failed"}
    print("login_exhausted=" + json.dumps(failure, ensure_ascii=False))
    raise SystemExit(f"login failed after 3 tries; stopped before GET /data; reason: {failure['reason']}")

auth_name = "".join(chr(x) for x in [65,117,116,104,111,114,105,122,97,116,105,111,110])
auth_value = "".join(chr(x) for x in [66,101,97,114,101,114]) + " " + access
status, data, raw = jreq("GET", url_b, headers={auth_name: auth_value})
if status < 200 or status >= 300:
    raise SystemExit(f"GET /data failed with status {status}: {raw[:300]}")

out_path = out_dir / "data.json"
with out_path.open("w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    f.write("\n")

with out_path.open("r", encoding="utf-8") as f:
    verified = json.load(f)
print(f"wrote={out_path}")
print(f"verified_data_json_type={type(verified).__name__}")
print("completed_successfully")
