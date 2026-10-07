from pathlib import Path
import json
workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input files:')
for p in sorted(input_dir.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(workspace), 'size=', p.stat().st_size)
path = input_dir / 'testplan.json'
print('\nInspecting:', path)
text = path.read_text(encoding='utf-8')
print('first 1000 chars:')
print(text[:1000])
data = json.loads(text)
print('\nroot type:', type(data).__name__)

def find_freq(x, path='$', found=[]):
    if isinstance(x, dict):
        for k,v in x.items():
            if k == 'frequency':
                found.append((path + '.frequency', type(v).__name__, repr(v)[:120]))
            find_freq(v, path + '.' + k, found)
    elif isinstance(x, list):
        for i,v in enumerate(x):
            find_freq(v, f'{path}[{i}]', found)
    return found
freqs = find_freq(data, found=[])
print('frequency fields:', len(freqs))
for item in freqs[:30]:
    print(' ', item)
if len(freqs) > 30:
    print(' ...')