from pathlib import Path
import subprocess
import sys
from openpyxl import load_workbook

ws = Path('.').resolve()
input_dir = ws / 'input'
output_dir = ws / 'output'
output_dir.mkdir(exist_ok=True)

fixed_code = '''"""Average Value per Model from input.csv into summary.xlsx.

Usage: python export.py --input input.csv --output summary.xlsx
Requires: openpyxl
"""

import argparse
import csv

from openpyxl import Workbook


def parse_number(text: str) -> float:
    """Parse a CSV Value cell as a number after trimming whitespace."""
    return float(text.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    totals = {}
    counts = {}

    with open(args.input, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("input CSV is missing a header row")
        required = {"Model", "Value"}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"input CSV is missing required column(s): {', '.join(sorted(missing))}")

        for row in reader:
            model = row["Model"]
            value_text = row["Value"]
            if value_text is None or value_text.strip() == "":
                continue
            value = parse_number(value_text)
            totals[model] = totals.get(model, 0.0) + value
            counts[model] = counts.get(model, 0) + 1

    book = Workbook()
    sheet = book.active
    sheet.title = "summary"
    sheet.append(["Model", "Average", "ValidCount"])
    for model in sorted(totals):
        sheet.append([model, totals[model] / counts[model], counts[model]])
    book.save(args.output)


if __name__ == "__main__":
    main()
'''

out_py = output_dir / 'export.py'
out_xlsx = output_dir / 'summary.xlsx'
out_py.write_text(fixed_code, encoding='utf-8')
print(f'wrote {out_py}')

cmd = [sys.executable, str(out_py), '--input', str(input_dir / 'input.csv'), '--output', str(out_xlsx)]
print('running:', ' '.join(cmd))
result = subprocess.run(cmd, cwd=ws, text=True, capture_output=True)
print('return code:', result.returncode)
if result.stdout:
    print('stdout:', result.stdout)
if result.stderr:
    print('stderr:', result.stderr)
if result.returncode != 0:
    raise SystemExit(result.returncode)

# Reopen every output file and verify requirements.
script_text = out_py.read_text(encoding='utf-8')
checks = []
checks.append(('output/export.py exists', out_py.exists()))
checks.append(('CLI --input is preserved', 'parser.add_argument("--input", required=True)' in script_text))
checks.append(('CLI --output is preserved', 'parser.add_argument("--output", required=True)' in script_text))
checks.append(('input files unchanged by script', (input_dir / 'export.py').exists() and (input_dir / 'input.csv').exists()))

wb = load_workbook(out_xlsx, data_only=True)
wsheet = wb['summary']
rows = list(wsheet.iter_rows(values_only=True))
print('summary.xlsx rows:')
for row in rows:
    print(row)

expected_rows = [
    ('Model', 'Average', 'ValidCount'),
    ('M1', 15, 2),
    ('M2', 10, 2),
]
checks.append(('output/summary.xlsx exists', out_xlsx.exists()))
checks.append(('worksheet named summary exists', 'summary' in wb.sheetnames))
checks.append(('columns are Model, Average, ValidCount', rows[0] == expected_rows[0]))
checks.append(('row count is header + two models', len(rows) == 3))
checks.append(('M1 average excludes blank Value', rows[1] == expected_rows[1]))
checks.append(('M2 average is correct', rows[2] == expected_rows[2]))
checks.append(('Average values are numeric', all(isinstance(r[1], (int, float)) for r in rows[1:])))
checks.append(('ValidCount values are integers', all(isinstance(r[2], int) for r in rows[1:])))

failed = [name for name, ok in checks if not ok]
print('checks:')
for name, ok in checks:
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise AssertionError('failed checks: ' + '; '.join(failed))
print('all checks passed')
