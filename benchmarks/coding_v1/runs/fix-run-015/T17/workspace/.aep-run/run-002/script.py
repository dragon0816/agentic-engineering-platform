import json
import re
from pathlib import Path
from collections import OrderedDict

ws = Path.cwd()
infile = ws / 'input' / 'testplan.json'
outdir = ws / 'output'
outdir.mkdir(parents=True, exist_ok=True)
outfile = outdir / 'testplan.json'
warnfile = outdir / 'warnings.json'

warnings = []
num_unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z]+)\s*$')

with infile.open('r', encoding='utf-8') as f:
    data = json.load(f, object_pairs_hook=OrderedDict)

def fmt_path(path):
    if not path:
        return '$'
    s = '$'
    for part in path:
        if isinstance(part, int):
            s += f'[{part}]'
        else:
            s += '.' + part
    return s

def to_int_if_whole(x):
    return int(x) if abs(x - int(x)) < 1e-12 else x

def transform(node, path=()):
    if isinstance(node, list):
        return [transform(item, path + (i,)) for i, item in enumerate(node)]
    if isinstance(node, dict):
        new = OrderedDict()
        for key, value in node.items():
            if key == 'frequency':
                if isinstance(value, str):
                    m = num_unit_re.match(value)
                    if m:
                        number = float(m.group(1))
                        unit = m.group(2).lower()
                        if unit == 'ghz':
                            new[key] = to_int_if_whole(number * 1000.0)
                            new['frequency_unit'] = 'MHz'
                        elif unit == 'mhz':
                            new[key] = to_int_if_whole(number)
                            new['frequency_unit'] = 'MHz'
                        else:
                            new[key] = value
                            warnings.append({
                                'path': fmt_path(path + (key,)),
                                'value': value,
                                'warning': f'Unknown frequency unit: {m.group(2)}'
                            })
                    else:
                        new[key] = value
                        warnings.append({
                            'path': fmt_path(path + (key,)),
                            'value': value,
                            'warning': 'Frequency string is not a recognized value with GHz/MHz unit'
                        })
                else:
                    # Numeric or other non-string frequency values are preserved as-is.
                    new[key] = value
            else:
                new[key] = transform(value, path + (key,))
        return new
    return node

transformed = transform(data)

with outfile.open('w', encoding='utf-8') as f:
    json.dump(transformed, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnfile.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

print(f'Wrote {outfile}')
print(f'Wrote {warnfile}')
print(f'Warnings: {len(warnings)}')
for w in warnings:
    print(f"WARNING {w['path']}: {w['value']} ({w['warning']})")

# Verification: reopen outputs and confirm stated requirements on the actual saved files.
with outfile.open('r', encoding='utf-8') as f:
    out = json.load(f, object_pairs_hook=OrderedDict)
with warnfile.open('r', encoding='utf-8') as f:
    saved_warnings = json.load(f)

errors = []
converted = []
numeric_preserved = []
unknown_preserved = []
non_frequency_unit_strings = []

def compare_structure(src, dst, path=()):
    if isinstance(src, dict):
        if not isinstance(dst, dict):
            errors.append(f'{fmt_path(path)} type changed from object to {type(dst).__name__}')
            return
        src_keys = list(src.keys())
        dst_keys = list(dst.keys())
        # dst may only add frequency_unit immediately after converted frequency fields.
        di = 0
        for si, k in enumerate(src_keys):
            if di >= len(dst_keys) or dst_keys[di] != k:
                errors.append(f'{fmt_path(path)} key order/content changed near key {k!r}: {dst_keys}')
                return
            sv = src[k]
            dv = dst[k]
            if k == 'frequency':
                if isinstance(sv, str):
                    m = num_unit_re.match(sv)
                    if m and m.group(2).lower() in ('ghz', 'mhz'):
                        expected = float(m.group(1)) * (1000.0 if m.group(2).lower() == 'ghz' else 1.0)
                        expected = to_int_if_whole(expected)
                        if dv != expected or not isinstance(dv, (int, float)):
                            errors.append(f'{fmt_path(path+(k,))} expected numeric {expected!r}, got {dv!r}')
                        if di + 1 >= len(dst_keys) or dst_keys[di+1] != 'frequency_unit' or dst.get('frequency_unit') != 'MHz':
                            errors.append(f'{fmt_path(path)} missing frequency_unit="MHz" immediately after converted frequency')
                        else:
                            di += 1
                            converted.append(fmt_path(path+(k,)))
                    else:
                        if dv != sv:
                            errors.append(f'{fmt_path(path+(k,))} unknown-unit string changed')
                        unknown_preserved.append(fmt_path(path+(k,)))
                else:
                    if dv != sv or type(dv) is not type(sv):
                        errors.append(f'{fmt_path(path+(k,))} numeric/non-string frequency not preserved')
                    if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                        numeric_preserved.append(fmt_path(path+(k,)))
                di += 1
            else:
                # Other fields and values must not be changed, except recursive additions inside them.
                compare_structure(sv, dv, path+(k,))
                if isinstance(sv, str) and re.search(r'(?i)\b(?:ghz|mhz)\b', sv):
                    non_frequency_unit_strings.append(fmt_path(path+(k,)))
                di += 1
        if di != len(dst_keys):
            errors.append(f'{fmt_path(path)} has unexpected extra keys: {dst_keys[di:]}')
    elif isinstance(src, list):
        if not isinstance(dst, list):
            errors.append(f'{fmt_path(path)} type changed from array to {type(dst).__name__}')
            return
        if len(src) != len(dst):
            errors.append(f'{fmt_path(path)} array length changed from {len(src)} to {len(dst)}')
            return
        for i, (sv, dv) in enumerate(zip(src, dst)):
            compare_structure(sv, dv, path+(i,))
    else:
        if src != dst or type(src) is not type(dst):
            errors.append(f'{fmt_path(path)} changed from {src!r} ({type(src).__name__}) to {dst!r} ({type(dst).__name__})')

compare_structure(data, out)
if saved_warnings != warnings:
    errors.append('warnings.json content does not match generated warnings')
expected_warning_paths = {'$.sub.nested[1].frequency'}
actual_warning_paths = {w.get('path') for w in saved_warnings}
if actual_warning_paths != expected_warning_paths:
    errors.append(f'warning paths expected {expected_warning_paths}, got {actual_warning_paths}')

print('\nVerification from saved outputs:')
print('converted frequency fields:', converted)
print('numeric frequency fields preserved:', numeric_preserved)
print('unknown-unit frequency strings preserved:', unknown_preserved)
print('non-frequency unit-bearing strings left untouched:', non_frequency_unit_strings)
print('warning records:', len(saved_warnings))
if errors:
    print('VERIFY FAILED')
    for e in errors:
        print('ERROR:', e)
    raise SystemExit(1)
print('VERIFY PASSED')