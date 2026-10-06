from pathlib import Path
import subprocess, json, sys
cli = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
projects=[f'P{i:03d}' for i in range(1,6)]
for p in projects:
    cmd=[cli,'quotes','list','--project',p,'--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
    res=subprocess.run(cmd,capture_output=True,text=True)
    print('\nPROJECT',p,'return',res.returncode)
    if res.stderr: print('stderr',res.stderr)
    print(res.stdout)
