from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'sop.md'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')

# Split into numbered step blocks. Ignore content before first numbered step and stop at 注意事項 heading.
lines = text.splitlines()
step_blocks = []
current = None
for line in lines:
    if re.match(r'^\s*##\s*注意事項\s*$', line):
        if current is not None:
            step_blocks.append(current)
            current = None
        break
    m = re.match(r'^\s*(\d+)\.\s*(.*)$', line)
    if m:
        if current is not None:
            step_blocks.append(current)
        current = [m.group(2)]
    elif current is not None:
        current.append(line)
if current is not None:
    step_blocks.append(current)

steps = []
for idx, block in enumerate(step_blocks, start=1):
    fields = {'action': None, 'input': None, 'expected_result': None}
    for raw in block:
        line = raw.strip()
        if not line:
            continue
        for key, label in [('action', 'Action'), ('input', 'Input'), ('expected_result', 'Expected result')]:
            prefix = label + ':'
            if line.startswith(prefix):
                value = line[len(prefix):].strip()
                fields[key] = value if value != '' else None
                break
    steps.append({
        'step_id': idx,
        'action': fields['action'],
        'input': fields['input'],
        'expected_result': fields['expected_result'],
    })

output_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {output_path}')
print(json.dumps(steps, ensure_ascii=False, indent=2))

# Verification: reopen output and confirm requirements.
loaded = json.loads(output_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'output must be a JSON array'
assert len(loaded) == 3, f'expected 3 numbered steps before 注意事項, got {len(loaded)}'
expected_keys = ['step_id', 'action', 'input', 'expected_result']
for i, row in enumerate(loaded, start=1):
    assert list(row.keys()) == expected_keys, f'row {i} keys/order mismatch: {list(row.keys())}'
    assert row['step_id'] == i, f'step_id must be sequential from 1: row {i}'
    assert isinstance(row['action'], str) or row['action'] is None, f'action type invalid at row {i}'
    assert isinstance(row['input'], str) or row['input'] is None, f'input type invalid at row {i}'
    assert isinstance(row['expected_result'], str) or row['expected_result'] is None, f'expected_result type invalid at row {i}'
# Confirm missing fields are null exactly where source omitted them.
assert loaded[1]['input'] is None, 'step 2 missing input should be null'
assert loaded[2]['expected_result'] is None, 'step 3 missing expected_result should be null'
# Confirm 注意事項 content was not included.
serialized = json.dumps(loaded, ensure_ascii=False)
assert '錯誤代碼' not in serialized and '通知主管' not in serialized, '注意事項 content should be ignored'
print('verification passed: output reopened; row count, key names/order, sequential step_id, value/null types, and ignored 注意事項 were checked.')