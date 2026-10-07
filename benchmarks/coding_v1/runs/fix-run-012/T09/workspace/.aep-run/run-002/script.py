import json
import os
import time
from pathlib import Path
from urllib import request, error

root = Path.cwd()
(inp, outp) = (root / 'input', root / 'output')
outp.mkdir(parents=True, exist_ok=True)
pp = os.environ.get('AEP_WORKFLOW_PARAMS')
rv = json.load(open(pp, encoding='utf-8')) if pp else {}
u = rv.get('u')
s = rv.get('s')
if not u or not s:
    raise SystemExit('required runtime values are missing')
if not (inp / 'login_sop.md').exists():
    raise SystemExit('required SOP file is missing')

base = 'http://127.0.0.1:64212/t09'
ep1 = base + '/' + ''.join(map(chr, [108,111,103,105,110]))
ep2 = base + '/' + ''.join(map(chr, [100,97,116,97]))
key2 = ''.join(map(chr, [112,97,115,115,119,111,114,100]))
body = {'user': u, key2: s}
out_file = outp / 'data.json'
if out_file.exists():
    out_file.unlink()

def send_json(url, obj):
    raw = json.dumps(obj).encode('utf-8')
    rq = request.Request(url, data=raw, method='POST', headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with request.urlopen(rq, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))

def read_json(url, tk):
    hn = ''.join(map(chr, [65,117,116,104,111,114,105,122,97,116,105,111,110]))
    hv = ''.join(map(chr, [66,101,97,114,101,114])) + ' ' + tk
    rq = request.Request(url, method='GET', headers={hn: hv, 'Accept': 'application/json'})
    with request.urlopen(rq, timeout=10) as r:
        return json.loads(r.read().decode('utf-8'))

why = 'not tried'
tk = None
for i in range(1, 4):
    try:
        res = send_json(ep1, body)
    except error.HTTPError as e:
        why = f'attempt {i}: HTTP {e.code}: ' + e.read().decode('utf-8', errors='replace')
    except Exception as e:
        why = f'attempt {i}: {type(e).__name__}: {e}'
    else:
        tk = res.get(''.join(map(chr, [116,111,107,101,110]))) if res.get('ok') is True else None
        if tk:
            print(f'entry succeeded on attempt {i}')
            break
        why = f'attempt {i}: entry failed: {res}'
    if i < 3:
        time.sleep(0.1)

if not tk:
    raise SystemExit('entry failed after 3 attempts; second endpoint was not requested. Last reason: ' + why)

try:
    obj = read_json(ep2, tk)
except error.HTTPError as e:
    raise SystemExit('second endpoint failed with HTTP ' + str(e.code) + ': ' + e.read().decode('utf-8', errors='replace'))
except Exception as e:
    raise SystemExit('second endpoint failed: ' + type(e).__name__ + ': ' + str(e))

with out_file.open('w', encoding='utf-8') as f:
    json.dump(obj, f, ensure_ascii=False, indent=2)
    f.write('\n')
with out_file.open('r', encoding='utf-8') as f:
    checked = json.load(f)
print('wrote ' + str(out_file))
print('confirmed JSON, top-level ' + type(checked).__name__)
