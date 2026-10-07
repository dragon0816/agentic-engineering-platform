from pathlib import Path
import subprocess, json, sys, time

WORKSPACE = Path.cwd()
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
FROM_DATE='2026-09-01'; TO_DATE='2026-09-30'; STATUS='Sent'
CLI_CMD = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd')
CLI_PY = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')

def base_cmd():
    if CLI_CMD.exists(): return [str(CLI_CMD)]
    if CLI_PY.exists(): return [sys.executable, str(CLI_PY)]
    raise FileNotFoundError('quote CLI not found')

run_log = {'query': {'from': FROM_DATE, 'to': TO_DATE, 'status': STATUS}, 'attempts': [], 'result': None, 'retry_policy': {'exit_code_4_max_retries': 2, 'exit_code_2_or_3_retry': False, 'stdout_used_only_on_success_parseable': True}}
try:
    args=['quotes','list','--from',FROM_DATE,'--to',TO_DATE,'--status',STATUS,'--format','json']
    temp_retries = 0
    while True:
        cp = subprocess.run(base_cmd()+args, cwd=str(WORKSPACE), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        run_log['attempts'].append({'command': args, 'returncode': cp.returncode, 'stdout_len': len(cp.stdout or ''), 'stderr': (cp.stderr or '').strip()})
        if cp.returncode == 0:
            try:
                data=json.loads(cp.stdout)
            except Exception as e:
                raise RuntimeError(f'quotes list: CLI succeeded but stdout was not parseable JSON: {e}')
            # In this operator scenario we do not expect success; if success, note not implemented here.
            run_log['result']={'status':'unexpected_success', 'count': data.get('count')}
            break
        if cp.returncode == 4 and temp_retries < 2:
            temp_retries += 1
            time.sleep(0.2)
            continue
        if cp.returncode in (2,3):
            run_log['result']={'status':'failed', 'exit_code': cp.returncode, 'reason_from_stderr': (cp.stderr or '').strip(), 'retried': False}
            break
        if cp.returncode == 4:
            run_log['result']={'status':'failed', 'exit_code': 4, 'reason_from_stderr': (cp.stderr or '').strip(), 'attempts': len(run_log['attempts'])}
            break
        run_log['result']={'status':'failed', 'exit_code': cp.returncode, 'reason_from_stderr': (cp.stderr or '').strip()}
        break
except Exception as e:
    run_log['result']={'status':'failed', 'reason': str(e)}

# Because exit 2/3 means do not retry and stdout is not data, no workbook is created/updated.
err = OUTPUT / 'quote_cli_error_2026-09_Sent.txt'
log = OUTPUT / 'quote_cli_run_log.json'
res = run_log['result'] or {}
if res.get('status') == 'failed':
    if 'exit_code' in res:
        text = f"quotes list failed with exit code {res['exit_code']}; stderr: {res.get('reason_from_stderr','')}\n"
    else:
        text = f"quotes list failed; reason: {res.get('reason','')}\n"
    err.write_text(text, encoding='utf-8')
elif err.exists():
    err.unlink()
log.write_text(json.dumps(run_log, ensure_ascii=False, indent=2), encoding='utf-8')
print('result:', run_log['result'])
print('attempts:', len(run_log['attempts']))
print('wrote:', err if err.exists() else '(no error file)', log)
