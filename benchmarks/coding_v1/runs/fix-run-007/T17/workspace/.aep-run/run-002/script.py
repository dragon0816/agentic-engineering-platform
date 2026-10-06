from pathlib import Path
import json, re, hashlib
from decimal import Decimal
from collections import OrderedDict

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
out_dir = workspace / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
output_path = out_dir / 'testplan.json'
warnings_path = out_dir / 'warnings.json'

before_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()

with input_path.open('r', encoding='utf-8') as f:
    original = json.load(f, object_pairs_hook=OrderedDict)

unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)
number_with_unitish_re = re.compile(r'^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*([A-Za-z]+)\s*$')
warnings = []
converted_count = 0
numeric_preserved_count = 0
unknown_count = 0

def path_to_string(path):
    if not path:
        return '$'
    s = '$'
    for part in path:
        if isinstance(part, int):
            s += f'[{part}]'
        else:
            s += '.' + str(part)
    return s

def dec_to_json_number(d: Decimal):
    d = d.normalize()
    if d == d.to_integral_value():
        return int(d)
    return float(d)

def transform(node, path=()):
    global converted_count, numeric_preserved_count, unknown_count
    if isinstance(node, OrderedDict):
        new = OrderedDict()
        for key, value in node.items():
            if key == 'frequency':
                if isinstance(value, str):
                    m = unit_re.match(value)
                    if m:
                        amount = Decimal(m.group(1))
                        unit = m.group(2).lower()
                        mhz = amount * (Decimal(1000) if unit == 'ghz' else Decimal(1))
                        new[key] = dec_to_json_number(mhz)
                        new['frequency_unit'] = 'MHz'
                        converted_count += 1
                    else:
                        new[key] = value
                        # A frequency string with a numeric value and some unit-like suffix, but not GHz/MHz.
                        m2 = number_with_unitish_re.match(value)
                        if m2:
                            warning = {
                                'path': path_to_string(path + (key,)),
                                'value': value,
                                'message': 'Unknown frequency unit; value left unchanged'
                            }
                            warnings.append(warning)
                            unknown_count += 1
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    new[key] = value
                    numeric_preserved_count += 1
                else:
                    new[key] = transform(value, path + (key,))
            else:
                new[key] = transform(value, path + (key,))
        return new
    if isinstance(node, list):
        return [transform(item, path + (i,)) for i, item in enumerate(node)]
    return node

transformed = transform(original)

with output_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(transformed, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8', newline='\n') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

after_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
print('Converted frequency strings:', converted_count)
print('Numeric frequency values preserved:', numeric_preserved_count)
print('Warnings recorded:', len(warnings))
print('Input unchanged:', before_hash == after_hash)
print('Wrote:', output_path.relative_to(workspace))
print('Wrote:', warnings_path.relative_to(workspace))
if warnings:
    print('Warning sample:', json.dumps(warnings[:5], ensure_ascii=False, indent=2))

# Verification by reopening outputs
with output_path.open('r', encoding='utf-8') as f:
    saved = json.load(f, object_pairs_hook=OrderedDict)
with warnings_path.open('r', encoding='utf-8') as f:
    saved_warnings = json.load(f)

verify_converted = 0
verify_numeric_preserved = 0
verify_warnings = []

def is_json_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def compare(orig, out, path=()):
    global verify_converted, verify_numeric_preserved
    if isinstance(orig, OrderedDict):
        assert isinstance(out, OrderedDict), f'Type changed at {path_to_string(path)}'
        orig_keys = list(orig.keys())
        out_keys = list(out.keys())
        oi = 0
        for ok in orig_keys:
            assert oi < len(out_keys), f'Missing key {ok} at {path_to_string(path)}'
            assert out_keys[oi] == ok, f'Key order/name changed at {path_to_string(path)}: expected {ok}, got {out_keys[oi]}'
            ov = orig[ok]
            nv = out[ok]
            if ok == 'frequency' and isinstance(ov, str) and unit_re.match(ov):
                m = unit_re.match(ov)
                expected = Decimal(m.group(1)) * (Decimal(1000) if m.group(2).lower() == 'ghz' else Decimal(1))
                expected_num = dec_to_json_number(expected)
                assert nv == expected_num and is_json_number(nv), f'Bad conversion at {path_to_string(path+(ok,))}: {nv} != {expected_num}'
                verify_converted += 1
                oi += 1
                assert oi < len(out_keys) and out_keys[oi] == 'frequency_unit', f'Missing frequency_unit immediately after {path_to_string(path+(ok,))}'
                assert out['frequency_unit'] == 'MHz', f'frequency_unit not MHz at {path_to_string(path)}'
            elif ok == 'frequency' and is_json_number(ov):
                assert nv == ov and type(nv) is type(ov), f'Numeric frequency not preserved at {path_to_string(path+(ok,))}'
                verify_numeric_preserved += 1
            else:
                compare(ov, nv, path + (ok,))
            oi += 1
        # Permit only inserted frequency_unit keys after converted frequency values.
        allowed_extra_positions = []
        oi = 0
        for ok in orig_keys:
            ov = orig[ok]
            oi += 1
            if ok == 'frequency' and isinstance(ov, str) and unit_re.match(ov):
                allowed_extra_positions.append(oi)
                oi += 1
        expected_len = len(orig_keys) + len(allowed_extra_positions)
        assert len(out_keys) == expected_len, f'Unexpected extra/missing keys at {path_to_string(path)}: {out_keys}'
    elif isinstance(orig, list):
        assert isinstance(out, list), f'Type changed at {path_to_string(path)}'
        assert len(orig) == len(out), f'Array length changed at {path_to_string(path)}'
        for i, (ov, nv) in enumerate(zip(orig, out)):
            compare(ov, nv, path + (i,))
    else:
        assert out == orig and type(out) is type(orig), f'Value changed at {path_to_string(path)}: {orig!r} -> {out!r}'

compare(original, saved)
assert saved_warnings == warnings, 'warnings.json content changed on reopen'
assert before_hash == after_hash, 'Input file was modified'
assert verify_converted == converted_count, 'Converted count mismatch'
assert verify_numeric_preserved == numeric_preserved_count, 'Numeric preserved count mismatch'

print('Verification passed:')
print(' - output/testplan.json re-opened and recursive object/array structure checked')
print(' - only frequency strings with GHz/MHz were converted to MHz numbers')
print(' - frequency_unit: MHz inserted after converted frequency fields')
print(' - numeric frequency values preserved with original numeric type')
print(' - other fields/values and array lengths/order checked unchanged')
print(' - warnings.json re-opened; warning count:', len(saved_warnings))
print(' - input/testplan.json SHA-256 unchanged:', before_hash)