from pathlib import Path
import json
import re

ws = Path.cwd()
input_path = ws / 'input' / 'sop.md'
output_dir = ws / 'output'
output_dir.mkdir(exist_ok=True)
output_path = output_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')
lines = text.splitlines()

steps = []
current = None

step_re = re.compile(r'^\s*(\d+)\.\s*(.*)$')
field_re = re.compile(r'^\s*(Action|Input|Expected result):\s*(.*)$', re.IGNORECASE)

for line in lines:
    # Stop before 注意事項 section; preface is naturally ignored until first numbered step.
    if re.match(r'^\s*#{1,6}\s*注意事項\s*$', line):
        break

    m = step_re.match(line)
    if m:
        if current is not None:
            steps.append(current)
        current = {
            'step_id': len(steps) + 1,
            'action': None,
            'input': None,
            'expected_result': None,
        }
        remainder = m.group(2).strip()
        fm = field_re.match(remainder)
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

output_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding='utf-8')

print('Wrote:', output_path)
print('Step count:', len(steps))
print(output_path.read_text(encoding='utf-8'))

# Verification: reopen output and confirm requirements.
loaded = json.loads(output_path.read_text(encoding='utf-8'))
required_keys = ['step_id', 'action', 'input', 'expected_result']
assert isinstance(loaded, list), 'output must be a JSON array'
assert len(loaded) == 3, f'expected 3 numbered steps, got {len(loaded)}'
for i, row in enumerate(loaded, start=1):
    assert list(row.keys()) == required_keys, f'row {i} keys/order mismatch: {list(row.keys())}'
    assert row['step_id'] == i, f'row {i} step_id mismatch: {row["step_id"]}'
assert loaded[0] == {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'}
assert loaded[1] == {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'}
assert loaded[2] == {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None}
print('Verification passed: sop.json exists, contains 3 sequential steps, exact columns, and nulls for missing fields.')