from pathlib import Path
import csv, json, re

base = Path.cwd()
in_dir = base / 'input'
out_dir = base / 'output'
out_dir.mkdir(parents=True, exist_ok=True)

CANON = {
    'device_id': ['device_id','device id','device','id','deviceid'],
    'test_name': ['test_name','test name','test','name','testname'],
    'status': ['status','result'],
    'value': ['value','val','reading','measurement'],
    'unit': ['unit','units'],
}

def norm_key(k):
    return re.sub(r'[^a-z0-9]+', '_', str(k).strip().lower()).strip('_')

def canonical_key(k):
    nk = norm_key(k)
    for c, aliases in CANON.items():
        if nk in [norm_key(a) for a in aliases]:
            return c
    return nk

def normalize_status(s):
    if s is None:
        return None
    t = str(s).strip()
    u = t.upper()
    if u in ('OK','PASS'):
        return 'Pass'
    if u in ('NG','FAIL'):
        return 'Fail'
    return t

def null_if_missing(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == '':
        return None
    return v

def make_record(row):
    mapped = {}
    for k, v in dict(row).items():
        mapped[canonical_key(k)] = v
    return {
        'device_id': None if mapped.get('device_id') is None else str(mapped.get('device_id')),
        'test_name': None if mapped.get('test_name') is None else str(mapped.get('test_name')),
        'status': normalize_status(mapped.get('status')),
        'value': null_if_missing(mapped.get('value')),
        'unit': null_if_missing(mapped.get('unit')),
    }

def parse_csv(path):
    records=[]
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        sample=f.read(4096)
        f.seek(0)
        try:
            dialect=csv.Sniffer().sniff(sample)
        except Exception:
            dialect=csv.excel
        reader=csv.DictReader(f, dialect=dialect)
        for row in reader:
            if row and any(v not in (None,'') for v in row.values()):
                records.append(make_record(row))
    return records

def extract_json_rows(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ('reports','results','data','items','tests'):
            if key in obj and isinstance(obj[key], list):
                return obj[key]
        # if dict of records, preserve values if they are dicts
        vals = list(obj.values())
        if vals and all(isinstance(v, dict) for v in vals):
            return vals
        return [obj]
    return []

def parse_json_file(path):
    with path.open('r', encoding='utf-8-sig') as f:
        data=json.load(f)
    return [make_record(x) for x in extract_json_rows(data) if isinstance(x, dict)]

def split_md_row(line):
    line=line.strip()
    if line.startswith('|'):
        line=line[1:]
    if line.endswith('|'):
        line=line[:-1]
    return [c.strip() for c in line.split('|')]

def is_sep(cells):
    return bool(cells) and all(re.fullmatch(r':?-{3,}:?', c.strip()) for c in cells)

def parse_markdown(path):
    text=path.read_text(encoding='utf-8-sig')
    lines=[ln for ln in text.splitlines() if '|' in ln]
    records=[]
    i=0
    while i < len(lines):
        header=split_md_row(lines[i])
        if i+1 < len(lines) and is_sep(split_md_row(lines[i+1])):
            i += 2
            while i < len(lines):
                cells=split_md_row(lines[i])
                if not cells or len(cells) < 2 or is_sep(cells):
                    i += 1
                    continue
                # Stop table if cell count wildly mismatched? Otherwise pad/truncate.
                if len(cells) < len(header):
                    cells += ['']*(len(header)-len(cells))
                row=dict(zip(header, cells[:len(header)]))
                records.append(make_record(row))
                i += 1
            break
        i += 1
    return records

all_records=[]
files=sorted([p for p in in_dir.iterdir() if p.is_file()])
print('Input files:', [p.name for p in files])
for p in files:
    ext=p.suffix.lower()
    try:
        if ext == '.csv':
            recs=parse_csv(p)
        elif ext == '.json':
            recs=parse_json_file(p)
        elif ext in ('.md', '.markdown'):
            recs=parse_markdown(p)
        else:
            print(f'Skipped unsupported: {p.name}')
            continue
        print(f'Parsed {len(recs)} records from {p.name}')
        all_records.extend(recs)
    except Exception as e:
        print(f'ERROR parsing {p.name}: {e}')
        raise

out_path=out_dir/'reports.json'
with out_path.open('w', encoding='utf-8') as f:
    json.dump(all_records, f, ensure_ascii=False, indent=2)
print(f'Wrote {len(all_records)} records to {out_path}')
print(json.dumps(all_records[:5], ensure_ascii=False, indent=2))