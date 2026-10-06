from pathlib import Path
import re, json

workspace = Path.cwd()
input_path = workspace / 'input' / 'sop.md'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'sop.json'

text = input_path.read_text(encoding='utf-8-sig')
lines = text.splitlines()

step_start_re = re.compile(r'^\s*(\d+)\s*[\.、\)）]\s*(.*?)\s*$')
heading_re = re.compile(r'^\s{0,3}#{1,6}\s*(.*?)\s*#*\s*$')
notes_heading_re = re.compile(r'(注意事項|注意|備註|附註|notes?|cautions?)', re.I)

# Keep only numbered SOP steps. Ignore preface before the first step, and stop at notes/cautions sections.
blocks = []
current = None
in_notes = False
for line in lines:
    hm = heading_re.match(line)
    if hm and notes_heading_re.search(hm.group(1)):
        in_notes = True
        if current is not None:
            blocks.append(current)
            current = None
        continue
    if in_notes:
        continue

    m = step_start_re.match(line)
    if m:
        if current is not None:
            blocks.append(current)
        current = {'orig_no': int(m.group(1)), 'first': m.group(2).strip(), 'body': []}
    elif current is not None:
        current['body'].append(line)

if current is not None:
    blocks.append(current)

label_re = re.compile(
    r'^\s*(?:[-*+]\s*)?(?:\*\*)?\s*'
    r'(action|動作|操作|步驟|執行|input|輸入|expected(?:\s+result)?|expected_result|預期(?:結果)?|結果)'
    r'\s*(?:\*\*)?\s*[:：-]\s*(.*)\s*$',
    re.I,
)

def clean(s):
    s = re.sub(r'\s+', ' ', s).strip()
    return s if s else None

def add_value(store, key, value):
    value = clean(value)
    if not value:
        return
    if store[key] is None:
        store[key] = value
    else:
        store[key] += ' ' + value

steps = []
for idx, block in enumerate(blocks, start=1):
    fields = {'action': None, 'input': None, 'expected_result': None}

    first = block['first']
    m = label_re.match(first)
    current_key = None
    if m:
        label = m.group(1).lower().replace('_', ' ')
        if label in {'input', '輸入'}:
            current_key = 'input'
        elif label.startswith('expected') or label in {'預期', '預期結果', '結果'}:
            current_key = 'expected_result'
        else:
            current_key = 'action'
        add_value(fields, current_key, m.group(2))
    else:
        current_key = 'action'
        add_value(fields, 'action', first)

    for raw in block['body']:
        line = raw.strip()
        if not line:
            continue
        m = label_re.match(line)
        if m:
            label = m.group(1).lower().replace('_', ' ')
            if label in {'input', '輸入'}:
                current_key = 'input'
            elif label.startswith('expected') or label in {'預期', '預期結果', '結果'}:
                current_key = 'expected_result'
            else:
                current_key = 'action'
            add_value(fields, current_key, m.group(2))
        else:
            # Continuation lines only extend an explicitly labelled field, so we do not invent
            # missing input/expected_result values from unrelated text.
            if current_key in fields:
                # Remove common markdown list markers without changing meaning.
                cont = re.sub(r'^[-*+]\s+', '', line)
                add_value(fields, current_key, cont)

    steps.append({
        'step_id': idx,
        'action': fields['action'],
        'input': fields['input'],
        'expected_result': fields['expected_result'],
    })

output_path.write_text(json.dumps(steps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print(f'Read: {input_path}')
print(f'Wrote: {output_path}')
print(f'Parsed steps: {len(steps)}')
print(output_path.read_text(encoding='utf-8'))