import os, urllib.request
from pathlib import Path
workspace=Path.cwd()
print('WORKSPACE', workspace)
print('INPUT FILES:')
for p in sorted((workspace/'input').glob('**/*')):
    if p.is_file():
        print('-', p.relative_to(workspace), 'size=', p.stat().st_size)
        try:
            data=p.read_text(encoding='utf-8')[:500]
        except Exception as e:
            data=f'<cannot read text: {e}>'
        print(data[:500].replace('\n','\\n'))
urls=['http://127.0.0.1:56996/t12/a','http://127.0.0.1:56996/t12/b','http://127.0.0.1:56996/t12/c']
for url in urls:
    print('\nURL', url)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            body=r.read(2000)
            print('status', getattr(r,'status',None), 'content-type', r.headers.get('content-type'))
            print(body.decode('utf-8', errors='replace')[:2000])
    except Exception as e:
        print('FETCH ERROR', repr(e))