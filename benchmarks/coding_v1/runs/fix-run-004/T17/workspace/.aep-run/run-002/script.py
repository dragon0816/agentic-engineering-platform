from pathlib import Path
import json
import re
from decimal import Decimal, InvalidOperation
from copy import deepcopy

workspace = Path('.')
input_path = workspace / 'input' / 'testplan.json'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

print('Processing input file:', input_path)
original_text = input_path.read_text(encoding='utf-8')
print('Input size:', len(original_text), 'characters')
data = json.loads(original_text)
print('Top-level type:', type(data).__name__)

freq_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)
unit_like_re = re.compile(r'^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*([A-Za-z]+)\s*$')
warnings = []
converted_paths = []
unchanged_numeric_paths = []
unknown_unit_paths = []

def decimal_to_json_number(d: Decimal):
    # Convert Decimal MHz values to int where exact integral, otherwise float for JSON numeric output.
    if d == d.to_integral_value():
        return int(d)
    return float(d)

def path_to_string(parts):
    s = '$'
    for part in parts:
        if isinstance(part, int):
            s += f'[{part}]'
        else:
            s += '.' + part
    return s

def transform(obj, path=()):
    if isinstance(obj, list):
        return [transform(item, path + (idx,)) for idx, item in enumerate(obj)]
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            if key == 'frequency':
                cur_path = path + (key,)
                if isinstance(value, str):
                    m = freq_re.match(value)
                    if m:
                        number_text, unit = m.group(1), m.group(2).lower()
                        amount = Decimal(number_text)
                        mhz = amount * Decimal(1000) if unit == 'ghz' else amount
                        new_obj[key] = decimal_to_json_number(mhz)
                        new_obj['frequency_unit'] = 'MHz'
                        converted_paths.append(path_to_string(cur_path))
                    else:
                        new_obj[key] = value
                        um = unit_like_re.match(value)
                        unit = um.group(1) if um else None
                        warning = {
                            'path': path_to_string(cur_path),
                            'value': value,
                            'warning': 'frequency string was not converted because the unit is not GHz or MHz'
                        }
                        if unit:
                            warning['unit'] = unit
                        warnings.append(warning)
                        unknown_unit_paths.append(path_to_string(cur_path))
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    new_obj[key] = value
                    unchanged_numeric_paths.append(path_to_string(cur_path))
                else:
                    # Preserve any other type unchanged. Not a GHz/MHz unit string.
                    new_obj[key] = transform(value, cur_path)
            else:
                new_obj[key] = transform(value, path + (key,))
        return new_obj
    return obj

transformed = transform(data)

output_path.write_text(json.dumps(transformed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Wrote:', output_path)
print('Wrote:', warnings_path)
print('Converted frequency paths:', converted_paths)
print('Numeric frequency paths preserved:', unchanged_numeric_paths)
print('Warnings:', warnings)

# Verification: reopen output files and confirm requirements.
out = json.loads(output_path.read_text(encoding='utf-8'))
warn_out = json.loads(warnings_path.read_text(encoding='utf-8'))

# Helper to compare all non-frequency content and array order, allowing only frequency conversion and inserted frequency_unit.
def verify(orig, new, path=()):
    if isinstance(orig, list):
        assert isinstance(new, list), f'{path_to_string(path)} type changed from list'
        assert len(orig) == len(new), f'{path_to_string(path)} array length changed'
        for i, (a, b) in enumerate(zip(orig, new)):
            verify(a, b, path + (i,))
    elif isinstance(orig, dict):
        assert isinstance(new, dict), f'{path_to_string(path)} type changed from object'
        orig_keys = list(orig.keys())
        new_keys = list(new.keys())
        expected_keys = []
        for k in orig_keys:
            expected_keys.append(k)
            if k == 'frequency' and isinstance(orig[k], str) and freq_re.match(orig[k]):
                expected_keys.append('frequency_unit')
        assert new_keys == expected_keys, f'{path_to_string(path)} keys/order changed: expected {expected_keys}, got {new_keys}'
        for k in orig_keys:
            if k == 'frequency':
                v = orig[k]
                if isinstance(v, str) and freq_re.match(v):
                    m = freq_re.match(v)
                    expected = decimal_to_json_number((Decimal(m.group(1)) * Decimal(1000)) if m.group(2).lower() == 'ghz' else Decimal(m.group(1)))
                    assert new[k] == expected, f'{path_to_string(path+(k,))} expected {expected}, got {new[k]}'
                    assert isinstance(new[k], (int, float)) and not isinstance(new[k], bool), f'{path_to_string(path+(k,))} is not numeric'
                    assert new['frequency_unit'] == 'MHz', f'{path_to_string(path)} frequency_unit missing/wrong'
                else:
                    assert new[k] == v, f'{path_to_string(path+(k,))} should be preserved'
            else:
                verify(orig[k], new[k], path + (k,))
    else:
        assert orig == new, f'{path_to_string(path)} scalar changed'

verify(data, out)
assert isinstance(warn_out, list), 'warnings.json is not a list'
assert len(warn_out) == len(warnings), 'warning count changed on reopen'
assert any(w.get('path') == '$.sub.nested[1].frequency' and w.get('value') == '100kHz' for w in warn_out), 'expected 100kHz warning missing'
assert out['center_frequency'] == data['center_frequency'], 'center_frequency should not be changed because key is not frequency'
assert out['bands'][0]['bandwidth'] == data['bands'][0]['bandwidth'], 'bandwidth should not be changed because key is not frequency'
print('Verification passed: output JSON reopened; recursive conversion, inserted frequency_unit, preserved numeric/unknown values, warning count, object key order, array lengths/order, and non-frequency fields checked.')
