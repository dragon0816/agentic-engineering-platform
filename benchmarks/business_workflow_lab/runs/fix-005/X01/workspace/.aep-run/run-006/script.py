from pathlib import Path
ws=Path.cwd()
for fn in ['sap_manual.md','expense_manual.md','quote_cli_manual.md']:
    p=ws/'input'/fn
    print('\n====', fn, '====')
    print(p.read_text(encoding='utf-8')[:4000])
