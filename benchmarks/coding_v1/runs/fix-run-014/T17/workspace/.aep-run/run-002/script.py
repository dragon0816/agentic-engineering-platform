from pathlib import Path
import json
import re
from decimal import Decimal

workspace = Path.cwd()
input_path = workspace / 'input' / 'testplan.json'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'testplan.json'
warnings_path = output_dir / 'warnings.json'

unit_re = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(GHz|MHz)\s*$', re.IGNORECASE)
warnings = []

def path_to_string(path):
    s = '$'
    for part in path:
        if isinstance(part, int):
            s += f'[{part}]'
        else:
            # JSON object key path notation; use bracket repr for unusual keys
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', part):
                s += '.' + part
            else:
                s += '[' + json.dumps(part, ensure_ascii=False) + ']'
    return s

def decimal_to_json_number(d):
    # Keep values such as 2400 as an integer, otherwise emit a JSON number with decimals.
    if d == d.to_integral_value():
        return int(d)
    return float(d)

def convert_frequency_string(value):
    m = unit_re.match(value)
    if not m:
        return None
    number = Decimal(m.group(1))
    unit = m.group(2).lower()
    if unit == 'ghz':
        number *= Decimal('1000')
    # MHz stays as-is
    return decimal_to_json_number(number)

def transform(node, path=()):
    if isinstance(node, list):
        return [transform(item, path + (idx,)) for idx, item in enumerate(node)]
    if isinstance(node, dict):
        out = {}
        converted_here = False
        for key, value in node.items():
            if key == 'frequency':
                if isinstance(value, str):
                    converted = convert_frequency_string(value)
                    if converted is not None:
                        out[key] = converted
                        out['frequency_unit'] = 'MHz'
                        converted_here = True
                    else:
                        out[key] = value
                        warnings.append({
                            'path': path_to_string(path + (key,)),
                            'value': value,
                            'warning': 'frequency string has an unknown or unsupported unit; value left unchanged'
                        })
                else:
                    # Numeric and all non-string values are preserved exactly except nested containers are not expected here.
                    out[key] = transform(value, path + (key,)) if isinstance(value, (dict, list)) else value
            else:
                # If a source object already had frequency_unit after a converted frequency, keep the required MHz marker.
                if converted_here and key == 'frequency_unit':
                    continue
                out[key] = transform(value, path + (key,))
        return out
    return node

with input_path.open('r', encoding='utf-8') as f:
    data = json.load(f)

result = transform(data)

with output_path.open('w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('wrote:', output_path.relative_to(workspace))
print('wrote:', warnings_path.relative_to(workspace))
print('warnings count:', len(warnings))
for warning in warnings:
    print('warning:', warning)
