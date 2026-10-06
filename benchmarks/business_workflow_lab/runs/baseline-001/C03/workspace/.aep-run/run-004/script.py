from pathlib import Path
import subprocess, json, sys, os
cli_py = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py'
projects=[f'P{i:03d}' for i in range(1,6)]
for p in projects:
    cmd=[sys.executable, cli_py,'quotes','list','--project',p,'--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
    res=subprocess.run(cmd,capture_output=True,text=True)
    print('\nPROJECT',p,'return',res.returncode)
    if res.stderr: print('stderr',res.stderr)
    print(res.stdout)
