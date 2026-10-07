from pathlib import Path
import json
import re

ws = Path.cwd()
input_path = ws / 'input' / 'sop.md'
out_dir = ws / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')

# Parse only numbered steps. Stop when a non-numbered heading that is 注意事項 appears.
lines = text.splitlines()
steps = []
current = None
current_field = None

step_re = re.compile(r'^\s*(\d+)\.\s*(.*)\s*$')
field_re = re.compile(r'^\s*(Action|Input|Expected result)\s*:\s*(.*)\s*$', re.IGNORECASE)
heading_re = re.compile(r'^\s*#{1,6}\s*(.*?)\s*$')

def finish_current():
    if current is not None:
        steps.append(current.copy())

for line in lines:
    h = heading_re.match(line)
    if h and '注意事項' in h.group(1):
        finish_current()
        current = None
        break

    m = step_re.match(line)
    if m:
        finish_current()
        current = {'action': None, 'input': None, 'expected_result': None}
        current_field = None
        rest = m.group(2).strip()
        fm = field_re.match(rest)
        if fm:
            label = fm.group(1).lower()
            value = fm.group(2).strip() or None
            key = {'action':'action','input':'input','expected result':'expected_result'}[label]
            current[key] = value
            current_field = key
        continue

    if current is None:
        continue

    fm = field_re.match(line)
    if fm:
        label = fm.group(1).lower()
        value = fm.group(2).strip() or None
        key = {'action':'action','input':'input','expected result':'expected_result'}[label]
        current[key] = value
        current_field = key
        continue

    # If a field value wraps onto an indented continuation line, append it.
    if current_field and line.strip():
        current[current_field] = (current[current_field] + ' ' + line.strip()) if current[current_field] else line.strip()

# If no 注意事項 heading appeared, close the last step.
if current is not None and (not steps or steps[-1] is not current):
    # Avoid duplicate if already appended before break; object identity copy prevents identity check, so use content guard.
    if not steps or steps[-1] != current:
        steps.append(current.copy())

result = []
for idx, step in enumerate(steps, start=1):
    result.append({
        'step_id': idx,
        'action': step.get('action'),
        'input': step.get('input'),
        'expected_result': step.get('expected_result'),
    })

out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {out_path}')
print(json.dumps(result, ensure_ascii=False, indent=2))

# Verification: reopen output and confirm requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'output must be a JSON array'
assert len(loaded) == 3, f'expected 3 numbered steps, got {len(loaded)}'
expected_keys = ['step_id', 'action', 'input', 'expected_result']
for i, item in enumerate(loaded, start=1):
    assert list(item.keys()) == expected_keys, f'keys/order mismatch at step {i}: {list(item.keys())}'
    assert item['step_id'] == i, f'step_id mismatch at step {i}'
assert loaded[0] == {'step_id': 1, 'action': '開啟量測儀器電源', 'input': '主電源開關', 'expected_result': '儀器開機畫面出現'}
assert loaded[1] == {'step_id': 2, 'action': '執行自我校正', 'input': None, 'expected_result': '校正狀態顯示 OK'}
assert loaded[2] == {'step_id': 3, 'action': '記錄環境溫度', 'input': '溫度計讀值', 'expected_result': None}
print('verification passed: sop.json exists, has 3 steps, sequential step_id, required columns, nulls for missing input/expected_result, and excludes preface/notes.')