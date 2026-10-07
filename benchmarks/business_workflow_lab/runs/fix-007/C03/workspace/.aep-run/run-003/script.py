from pathlib import Path
import subprocess, json, sys, csv, re, os
ws=Path.cwd()
manual=(ws/'input'/'quote_cli_manual.md').read_text(encoding='utf-8')
print('workspace', ws)
print('inputs', [p.name for p in sorted((ws/'input').iterdir())])
cmd_match=re.search(r'python "([^"]*run_quote_cli\.py)" <command>', manual)
if not cmd_match:
    print('no cli path found')
    sys.exit(1)
cli=cmd_match.group(1)
print('cli path:', cli)
projects=[f'P{i:03d}' for i in range(1,6)]
all_items=[]
for p in projects:
    args=[sys.executable, cli, 'quotes', 'list', '--project', p, '--from', '2026-09-01', '--to', '2026-09-30', '--status', 'Accepted', '--format', 'json']
    res=subprocess.run(args, capture_output=True, text=True)
    print('\nQUERY', p, 'exit', res.returncode)
    if res.stderr.strip(): print('stderr:', res.stderr.strip())
    print('stdout:', res.stdout[:1000])
    if res.returncode!=0: sys.exit(res.returncode)
    data=json.loads(res.stdout)
    print('count', data.get('count'))
    all_items.extend(data.get('items', []))
print('\ncombined items', len(all_items))
for it in all_items[:10]: print(it)
if all_items:
    qid=all_items[0]['QuoteID']
    res=subprocess.run([sys.executable, cli, 'quotes', 'get', qid, '--format', 'json'], capture_output=True, text=True)
    print('\nsample get', qid, 'exit', res.returncode)
    if res.stderr.strip(): print('stderr:', res.stderr.strip())
    print(res.stdout[:2000])