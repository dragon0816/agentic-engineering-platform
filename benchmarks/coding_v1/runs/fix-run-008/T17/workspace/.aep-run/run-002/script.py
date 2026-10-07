from pathlib import Path
import json
import re
import hashlib
from collections import OrderedDict

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

before_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()

number_unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)
number_any_unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)\s*$')

warnings = []

def numeric_value(text, unit):
    n = float(text)
    if unit.lower() == 'ghz':
        n *= 1000
    # MHz remains as-is
    # emit integer for exact integer values, otherwise float
    if n.is_integer():
        return int(n)
    return n

def walk(value, path='$'):
    if isinstance(value, dict):
        out = OrderedDict()
        for key, child in value.items():
            if key == 'frequency':
                if isinstance(child, str):
                    m = number_unit_re.match(child)
                    if m:
                        out[key] = numeric_value(m.group(1), m.group(2))
                        out['frequency_unit'] = 'MHz'
                    else:
                        out[key] = child
                        unit_match = number_any_unit_re.match(child)
                        detail = {
                            'path': f'{path}.frequency',
                            'value': child,
                            'warning': 'frequency string has unknown or unsupported unit; value kept unchanged'
                        }
                        if unit_match:
                            detail['unit'] = unit_match.group(2)
                        warnings.append(detail)
                elif isinstance(child, (int, float)) and not isinstance(child, bool):
                    out[key] = child
                else:
                    out[key] = walk(child, f'{path}.frequency')
            else:
                out[key] = walk(child, f'{path}.{key}')
        return out
    if isinstance(value, list):
        return [walk(item, f'{path}[{i}]') for i, item in enumerate(value)]
    return value

with input_path.open('r', encoding='utf-8') as f:
    data = json.load(f, object_pairs_hook=OrderedDict)

processed = walk(data)

with output_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(processed, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

after_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
print('Wrote:', output_path.relative_to(workspace))
print('Wrote:', warnings_path.relative_to(workspace))
print('Input SHA256 before:', before_hash)
print('Input SHA256 after :', after_hash)
print('Input unchanged:', before_hash == after_hash)
print('Warnings:', len(warnings))
for w in warnings:
    print(' -', w)
print('Output preview:')
print(output_path.read_text(encoding='utf-8'))

# Verification: reopen outputs and check stated requirements on this input.
with input_path.open('r', encoding='utf-8') as f:
    original = json.load(f, object_pairs_hook=OrderedDict)
with output_path.open('r', encoding='utf-8') as f:
    actual = json.load(f, object_pairs_hook=OrderedDict)
with warnings_path.open('r', encoding='utf-8') as f:
    actual_warnings = json.load(f)

expected = OrderedDict([
    ('name', 'RF plan'),
    ('description', 'frequency values in GHz or MHz; keep this text'),
    ('center_frequency', '2.4GHz'),
    ('bands', [
        OrderedDict([('label', 'WLAN 2G'), ('frequency', 2400), ('frequency_unit', 'MHz'), ('bandwidth', '20MHz'), ('power', 18)]),
        OrderedDict([('label', 'WLAN 5G'), ('frequency', 5000), ('frequency_unit', 'MHz'), ('bandwidth', '80MHz'), ('power', 17)]),
        OrderedDict([('label', 'ISM'), ('frequency', 2400), ('frequency_unit', 'MHz'), ('timeout', 30)]),
    ]),
    ('sub', OrderedDict([
        ('nested', [
            OrderedDict([('frequency', 915), ('power', 10)]),
            OrderedDict([('frequency', '100kHz'), ('note', 'LF')]),
        ])
    ])),
    ('timeout', 120),
])

checks = []
checks.append(('input file unchanged by hash', before_hash == after_hash))
checks.append(('output JSON equals expected recursive conversion', actual == expected))
checks.append(('top-level key order unchanged', list(actual.keys()) == list(original.keys())))
checks.append(('center_frequency not changed', actual['center_frequency'] == original['center_frequency']))
checks.append(('bands array order unchanged by labels', [b['label'] for b in actual['bands']] == [b['label'] for b in original['bands']]))
checks.append(('converted frequency values are numeric', all(isinstance(actual['bands'][i]['frequency'], (int, float)) and not isinstance(actual['bands'][i]['frequency'], bool) for i in range(3))))
checks.append(('frequency_unit added only to converted string frequency objects', [list(b.keys()) for b in actual['bands']] == [list(expected['bands'][i].keys()) for i in range(3)]))
checks.append(('numeric frequency retained with no unit added', actual['sub']['nested'][0] == expected['sub']['nested'][0]))
checks.append(('unknown unit frequency retained', actual['sub']['nested'][1]['frequency'] == '100kHz'))
checks.append(('one warning recorded for unknown unit', len(actual_warnings) == 1 and actual_warnings[0]['path'] == '$.sub.nested[1].frequency' and actual_warnings[0]['value'] == '100kHz'))

failed = [name for name, ok in checks if not ok]
print('Verification checks:')
for name, ok in checks:
    print(('PASS' if ok else 'FAIL') + ': ' + name)
if failed:
    raise SystemExit('Verification failed: ' + '; '.join(failed))