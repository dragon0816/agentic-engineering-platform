from pathlib import Path
import re, json

workspace = Path('.').resolve()
input_path = Path('input') / 'sop.md'
out_dir = Path('output')
out_dir.mkdir(exist_ok=True)
out_path = out_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')
lines = text.splitlines()

steps = []
current = None
seen_numbered = False

numbered_re = re.compile(r'^\s*(\d+)\.\s*(.*)$')
field_re = re.compile(r'^\s*(Action|Input|Expected result)\s*:\s*(.*)\s*$', re.IGNORECASE)

for line in lines:
    # Stop at notes section after steps begin; ignore notes and anything after it.
    if seen_numbered and re.match(r'^\s*#{1,6}\s*注意事項\s*$', line):
        break

    m_num = numbered_re.match(line)
    if m_num:
        seen_numbered = True
        if current is not None:
            steps.append(current)
        current = {
            'step_id': len(steps) + 1,
            'action': None,
            'input': None,
            'expected_result': None,
        }
        remainder = m_num.group(2).strip()
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

    if current is not None:
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

out_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Reopen and validate all stated requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'sop.json must be a JSON array'
assert len(loaded) == 3, f'expected 3 numbered steps before 注意事項, got {len(loaded)}'
expected_keys = ['step_id', 'action', 'input', 'expected_result']
expected = [
    {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'},
    {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'},
    {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None},
]
for idx, row in enumerate(loaded, 1):
    assert list(row.keys()) == expected_keys, f'step {idx} keys/order mismatch: {list(row.keys())}'
    assert row['step_id'] == idx, f'step_id for row {idx} is not sequential from 1'
    assert row == expected[idx-1], f'row {idx} content mismatch: {row}'
    assert (row['input'] is None or isinstance(row['input'], str)), f'input type invalid in row {idx}'
    assert (row['expected_result'] is None or isinstance(row['expected_result'], str)), f'expected_result type invalid in row {idx}'

print('Wrote:', out_path.resolve())
print('Validated: JSON array, 3 numbered steps only, keys step_id/action/input/expected_result, sequential step_id 1..3, null for missing input/expected_result, and no 注意事項 content included.')
print(out_path.read_text(encoding='utf-8'))