from pathlib import Path
import csv, json, subprocess, sys
base=Path.cwd()
downloads=base/'output'/'downloads'
print('DOWNLOADS')
for p in sorted(downloads.glob('*')):
    print('-', p.name, p.stat().st_size)
    try:
        with p.open(newline='', encoding='utf-8-sig') as f:
            r=csv.reader(f)
            for i,row in zip(range(5), r): print(' ', i, row)
    except Exception as e: print(' read error', e)

cli=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')
cmd=[sys.executable, str(cli), 'quotes', 'list', '--customer', 'C001', '--from', '2026-09-01', '--to', '2026-09-30', '--format','json']
print('\nQUOTE CMD', cmd)
res=subprocess.run(cmd, text=True, capture_output=True)
print('returncode', res.returncode)
print('stderr', res.stderr)
print('stdout', res.stdout)
if res.returncode==0:
    data=json.loads(res.stdout)
    out=base/'output'/'quotes_C001_2026-09.json'
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('wrote', out)
    print('projects', sorted({x.get('ProjectID','') for x in data.get('items',[])}))
