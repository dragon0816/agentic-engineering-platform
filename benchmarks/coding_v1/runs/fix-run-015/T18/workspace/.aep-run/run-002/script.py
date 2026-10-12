from pathlib import Path
import subprocess
import sys
from openpyxl import load_workbook
import csv
from collections import defaultdict

base = Path('.').resolve()
out_dir = base / 'output'
out_dir.mkdir(exist_ok=True)

fixed = '''"""Average Value per Model from input.csv into summary.xlsx.

Usage: python export.py --input input.csv --output summary.xlsx
Requires: openpyxl
"""

import argparse
import csv
from pathlib import Path

from openpyxl import Workbook


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    totals = {}
    counts = {}
    with open(args.input, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            model = row["Model"]
            value_text = row["Value"]
            if value_text == "":
                continue
            value = float(value_text)
            totals[model] = totals.get(model, 0.0) + value
            counts[model] = counts.get(model, 0) + 1

    book = Workbook()
    sheet = book.active
    sheet.title = "summary"
    sheet.append(["Model", "Average", "ValidCount"])
    for model in sorted(totals):
        sheet.append([model, totals[model] / counts[model], counts[model]])

    output_path = Path(args.output)
    if output_path.parent:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    book.save(output_path)


if __name__ == "__main__":
    main()
'''

export_path = out_dir / 'export.py'
export_path.write_text(fixed, encoding='utf-8')
print('wrote', export_path)

cmd = [sys.executable, 'output\\export.py', '--input', 'input\\input.csv', '--output', 'output\\summary.xlsx']
print('running:', ' '.join(cmd))
proc = subprocess.run(cmd, cwd=base, text=True, capture_output=True)
print('exit_code=', proc.returncode)
if proc.stdout:
    print('STDOUT:\n' + proc.stdout)
if proc.stderr:
    print('STDERR:\n' + proc.stderr)
if proc.returncode != 0:
    raise SystemExit(proc.returncode)

# Independent expected-result calculation from input.csv
expected_totals = defaultdict(float)
expected_counts = defaultdict(int)
with (base / 'input' / 'input.csv').open(newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        value_text = row['Value']
        if value_text == '':
            continue
        expected_totals[row['Model']] += float(value_text)
        expected_counts[row['Model']] += 1
expected_rows = [(m, expected_totals[m] / expected_counts[m], expected_counts[m]) for m in sorted(expected_totals)]
print('expected_rows=', expected_rows)

# Reopen and validate the generated workbook.
summary_path = base / 'output' / 'summary.xlsx'
if not summary_path.exists():
    raise AssertionError('summary.xlsx was not created')
wb = load_workbook(summary_path, data_only=True)
if wb.sheetnames != ['summary']:
    raise AssertionError(f'unexpected sheets: {wb.sheetnames}')
ws = wb['summary']
rows = list(ws.iter_rows(values_only=True))
print('workbook_rows=', rows)
if rows[0] != ('Model', 'Average', 'ValidCount'):
    raise AssertionError(f'unexpected header: {rows[0]}')
actual_rows = rows[1:]
if len(actual_rows) != len(expected_rows):
    raise AssertionError(f'unexpected data row count: {len(actual_rows)} != {len(expected_rows)}')
for actual, expected in zip(actual_rows, expected_rows):
    model, avg, cnt = actual
    exp_model, exp_avg, exp_cnt = expected
    if model != exp_model:
        raise AssertionError(f'model mismatch: {model} != {exp_model}')
    if not isinstance(avg, (int, float)):
        raise AssertionError(f'Average is not numeric for {model}: {avg!r}')
    if abs(float(avg) - exp_avg) > 1e-9:
        raise AssertionError(f'Average mismatch for {model}: {avg} != {exp_avg}')
    if cnt != exp_cnt or not isinstance(cnt, int):
        raise AssertionError(f'ValidCount mismatch/not int for {model}: {cnt!r} != {exp_cnt}')

# Confirm input files remain present and output files are in output.
print('validated output/export.py exists=', export_path.exists())
print('validated output/summary.xlsx exists=', summary_path.exists(), 'size=', summary_path.stat().st_size)
print('all checks passed')
