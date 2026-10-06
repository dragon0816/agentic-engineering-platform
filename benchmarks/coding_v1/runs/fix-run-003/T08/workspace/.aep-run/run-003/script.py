from pathlib import Path
import csv, json, re

base = Path.cwd()
in_dir = base / 'input'
out_dir = base / 'output'
out_dir.mkdir(parents=True, exist_ok=True)

ALIASES = {
    'device_id': {'device_id','device id','device','id','deviceid','dut','serial','serial no','serial number'},
    'test_name': {'test_name','test name','test','name','testname','item','parameter'},
    'status': {'status','result','outcome','pass fail','pass/fail'},
    'value': {'value','val','reading','measurement','measured','measure'},
    'unit': {'unit','units'},
}

def norm_key(k):
    return re.sub(r'[^a-z0-9]+', ' ', str(k).strip().lower()).strip()

def canonical_key(k):
    nk = norm_key(k)
    for c, aliases in ALIASES.items():
        if nk in {norm_key(a) for a in aliases}:
            return c
    return re.sub(r'\s+', '_', nk)

def normalize_status(v):
    if v is None:
        return None
    s = str(v).strip()
    u = s.upper()
    if u in {'OK', 'PASS'}:
        return 'Pass'
    if u in {'NG', 'FAIL'}:
        return 'Fail'
    return s if s != '' else None

def value_or_null(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == '':
        return None
    return v

def record_from(row):
    mapped = {}
    for k, v in dict(row).items():
        mapped[canonical_key(k)] = v
    device = mapped.get('device_id')
    test = mapped.get('test_name')
    return {
        'device_id': None if device is None else str(device),
        'test_name': None if test is None else str(test),
        'status': normalize_status(mapped.get('status')),
        'value': value_or_null(mapped.get('value')),
        'unit': value_or_null(mapped.get('unit')),
    }

def parse_csv(path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        return [record_from(row) for row in reader if any(value_or_null(v) is not None for v in row.values())]

def json_rows(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ('reports','results','data','items','tests'):
            if isinstance(obj.get(key), list):
                return obj[key]
        vals = list(obj.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals
        return [obj]
    return []

def parse_json(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    return [record_from(row) for row in json_rows(data) if isinstance(row, dict)]

def md_cells(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [cell.strip() for cell in line.split('|')]

def md_sep(cells):
    return bool(cells) and all(re.fullmatch(r':?-{3,}:?', c.strip()) for c in cells)

def parse_md(path):
    lines = [line for line in path.read_text(encoding='utf-8-sig').splitlines() if '|' in line]
    out = []
    for i in range(len(lines)-1):
        header = md_cells(lines[i])
        if md_sep(md_cells(lines[i+1])):
            for line in lines[i+2:]:
                cells = md_cells(line)
                if not cells or md_sep(cells):
                    continue
                if len(cells) < len(header):
                    cells += [''] * (len(header) - len(cells))
                out.append(record_from(dict(zip(header, cells[:len(header)]))))
            break
    return out

records = []
for path in sorted(in_dir.iterdir()):
    if not path.is_file():
        continue
    ext = path.suffix.lower()
    if ext == '.csv':
        parsed = parse_csv(path)
    elif ext == '.json':
        parsed = parse_json(path)
    elif ext in {'.md', '.markdown'}:
        parsed = parse_md(path)
    else:
        continue
    print(f'{path.name}: {len(parsed)} records')
    records.extend(parsed)

out_path = out_dir / 'reports.json'
out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {len(records)} records to {out_path}')
print(out_path.read_text(encoding='utf-8'))