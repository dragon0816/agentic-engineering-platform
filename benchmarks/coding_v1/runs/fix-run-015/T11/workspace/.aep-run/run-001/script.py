from pathlib import Path
from urllib.request import urlopen

workspace = Path.cwd()
print('WORKSPACE:', workspace)
print('INPUT FILES:')
input_dir = workspace / 'input'
if input_dir.exists():
    for p in sorted(input_dir.rglob('*')):
        print(' -', p.relative_to(workspace), 'DIR' if p.is_dir() else f'{p.stat().st_size} bytes')
else:
    print(' - input directory does not exist')

url = 'http://127.0.0.1:50447/t11/list'
print('\nFETCHING LIST PAGE:', url)
with urlopen(url, timeout=10) as resp:
    data = resp.read()
    print('STATUS:', getattr(resp, 'status', 'unknown'))
    print('CONTENT-TYPE:', resp.headers.get('content-type'))
    text = data.decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')
print('LIST PAGE MARKUP SAMPLE START')
print(text[:4000])
print('LIST PAGE MARKUP SAMPLE END')
