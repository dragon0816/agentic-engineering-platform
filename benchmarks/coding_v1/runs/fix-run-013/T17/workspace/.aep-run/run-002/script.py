import json, re, os, copy
from pathlib import Path

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

with input_path.open('r', encoding='utf-8') as f:
    data = json.load(f)

warnings = []
pattern = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)

def path_to_str(parts):
    s = '$'
    for p in parts:
        if isinstance(p, int):
            s += f'[{p}]'
        else:
            # JSON object key path; good enough for warning/debug
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', str(p)):
                s += '.' + str(p)
            else:
                s += '[' + json.dumps(str(p), ensure_ascii=False) + ']'
    return s

def convert_value(text):
    m = pattern.match(text)
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    if unit == 'ghz':
        value *= 1000
    # Return int where exact, so 2.4GHz becomes 2400 not 2400.0.
    if value.is_integer():
        return int(value)
    return value

def walk(obj, parts=()):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == 'frequency':
                if isinstance(v, str):
                    converted = convert_value(v)
                    if converted is not None:
                        obj[k] = converted
                        obj['frequency_unit'] = 'MHz'
                    else:
                        warnings.append({
                            'path': path_to_str(parts + (k,)),
                            'value': v,
                            'warning': 'frequency string has unknown or unsupported unit; value left unchanged'
                        })
                # Numeric and all other non-string values are kept as-is, without adding unit.
            else:
                walk(v, parts + (k,))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            walk(item, parts + (i,))

walk(data)

with output_path.open('w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('wrote:', output_path)
print('wrote:', warnings_path)
print('warnings:', len(warnings))
for w in warnings:
    print('warning:', w)
