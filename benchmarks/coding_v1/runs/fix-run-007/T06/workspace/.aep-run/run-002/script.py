from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'sop.md'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')
lines = text.splitlines()

steps = []
current = None

step_re = re.compile(r'^\s*(\d+)\.\s*(.*)$')
field_re = re.compile(r'^\s*(Action|Input|Expected result)\s*:\s*(.*)\s*$', re.IGNORECASE)
heading_re = re.compile(r'^\s*#{1,6}\s+')

for line in lines:
    # Stop once notes section starts; requested to ignore 注意事項.
    if heading_re.match(line) and '注意事項' in line:
        break

    m_step = step_re.match(line)
    if m_step:
        if current is not None:
            steps.append(current)
        current = {'action': None, 'input': None, 'expected_result': None}
        remainder = m_step.group(2).strip()
        if remainder:
            m_field = field_re.match(remainder)
            if m_field:
                key = m_field.group(1).lower()
                value = m_field.group(2).strip()
                if key == 'action':
                    current['action'] = value if value != '' else None
                elif key == 'input':
                    current['input'] = value if value != '' else None
                elif key == 'expected result':
                    current['expected_result'] = value if value != '' else None
        continue

    if current is not None:
        m_field = field_re.match(line)
        if m_field:
            key = m_field.group(1).lower()
            value = m_field.group(2).strip()
            value = value if value != '' else None
            if key == 'action':
                current['action'] = value
            elif key == 'input':
                current['input'] = value
            elif key == 'expected result':
                current['expected_result'] = value

if current is not None:
    steps.append(current)

output = []
for i, step in enumerate(steps, start=1):
    output.append({
        'step_id': i,
        'action': step['action'],
        'input': step['input'],
        'expected_result': step['expected_result'],
    })

output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification: reopen output and confirm requirements.
loaded = json.loads(output_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'sop.json must contain a list'
assert len(loaded) == 3, f'expected 3 numbered steps, got {len(loaded)}'
for idx, row in enumerate(loaded, start=1):
    assert list(row.keys()) == ['step_id', 'action', 'input', 'expected_result'], f'wrong keys at row {idx}: {row.keys()}'
    assert row['step_id'] == idx, f'step_id not sequential at row {idx}'
    assert isinstance(row['step_id'], int), f'step_id must be int at row {idx}'
    assert row['action'] is None or isinstance(row['action'], str), f'action must be string/null at row {idx}'
    assert row['input'] is None or isinstance(row['input'], str), f'input must be string/null at row {idx}'
    assert row['expected_result'] is None or isinstance(row['expected_result'], str), f'expected_result must be string/null at row {idx}'

expected = [
    {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'},
    {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'},
    {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None},
]
assert loaded == expected, 'output content does not match explicitly provided SOP fields'

print('WROTE', output_path)
print('ROWS', len(loaded))
print('VERIFIED keys, sequential integer step_id, null missing fields, explicit content only')
print(json.dumps(loaded, ensure_ascii=False, indent=2))