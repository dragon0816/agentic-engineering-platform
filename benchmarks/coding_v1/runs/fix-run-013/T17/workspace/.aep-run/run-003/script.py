import json, re
from pathlib import Path

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
output_path = workspace / 'output' / 'testplan.json'
warnings_path = workspace / 'output' / 'warnings.json'

src = json.loads(input_path.read_text(encoding='utf-8'))
out = json.loads(output_path.read_text(encoding='utf-8'))
warnings = json.loads(warnings_path.read_text(encoding='utf-8'))

pattern = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)
converted = []
unknown = []
numeric_kept = []

# Verify recursively: same object keys except frequency_unit may be added only to converted objects;
# same list lengths/order; only eligible frequency values may change.
def expected_convert(v):
    m = pattern.match(v) if isinstance(v, str) else None
    if not m:
        return None
    num = float(m.group(1))
    if m.group(2).lower() == 'ghz':
        num *= 1000
    return int(num) if num.is_integer() else num

def pstr(parts):
    s='$'
    for p in parts:
        s += f'[{p}]' if isinstance(p,int) else '.' + str(p)
    return s

def check(a, b, parts=()):
    if isinstance(a, dict):
        assert isinstance(b, dict), f'type changed at {pstr(parts)}'
        exp_keys = list(a.keys())
        b_keys_no_unit = [k for k in b.keys() if k != 'frequency_unit']
        assert b_keys_no_unit == exp_keys, f'keys/order changed at {pstr(parts)}: {b_keys_no_unit} != {exp_keys}'
        should_have_unit = False
        if 'frequency' in a and isinstance(a['frequency'], str):
            conv = expected_convert(a['frequency'])
            if conv is not None:
                assert b['frequency'] == conv, f'frequency not converted at {pstr(parts)}'
                assert isinstance(b['frequency'], (int,float)) and not isinstance(b['frequency'], bool), f'converted frequency not numeric at {pstr(parts)}'
                should_have_unit = True
                converted.append((pstr(parts + ('frequency',)), a['frequency'], b['frequency']))
            else:
                assert b['frequency'] == a['frequency'], f'unknown unit frequency changed at {pstr(parts)}'
                unknown.append((pstr(parts + ('frequency',)), a['frequency']))
        elif 'frequency' in a and isinstance(a['frequency'], (int,float)) and not isinstance(a['frequency'], bool):
            assert b['frequency'] == a['frequency'], f'numeric frequency changed at {pstr(parts)}'
            assert 'frequency_unit' not in b or a.get('frequency_unit') == b.get('frequency_unit'), f'unit added to numeric frequency at {pstr(parts)}'
            numeric_kept.append((pstr(parts + ('frequency',)), a['frequency']))
        if should_have_unit:
            assert b.get('frequency_unit') == 'MHz', f'frequency_unit missing/wrong at {pstr(parts)}'
        else:
            if 'frequency_unit' not in a:
                assert not ('frequency_unit' in b and ('frequency' in a)), f'unexpected frequency_unit at {pstr(parts)}'
        for k in a.keys():
            if not (k == 'frequency' and isinstance(a.get(k), str) and expected_convert(a[k]) is not None):
                check(a[k], b[k], parts + (k,))
    elif isinstance(a, list):
        assert isinstance(b, list), f'type changed at {pstr(parts)}'
        assert len(a) == len(b), f'list length changed at {pstr(parts)}'
        for i, (x,y) in enumerate(zip(a,b)):
            check(x,y,parts+(i,))
    else:
        assert a == b, f'value changed at {pstr(parts)}: {a!r} -> {b!r}'

check(src, out)
assert len(warnings) == len(unknown), f'warnings count {len(warnings)} != unknown {len(unknown)}'
for path, value in unknown:
    assert any(w.get('path') == path and w.get('value') == value for w in warnings), f'missing warning for {path}'

print('CHECK OK')
print('output exists:', output_path.exists(), 'warnings exists:', warnings_path.exists())
print('converted count:', len(converted), converted)
print('numeric frequency kept:', len(numeric_kept), numeric_kept)
print('unknown unit warnings:', len(warnings), warnings)
print('input unchanged readable:', input_path.exists(), 'output files:', sorted(p.name for p in (workspace/'output').iterdir()))
