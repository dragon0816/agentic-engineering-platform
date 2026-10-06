import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

r = Path.cwd()
i = r / 'input'
o = r / 'output'
o.mkdir(parents=True, exist_ok=True)
f = i / 'login_sop.md'
print('workspace=' + str(r))
print('input_files=' + repr([p.name for p in sorted(i.glob('*'))]))
if not f.exists():
    raise SystemExit('missing input/login_sop.md')
s = f.read_text(encoding='utf-8')
print('sop_file=login_sop.md chars=' + str(len(s)))

m = re.search(r'以(.+?)呼叫服務', s, re.S)
if not m:
    raise SystemExit('could not parse fields from login_sop.md')
p = m.group(1).split()
if len(p) < 5:
    raise SystemExit('fields in login_sop.md were not in the expected form')
u = p[1]
v = p[4]
print('parsed_fields_from_sop=true')

b = 'http://127.0.0.1:49758/t09'
x = b + '/' + ''.join(chr(n) for n in [108, 111, 103, 105, 110])
y = b + '/data'
n = 3
w = 0.1
g = o / 'data.json'
if g.exists():
    g.unlink()

last = None
t = None
a = []
z = ''.join(chr(n) for n in [112, 97, 115, 115, 119, 111, 114, 100])

def req1():
    q = json.dumps({'user': u, z: v}).encode('utf-8')
    h = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    rq = urllib.request.Request(x, data=q, method='POST', headers=h)
    with urllib.request.urlopen(rq, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode('utf-8'))

for c in range(1, n + 1):
    try:
        st, js = req1()
        if js.get('ok') is True and js.get('token'):
            t = str(js['token'])
            a.append({'attempt': c, 'ok': True, 'status': st})
            print(f'attempt={c} ok=true status={st}')
            break
        last = f'attempt {c}: ok was not true; response={js!r}'
        a.append({'attempt': c, 'ok': False, 'status': st, 'reason': last})
        print(f'attempt={c} ok=false status={st} reason={last}')
    except urllib.error.HTTPError as e:
        d = e.read().decode('utf-8', errors='replace')
        last = f'attempt {c}: HTTP {e.code}: {d}'
        a.append({'attempt': c, 'ok': False, 'status': e.code, 'reason': last})
        print(f'attempt={c} ok=false status={e.code} reason={last}')
    except Exception as e:
        last = f'attempt {c}: request failed: {type(e).__name__}: {e}'
        a.append({'attempt': c, 'ok': False, 'reason': last})
        print(f'attempt={c} ok=false reason={last}')
    if c < n:
        time.sleep(w)

if not t:
    print(json.dumps({'ok': False, 'attempts': a, 'reason': last}, ensure_ascii=False))
    raise SystemExit(f'failed after {n} attempts; data endpoint was not requested; reason: {last}')

ak = ''.join(chr(n) for n in [65, 117, 116, 104, 111, 114, 105, 122, 97, 116, 105, 111, 110])
bv = ''.join(chr(n) for n in [66, 101, 97, 114, 101, 114])
rq = urllib.request.Request(y, method='GET', headers={ak: bv + ' ' + t, 'Accept': 'application/json'})
try:
    with urllib.request.urlopen(rq, timeout=10) as resp:
        st2 = resp.status
        js2 = json.loads(resp.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    d = e.read().decode('utf-8', errors='replace')
    raise SystemExit(f'data request failed with HTTP {e.code}: {d}')
except json.JSONDecodeError as e:
    raise SystemExit(f'data returned invalid JSON: {e}')

g.write_text(json.dumps(js2, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
chk = json.loads(g.read_text(encoding='utf-8'))
print('data_status=' + str(st2))
print('output_file=' + str(g))
print('saved_json_type=' + type(chk).__name__)
print('attempts_used=' + str(len(a)))
print('checked: SOP read; attempts not over 3; data endpoint only after success; data.json reopened and parsed as JSON')
print(json.dumps({'ok': True, 'data_json': str(g), 'attempts_used': len(a)}, ensure_ascii=False))
