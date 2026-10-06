from pathlib import Path
ws=Path.cwd()
for p in [ws/'input'/'sap_manual.md', ws/'input'/'sales_template.xlsx', ws/'input'/'fx_rates.csv']:
    print('FILE', p.name, 'exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
print('--- sap_manual head ---')
print((ws/'input'/'sap_manual.md').read_text(encoding='utf-8')[:4000])
print('--- fx_rates ---')
print((ws/'input'/'fx_rates.csv').read_text(encoding='utf-8'))