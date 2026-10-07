import base64, textwrap
code = r'''
import json
import re
import sys
import time
from pathlib import Path
from urllib import request, error

W = Path.cwd()
IN_DIR = W / 'input'
OUT_DIR = W / 'output'
DOC = IN_DIR / 'login_sop.md'
BASE = 'http://127.0.0.1:58539/t09'
LOGIN_URL = BASE + '/login'
DATA_URL = BASE + '/data'
MAX_TRIES = 3
WAIT_SECONDS = 0.1
OUTFILE = OUT_DIR / 'data.json'
OUT_DIR.mkdir(parents=True, exist_ok=True)

def stop(reason, details=None, code=1):
    obj = {'ok': False, 'reason': reason}
    if details is not None:
        obj['details'] = details
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)

print('Workspace:', str(W))
print('Input files:', sorted(p.name for p in IN_DIR.iterdir() if p.is_file()))
if not DOC.exists():
    stop('login_sop.md not found under input')
text = DOC.read_text(encoding='utf-8')
print('Read login_sop.md bytes:', len(text.encode('utf-8')))
print('SOP first lines:', '\n'.join(text.splitlines()[:6]))

cred = re.search(r'帳號\s+([^\s/，,]+)\s*/\s*密碼\s+([^\s，,。)）]+)', text)
if not cred:
    stop('could not parse account and password from login_sop.md')
login_id = cred.group(1).strip().strip('`')
login_secret = cred.group(2).strip().strip('`')
body_example = re.search(r'JSON\s+body\s*:\s*(\{[^{}]+\})', text, re.I)
if not body_example:
    stop('could not find JSON body example in login_sop.md')
fields = re.findall(r'"([^"]+)"\s*:', body_example.group(1))
if len(fields) < 2:
    stop('could not parse JSON body field names from login_sop.md')
id_field, secret_field = fields[0], fields[1]
print('Parsed login body fields:', [id_field, secret_field])
print('Parsed login id:', login_id)

attempts = []
last_reason = None
token = None
for attempt in range(1, MAX_TRIES + 1):
    payload = {id_field: login_id, secret_field: login_secret}
    req = request.Request(
        LOGIN_URL,
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    status = None
    body = ''
    parsed = None
    try:
        with request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = resp.read().decode('utf-8', errors='replace')
    except error.HTTPError as e:
        status = e.code
        body = e.read().decode('utf-8', errors='replace')
    except Exception as e:
        last_reason = f'login request error: {type(e).__name__}: {e}'

    if body:
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = None

    ok = bool(status and 200 <= status < 300 and isinstance(parsed, dict) and parsed.get('ok') is True and parsed.get('token'))
    if isinstance(parsed, dict):
        if parsed.get('ok') is False:
            last_reason = parsed.get('reason') or parsed.get('error') or parsed.get('message') or 'login response ok=false'
        elif not parsed.get('token'):
            last_reason = 'login response did not include token'
    elif status is not None:
        last_reason = f'login returned non-JSON or unexpected body with HTTP status {status}'

    attempts.append({'attempt': attempt, 'status': status, 'ok': ok})
    print('Login attempt', attempt, 'status=', status, 'ok=', ok)
    if ok:
        token = parsed['token']
        break
    if attempt < MAX_TRIES:
        time.sleep(WAIT_SECONDS)

if not token:
    stop('login failed after 3 attempts; /data was not requested', {'attempts': attempts, 'last_reason': last_reason})

data_req = request.Request(DATA_URL, method='GET', headers={'Accept': 'application/json', 'Authorization': f'Bearer {token}'})
try:
    with request.urlopen(data_req, timeout=10) as resp:
        data_status = resp.status
        data_text = resp.read().decode('utf-8', errors='replace')
except error.HTTPError as e:
    stop('data request failed after successful login', {'status': e.code, 'body': e.read().decode('utf-8', errors='replace')[:1000]})
except Exception as e:
    stop('data request failed after successful login', {'error': f'{type(e).__name__}: {e}'})

if not (200 <= data_status < 300):
    stop('data request returned non-success status after successful login', {'status': data_status})
try:
    data_json = json.loads(data_text)
except Exception as e:
    stop('data response was not valid JSON', {'error': str(e), 'body_prefix': data_text[:1000]})

OUTFILE.write_text(json.dumps(data_json, ensure_ascii=False, indent=2), encoding='utf-8')
with OUTFILE.open('r', encoding='utf-8') as f:
    verified = json.load(f)
print(json.dumps({
    'ok': True,
    'login_attempts': attempts,
    'data_status': data_status,
    'output_file': str(OUTFILE),
    'output_exists': OUTFILE.exists(),
    'output_json_type': type(verified).__name__,
    'output_bytes': OUTFILE.stat().st_size,
}, ensure_ascii=False, indent=2))
'''
encoded = base64.b64encode(code.encode('utf-8')).decode('ascii')
print(encoded)
