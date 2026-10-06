from pathlib import Path
ws=Path.cwd()
print('WORKSPACE', ws)
for p in sorted((ws/'input').glob('*')):
    print('INPUT_FILE', p.name, 'size', p.stat().st_size)
    if p.name.lower() == 'login_sop.md':
        print('--- login_sop.md ---')
        print(p.read_text(encoding='utf-8'))
        print('--- end login_sop.md ---')
print('OUTPUT_DIR_EXISTS', (ws/'output').exists())