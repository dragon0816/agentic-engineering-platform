from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'sop.md'
out_dir = workspace / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
output_path = out_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')
lines = text.splitlines()

steps = []
current = None
in_steps = False

step_re = re.compile(r'^\s*(\d+)\.\s*(.*)$')
field_re = re.compile(r'^\s*(Action|Input|Expected result)\s*:\s*(.*)\s*$', re.IGNORECASE)
heading_re = re.compile(r'^\s*#{1,6}\s+')

for line in lines:
    m_step = step_re.match(line)
    if m_step:
        if current is not None:
            steps.append(current)
        in_steps = True
        current = {'step_id': len(steps) + 1, 'action': None, 'input': None, 'expected_result': None}
        remainder = m_step.group(2).strip()
        if remainder:
            m_field = field_re.match(remainder)
            if m_field:
                key = m_field.group(1).lower()
                value = m_field.group(2).strip() or None
                if key == 'action':
                    current['action'] = value
                elif key == 'input':
                    current['input'] = value
                elif key == 'expected result':
                    current['expected_result'] = value
        continue

    if in_steps and heading_re.match(line):
        if current is not None:
            steps.append(current)
            current = None
        in_steps = False
        continue

    if in_steps and current is not None:
        m_field = field_re.match(line)
        if m_field:
            key = m_field.group(1).lower()
            value = m_field.group(2).strip() or None
            if key == 'action':
                current['action'] = value
            elif key == 'input':
                current['input'] = value
            elif key == 'expected result':
                current['expected_result'] = value

if current is not None:
    steps.append(current)

output_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {output_path}')
print(json.dumps(steps, ensure_ascii=False, indent=2))

# Verification: reopen output and confirm requirements
loaded = json.loads(output_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'output must be a JSON array'
required_keys = ['step_id', 'action', 'input', 'expected_result']
assert len(loaded) == 3, f'expected 3 numbered steps, got {len(loaded)}'
for i, item in enumerate(loaded, start=1):
    assert list(item.keys()) == required_keys, f'step {i} keys are {list(item.keys())}'
    assert item['step_id'] == i, f'step_id for position {i} is {item["step_id"]}'
    assert isinstance(item['action'], str) and item['action'], f'step {i} action missing'
    assert item['input'] is None or isinstance(item['input'], str), f'step {i} input must be string or null'
    assert item['expected_result'] is None or isinstance(item['expected_result'], str), f'step {i} expected_result must be string or null'
assert loaded[1]['input'] is None, 'step 2 input should be null'
assert loaded[2]['expected_result'] is None, 'step 3 expected_result should be null'
assert all('注意' not in json.dumps(x, ensure_ascii=False) for x in loaded), '注意事項 content should be ignored'
print('verification passed: sop.json reopened; keys, step_id sequence, null placeholders, row count, and ignored notes checked.')