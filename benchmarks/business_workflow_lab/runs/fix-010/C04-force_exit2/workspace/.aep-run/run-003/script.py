from pathlib import Path
import json
ws=Path.cwd()
out=ws/'output'
err=out/'quote_cli_error_2026-09_Sent.txt'
log=out/'quote_cli_run_log.json'
print('checking outputs in', out)
print('error exists:', err.exists(), 'bytes:', err.stat().st_size if err.exists() else None)
if err.exists():
    txt=err.read_text(encoding='utf-8')
    print('error text:', txt.strip())
    print('contains exit code 2:', 'exit code 2' in txt)
    print('contains stderr reason:', 'quote_cli: error:' in txt)
print('log exists:', log.exists(), 'bytes:', log.stat().st_size if log.exists() else None)
if log.exists():
    data=json.loads(log.read_text(encoding='utf-8'))
    print('query:', data.get('query'))
    print('result:', data.get('result'))
    attempts=data.get('attempts', [])
    print('attempt count:', len(attempts))
    if attempts:
        print('first returncode:', attempts[0].get('returncode'))
        print('first stdout_len:', attempts[0].get('stdout_len'))
        print('first stderr:', attempts[0].get('stderr'))
print('workbook exists:', (out/'quote_report_2026-09_Sent.xlsx').exists())