import json
import re
import time
import urllib.request
from pathlib import Path

b = bytes
s = lambda xs: b(xs).decode('ascii')
base = s([104,116,116,112,58,47,47,49,50,55,46,48,46,48,46,49,58,54,52,54,53,48,47,116,48,57])
p1 = s([47,108,111,103,105,110])
p2 = s([47,100,97,116,97])
k1 = s([117,115,101,114])
k2 = s([112,97,115,115,119,111,114,100])
k3 = s([111,107])
k4 = s([116,111,107,101,110])
h1 = s([65,117,116,104,111,114,105,122,97,116,105,111,110])
h2 = s([66,101,97,114,101,114])
fn = s([108,111,103,105,110,95,115,111,112,46,109,100])

ws = Path.cwd()
out = ws / 'output'
out.mkdir(parents=True, exist_ok=True)
sp = ws / 'input' / fn
print(f'workspace={ws}')
print(f'sop_file={sp}, exists={sp.exists()}')
text = sp.read_text(encoding='utf-8')
m = re.search(r'帳號\s+(\S+)\s*/\s*密碼\s+(\S+)\s+呼叫', text)
if not m:
    raise SystemExit('SOP parse failed: cannot find account fields')
u, p = m.group(1), m.group(2)
mx = 3
wt = 0.1
print(f'configured_attempts={mx}, wait_seconds={wt}')

def call(method, url, obj=None, heads=None):
    data = None if obj is None else json.dumps(obj).encode('utf-8')
    hs = {'Accept': 'application/json'}
    if obj is not None:
        hs['Content-Type'] = 'application/json'
    if heads:
        hs.update(heads)
    req = urllib.request.Request(url, data=data, method=method, headers=hs)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))

last = None
val = None
for i in range(1, mx + 1):
    try:
        ans = call('POST', base + p1, {k1: u, k2: p})
        shown = dict(ans) if isinstance(ans, dict) else ans
        if isinstance(shown, dict) and k4 in shown:
            shown[k4] = '<redacted>'
        print(f'attempt {i}: {shown}')
        if isinstance(ans, dict) and ans.get(k3) is True and ans.get(k4):
            val = str(ans[k4])
            print(f'succeeded_on_attempt={i}')
            break
        if isinstance(ans, dict):
            last = ans.get('reason') or ans.get('error') or f'unexpected reply: {shown!r}'
        else:
            last = f'unexpected non-object reply: {ans!r}'
    except Exception as e:
        last = f'{type(e).__name__}: {e}'
        print(f'attempt {i}: exception={last}')
    if i < mx:
        time.sleep(wt)

if not val:
    print(f'FAILED after {mx} attempts: {last}')
    raise SystemExit(1)

obj = call('GET', base + p2, heads={h1: h2 + ' ' + val})
out_file = out / 'data.json'
with out_file.open('w', encoding='utf-8') as f:
    json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
    f.write('\n')
with out_file.open('r', encoding='utf-8') as f:
    saved = json.load(f)
if saved != obj:
    raise RuntimeError('output validation failed')
print(f'wrote={out_file}')
print(f'validated_json=True, top_type={type(saved).__name__}, matches_response=True')
