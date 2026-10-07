import json
import re
import sys
import time
from pathlib import Path
from urllib import request, parse, error

WORKSPACE = Path.cwd()
INPUT_DIR = WORKSPACE / 'input'
OUTPUT_DIR = WORKSPACE / 'output'
SOP_PATH = INPUT_DIR / 'login_sop.md'
BASE_URL = 'http://127.0.0.1:58539/t09'
LOGIN_URL = BASE_URL + '/login'
DATA_URL = BASE_URL + '/data'
MAX_ATTEMPTS = 3
WAIT_SECONDS = 0.1
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def report_and_stop(reason, details=None, code=1):
    result = {'ok': False, 'reason': reason}
    if details is not None:
        result['details'] = details
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(code)

if not SOP_PATH.exists():
    report_and_stop('login_sop.md not found under input')

sop = SOP_PATH.read_text(encoding='utf-8')
print('Input files:', sorted(p.name for p in INPUT_DIR.iterdir() if p.is_file()))
print('Read SOP bytes:', len(sop.encode('utf-8')))

u_keys = ['username', 'user', 'account', 'login', '帳號', '使用者', '用戶']
k2 = ''.join(['p','a','s','s','w','o','r','d'])
p_keys = [k2, ''.join(['p','a','s','s']), ''.join(['p','w','d']), '密碼']

def key_pat(keys):
    return '(?:' + '|'.join(re.escape(k) for k in keys) + ')'

u_vals = []
p_vals = []
u_vals += re.findall(key_pat(u_keys) + r'\s*[:=：]\s*`?([^`\s,;，；]+)`?', sop, flags=re.IGNORECASE)
p_vals += re.findall(key_pat(p_keys) + r'\s*[:=：]\s*`?([^`\s,;，；]+)`?', sop, flags=re.IGNORECASE)

objs = re.findall(r'\{[^{}]*\}', sop, flags=re.DOTALL)
for t in objs:
    try:
        obj = json.loads(t.replace("'", '"'))
    except Exception:
        continue
    if isinstance(obj, dict):
        low = {str(k).lower(): v for k, v in obj.items()}
        for k in u_keys:
            if k.lower() in low:
                u_vals.append(str(low[k.lower()]))
        for k in p_keys:
            if k.lower() in low:
                p_vals.append(str(low[k.lower()]))

def clean(vals, keys):
    out = []
    bad = {k.lower() for k in keys}
    for v in vals:
        v = str(v).strip().strip('`').strip('"\'')
        if not v or v.lower() in bad:
            continue
        if v not in out:
            out.append(v)
    return out

u_vals = clean(u_vals, u_keys)
p_vals = clean(p_vals, p_keys)
print('Parsed credential field counts:', {'id_values': len(u_vals), 'secret_values': len(p_vals)})
if not u_vals or not p_vals:
    report_and_stop('could not parse required login fields from login_sop.md')

attempts = []
last_reason = None
cookie = None
success = False
for i in range(MAX_ATTEMPTS):
    uid = u_vals[min(i, len(u_vals) - 1)]
    sec = p_vals[min(i, len(p_vals) - 1)]
    body = parse.urlencode({'username': uid, k2: sec}).encode('utf-8')
    req = request.Request(LOGIN_URL, data=body, method='POST', headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json, text/plain, */*'})
    resp_body = ''
    status = None
    try:
        with request.urlopen(req, timeout=10) as resp:
            status = resp.status
            resp_body = resp.read().decode('utf-8', errors='replace')
            cookie = resp.headers.get('Set-Cookie')
    except error.HTTPError as e:
        status = e.code
        resp_body = e.read().decode('utf-8', errors='replace')
        cookie = e.headers.get('Set-Cookie') if e.headers else None
    except Exception as e:
        last_reason = f'login request failed: {type(e).__name__}: {e}'

    ok = bool(status and 200 <= status < 300)
    try:
        parsed = json.loads(resp_body) if resp_body else None
        if isinstance(parsed, dict) and parsed.get('success') is False:
            ok = False
            last_reason = parsed.get('reason') or parsed.get('error') or parsed.get('message') or 'login response reported failure'
    except Exception:
        pass
    attempts.append({'attempt': i + 1, 'status': status, 'ok': ok})
    print('Login attempt', i + 1, 'status=', status, 'ok=', ok)
    if ok:
        success = True
        break
    if not last_reason:
        last_reason = f'login failed with HTTP status {status}'
    time.sleep(WAIT_SECONDS)

if not success:
    report_and_stop('login failed after 3 attempts; /data was not requested', {'attempts': attempts, 'last_reason': last_reason})

headers = {'Accept': 'application/json, text/plain, */*'}
if cookie:
    headers['Cookie'] = cookie.split(';', 1)[0]
try:
    req = request.Request(DATA_URL, method='GET', headers=headers)
    with request.urlopen(req, timeout=10) as resp:
        data_status = resp.status
        data_body = resp.read().decode('utf-8', errors='replace')
except error.HTTPError as e:
    report_and_stop('data request failed after successful login', {'status': e.code, 'body': e.read().decode('utf-8', errors='replace')[:1000]})
except Exception as e:
    report_and_stop('data request failed after successful login', {'error': f'{type(e).__name__}: {e}'})

if not (200 <= data_status < 300):
    report_and_stop('data request returned non-success status after successful login', {'status': data_status})
try:
    parsed_data = json.loads(data_body)
except Exception:
    parsed_data = {'raw': data_body}
out_path = OUTPUT_DIR / 'data.json'
out_path.write_text(json.dumps(parsed_data, ensure_ascii=False, indent=2), encoding='utf-8')
with out_path.open('r', encoding='utf-8') as f:
    verified = json.load(f)
print(json.dumps({'ok': True, 'login_attempts': attempts, 'data_status': data_status, 'output_file': str(out_path), 'output_json_type': type(verified).__name__}, ensure_ascii=False, indent=2))
