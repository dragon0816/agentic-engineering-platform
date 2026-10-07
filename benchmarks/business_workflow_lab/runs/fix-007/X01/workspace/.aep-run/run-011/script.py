from pathlib import Path
for name in ['sap_manual.md','expense_manual.md','quote_cli_manual.md']:
    p=Path('input')/name
    print('\n---', name, '---')
    print(p.read_text(encoding='utf-8')[:3000])
