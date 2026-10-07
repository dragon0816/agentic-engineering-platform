from pathlib import Path
import csv, json

base = Path.cwd()
input_dir = base / 'input'
output_dir = base / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}
OUT_FIELDS = ['device_id', 'test_name', 'status', 'value', 'unit']


def clean_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s != '' else None


def normalize_status(v):
    s = clean_text(v)
    if s is None:
        return None
    return STATUS_MAP.get(s.upper(), s)


def normalize_value(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == '':
            return None
        # Convert numeric-looking strings to numbers while preserving nonnumeric data if present.
        try:
            if any(ch in s for ch in '.eE'):
                return float(s)
            return int(s)
        except ValueError:
            return s
    return v


def make_record(device_id, test_name, status, value=None, unit=None):
    return {
        'device_id': '' if device_id is None else str(device_id).strip(),
        'test_name': '' if test_name is None else str(test_name).strip(),
        'status': normalize_status(status),
        'value': normalize_value(value),
        'unit': clean_text(unit),
    }


def read_csv_report(path):
    records = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        print(f'CSV {path.name} headers:', reader.fieldnames)
        for row in reader:
            records.append(make_record(
                row.get('DUT'), row.get('Item'), row.get('Result'),
                row.get('Measurement'), row.get('Unit')
            ))
    return records


def read_json_report(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    print(f'JSON {path.name} top-level:', type(data).__name__)
    if isinstance(data, dict):
        # Accept a common wrapper if present; otherwise treat values that are lists as records.
        for key in ('results', 'records', 'reports', 'data'):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError(f'{path.name} JSON must be a list or contain a list of records')
    records = []
    for row in data:
        if not isinstance(row, dict):
            raise ValueError(f'{path.name} contains non-object row: {row!r}')
        records.append(make_record(
            row.get('device', row.get('device_id')),
            row.get('test', row.get('test_name')),
            row.get('outcome', row.get('status')),
            row.get('value'),
            row.get('unit'),
        ))
    return records


def split_md_row(line):
    line = line.strip()
    if not (line.startswith('|') and line.endswith('|')):
        return None
    return [cell.strip() for cell in line.strip('|').split('|')]


def is_separator_row(cells):
    return all(cell and set(cell.replace(':', '').replace('-', '')) == set() for cell in cells)


def read_markdown_report(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    rows = []
    for line in lines:
        cells = split_md_row(line)
        if cells is not None:
            rows.append(cells)
    if not rows:
        return []
    header = rows[0]
    print(f'Markdown {path.name} headers:', header)
    data_rows = rows[1:]
    if data_rows and is_separator_row(data_rows[0]):
        data_rows = data_rows[1:]
    lower_header = [h.strip().lower() for h in header]
    def idx(name):
        return lower_header.index(name.lower()) if name.lower() in lower_header else None
    i_device = idx('Device')
    i_test = idx('Test')
    i_status = idx('Status')
    i_value = idx('Value')
    i_unit = idx('Unit')
    records = []
    for cells in data_rows:
        # Pad short rows so missing value/unit become None.
        padded = cells + [None] * max(0, len(header) - len(cells))
        records.append(make_record(
            padded[i_device] if i_device is not None else None,
            padded[i_test] if i_test is not None else None,
            padded[i_status] if i_status is not None else None,
            padded[i_value] if i_value is not None else None,
            padded[i_unit] if i_unit is not None else None,
        ))
    return records


all_records = []
source_counts = {}
for path in sorted(input_dir.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        recs = read_csv_report(path)
    elif suffix == '.json':
        recs = read_json_report(path)
    elif suffix in {'.md', '.markdown'}:
        recs = read_markdown_report(path)
    else:
        print('Skipping unsupported file:', path.name)
        continue
    source_counts[path.name] = len(recs)
    all_records.extend(recs)

out_path = output_dir / 'reports.json'
out_path.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding='utf-8')
print('Wrote:', out_path)
print('Source counts:', source_counts)
print('Total records:', len(all_records))
print('Records:', json.dumps(all_records, ensure_ascii=False, indent=2))

# Verification: reopen output file and confirm stated requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'reports.json must contain a JSON array'
assert len(loaded) == sum(source_counts.values()) == 6, f'expected 6 records, got {len(loaded)}'
for i, rec in enumerate(loaded):
    assert list(rec.keys()) == OUT_FIELDS, f'record {i} fields/order mismatch: {list(rec.keys())}'
    assert isinstance(rec['device_id'], str), f'record {i} device_id is not text'
    assert rec['status'] in {'Pass', 'Fail'}, f'record {i} status not normalized: {rec["status"]}'
    assert 'value' in rec and 'unit' in rec, f'record {i} missing value/unit key'
assert loaded[1]['value'] is None, 'CSV missing Measurement should be null'
assert loaded[3]['unit'] is None, 'JSON missing unit should be null'
print('Verification OK: reopened reports.json; checked field names/order, 6 rows, text IDs, normalized statuses, value/unit null placeholders.')