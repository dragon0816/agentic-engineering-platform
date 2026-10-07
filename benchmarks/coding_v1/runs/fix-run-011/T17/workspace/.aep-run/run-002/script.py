from pathlib import Path
import json
import re
from copy import deepcopy

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

with input_path.open('r', encoding='utf-8') as f:
    data = json.load(f)
original = deepcopy(data)

unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)
warnings = []
converted_count = 0
numeric_preserved_count = 0
unknown_count = 0

def fmt_path(parts):
    s = '$'
    for p in parts:
        if isinstance(p, int):
            s += f'[{p}]'
        else:
            s += '.' + p
    return s

def number_for_json(value):
    # Keep integer-looking MHz values as int, otherwise preserve decimals as float.
    if abs(value - round(value)) < 1e-12:
        return int(round(value))
    return value

def walk(node, path_parts):
    global converted_count, numeric_preserved_count, unknown_count
    if isinstance(node, dict):
        # Iterate over a snapshot so adding frequency_unit does not affect traversal.
        for key, value in list(node.items()):
            child_path = path_parts + [key]
            if key == 'frequency':
                if isinstance(value, str):
                    m = unit_re.match(value)
                    if m:
                        amount = float(m.group(1))
                        unit = m.group(2).lower()
                        mhz = amount * 1000 if unit == 'ghz' else amount
                        node[key] = number_for_json(mhz)
                        node['frequency_unit'] = 'MHz'
                        converted_count += 1
                    else:
                        warnings.append({
                            'path': fmt_path(child_path),
                            'value': value,
                            'warning': 'unknown frequency unit; value preserved'
                        })
                        unknown_count += 1
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    numeric_preserved_count += 1
                # Non-string, non-numeric frequency values are preserved silently unless unknown string.
            walk(value, child_path)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            walk(item, path_parts + [i])

walk(data, [])

with output_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen outputs and assert every stated requirement that can be checked.
with output_path.open('r', encoding='utf-8') as f:
    out = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    out_warnings = json.load(f)
with input_path.open('r', encoding='utf-8') as f:
    input_after = json.load(f)
assert input_after == original, 'input/testplan.json was modified'
assert out_warnings == warnings, 'warnings output mismatch'

# Expected checks for this input.
assert out['name'] == original['name']
assert out['description'] == original['description']
assert out['center_frequency'] == original['center_frequency'], 'non-frequency key should not be converted'
assert len(out['bands']) == len(original['bands']), 'array length changed'
assert [b['label'] for b in out['bands']] == [b['label'] for b in original['bands']], 'array order changed'
assert out['bands'][0]['frequency'] == 2400 and isinstance(out['bands'][0]['frequency'], int)
assert out['bands'][0]['frequency_unit'] == 'MHz'
assert out['bands'][0]['bandwidth'] == original['bands'][0]['bandwidth'], 'non-frequency bandwidth changed'
assert out['bands'][1]['frequency'] == 5000 and isinstance(out['bands'][1]['frequency'], int)
assert out['bands'][1]['frequency_unit'] == 'MHz'
assert out['bands'][2]['frequency'] == 2400 and isinstance(out['bands'][2]['frequency'], int)
assert out['bands'][2]['frequency_unit'] == 'MHz'
assert out['sub']['nested'][0]['frequency'] == 915 and 'frequency_unit' not in out['sub']['nested'][0], 'numeric frequency should be preserved without added unit'
assert out['sub']['nested'][1]['frequency'] == '100kHz', 'unknown unit string should be preserved'
assert len(out_warnings) == 1, 'expected exactly one warning'
assert out_warnings[0]['path'] == '$.sub.nested[1].frequency'
assert out_warnings[0]['value'] == '100kHz'

# Generic structural check: no dict/list lengths changed except dicts where frequency_unit was added for converted frequency strings.
def generic_check(src, dst, path='$'):
    if isinstance(src, dict):
        converted_here = False
        if isinstance(src.get('frequency'), str) and unit_re.match(src['frequency']):
            converted_here = True
        src_keys = list(src.keys())
        dst_keys = list(dst.keys())
        expected_keys = src_keys + ([] if not converted_here or 'frequency_unit' in src else ['frequency_unit'])
        assert dst_keys == expected_keys, f'key order/keys changed at {path}: {dst_keys} != {expected_keys}'
        for k in src_keys:
            if k == 'frequency' and isinstance(src[k], str):
                m = unit_re.match(src[k])
                if m:
                    amount = float(m.group(1)); unit = m.group(2).lower()
                    exp = number_for_json(amount * 1000 if unit == 'ghz' else amount)
                    assert dst[k] == exp, f'frequency conversion wrong at {path}.{k}'
                    assert dst['frequency_unit'] == 'MHz', f'missing MHz unit at {path}'
                else:
                    assert dst[k] == src[k], f'unknown frequency string changed at {path}.{k}'
            elif k == 'frequency' and isinstance(src[k], (int, float)) and not isinstance(src[k], bool):
                assert dst[k] == src[k], f'numeric frequency changed at {path}.{k}'
            else:
                generic_check(src[k], dst[k], f'{path}.{k}')
    elif isinstance(src, list):
        assert isinstance(dst, list) and len(dst) == len(src), f'array changed at {path}'
        for i, (a, b) in enumerate(zip(src, dst)):
            generic_check(a, b, f'{path}[{i}]')
    else:
        assert dst == src, f'value changed at {path}'

generic_check(original, out)

print('Wrote:', output_path)
print('Wrote:', warnings_path)
print('converted frequency strings:', converted_count)
print('numeric frequency fields preserved:', numeric_preserved_count)
print('unknown-unit warnings:', unknown_count)
print('verification: reopened outputs, confirmed input unchanged, recursive conversions, frequency_unit additions, numeric preservation, warning content, array order, and non-frequency fields unchanged')
print('warnings:', json.dumps(out_warnings, ensure_ascii=False))