from pathlib import Path
repo=Path('../../../../..').resolve().parent
for f in ['benchmarks/coding_v1/evaluator/validators.py','benchmarks/coding_v1/evaluator']:
    p=repo/f
    print('\n====', f,'====')
    if p.is_file():
        txt=p.read_text(encoding='utf-8', errors='replace')
        idx=txt.find('T09')
        print(txt[max(0,idx-2000):idx+5000])
    elif p.is_dir():
        for q in p.rglob('*'):
            if q.is_file(): print(q.relative_to(repo))