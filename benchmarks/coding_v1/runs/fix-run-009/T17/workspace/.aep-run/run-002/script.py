import json, re, os, hashlib
from pathlib import Path
from collections import OrderedDict

ws = Path.cwd()
input_path = ws / 'input' / 'testplan.json'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

before_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()

with input_path.open('r', encoding='utf-8') as f:
    data = json.load(f, object_pairs_hook=OrderedDict)

warnings = []
unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([GM]Hz)\s*$', re.IGNORECASE)

def path_to_str(path):
    if not path:
        return '$'
    s = '$'
    for part in path:
        if isinstance(part, int):
            s += f'[{part}]'
        else:
            s += '.' + part
    return s

def mhz_number(value, unit):
    n = float(value)
    if unit.lower() == 'ghz':
        n *= 1000
    # MHz remains as-is
    if n.is_integer():
        return int(n)
    return n

def transform(node, path=()):
    if isinstance(node, list):
        return [transform(item, path + (idx,)) for idx, item in enumerate(node)]
    if isinstance(node, OrderedDict):
        new_obj = OrderedDict()
        for key, value in node.items():
            if key == 'frequency':
                if isinstance(value, str):
                    m = unit_re.match(value)
                    if m:
                        converted = mhz_number(m.group(1), m.group(2))
                        new_obj[key] = converted
                        new_obj['frequency_unit'] = 'MHz'
                    else:
                        new_obj[key] = value
                        warnings.append({
                            'path': path_to_str(path + (key,)),
                            'value': value,
                            'warning': 'Unknown frequency unit; value left unchanged'
                        })
                else:
                    # Numeric and all non-string values are preserved as-is.
                    new_obj[key] = value
            else:
                new_obj[key] = transform(value, path + (key,))
        return new_obj
    return node

transformed = transform(data)

with output_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(transformed, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen outputs and confirm requirements.
with output_path.open('r', encoding='utf-8') as f:
    out_data = json.load(f, object_pairs_hook=OrderedDict)
with warnings_path.open('r', encoding='utf-8') as f:
    out_warnings = json.load(f)
after_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()

errors = []
if before_hash != after_hash:
    errors.append('input/testplan.json changed')

# Specific checks from observed input.
try:
    if out_data['center_frequency'] != data['center_frequency']:
        errors.append('center_frequency was changed even though its name is not exactly frequency')
    bands = out_data['bands']
    expected_band_freqs = [2400, 5000, 2400]
    for i, expected in enumerate(expected_band_freqs):
        if bands[i]['frequency'] != expected:
            errors.append(f'bands[{i}].frequency expected {expected}, got {bands[i].get("frequency")!r}')
        if bands[i].get('frequency_unit') != 'MHz':
            errors.append(f'bands[{i}].frequency_unit missing or not MHz')
    if out_data['sub']['nested'][0]['frequency'] != 915:
        errors.append('numeric frequency was not preserved')
    if 'frequency_unit' in out_data['sub']['nested'][0]:
        errors.append('numeric frequency received frequency_unit unexpectedly')
    if out_data['sub']['nested'][1]['frequency'] != '100kHz':
        errors.append('unknown-unit frequency string was not preserved')
    if len(out_warnings) != 1 or out_warnings[0].get('path') != '$.sub.nested[1].frequency':
        errors.append(f'warnings did not record expected unknown unit: {out_warnings!r}')
    if [b['label'] for b in out_data['bands']] != [b['label'] for b in data['bands']]:
        errors.append('array order changed in bands')
    # Other named fields preserve values.
    if out_data['description'] != data['description'] or out_data['timeout'] != data['timeout']:
        errors.append('unrelated root fields changed')
    if out_data['bands'][0]['bandwidth'] != data['bands'][0]['bandwidth']:
        errors.append('non-frequency field bandwidth changed')
except Exception as exc:
    errors.append(f'check exception: {exc}')

if errors:
    print('VERIFICATION FAILED')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)

print('Wrote:', output_path.relative_to(ws))
print('Wrote:', warnings_path.relative_to(ws))
print('Converted frequency strings:')
print(' - $.bands[0].frequency: "2.4GHz" -> 2400 MHz')
print(' - $.bands[1].frequency: "5 GHz" -> 5000 MHz')
print(' - $.bands[2].frequency: "2400MHz" -> 2400 MHz')
print('Warnings:', len(out_warnings), out_warnings)
print('Verified: input unchanged, exact-name frequency only, converted GHz/MHz strings to numeric MHz, added frequency_unit only to converted objects, preserved numeric frequency, recorded unknown unit warning, preserved unrelated fields and array order.')