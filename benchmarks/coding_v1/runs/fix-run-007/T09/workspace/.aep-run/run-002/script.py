from pathlib import Path
root = Path.cwd()
out = root / 'output'
out.mkdir(parents=True, exist_ok=True)
worker = out / 't09_worker.py'
worker.write_text(r'''import json
import re
import time
from pathlib import Path
from urllib import request, error

ROOT = Path.cwd()
IN_DIR = ROOT / "input"
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sop_path = IN_DIR / "login_sop.md"
sop_text = sop_path.read_text(encoding="utf-8")
line = next((ln for ln in sop_text.splitlines() if "POST /login" in ln or "/login" in ln), "")
m = re.search(r"帳號\s+([^\s/]+)\s*/\s*密碼\s+([^\s]+)", line)
if not m:
    raise SystemExit("Cannot parse account/password from input/login_sop.md")
user_value = m.group(1)
pass_value = m.group(2)

BASE = "http://127.0.0.1:57997/t09"
LOGIN_URL = BASE + "/login"
DATA_URL = BASE + "/data"
MAX_ATTEMPTS = 3
WAIT_SECONDS = 0.1

def post_json(url, payload):
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def get_json(url, token):
    req = request.Request(
        url,
        method="GET",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    with request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

last_reason = None
token = None
attempts = []
for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        response = post_json(LOGIN_URL, {"user": user_value, "password": pass_value})
        attempts.append({"attempt": attempt, "ok": response.get("ok")})
        if response.get("ok") is True and response.get("token"):
            token = response["token"]
            break
        last_reason = response.get("reason") or response.get("error") or response.get("message") or f"login response ok was not true: {response!r}"
    except error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = ""
        last_reason = f"HTTP {exc.code} during login: {detail}"
        attempts.append({"attempt": attempt, "error": last_reason})
    except Exception as exc:
        last_reason = f"{type(exc).__name__} during login: {exc}"
        attempts.append({"attempt": attempt, "error": last_reason})

    if attempt < MAX_ATTEMPTS:
        time.sleep(WAIT_SECONDS)

if not token:
    raise SystemExit(f"Login failed after {MAX_ATTEMPTS} attempts; /data was not requested. Reason: {last_reason}")

data = get_json(DATA_URL, token)
out_path = OUT_DIR / "data.json"
out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

loaded = json.loads(out_path.read_text(encoding="utf-8"))
print(json.dumps({
    "status": "success",
    "login_attempts": len(attempts),
    "max_attempts": MAX_ATTEMPTS,
    "wait_seconds_after_failed_attempt": WAIT_SECONDS,
    "wrote": str(out_path),
    "output_exists": out_path.exists(),
    "output_is_json": True,
    "data_type": type(loaded).__name__,
    "data_keys": sorted(loaded.keys()) if isinstance(loaded, dict) else None,
}, ensure_ascii=False, indent=2))
''', encoding='utf-8')
print('wrote', worker)
print('input files remain:')
for p in sorted((root/'input').glob('*')):
    print('-', p.name, p.stat().st_size)
print('worker size', worker.stat().st_size)