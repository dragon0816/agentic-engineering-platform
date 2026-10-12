from pathlib import Path
import json
ws = Path.cwd()
out = ws/'output'
print('OUTPUT_FILES')
for p in sorted(out.glob('*')):
    print(p.name, p.stat().st_size)

err = out/'quote_cli_error.txt'
log = out/'quote_cli_run_log.json'
xlsx = out/'sent_quotes_2026-09.xlsx'
assert err.exists() and err.stat().st_size > 0, 'missing nonempty error file'
assert log.exists() and log.stat().st_size > 0, 'missing nonempty run log'
assert not xlsx.exists(), 'xlsx should not be produced when CLI exits 2'
log_data = json.loads(log.read_text(encoding='utf-8'))
assert log_data['status'] == 'failed'
assert len(log_data['events']) == 1, 'exit 2 must not be retried'
assert log_data['events'][0]['exit_code'] == 2
assert 'rejected the request parameters' in log_data['events'][0]['stderr']
print('CHECK_OK: error file and run log are nonempty; no workbook was produced; exit code 2 was not retried; stderr reason captured.')
print('STDERR_REASON:', log_data['events'][0]['stderr'].strip())
