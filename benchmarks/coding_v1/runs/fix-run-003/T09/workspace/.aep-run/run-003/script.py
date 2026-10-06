from pathlib import Path
for base in [Path('../../../../fixtures'), Path('../../../../prompts'), Path('../../../../README.md'), Path('../prompt.md')]:
    print('\n###', base.resolve())
    if base.is_file():
        print(base.read_text(encoding='utf-8', errors='replace')[:8000])
    elif base.is_dir():
        for p in base.rglob('*'):
            if p.is_file():
                print('FILE', p)
                print(p.read_text(encoding='utf-8', errors='replace')[:2000])