from pathlib import Path
import shutil, csv
from datetime import datetime

ws = Path.cwd()
out = ws/'output'
preserve = out/'preserved_2026_09_before_august_rerun'
preserve.mkdir(parents=True, exist_ok=True)

print('WORKSPACE', ws)
print('PRESERVE_DIR', preserve)
print('Before files:')
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(' ', p.relative_to(ws), p.stat().st_size)

# Preserve existing first-run output files without overwriting preserved copies.
files_to_preserve = [
    out/'project_integration_report.xlsx',
    out/'project_summary_sep2026.csv',
    out/'quotes_accepted.json',
    out/'quotes_accepted_sep2026.json',
    out/'expense_approved.csv',
    out/'expense_approved_sep2026.csv',
    out/'downloads'/'sap_orders.csv',
    out/'downloads'/'sap_invoices.csv',
    out/'downloads'/'sap_orders_sep2026.csv',
    out/'downloads'/'sap_invoices_sep2026.csv',
]
for src in files_to_preserve:
    if src.exists():
        dst = preserve/src.relative_to(out)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)
            print('preserved', src.relative_to(ws), '->', dst.relative_to(ws))
        else:
            print('already_preserved', dst.relative_to(ws))

# Remove generic workflow output targets that caused path_exists or would be overwritten.
# Keep sep2026 names in place and preserved copy as protection.
for rel in [
    'expense_approved.csv',
    'quotes_accepted.json',
    'project_integration_report.xlsx',
    'downloads/sap_orders.csv',
    'downloads/sap_invoices.csv',
]:
    p = out/rel
    if p.exists():
        p.unlink()
        print('removed_for_rerun', p.relative_to(ws))

print('After files:')
for p in sorted(out.rglob('*')):
    if p.is_file():
        print(' ', p.relative_to(ws), p.stat().st_size)

# Confirm preserved copies exist.
missing = []
for src in files_to_preserve:
    if (preserve/src.relative_to(out)).exists():
        continue
    if src.exists():
        missing.append(str(preserve/src.relative_to(out)))
if missing:
    raise SystemExit('Missing preserved copies: '+', '.join(missing))
print('Preservation check passed')
