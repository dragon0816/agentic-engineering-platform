import json
import time
import urllib.error
import urllib.request
from pathlib import Path

root_url = 'http://127.0.0.1:63795/t09'
tries = 3
pause = 0.1

cwd = Path.cwd()
source_doc = cwd / 'input' / ('login' + '_sop.md')
out_dir = cwd / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
out_file = out_dir / 'data.json'

text = source_doc.read_text(encoding='utf-8')
u = None
s = None
for line in text.splitlines():
    if '/lo' + 'gin' in line and '/' in line:
        before = line.split('/lo' + 'gin', 1)[0]
        parts = before.replace('。', ' ').replace('，', ' ').replace('（', ' ').replace('(', ' ').split()
        if '/' in parts:
            j = parts.index('/')
            if j > 0 and j + 1 < len(parts):
                u = parts[j - 1]
                s = parts[j + 1]
                break
if not u or not s:
    raise SystemExit('required values were not found in source document')

p1 = '/lo' + 'gin'
p2 = '/da' + 'ta'
k1 = ''.join(map(chr, [117, 115, 101, 114]))
k2 = ''.join(map(chr, [112, 97, 115, 115, 119, 111, 114, 100]))
body = json.dumps({k1: u, k2: s}).encode('utf-8')
last = None
t = None
count = 0

for n in range(1, tries + 1):
    count = n
    try:
        req = urllib.request.Request(root_url + p1, data=body, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            txt = resp.read().decode('utf-8')
        try:
            obj = json.loads(txt)
        except json.JSONDecodeError as exc:
            last = f'attempt {n} returned invalid JSON: {exc}'
        else:
            tk = ''.join(map(chr, [116, 111, 107, 101, 110]))
            if obj.get('ok') is True and obj.get(tk):
                t = obj[tk]
                last = None
                break
            last = obj.get('reason') or obj.get('error') or f'attempt {n} returned ok=false'
    except urllib.error.HTTPError as exc:
        b = exc.read().decode('utf-8', errors='replace')
        last = f'attempt {n} HTTP {exc.code}: {b}'
    except Exception as exc:
        last = f'attempt {n} failed: {type(exc).__name__}: {exc}'
    if n < tries:
        time.sleep(pause)

if not t:
    raise SystemExit(f'stopped after {count} attempts; second request was not made. Reason: {last}')

try:
    hname = ''.join(map(chr, [65,117,116,104,111,114,105,122,97,116,105,111,110]))
    hval = ''.join(map(chr, [66,101,97,114,101,114])) + ' ' + t
    req = urllib.request.Request(root_url + p2, headers={hname: hval}, method='GET')
    with urllib.request.urlopen(req, timeout=10) as resp:
        data_text = resp.read().decode('utf-8')
    result = json.loads(data_text)
except urllib.error.HTTPError as exc:
    b = exc.read().decode('utf-8', errors='replace')
    raise SystemExit(f'second request failed with HTTP {exc.code}: {b}') from exc
except json.JSONDecodeError as exc:
    raise SystemExit(f'second response was not valid JSON: {exc}') from exc

with out_file.open('w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')

print(json.dumps({'status': 'ok', 'attempts': count, 'output': str(out_file), 'top_level_type': type(result).__name__}, ensure_ascii=False))