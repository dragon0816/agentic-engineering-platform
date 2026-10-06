from pathlib import Path
base=Path('../../../../..').resolve() # benchmarks
repo=base.parent
print('repo', repo)
# find files mentioning workflow format/runtime perhaps in docs
patterns=['*.md','*.py','*.yaml','*.yml','*.json']
terms=['workflow', 'runtime', 'platform format', 'steps']
count=0
for p in repo.rglob('*'):
    if p.is_file() and p.suffix.lower() in ['.md','.py','.yaml','.yml','.json']:
        if any(part in {'.venv','node_modules','.git','__pycache__'} for part in p.parts):
            continue
        try:
            txt=p.read_text(encoding='utf-8', errors='ignore')
        except: continue
        low=txt.lower()
        if 'workflow' in low and ('runtime' in low or 'steps' in low or 'format' in low):
            print('MATCH', p.relative_to(repo))
            count+=1
            if count>100: break
print('count', count)