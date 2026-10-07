from pathlib import Path
import json
import re

ws = Path.cwd()
input_path = ws / 'input' / 'sop.md'
out_dir = ws / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')
lines = text.splitlines()

# Keep only the numbered SOP section; stop at 注意事項 heading.
numbered_lines = []
in_steps = False
for line in lines:
    if re.match(r'^\s*##\s*注意事項\s*$', line):
        break
    if re.match(r'^\s*\d+\.\s*Action\s*:', line):
        in_steps = True
    if in_steps:
        numbered_lines.append(line)

steps = []
current = None

field_map = {
    'Action': 'action',
    'Input': 'input',
    'Expected result': 'expected_result',
}

for line in numbered_lines:
    m_step = re.match(r'^\s*\d+\.\s*Action\s*:\s*(.*)\s*$', line)
    if m_step:
        if current is not None:
            steps.append(current)
        current = {
            'step_id': len(steps) + 1,
            'action': m_step.group(1).strip() or None,
            'input': None,
            'expected_result': None,
        }
        continue

    if current is None:
        continue

    m_field = re.match(r'^\s*(Input|Expected result)\s*:\s*(.*)\s*$', line)
    if m_field:
        key = field_map[m_field.group(1)]
        value = m_field.group(2).strip()
        current[key] = value if value != '' else None

if current is not None:
    steps.append(current)

out_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding='utf-8')

# Validation: reopen output and confirm requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
required_keys = ['step_id', 'action', 'input', 'expected_result']
assert isinstance(loaded, list), 'Output root must be a list'
assert len(loaded) == 3, f'Expected 3 numbered steps, got {len(loaded)}'
for idx, row in enumerate(loaded, 1):
    assert list(row.keys()) == required_keys, f'Keys/order mismatch at step {idx}: {list(row.keys())}'
    assert row['step_id'] == idx, f'step_id mismatch at step {idx}'
    assert isinstance(row['action'], str) or row['action'] is None
    assert isinstance(row['input'], str) or row['input'] is None
    assert isinstance(row['expected_result'], str) or row['expected_result'] is None
# Confirm missing fields remain null as shown in source.
assert loaded[1]['input'] is None, 'Step 2 input should be null'
assert loaded[2]['expected_result'] is None, 'Step 3 expected_result should be null'

print('Wrote:', out_path)
print('Validated rows:', len(loaded))
print(json.dumps(loaded, ensure_ascii=False, indent=2))