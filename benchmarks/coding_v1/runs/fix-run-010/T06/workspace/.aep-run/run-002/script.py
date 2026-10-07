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
in_numbered_steps = False

numbered_re = re.compile(r'^\s*(\d+)\.\s*(.*)$')
field_re = re.compile(r'^\s*(Action|Input|Expected result):\s*(.*)$', re.IGNORECASE)
heading_re = re.compile(r'^\s*#{1,6}\s+(.+)')

for line in lines:
    if in_numbered_steps and heading_re.match(line):
        # Ignore 注意事項 and anything after the numbered SOP section.
        break

    m = numbered_re.match(line)
    if m:
        if current is not None:
            steps.append(current)
        in_numbered_steps = True
        current = {
            'step_id': len(steps) + 1,
            'action': None,
            'input': None,
            'expected_result': None,
        }
        rest = m.group(2).strip()
        fm = field_re.match(rest)
        if fm:
            key = fm.group(1).lower()
            value = fm.group(2).strip()
            if key == 'action':
                current['action'] = value if value != '' else None
            elif key == 'input':
                current['input'] = value if value != '' else None
            elif key == 'expected result':
                current['expected_result'] = value if value != '' else None
        continue

    if current is not None:
        fm = field_re.match(line)
        if fm:
            key = fm.group(1).lower()
            value = fm.group(2).strip()
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

# Reopen and verify stated requirements.
loaded = json.loads(output_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'sop.json must contain a JSON list'
assert len(loaded) == 3, f'expected 3 numbered steps, got {len(loaded)}'
expected_keys = ['step_id', 'action', 'input', 'expected_result']
for idx, row in enumerate(loaded, 1):
    assert list(row.keys()) == expected_keys, f'row {idx} keys differ: {list(row.keys())}'
    assert row['step_id'] == idx, f'row {idx} step_id is not sequential from 1'

assert loaded[0] == {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'}
assert loaded[1] == {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'}
assert loaded[2] == {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None}

print('Wrote:', output_path)
print('Verified output file exists:', output_path.exists())
print('Verified JSON row count:', len(loaded))
print('Verified columns/order:', expected_keys)
print('Verified step_id sequence:', [row['step_id'] for row in loaded])
print('Verified missing input/expected_result are JSON null where not provided.')
print('Verified 注意事項 text was not included.')
print(json.dumps(loaded, ensure_ascii=False, indent=2))