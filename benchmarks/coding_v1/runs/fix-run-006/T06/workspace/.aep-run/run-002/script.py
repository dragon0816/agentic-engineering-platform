from pathlib import Path
import json, re

workspace = Path.cwd()
input_path = workspace / 'input' / 'sop.md'
out_dir = workspace / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')
steps = []
current = None
in_notes = False

step_re = re.compile(r'^\s*(\d+)\.\s*Action:\s*(.*)\s*$')
field_re = re.compile(r'^\s*(Input|Expected result):\s*(.*)\s*$', re.IGNORECASE)

for line in text.splitlines():
    if re.match(r'^\s*#{1,6}\s*注意事項\s*$', line):
        in_notes = True
        if current is not None:
            steps.append(current)
            current = None
        break
    if in_notes:
        continue

    m = step_re.match(line)
    if m:
        if current is not None:
            steps.append(current)
        current = {
            'step_id': len(steps) + 1,
            'action': m.group(2).strip() or None,
            'input': None,
            'expected_result': None,
        }
        continue

    if current is not None:
        fm = field_re.match(line)
        if fm:
            key = fm.group(1).lower()
            value = fm.group(2).strip() or None
            if key == 'input':
                current['input'] = value
            elif key == 'expected result':
                current['expected_result'] = value

if current is not None:
    steps.append(current)

out_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'wrote {out_path}')
print(json.dumps(steps, ensure_ascii=False, indent=2))

# Verification: reopen output and check stated requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'output must be a JSON array'
assert len(loaded) == 3, f'expected 3 numbered steps before 注意事項, got {len(loaded)}'
required_keys = ['step_id', 'action', 'input', 'expected_result']
for idx, row in enumerate(loaded, 1):
    assert list(row.keys()) == required_keys, f'row {idx} keys differ: {list(row.keys())}'
    assert row['step_id'] == idx, f'step_id must be sequential from 1 at row {idx}'
    assert row['action'] is None or isinstance(row['action'], str), f'action type invalid at row {idx}'
    assert row['input'] is None or isinstance(row['input'], str), f'input type invalid at row {idx}'
    assert row['expected_result'] is None or isinstance(row['expected_result'], str), f'expected_result type invalid at row {idx}'

assert loaded[0] == {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'}
assert loaded[1] == {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'}
assert loaded[2] == {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None}
print('verification passed: sop.json exists, has 3 steps, sequential step_id 1..3, required keys only, missing fields are null, 注意事項 ignored.')