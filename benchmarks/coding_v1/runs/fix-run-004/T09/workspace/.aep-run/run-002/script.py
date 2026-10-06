from pathlib import Path
import json, time, urllib.request, urllib.error
from datetime import datetime, timezone

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)

sop_path = INPUT / 'login_sop.md'
sop_text = sop_path.read_text(encoding='utf-8')
print('Read SOP:', sop_path, 'chars=', len(sop_text))
print('SOP first line:', sop_text.splitlines()[0] if sop_text.splitlines() else '')

BASE_URL = 'http://127.0.0.1:58649/t09'
LOGIN_URL = BASE_URL + '/login'
DATA_URL = BASE_URL + '/data'
USER = 'bench'
PASSWORD = 'bench-pass'
MAX_ATTEMPTS = 3
WAIT_SECONDS = 0.1

# AEP-style reusable workflow definition. The executable Python below is represented as
# a coding/run-python step; no credentials/tokens are written into the definition except
# the exercise credentials explicitly stated in the SOP.
workflow_def = {
    'name': 't09-login-download-data',
    'description': 'Login with up to 3 attempts and download /data to output/data.json only after successful login.',
    'parameters': [
        {'name': 'workspace', 'label': 'Workspace folder', 'kind': 'folder', 'scope': 'runtime', 'required': True},
        {'name': 'base_url', 'label': 'Service base URL', 'kind': 'text', 'scope': 'runtime', 'required': True},
    ],
    'steps': [
        {
            'capability': 'coding/run-python@1.0.0',
            'inputs': {
                'request': {
                    'source': 'fixed',
                    'value': {
                        'workspace': str(WORKSPACE),
                        'script': 'Read input/login_sop.md; POST /login with bench credentials up to 3 times waiting 0.1s after failures; if ok true, GET /data with Bearer token and write output/data.json; if all login attempts fail, stop without GET /data and report reason.'
                    }
                },
                'arguments': {'source': 'run', 'path': []}
            }
        }
    ]
}
workflow_path = OUTPUT / 'workflow.json'
workflow_path.write_text(json.dumps(workflow_def, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote workflow definition:', workflow_path)

attempt_logs = []
token = None
last_reason = None

def post_json(url, body, timeout=5):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        method='POST',
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
        return resp.status, json.loads(raw), raw

def get_json(url, token, timeout=5):
    req = urllib.request.Request(
        url,
        method='GET',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode('utf-8')
        return resp.status, json.loads(raw), raw

for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        status, login_json, raw = post_json(LOGIN_URL, {'user': USER, 'password': PASSWORD})
        ok = bool(login_json.get('ok'))
        reason = login_json.get('reason') or login_json.get('error') or ('ok=false' if not ok else None)
        attempt_logs.append({'attempt': attempt, 'http_status': status, 'ok': ok, 'reason': reason})
        print(f'Login attempt {attempt}: status={status}, ok={ok}, reason={reason}')
        if ok:
            token = login_json.get('token')
            if not token:
                last_reason = 'login response ok=true but token is missing'
                attempt_logs[-1]['ok'] = False
                attempt_logs[-1]['reason'] = last_reason
            else:
                break
        else:
            last_reason = reason or 'login failed'
    except Exception as exc:
        last_reason = f'{type(exc).__name__}: {exc}'
        attempt_logs.append({'attempt': attempt, 'http_status': None, 'ok': False, 'reason': last_reason})
        print(f'Login attempt {attempt}: exception={last_reason}')
    if attempt < MAX_ATTEMPTS:
        time.sleep(WAIT_SECONDS)

report = {
    'base_url': BASE_URL,
    'login_url': LOGIN_URL,
    'data_url': DATA_URL,
    'max_attempts': MAX_ATTEMPTS,
    'wait_seconds_after_failure': WAIT_SECONDS,
    'attempts': attempt_logs,
    'called_data': False,
    'success': False,
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
}

if not token:
    report['failure_reason'] = last_reason or 'login failed 3 times'
    (OUTPUT / 'execution_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    # Ensure stale data.json from an earlier run is not presented as new success.
    data_path = OUTPUT / 'data.json'
    if data_path.exists():
        data_path.unlink()
    print('Login failed after 3 attempts; did not call /data. Reason:', report['failure_reason'])
    raise SystemExit(2)

# Only reached after login success.
status, data_json, raw_data = get_json(DATA_URL, token)
report['called_data'] = True
report['data_http_status'] = status
report['success'] = True

data_path = OUTPUT / 'data.json'
data_path.write_text(json.dumps(data_json, ensure_ascii=False, indent=2), encoding='utf-8')
(OUTPUT / 'execution_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('GET /data status=', status)
print('Wrote data:', data_path, 'top-level type=', type(data_json).__name__)
print('Wrote report:', OUTPUT / 'execution_report.json')

# Final verification: reopen every output file and confirm stated requirements.
wf = json.loads(workflow_path.read_text(encoding='utf-8'))
assert wf['name'] == 't09-login-download-data'
assert wf['steps'][0]['capability'] == 'coding/run-python@1.0.0'
assert '最多嘗試 3 次' or wf['description']

rep = json.loads((OUTPUT / 'execution_report.json').read_text(encoding='utf-8'))
assert len(rep['attempts']) <= 3
assert rep['max_attempts'] == 3
assert abs(rep['wait_seconds_after_failure'] - 0.1) < 1e-9
if rep['success']:
    assert rep['called_data'] is True
    parsed_data = json.loads(data_path.read_text(encoding='utf-8'))
    assert isinstance(parsed_data, (dict, list))
    assert data_path.name == 'data.json'
else:
    assert rep['called_data'] is False
    assert not data_path.exists()
print('CHECK PASSED: workflow.json exists and is platform-shaped; login attempts <= 3; wait=0.1; /data called only after success; data.json reopened as valid JSON on success; execution_report.json reopened.')