from pathlib import Path
import json, re, copy, math
from collections import OrderedDict

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

with input_path.open('r', encoding='utf-8') as f:
    data = json.load(f, object_pairs_hook=OrderedDict)

warnings = []
number_unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)\s*$')

def path_to_string(path):
    s = '$'
    for part in path:
        if isinstance(part, int):
            s += f'[{part}]'
        else:
            # JSON-ish dot path for simple keys, bracket otherwise
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', part):
                s += '.' + part
            else:
                s += '[' + json.dumps(part, ensure_ascii=False) + ']'
    return s

def mhz_number(value, unit):
    n = float(value)
    unit_l = unit.lower()
    if unit_l == 'ghz':
        n *= 1000.0
    elif unit_l == 'mhz':
        pass
    else:
        raise ValueError(unit)
    if math.isfinite(n) and n.is_integer():
        return int(n)
    return n

def walk(obj, path=()):
    if isinstance(obj, list):
        return [walk(item, path + (idx,)) for idx, item in enumerate(obj)]
    if isinstance(obj, dict):
        new = OrderedDict()
        for key, value in obj.items():
            if key == 'frequency':
                if isinstance(value, str):
                    m = number_unit_re.match(value)
                    if m and m.group(2).lower() in ('ghz', 'mhz'):
                        new[key] = mhz_number(m.group(1), m.group(2))
                        # Add next to frequency while preserving all existing field order otherwise.
                        new['frequency_unit'] = 'MHz'
                    else:
                        new[key] = value
                        unit = m.group(2) if m else None
                        warnings.append(OrderedDict([
                            ('path', path_to_string(path + (key,))),
                            ('value', value),
                            ('warning', 'frequency string has unknown or unsupported unit; left unchanged'),
                            ('unit', unit)
                        ]))
                else:
                    # Numeric and any non-string value are preserved as-is.
                    new[key] = value
            else:
                new[key] = walk(value, path + (key,))
        return new
    return obj

converted = walk(data)

with output_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(converted, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('Wrote:', output_path)
print('Wrote:', warnings_path)
print('Warnings count:', len(warnings))
for w in warnings:
    print('WARNING:', w['path'], repr(w['value']), 'unit=', w['unit'])

# Verification: reopen outputs and check stated requirements on this input.
with output_path.open('r', encoding='utf-8') as f:
    out = json.load(f, object_pairs_hook=OrderedDict)
with warnings_path.open('r', encoding='utf-8') as f:
    warn_out = json.load(f, object_pairs_hook=OrderedDict)

checks = []
checks.append(('output_json_exists', output_path.exists() and output_path.stat().st_size > 0))
checks.append(('warnings_json_exists', warnings_path.exists() and warnings_path.stat().st_size > 0))
checks.append(('center_frequency_unchanged', out['center_frequency'] == data['center_frequency']))
checks.append(('bands_order_unchanged', [b['label'] for b in out['bands']] == [b['label'] for b in data['bands']]))
checks.append(('ghz_2_4_converted_to_2400', out['bands'][0]['frequency'] == 2400 and isinstance(out['bands'][0]['frequency'], int)))
checks.append(('ghz_5_converted_to_5000', out['bands'][1]['frequency'] == 5000 and isinstance(out['bands'][1]['frequency'], int)))
checks.append(('mhz_2400_converted_to_2400', out['bands'][2]['frequency'] == 2400 and isinstance(out['bands'][2]['frequency'], int)))
checks.append(('frequency_unit_added_to_converted', all(out['bands'][i].get('frequency_unit') == 'MHz' for i in range(3))))
checks.append(('numeric_frequency_preserved_no_unit_added', out['sub']['nested'][0]['frequency'] == 915 and 'frequency_unit' not in out['sub']['nested'][0]))
checks.append(('unknown_unit_preserved', out['sub']['nested'][1]['frequency'] == '100kHz' and 'frequency_unit' not in out['sub']['nested'][1]))
checks.append(('unknown_unit_warning_recorded', len(warn_out) == 1 and warn_out[0]['path'] == '$.sub.nested[1].frequency' and warn_out[0]['value'] == '100kHz'))
checks.append(('other_fields_preserved', out['name'] == data['name'] and out['description'] == data['description'] and out['bands'][0]['bandwidth'] == data['bands'][0]['bandwidth'] and out['timeout'] == data['timeout']))

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(('PASS' if ok else 'FAIL') + ':', name)
if failed:
    raise SystemExit('Verification failed: ' + ', '.join(failed))
print('All verification checks passed.')