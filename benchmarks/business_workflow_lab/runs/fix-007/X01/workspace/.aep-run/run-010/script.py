from pathlib import Path
import os, shutil, subprocess
ws=Path.cwd()
print('WORKSPACE', ws)
for base in ['input','output','output/downloads']:
    p=ws/base
    print('\nDIR', base, 'exists=', p.exists())
    if p.exists():
        for f in sorted(p.iterdir()):
            print(' ', f.name, f.stat().st_size if f.is_file() else 'dir')
print('\nquote executables:', [x for x in ['quote','quotes','quote-cli','quote_cli'] if shutil.which(x)])
for exe in ['quote','quotes','quote-cli','quote_cli']:
    if shutil.which(exe):
        try:
            r=subprocess.run([exe,'--help'], capture_output=True, text=True, timeout=10)
            print('\nHELP', exe, 'rc', r.returncode)
            print((r.stdout or r.stderr)[:1000])
        except Exception as e:
            print('ERR', exe, e)
