from pathlib import Path
p=Path('output/expense_export_E006_2026-01-01_2026-01-31.csv')
print('exists', p.exists())
if p.exists():
    print('size', p.stat().st_size)
    raw=p.read_bytes()[:500]
    print('bytes', raw)
    try:
        print('text', p.read_text(encoding='utf-8-sig')[:500])
    except Exception as e:
        print('read err', repr(e))
print('all output', [(x.name,x.stat().st_size) for x in Path('output').glob('*')])