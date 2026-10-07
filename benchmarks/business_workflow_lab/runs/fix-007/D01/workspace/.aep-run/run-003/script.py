from pathlib import Path
print('cwd', Path.cwd())
out=Path.cwd()/'output'
print('exists', out.exists())
print([p.name for p in out.iterdir()])
for p in out.iterdir():
    print(p, p.stat().st_size)
    if p.suffix.lower()=='.csv':
        data=p.read_bytes()[:500]
        print(data)
