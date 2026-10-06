from pathlib import Path
ws=Path.cwd()
for fn in ['quote_cli_manual.md','sap_manual.md','expense_manual.md']:
    print('\n====', fn, '====')
    print((ws/'input'/fn).read_text(encoding='utf-8', errors='replace')[:2500])
print('\n==== old integration script tail ====')
old=(ws/'.aep-run'/'run-009'/'script.py').read_text(encoding='utf-8', errors='replace')
print(old[-3500:])
