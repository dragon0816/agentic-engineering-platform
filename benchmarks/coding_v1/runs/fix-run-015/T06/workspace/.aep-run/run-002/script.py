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

step_re = re.compile(r'^\s*(\d+)\.\s*(?:Action\s*:\s*)?(.*\S)?\s*$')
field_re = re.compile(r'^\s*(Input|Expected result)\s*:\s*(.*)\s*$', re.IGNORECASE)
heading_re = re.compile(r'^\s*#{1,6}\s+')

for line in lines:
    # Ignore notes and anything after the notes section.
    if heading_re.match(line) and '注意事項' in line:
        break

    m_step = step_re.match(line)
    if m_step:
        if current is not None:
            steps.append(current)
        # Use sequential step_id from 1, not the source numbering.
        action = (m_step.group(2) or '').strip()
        current = {
            'step_id': len(steps) + 1,
            'action': action if action != '' else None,
            'input': None,
            'expected_result': None,
        }
        continue

    if current is None:
        continue

    m_field = field_re.match(line)
    if m_field:
        key = m_field.group(1).lower()
        value = m_field.group(2).strip()
        value = value if value != '' else None
        if key == 'input':
            current['input'] = value
        elif key == 'expected result':
            current['expected_result'] = value

if current is not None:
    steps.append(current)

output_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Verification: reopen output and confirm stated requirements.
loaded = json.loads(output_path.read_text(encoding='utf-8'))
print('WROTE', output_path)
print('ROW_COUNT', len(loaded))
print('DATA')
print(json.dumps(loaded, ensure_ascii=False, indent=2))

required_keys = ['step_id', 'action', 'input', 'expected_result']
assert isinstance(loaded, list), 'Output must be a JSON list'
assert len(loaded) == 3, f'Expected 3 numbered steps before 注意事項, got {len(loaded)}'
for idx, item in enumerate(loaded, 1):
    assert list(item.keys()) == required_keys, f'Step {idx} keys/order mismatch: {list(item.keys())}'
    assert item['step_id'] == idx, f'Step {idx} has wrong step_id: {item["step_id"]}'
    assert item['action'] is None or isinstance(item['action'], str), f'Step {idx} action type invalid'
    assert item['input'] is None or isinstance(item['input'], str), f'Step {idx} input type invalid'
    assert item['expected_result'] is None or isinstance(item['expected_result'], str), f'Step {idx} expected_result type invalid'

assert loaded[0] == {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'}
assert loaded[1] == {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'}
assert loaded[2] == {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None}
print('CHECKS_OK: sop.json exists, has required fields, sequential step_id, nulls for missing fields, and excludes preface/notes.')