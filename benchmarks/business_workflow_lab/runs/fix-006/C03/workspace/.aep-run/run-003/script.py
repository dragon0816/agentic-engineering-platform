from pathlib import Path
import subprocess, json, sys
cli = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')
print('CLI exists:', cli.exists(), cli)
cmd=[sys.executable, str(cli), 'quotes', 'list', '--from', '2026-09-01', '--to', '2026-09-30', '--status', 'Accepted', '--format', 'json']
for p in ['P001','P002','P003','P004','P005']:
    pcmd=cmd[:4]+['--project', p]+cmd[4:]
    print('\nRUN', ' '.join(pcmd))
    res=subprocess.run(pcmd, text=True, capture_output=True)
    print('exit', res.returncode)
    print('stderr', res.stderr[:300])
    print('stdout', res.stdout[:1000])
