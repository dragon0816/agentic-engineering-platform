from pathlib import Path
import os
base=Path.cwd()
repo=base
for p in [base, *base.parents]:
    if (p/'pyproject.toml').exists() or (p/'.git').exists():
        repo=p; break
print('repo candidate', repo)
for name in ['pyproject.toml','README.md','README.md','package.json']:
    f=repo/name
    print(name, f.exists())
    if f.exists():
        print(f.read_text(encoding='utf-8', errors='replace')[:3000])
print('top entries')
for p in sorted(repo.iterdir()):
    print(('DIR ' if p.is_dir() else 'FILE'), p.name)
