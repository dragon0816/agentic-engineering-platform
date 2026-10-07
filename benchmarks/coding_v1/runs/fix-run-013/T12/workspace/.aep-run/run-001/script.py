from pathlib import Path
from urllib.request import urlopen

workspace = Path.cwd()
print('Workspace:', workspace)
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('Input dir exists:', input_dir.exists())
print('Output dir exists:', output_dir.exists())
if input_dir.exists():
    print('Input files:')
    for p in sorted(input_dir.iterdir()):
        print(' -', p.name, 'size=', p.stat().st_size)
        if p.is_file():
            try:
                data = p.read_text(encoding='utf-8')[:500]
            except Exception as e:
                data = f'<cannot read text: {e}>'
            print('   sample:', repr(data[:300]))

urls = [
    'http://127.0.0.1:63795/t12/a',
    'http://127.0.0.1:63795/t12/b',
    'http://127.0.0.1:63795/t12/c',
]
for url in urls:
    print('\nURL:', url)
    try:
        with urlopen(url, timeout=10) as resp:
            body = resp.read()
            print(' status:', getattr(resp, 'status', None), 'content-type:', resp.headers.get('content-type'), 'bytes:', len(body))
            text = body.decode('utf-8', errors='replace')
            print(' sample:', repr(text[:1000]))
    except Exception as e:
        print(' ERROR:', type(e).__name__, str(e))
