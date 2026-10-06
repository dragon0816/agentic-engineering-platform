from pathlib import Path
from openpyxl import Workbook
import re

ws = Path.cwd()
input_path = ws/'input'/'specs.md'
output_path = ws/'output'/'specs.xlsx'
output_path.parent.mkdir(parents=True, exist_ok=True)
text = input_path.read_text(encoding='utf-8')
print('--- specs.md ---')
print(text)
print('--- end ---')

# Helpers
UNIT_FACTORS_TO_MHZ = {
    'hz': 1e-6,
    'khz': 1e-3,
    'mhz': 1.0,
    'ghz': 1000.0,
}

def to_mhz(num_s, unit):
    val = float(num_s.replace(',', ''))
    return val * UNIT_FACTORS_TO_MHZ[unit.lower()]

def fmt_num(x):
    if x is None:
        return None
    if abs(x - round(x)) < 1e-9:
        return int(round(x))
    return x

def split_products(md):
    # Split into non-empty paragraph/list blocks. A product paragraph is any block with a model-like field/name.
    blocks = []
    cur = []
    for line in md.splitlines():
        if line.strip():
            cur.append(line.rstrip())
        elif cur:
            blocks.append('\n'.join(cur))
            cur=[]
    if cur:
        blocks.append('\n'.join(cur))
    # Prefer markdown headings with following text, if present
    products=[]
    current=None
    for line in md.splitlines():
        if re.match(r'^#{1,6}\s+', line):
            if current:
                products.append('\n'.join(current).strip())
            current=[line]
        elif current is not None:
            if line.strip() or current:
                current.append(line)
    if current:
        products.append('\n'.join(current).strip())
    products=[p for p in products if re.search(r'(?i)\b(model|frequency|bandwidth|interface)\b', p)]
    if len(products) >= 3:
        return products[:3]
    # Fallback: blocks that mention model/frequency/etc, excluding title-only blocks
    candidates=[b for b in blocks if re.search(r'(?i)\b(model|frequency|bandwidth|interface)\b', b)]
    return candidates[:3]

def extract_model(block):
    patterns = [
        r'(?im)^\s*(?:[-*]\s*)?(?:Model|型號)\s*[:：]\s*([^\n;,]+)',
        r'(?i)\bModel\s+([A-Za-z0-9][A-Za-z0-9._\-/]+)',
        r'(?im)^\s*#{1,6}\s*([^\n]+)',
        r'(?im)^\s*(?:[-*]\s*)?([A-Za-z][A-Za-z0-9._\-/]{1,})\s*(?:[:：-]|$)',
    ]
    for pat in patterns:
        m = re.search(pat, block)
        if m:
            s=m.group(1).strip()
            # remove trailing field text if heading includes description
            s=re.split(r'\s+[–—-]\s+|\s+\|\s+', s)[0].strip()
            return s
    return ''

def extract_freq(block):
    # isolate phrases/lines containing frequency/freq
    lines=' '.join([ln.strip() for ln in block.splitlines() if re.search(r'(?i)freq(?:uency)?|頻率', ln)])
    if not lines:
        return None, None
    # range: 100 MHz to 6 GHz / 100 MHz - 6 GHz / 100 MHz ~ 6 GHz
    pat = r'([0-9]+(?:\.[0-9]+)?)\s*(Hz|kHz|MHz|GHz)\s*(?:to|through|[-–—~]|\.\.)\s*([0-9]+(?:\.[0-9]+)?)\s*(Hz|kHz|MHz|GHz)'
    m=re.search(pat, lines, flags=re.I)
    if m:
        return fmt_num(to_mhz(m.group(1), m.group(2))), fmt_num(to_mhz(m.group(3), m.group(4)))
    # range: 100 to 6000 MHz (unit after second number)
    pat2 = r'([0-9]+(?:\.[0-9]+)?)\s*(?:to|through|[-–—~]|\.\.)\s*([0-9]+(?:\.[0-9]+)?)\s*(Hz|kHz|MHz|GHz)'
    m=re.search(pat2, lines, flags=re.I)
    if m:
        return fmt_num(to_mhz(m.group(1), m.group(3))), fmt_num(to_mhz(m.group(2), m.group(3)))
    # up to / max
    m=re.search(r'(?i)(?:up to|max(?:imum)?)\s*([0-9]+(?:\.[0-9]+)?)\s*(Hz|kHz|MHz|GHz)', lines)
    if m:
        return None, fmt_num(to_mhz(m.group(1), m.group(2)))
    return None, None

def extract_bandwidth(block):
    lines=' '.join([ln.strip() for ln in block.splitlines() if re.search(r'(?i)band\s*width|bandwidth|BW|頻寬|帶寬', ln)])
    if not lines:
        return None
    # avoid grabbing ranges; take first value associated with bandwidth
    m=re.search(r'(?i)(?:band\s*width|bandwidth|BW|頻寬|帶寬)\s*(?:[:：=]|of|up to|max(?:imum)?|is)?\s*([0-9]+(?:\.[0-9]+)?)\s*(Hz|kHz|MHz|GHz)', lines)
    if not m:
        m=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(Hz|kHz|MHz|GHz)\s*(?:band\s*width|bandwidth|BW|頻寬|帶寬)', lines, flags=re.I)
    if m:
        return fmt_num(to_mhz(m.group(1), m.group(2)))
    return None

def extract_interface(block):
    # get interface field text from line(s)
    vals=[]
    for ln in block.splitlines():
        if re.search(r'(?i)interfaces?|I/O|ports?|介面|接口', ln):
            if re.search(r'(?i)freq(?:uency)?', ln) and not re.search(r'(?i)interfaces?|I/O|ports?|介面|接口', ln):
                continue
            s=ln.strip()
            s=re.sub(r'^\s*[-*]\s*', '', s)
            s=re.sub(r'(?i)^\s*(?:interfaces?|I/O|ports?|介面|接口)\s*[:：=]?\s*', '', s)
            # If line says "Interface: ..."
            if re.search(r'(?i)interfaces?|I/O|ports?|介面|接口', s):
                parts=re.split(r'[:：]', s, maxsplit=1)
                if len(parts)>1:
                    s=parts[1]
            # remove parenthetical descriptions? keep names only, but don't invent.
            for part in re.split(r'\s*(?:,|;|/\s*(?=[A-Za-z])|\band\b|＆|、)\s*', s):
                part=part.strip().strip('. ')
                if not part:
                    continue
                # Stop before next specs embedded in same paragraph
                part=re.split(r'(?i)\b(?:Frequency|Bandwidth|Model)\b\s*[:：]', part)[0].strip().strip('. ')
                if part and part not in vals:
                    vals.append(part)
    return '; '.join(vals)

products=split_products(text)
print(f'Found {len(products)} product blocks')
rows=[]
for i,b in enumerate(products,1):
    model=extract_model(b)
    fmin,fmax=extract_freq(b)
    bw=extract_bandwidth(b)
    iface=extract_interface(b)
    row=[model, fmin, fmax, bw, iface]
    rows.append(row)
    print(f'Product {i}:', row)
    print('BLOCK:', b)

wb=Workbook()
sh=wb.active
sh.title='Specs'
headers=['Model','FrequencyMinMHz','FrequencyMaxMHz','BandwidthMHz','Interface']
sh.append(headers)
for row in rows:
    sh.append(['' if v is None else v for v in row])
# widths
for col in sh.columns:
    maxlen=max(len(str(c.value)) if c.value is not None else 0 for c in col)
    sh.column_dimensions[col[0].column_letter].width=max(14, min(maxlen+2, 40))
wb.save(output_path)
print('Wrote', output_path)
