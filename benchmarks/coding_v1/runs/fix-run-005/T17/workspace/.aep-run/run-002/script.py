from pathlib import Path
import json
import re
from decimal import Decimal, InvalidOperation

ws = Path.cwd()
input_path = ws / 'input' / 'testplan.json'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

print('Reading:', input_path)
source_text = input_path.read_text(encoding='utf-8')
data = json.loads(source_text)
print('Loaded top-level type:', type(data).__name__)

freq_pattern = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)\s*$')
warnings = []
converted_count = 0
numeric_preserved_count = 0
unknown_count = 0

def decimal_to_json_number(value: Decimal):
    # Normalize values like 2400.0 to integer 2400, otherwise keep a JSON float.
    if value == value.to_integral_value():
        return int(value)
    return float(value)

def convert_frequency_string(value: str):
    match = freq_pattern.match(value)
    if not match:
        return None
    number_text, unit_text = match.groups()
    unit = unit_text.lower()
    if unit not in {'ghz', 'mhz'}:
        return None
    try:
        number = Decimal(number_text)
    except InvalidOperation:
        return None
    mhz_value = number * Decimal(1000) if unit == 'ghz' else number
    return decimal_to_json_number(mhz_value)

def walk(node, path='$'):
    global converted_count, numeric_preserved_count, unknown_count
    if isinstance(node, list):
        return [walk(item, f'{path}[{idx}]') for idx, item in enumerate(node)]
    if isinstance(node, dict):
        new_obj = {}
        for key, value in node.items():
            current_path = f'{path}.{key}'
            if key == 'frequency':
                if isinstance(value, str):
                    converted = convert_frequency_string(value)
                    if converted is not None:
                        new_obj[key] = converted
                        new_obj['frequency_unit'] = 'MHz'
                        converted_count += 1
                    else:
                        new_obj[key] = value
                        warnings.append({
                            'path': current_path,
                            'value': value,
                            'warning': 'frequency string has an unknown or unsupported unit; value preserved'
                        })
                        unknown_count += 1
                else:
                    new_obj[key] = value
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        numeric_preserved_count += 1
            else:
                new_obj[key] = walk(value, current_path)
        return new_obj
    return node

result = walk(data)

# Write outputs. input/ is not modified.
output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Wrote:', output_path)
print('Wrote:', warnings_path)
print('Converted frequency fields:', converted_count)
print('Numeric frequency fields preserved:', numeric_preserved_count)
print('Warnings:', len(warnings))

# Verification from saved outputs.
saved = json.loads(output_path.read_text(encoding='utf-8'))
saved_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
original = json.loads(input_path.read_text(encoding='utf-8'))

checks = []

def assert_check(name, condition, detail=''):
    checks.append((name, bool(condition), detail))
    if not condition:
        raise AssertionError(f'{name} failed: {detail}')

# Required examples / targeted assertions.
assert_check('top-level center_frequency unchanged because key is not exactly frequency', saved['center_frequency'] == original['center_frequency'], repr(saved.get('center_frequency')))
assert_check('bands[0].frequency converted 2.4GHz to 2400', saved['bands'][0]['frequency'] == 2400, repr(saved['bands'][0]['frequency']))
assert_check('bands[0].frequency_unit added as MHz', saved['bands'][0].get('frequency_unit') == 'MHz', repr(saved['bands'][0]))
assert_check('bands[1].frequency converted 5 GHz to 5000', saved['bands'][1]['frequency'] == 5000, repr(saved['bands'][1]['frequency']))
assert_check('bands[1].frequency_unit added as MHz', saved['bands'][1].get('frequency_unit') == 'MHz', repr(saved['bands'][1]))
assert_check('bands[2].frequency converted 2400MHz to 2400', saved['bands'][2]['frequency'] == 2400, repr(saved['bands'][2]['frequency']))
assert_check('bands[2].frequency_unit added as MHz', saved['bands'][2].get('frequency_unit') == 'MHz', repr(saved['bands'][2]))
assert_check('numeric frequency preserved', saved['sub']['nested'][0]['frequency'] == 915 and 'frequency_unit' not in saved['sub']['nested'][0], repr(saved['sub']['nested'][0]))
assert_check('unknown-unit frequency preserved', saved['sub']['nested'][1]['frequency'] == '100kHz' and 'frequency_unit' not in saved['sub']['nested'][1], repr(saved['sub']['nested'][1]))
assert_check('one warning recorded for unknown unit', len(saved_warnings) == 1 and saved_warnings[0]['path'] == '$.sub.nested[1].frequency', repr(saved_warnings))
assert_check('array order unchanged for bands labels', [x['label'] for x in saved['bands']] == [x['label'] for x in original['bands']], repr([x.get('label') for x in saved['bands']]))
assert_check('other non-frequency fields preserved', saved['description'] == original['description'] and saved['timeout'] == original['timeout'] and saved['bands'][0]['bandwidth'] == original['bands'][0]['bandwidth'], 'description/timeout/bandwidth')

# General recursive verification: only frequency conversions plus inserted frequency_unit keys.
def compare_allowed(orig, new, path='$'):
    if isinstance(orig, dict):
        oi = list(orig.items())
        ni = list(new.items()) if isinstance(new, dict) else []
        j = 0
        for key, oval in oi:
            if j >= len(ni):
                raise AssertionError(f'missing key at {path}.{key}')
            nkey, nval = ni[j]
            if nkey != key:
                raise AssertionError(f'key order/name changed at {path}: expected {key}, got {nkey}')
            if key == 'frequency' and isinstance(oval, str) and convert_frequency_string(oval) is not None:
                expected = convert_frequency_string(oval)
                if nval != expected:
                    raise AssertionError(f'frequency not converted at {path}.{key}: {nval} != {expected}')
                j += 1
                if j >= len(ni) or ni[j][0] != 'frequency_unit' or ni[j][1] != 'MHz':
                    raise AssertionError(f'frequency_unit not inserted after {path}.{key}')
                j += 1
            else:
                compare_allowed(oval, nval, f'{path}.{key}')
                j += 1
        if j != len(ni):
            raise AssertionError(f'unexpected extra keys at {path}: {ni[j:]}')
    elif isinstance(orig, list):
        if not isinstance(new, list) or len(orig) != len(new):
            raise AssertionError(f'list length/type changed at {path}')
        for idx, (oval, nval) in enumerate(zip(orig, new)):
            compare_allowed(oval, nval, f'{path}[{idx}]')
    else:
        if orig != new:
            raise AssertionError(f'value changed at {path}: {orig!r} -> {new!r}')

compare_allowed(original, saved)
assert_check('recursive diff allows only requested conversions and frequency_unit insertions', True)

print('Verification checks:')
for name, ok, detail in checks:
    print(('PASS' if ok else 'FAIL') + ' - ' + name + (f' ({detail})' if detail else ''))
print('Output files:', output_path.relative_to(ws), warnings_path.relative_to(ws))
