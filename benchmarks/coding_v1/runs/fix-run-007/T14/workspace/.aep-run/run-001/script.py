from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
print('Workspace:', workspace)
print('Input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, p.stat().st_size, 'bytes')

csv_path = input_dir / 'large_results.csv'
print('\nInspecting:', csv_path)
with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    headers = next(reader)
    print('Headers:', headers)
    print('Sample rows:')
    for i, row in zip(range(5), reader):
        print(i+1, row)

# Show distinct-ish status/model examples and duration candidates
with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    dr = csv.DictReader(f)
    rows = []
    for i, r in zip(range(1000), dr):
        rows.append(r)

print('\nRow sample count read:', len(rows))
for col in headers:
    lname = col.lower()
    if any(k in lname for k in ['status', 'result', 'pass', 'fail', 'device', 'model', 'duration', 'time', 'second']):
        vals = []
        seen = set()
        for r in rows:
            v = r.get(col, '')
            if v not in seen:
                seen.add(v); vals.append(v)
            if len(vals) >= 10:
                break
        print(f'Column {col!r} sample distinct values:', vals)
