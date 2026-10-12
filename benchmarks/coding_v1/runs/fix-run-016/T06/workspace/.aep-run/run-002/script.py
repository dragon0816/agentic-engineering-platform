from pathlib import Path
import json
import re

ws = Path.cwd()
input_path = ws / 'input' / 'sop.md'
out_dir = ws / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8')

# Ignore notes section and anything after it.
text_before_notes = re.split(r'^##\s*注意事項\s*$', text, flags=re.MULTILINE)[0]

# Find numbered SOP steps. Each block starts with "N." and ends before the next numbered step or EOF.
pattern = re.compile(r'^\s*(\d+)\.\s*(.*?)(?=^\s*\d+\.\s*|\Z)', re.MULTILINE | re.DOTALL)
steps = []
for match in pattern.finditer(text_before_notes):
    block = match.group(2).strip('\n')
    fields = {'Action': None, 'Input': None, 'Expected result': None}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        for label in list(fields):
            prefix = label + ':'
            if line.startswith(prefix):
                value = line[len(prefix):].strip()
                fields[label] = value if value != '' else None
                break
    # Only convert numbered blocks that have an Action line; preface text has no numbered block here,
    # and we do not invent any missing values.
    if fields['Action'] is not None:
        steps.append({
            'step_id': len(steps) + 1,
            'action': fields['Action'],
            'input': fields['Input'],
            'expected_result': fields['Expected result'],
        })

out_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'WROTE {out_path}')
print(json.dumps(steps, ensure_ascii=False, indent=2))

# Verification: reopen output and confirm requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'sop.json must contain a JSON list'
expected_keys = ['step_id', 'action', 'input', 'expected_result']
assert len(loaded) == 3, f'expected 3 numbered steps before 注意事項, got {len(loaded)}'
for i, item in enumerate(loaded, start=1):
    assert list(item.keys()) == expected_keys, f'keys/order mismatch at step {i}: {list(item.keys())}'
    assert item['step_id'] == i, f'step_id should be sequential from 1 at step {i}'
    assert isinstance(item['action'], str) and item['action'], f'action missing at step {i}'
    assert item['input'] is None or isinstance(item['input'], str), f'input should be string or null at step {i}'
    assert item['expected_result'] is None or isinstance(item['expected_result'], str), f'expected_result should be string or null at step {i}'
assert loaded[1]['input'] is None, 'missing input in source step 2 should be null'
assert loaded[2]['expected_result'] is None, 'missing expected result in source step 3 should be null'
assert all('注意事項' not in json.dumps(item, ensure_ascii=False) for item in loaded), '注意事項 content should be ignored'
print('CHECK PASSED: output file exists, JSON list has 3 steps, required keys, sequential step_id, missing fields as null, notes ignored.')