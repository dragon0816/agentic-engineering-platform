from pathlib import Path
import json
import re
from decimal import Decimal, InvalidOperation
from copy import deepcopy

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input' / 'testplan.json'
OUTDIR = WORKSPACE / 'output'
OUT_JSON = OUTDIR / 'testplan.json'
OUT_WARN = OUTDIR / 'warnings.json'

OUTDIR.mkdir(parents=True, exist_ok=True)

with INPUT.open('r', encoding='utf-8') as f:
    data = json.load(f)

warnings = []
number_unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)\s*$')

def decimal_to_json_number(d: Decimal):
    # Keep whole-number MHz values as int (e.g. 2.4GHz -> 2400); otherwise use float.
    if d == d.to_integral_value():
        return int(d)
    return float(d)

def transform(node, path='$'):
    if isinstance(node, list):
        return [transform(item, f'{path}[{i}]') for i, item in enumerate(node)]
    if isinstance(node, dict):
        new_obj = {}
        converted_here = False
        for key, value in node.items():
            cur_path = f'{path}.{key}'
            if key == 'frequency':
                if isinstance(value, str):
                    m = number_unit_re.match(value)
                    if m:
                        num_s, unit = m.group(1), m.group(2)
                        unit_l = unit.lower()
                        if unit_l in ('ghz', 'mhz'):
                            try:
                                num = Decimal(num_s)
                                mhz = num * (Decimal(1000) if unit_l == 'ghz' else Decimal(1))
                                new_obj[key] = decimal_to_json_number(mhz)
                                converted_here = True
                            except InvalidOperation:
                                new_obj[key] = value
                                warnings.append({'path': cur_path, 'value': value, 'warning': 'invalid numeric value; left unchanged'})
                        else:
                            new_obj[key] = value
                            warnings.append({'path': cur_path, 'value': value, 'warning': f'unknown frequency unit {unit}; left unchanged'})
                    else:
                        new_obj[key] = value
                        warnings.append({'path': cur_path, 'value': value, 'warning': 'frequency string has no recognized unit; left unchanged'})
                else:
                    # Numeric and other non-string values are preserved; only strings with GHz/MHz are converted.
                    new_obj[key] = transform(value, cur_path) if isinstance(value, (dict, list)) else value
            else:
                new_obj[key] = transform(value, cur_path)
        if converted_here:
            new_obj['frequency_unit'] = 'MHz'
        return new_obj
    return node

result = transform(data)

with OUT_JSON.open('w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
with OUT_WARN.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen outputs and check stated requirements.
with OUT_JSON.open('r', encoding='utf-8') as f:
    saved = json.load(f)
with OUT_WARN.open('r', encoding='utf-8') as f:
    saved_warnings = json.load(f)

# Expected exact structure for this input, preserving non-frequency fields and array order.
expected = {
  "name": "RF plan",
  "description": "frequency values in GHz or MHz; keep this text",
  "center_frequency": "2.4GHz",
  "bands": [
    {
      "label": "WLAN 2G",
      "frequency": 2400,
      "bandwidth": "20MHz",
      "power": 18,
      "frequency_unit": "MHz"
    },
    {
      "label": "WLAN 5G",
      "frequency": 5000,
      "bandwidth": "80MHz",
      "power": 17,
      "frequency_unit": "MHz"
    },
    {
      "label": "ISM",
      "frequency": 2400,
      "timeout": 30,
      "frequency_unit": "MHz"
    }
  ],
  "sub": {
    "nested": [
      {
        "frequency": 915,
        "power": 10
      },
      {
        "frequency": "100kHz",
        "note": "LF"
      }
    ]
  },
  "timeout": 120
}

checks = []
checks.append(('output JSON exists', OUT_JSON.exists()))
checks.append(('warnings JSON exists', OUT_WARN.exists()))
checks.append(('converted only exact frequency GHz/MHz strings and added units', saved == expected))
checks.append(('center_frequency unchanged', saved.get('center_frequency') == '2.4GHz'))
checks.append(('band array order preserved', [b.get('label') for b in saved['bands']] == ['WLAN 2G', 'WLAN 5G', 'ISM']))
checks.append(('numeric frequency preserved without frequency_unit', saved['sub']['nested'][0] == {'frequency': 915, 'power': 10}))
checks.append(('unknown unit preserved', saved['sub']['nested'][1]['frequency'] == '100kHz'))
checks.append(('one warning recorded for unknown unit', len(saved_warnings) == 1 and saved_warnings[0]['path'] == '$.sub.nested[1].frequency' and saved_warnings[0]['value'] == '100kHz'))
checks.append(('input file still exists and was not overwritten in output step', INPUT.exists() and INPUT.resolve() != OUT_JSON.resolve()))

failed = [name for name, ok in checks if not ok]
print('Wrote:', OUT_JSON)
print('Wrote:', OUT_WARN)
print('Warnings:', json.dumps(saved_warnings, ensure_ascii=False))
print('Checks:')
for name, ok in checks:
    print(('[OK] ' if ok else '[FAIL] ') + name)
if failed:
    raise SystemExit('Verification failed: ' + '; '.join(failed))
print('All verification checks passed.')