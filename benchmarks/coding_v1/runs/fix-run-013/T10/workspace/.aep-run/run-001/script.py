from pathlib import Path
import urllib.request

base = Path.cwd()
print('CWD:', base)
print('Input files:')
for p in sorted((base/'input').glob('*')):
    print(' -', p.name, p.stat().st_size, 'bytes')

notes = base/'input'/'catalog_notes.md'
if notes.exists():
    print('\n--- catalog_notes.md ---')
    print(notes.read_text(encoding='utf-8')[:4000])
else:
    print('catalog_notes.md not found')

url = 'http://127.0.0.1:63795/t10/catalog'
print('\nFetching:', url)
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = r.read()
        final_url = r.geturl()
        ctype = r.headers.get('content-type')
    text = data.decode('utf-8', errors='replace')
    print('Final URL:', final_url)
    print('Content-Type:', ctype)
    print('Length:', len(text))
    print('\n--- page markup sample ---')
    print(text[:5000])
except Exception as e:
    print('FETCH ERROR:', repr(e))
