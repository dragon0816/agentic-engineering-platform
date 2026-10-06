from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'sop.md'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')

steps = []
current = None
in_steps = False

for raw_line in text.splitlines():
    line = raw_line.rstrip('\n')
    stripped = line.strip()

    # Ignore notes and anything after the notes heading.
    if re.match(r'^#{1,6}\s*注意事項\s*$', stripped):
        break

    m = re.match(r'^(\d+)\.\s*(.*)$', stripped)
    if m:
        if current is not None:
            steps.append(current)
        in_steps = True
        current = {
            'step_id': len(steps) + 1,
            'action': None,
            'input': None,
            'expected_result': None,
        }
        rest = m.group(2).strip()
        if rest:
            field_match = re.match(r'^(Action|Input|Expected result)\s*:\s*(.*)$', rest, flags=re.IGNORECASE)
            if field_match:
                label = field_match.group(1).lower()
                value = field_match.group(2).strip()
                if label == 'action':
                    current['action'] = value if value != '' else None
                elif label == 'input':
                    current['input'] = value if value != '' else None
                elif label == 'expected result':
                    current['expected_result'] = value if value != '' else None
        continue

    if not in_steps or current is None or not stripped:
        continue

    field_match = re.match(r'^(Action|Input|Expected result)\s*:\s*(.*)$', stripped, flags=re.IGNORECASE)
    if field_match:
        label = field_match.group(1).lower()
        value = field_match.group(2).strip()
        if label == 'action':
            current['action'] = value if value != '' else None
        elif label == 'input':
            current['input'] = value if value != '' else None
        elif label == 'expected result':
            current['expected_result'] = value if value != '' else None

if current is not None:
    steps.append(current)

output_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification: reopen output and confirm requirements.
data = json.loads(output_path.read_text(encoding='utf-8'))
required_keys = ['step_id', 'action', 'input', 'expected_result']
assert isinstance(data, list), 'Output JSON must be a list'
assert len(data) == 3, f'Expected 3 numbered steps, got {len(data)}'
for idx, item in enumerate(data, start=1):
    assert list(item.keys()) == required_keys, f'Step {idx} keys/order mismatch: {list(item.keys())}'
    assert item['step_id'] == idx, f'Step {idx} has wrong step_id {item["step_id"]}'
    assert item['action'] is None or isinstance(item['action'], str), f'Step {idx} action type invalid'
    assert item['input'] is None or isinstance(item['input'], str), f'Step {idx} input type invalid'
    assert item['expected_result'] is None or isinstance(item['expected_result'], str), f'Step {idx} expected_result type invalid'

assert data[0] == {
    'step_id': 1,
    'action': '開啟量測儀器電源',
    'input': '主電源開關',
    'expected_result': '儀器開機畫面出現',
}
assert data[1] == {
    'step_id': 2,
    'action': '執行自我校正',
    'input': None,
    'expected_result': '校正狀態顯示 OK',
}
assert data[2] == {
    'step_id': 3,
    'action': '記錄環境溫度',
    'input': '溫度計讀值',
    'expected_result': None,
}

print('Wrote:', output_path)
print('Verified: JSON list with 3 steps, step_id values 1..3, exact keys step_id/action/input/expected_result, missing fields as null, and notes/preface excluded.')
print(output_path.read_text(encoding='utf-8'))