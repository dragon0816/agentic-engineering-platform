from pathlib import Path
import os
for rel in ['..','../..','../../..','../../../..','../../../../..']:
    p=Path(rel).resolve()
    print('\n##', rel, p)
    try:
        for child in list(p.iterdir())[:50]:
            print(' ', child.name)
    except Exception as e:
        print(' ERR',e)