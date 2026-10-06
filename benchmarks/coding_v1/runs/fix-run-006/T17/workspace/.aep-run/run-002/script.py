from pathlib import Path
import json
import re
import hashlib
from collections import OrderedDict

ws = Path.cwd()
input_path = ws / 'input' / 'testplan.json'
out_dir = ws / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
output_path = out_dir / 'testplan_converted.json'
warnings_path = out_dir / 'warnings.json'

before_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()

# Use object_pairs_hook to preserve source object key order while reading.
with input_path.open('r', encoding='utf-8') as f:
    data = json.load(f, object_pairs_hook=OrderedDict)

warnings = []
number_unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)\s*$')

def nice_number(value):
    # Emit integer when exact, e.g. 2400.0 -> 2400.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value

def convert_frequency_string(s):
    m = number_unit_re.match(s)
    if not m:
        return None, None
    magnitude = float(m.group(1))
    unit = m.group(2).lower()
    if unit == 'ghz':
        return nice_number(magnitude * 1000), 'MHz'
    if unit == 'mhz':
        return nice_number(magnitude), 'MHz'
    return None, m.group(2)

def path_to_string(path):
    out = '$'
    for part in path:
        if isinstance(part, int):
            out += f'[{part}]'
        else:
            out += f'.{part}'
    return out

def process(node, path=()):
    if isinstance(node, list):
        for idx, item in enumerate(node):
            process(item, path + (idx,))
    elif isinstance(node, dict):
        # Iterate over a snapshot so adding frequency_unit does not disturb traversal.
        items = list(node.items())
        for key, value in items:
            if key == 'frequency':
                if isinstance(value, str):
                    converted, unit = convert_frequency_string(value)
                    if unit == 'MHz':
                        # Rebuild this object so frequency_unit is inserted immediately
                        # after frequency without moving any existing keys.
                        new_obj = OrderedDict()
                        inserted = False
                        for old_key, old_value in node.items():
                            if old_key == key:
                                new_obj[old_key] = converted
                                new_obj['frequency_unit'] = 'MHz'
                                inserted = True
                            elif old_key == 'frequency_unit' and inserted:
                                # Avoid duplicate/contradictory frequency_unit if present.
                                new_obj[old_key] = 'MHz'
                            else:
                                new_obj[old_key] = old_value
                        node.clear()
                        node.update(new_obj)
                    else:
                        warnings.append(OrderedDict([
                            ('path', path_to_string(path + (key,))),
                            ('value', value),
                            ('warning', 'frequency string has unknown or unsupported unit; value left unchanged')
                        ]))
                # Numeric frequency and all other value types are left unchanged.
            else:
                process(value, path + (key,))

process(data)

with output_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Reopen and validate outputs against the stated requirements.
with output_path.open('r', encoding='utf-8') as f:
    out_data = json.load(f, object_pairs_hook=OrderedDict)
with warnings_path.open('r', encoding='utf-8') as f:
    out_warnings = json.load(f, object_pairs_hook=OrderedDict)
with input_path.open('r', encoding='utf-8') as f:
    original = json.load(f, object_pairs_hook=OrderedDict)

def collect_freqs(node, path=()):
    found = []
    if isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(collect_freqs(item, path + (i,)))
    elif isinstance(node, dict):
        for k, v in node.items():
            if k == 'frequency':
                found.append((path + (k,), v, node))
            found.extend(collect_freqs(v, path + (k,)))
    return found

def comparable_without_converted_freq_units(orig_node, out_node, path=()):
    """Check non-frequency content and array lengths/order recursively."""
    if isinstance(orig_node, list):
        assert isinstance(out_node, list), path_to_string(path)
        assert len(orig_node) == len(out_node), path_to_string(path)
        for i, (a, b) in enumerate(zip(orig_node, out_node)):
            comparable_without_converted_freq_units(a, b, path + (i,))
    elif isinstance(orig_node, dict):
        assert isinstance(out_node, dict), path_to_string(path)
        orig_keys = list(orig_node.keys())
        out_keys_wo_added = [k for k in out_node.keys() if not (k == 'frequency_unit' and k not in orig_node)]
        assert out_keys_wo_added == orig_keys, f'key order/content mismatch at {path_to_string(path)}: {out_keys_wo_added} != {orig_keys}'
        for k in orig_node.keys():
            if k == 'frequency':
                continue
            comparable_without_converted_freq_units(orig_node[k], out_node[k], path + (k,))
    else:
        assert orig_node == out_node, f'value changed at {path_to_string(path)}: {orig_node!r} -> {out_node!r}'

comparable_without_converted_freq_units(original, out_data)

freqs = {path_to_string(p): (v, obj) for p, v, obj in collect_freqs(out_data)}
assert freqs['$.bands[0].frequency'][0] == 2400 and isinstance(freqs['$.bands[0].frequency'][0], int)
assert freqs['$.bands[0].frequency'][1].get('frequency_unit') == 'MHz'
assert freqs['$.bands[1].frequency'][0] == 5000 and isinstance(freqs['$.bands[1].frequency'][0], int)
assert freqs['$.bands[1].frequency'][1].get('frequency_unit') == 'MHz'
assert freqs['$.bands[2].frequency'][0] == 2400 and isinstance(freqs['$.bands[2].frequency'][0], int)
assert freqs['$.bands[2].frequency'][1].get('frequency_unit') == 'MHz'
assert freqs['$.sub.nested[0].frequency'][0] == 915 and isinstance(freqs['$.sub.nested[0].frequency'][0], int)
assert 'frequency_unit' not in freqs['$.sub.nested[0].frequency'][1]
assert freqs['$.sub.nested[1].frequency'][0] == '100kHz'
assert 'frequency_unit' not in freqs['$.sub.nested[1].frequency'][1]
assert out_data['center_frequency'] == original['center_frequency'] == '2.4GHz'
assert out_data['bands'][0]['bandwidth'] == '20MHz'
assert out_data['bands'][1]['bandwidth'] == '80MHz'
assert len(out_data['bands']) == len(original['bands'])
assert len(out_data['sub']['nested']) == len(original['sub']['nested'])
assert len(out_warnings) == 1
assert out_warnings[0]['path'] == '$.sub.nested[1].frequency'
assert out_warnings[0]['value'] == '100kHz'
after_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
assert before_hash == after_hash, 'input file was modified'

print('Wrote:', output_path)
print('Wrote:', warnings_path)
print('Converted frequency fields: $.bands[0].frequency=2400, $.bands[1].frequency=5000, $.bands[2].frequency=2400')
print('Preserved numeric frequency:', freqs['$.sub.nested[0].frequency'][0])
print('Warnings:', out_warnings)
print('Validation passed: output files reopened; only frequency keys with GHz/MHz strings converted; frequency_unit added as MHz to converted objects; numeric and unknown-unit frequencies preserved; non-frequency fields and array lengths/order preserved; input hash unchanged.')
