from pathlib import Path
import json
import re

ws = Path.cwd()
input_path = ws / 'input' / 'sop.md'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')
lines = text.splitlines()

steps = []
current = None

step_re = re.compile(r'^\s*(\d+)\.\s*(.*)$')
field_re = re.compile(r'^\s*(Action|Input|Expected result)\s*:\s*(.*)\s*$', re.IGNORECASE)

for line in lines:
    # Stop at 注意事項 section; this also ignores all later notes.
    if re.match(r'^\s*#{1,6}\s*注意事項\s*$', line):
        break

    m_step = step_re.match(line)
    if m_step:
        if current is not None:
            steps.append(current)
        current = {
            'step_id': len(steps) + 1,
            'action': None,
            'input': None,
            'expected_result': None,
        }
        rest = m_step.group(2).strip()
        if rest:
            m_field = field_re.match(rest)
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

output_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Verification: reopen output and confirm stated requirements.
loaded = json.loads(output_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'sop.json must contain a JSON array'
expected_keys = ['step_id', 'action', 'input', 'expected_result']
for i, item in enumerate(loaded, start=1):
    assert list(item.keys()) == expected_keys, f'keys mismatch at step {i}: {list(item.keys())}'
    assert item['step_id'] == i, f'step_id not sequential at step {i}'
    for key in ['action', 'input', 'expected_result']:
        assert item[key] is None or isinstance(item[key], str), f'{key} must be string or null at step {i}'

# Confirm no notes/preamble material was added by checking exact expected extraction from input.
assert len(loaded) == 3, f'expected 3 numbered steps, got {len(loaded)}'
assert loaded[0] == {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'}
assert loaded[1] == {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'}
assert loaded[2] == {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None}

print('Wrote:', output_path)
print('Verification passed:')
print('- sop.json exists and is valid JSON array')
print('- 3 numbered steps extracted; preface and 注意事項 ignored')
print('- step_id values are sequential from 1')
print('- keys are exactly step_id, action, input, expected_result')
print('- missing input/expected_result fields are JSON null')
print(output_path.read_text(encoding='utf-8'))
