from pathlib import Path
import csv
ws=Path.cwd()
out=ws/'output'
cache=out/'order_detail_cache.csv'
details = {
"0045000109": {"CustomerContact": "Grace Lin <grace.lin@acme-precision.example>", "PaymentTerms": "NET10"},
"0045000110": {"CustomerContact": "張美玲 <mei@tw-precision.example>", "PaymentTerms": "NET30"},
"0045000112": {"CustomerContact": "Peter Ho <peter.ho@acme-limited.example>", "PaymentTerms": "NET15"},
"0045000113": {"CustomerContact": "", "PaymentTerms": "NET15"},
"0045000115": {"CustomerContact": "Sam Patel <sam@pacifictest.example>", "PaymentTerms": "NET20"},
"0045000116": {"CustomerContact": "李建宏 <jh.lee@hsinchu-metrology.example>", "PaymentTerms": "NET30"},
"0045000118": {"CustomerContact": "Jonas Krüger <jk@northwind.example>", "PaymentTerms": "NET0"},
"0045000119": {"CustomerContact": "Grace Lin <grace.lin@acme-precision.example>", "PaymentTerms": "NET30"},
"0045000120": {"CustomerContact": "Eva de Vries <eva@helios.example>", "PaymentTerms": "NET10"},
"0045000122": {"CustomerContact": "張美玲 <mei@tw-precision.example>", "PaymentTerms": "NET5"},
"0045000124": {"CustomerContact": "", "PaymentTerms": "NET30"},
"0045000126": {"CustomerContact": "李建宏 <jh.lee@hsinchu-metrology.example>", "PaymentTerms": "NET30"},
"0045000127": {"CustomerContact": "Peter Ho <peter.ho@acme-limited.example>", "PaymentTerms": "NET30"},
"0045000128": {"CustomerContact": "Jonas Krüger <jk@northwind.example>", "PaymentTerms": "NET5"},
}
with open(cache,'w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=['OrderID','CustomerContact','PaymentTerms'])
    w.writeheader()
    for oid in sorted(details):
        w.writerow({'OrderID': oid, **details[oid]})
print('wrote cache', cache)
# verify deliverable exists and cache rows
print('deliverable exists', (out/'september_open_orders.xlsx').exists())
with open(cache, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('cache rows', len(rows), 'headers', rows[0].keys())