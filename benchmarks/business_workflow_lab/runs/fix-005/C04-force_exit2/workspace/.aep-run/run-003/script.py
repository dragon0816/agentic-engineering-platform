from pathlib import Path
import json
ws = Path.cwd()
out = ws/'output'
print('OUTPUT_FILES')
for p in sorted(out.glob('*')):
    print('-', p.relative_to(ws), p.stat().st_size, 'bytes')

err_path = out/'quote_cli_error.txt'
log_path = out/'quote_cli_run_log.json'
xlsx_path = out/'quote_report_2026-09_sent.xlsx'

assert err_path.exists(), 'quote_cli_error.txt missing'
assert log_path.exists(), 'quote_cli_run_log.json missing'
err = err_path.read_text(encoding='utf-8')
log = json.loads(log_path.read_text(encoding='utf-8'))
print('\nERROR_TEXT')
print(err)
print('\nLOG_SUMMARY')
print('status=', log.get('status'))
print('error=', log.get('error'))
print('attempt_count=', len(log.get('attempts', [])))
for a in log.get('attempts', []):
    print('attempt', a.get('attempt'), 'label', a.get('label'), 'exit_code', a.get('exit_code'), 'stderr', a.get('stderr'))

assert log.get('status') == 'failed', 'log status is not failed'
assert len(log.get('attempts', [])) == 1, 'exit code 2 should not be retried'
assert log['attempts'][0].get('exit_code') == 2, 'first attempt was not exit code 2'
assert 'stderr:' in log.get('error', ''), 'stderr reason not included in log error'
assert 'exit code 2' in err, 'error text does not report exit code 2'
assert 'stderr:' in err, 'error text does not include stderr reason'
assert not xlsx_path.exists(), 'report workbook should not be produced when CLI failed with exit code 2'
print('\nCHECKS_OK: error file and log reopened; confirmed exit code 2, no retry, stderr included, no workbook generated.')
