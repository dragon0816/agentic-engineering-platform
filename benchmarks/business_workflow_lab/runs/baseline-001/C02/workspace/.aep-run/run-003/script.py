import subprocess, json, sys
cli=[sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py']
cmd=cli+['quotes','list','--from','2026-09-01','--to','2026-09-30','--format','json']
print('RUN', cmd)
res=subprocess.run(cmd, capture_output=True, text=True)
print('rc',res.returncode)
print('stderr',res.stderr)
print('stdout',res.stdout[:5000])
if res.returncode==0:
    data=json.loads(res.stdout)
    print('count', data['count'])
    for item in data['items'][:20]: print(item)
