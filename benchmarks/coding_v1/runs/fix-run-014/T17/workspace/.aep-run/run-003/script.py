from pathlib import Path
import json
import re
from decimal import Decimal

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
output_path = workspace / 'output' / 'testplan.json'
warnings_path = workspace / 'output' / 'warnings.json'

unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)

def path_to_string(path):
    s = '$'
    for part in path:
        if isinstance(part, int):
            s += f'[{part}]'
        elif re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', part):
            s += '.' + part
        else:
            s += '[' + json.dumps(part, ensure_ascii=False) + ']'
    return s

def expected_num(s):
    m = unit_re.match(s)
    if not m:
        return None
    d = Decimal(m.group(1))
    if m.group(2).lower() == 'ghz':
        d *= Decimal('1000')
    if d == d.to_integral_value():
        return int(d)
    return float(d)

with input_path.open('r', encoding='utf-8') as f:
    src = json.load(f)
with output_path.open('r', encoding='utf-8') as f:
    out = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings = json.load(f)

expected_warnings = []
converted_paths = []
numeric_preserved = []
unknown_preserved = []
other_frequency_named = []

# Recursively verify full structure under the user's rules.
def verify(src_node, out_node, path=()):
    if isinstance(src_node, dict):
        assert isinstance(out_node, dict), f'type changed at {path_to_string(path)}'
        src_keys = list(src_node.keys())
        out_keys = list(out_node.keys())
        # Output may add frequency_unit only to objects whose frequency string converted.
        conv = False
        if 'frequency' in src_node and isinstance(src_node['frequency'], str):
            conv = expected_num(src_node['frequency']) is not None
        expected_keys = []
        for k in src_keys:
            expected_keys.append(k)
            if k == 'frequency' and conv:
                expected_keys.append('frequency_unit')
        # If source already had frequency_unit immediately after conversion, no duplicate possible; allow same final key set/order behavior.
        if conv and 'frequency_unit' in src_node:
            expected_keys = []
            seen = set()
            for k in src_keys:
                expected_keys.append(k)
                seen.add(k)
                if k == 'frequency' and 'frequency_unit' not in seen:
                    expected_keys.append('frequency_unit')
            # dict cannot contain duplicate keys; final order check below handles practical case.
            expected_keys = list(out_node.keys()) if set(out_keys) == (set(src_keys) | {'frequency_unit'}) else expected_keys
        assert out_keys == expected_keys, f'keys/order mismatch at {path_to_string(path)}: {out_keys} != {expected_keys}'
        for k, v in src_node.items():
            if k == 'frequency':
                if isinstance(v, str):
                    num = expected_num(v)
                    if num is not None:
                        assert out_node[k] == num, f'converted value mismatch at {path_to_string(path+(k,))}: {out_node[k]} != {num}'
                        assert isinstance(out_node[k], (int, float)) and not isinstance(out_node[k], bool), f'converted value not numeric at {path_to_string(path+(k,))}'
                        assert out_node.get('frequency_unit') == 'MHz', f'missing frequency_unit MHz at {path_to_string(path)}'
                        converted_paths.append(path_to_string(path+(k,)))
                    else:
                        assert out_node[k] == v, f'unknown-unit string changed at {path_to_string(path+(k,))}'
                        expected_warnings.append({'path': path_to_string(path+(k,)), 'value': v})
                        unknown_preserved.append(path_to_string(path+(k,)))
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    assert out_node[k] == v, f'numeric frequency changed at {path_to_string(path+(k,))}'
                    assert 'frequency_unit' not in out_node or 'frequency_unit' in src_node, f'frequency_unit added to numeric frequency at {path_to_string(path)}'
                    numeric_preserved.append(path_to_string(path+(k,)))
                else:
                    verify(v, out_node[k], path+(k,)) if isinstance(v, (dict, list)) else None
            elif conv and k == 'frequency_unit' and k not in out_node:
                pass
            else:
                verify(v, out_node[k], path+(k,))
    elif isinstance(src_node, list):
        assert isinstance(out_node, list), f'array type changed at {path_to_string(path)}'
        assert len(src_node) == len(out_node), f'array length changed at {path_to_string(path)}'
        for i, (sv, ov) in enumerate(zip(src_node, out_node)):
            verify(sv, ov, path+(i,))
    else:
        assert src_node == out_node, f'value changed at {path_to_string(path)}: {out_node!r} != {src_node!r}'

verify(src, out)

assert isinstance(warnings, list), 'warnings.json is not a list'
warning_pairs = [{'path': w.get('path'), 'value': w.get('value')} for w in warnings]
assert warning_pairs == expected_warnings, f'warnings mismatch: {warning_pairs} != {expected_warnings}'

print('CHECK PASSED')
print('output files reopened:', output_path.relative_to(workspace), warnings_path.relative_to(workspace))
print('converted frequency paths:', converted_paths)
print('numeric frequency preserved:', numeric_preserved)
print('unknown frequency strings preserved with warnings:', unknown_preserved)
print('warning count:', len(warnings))
print('root keys preserved except required additions inside converted objects:', list(out.keys()))
