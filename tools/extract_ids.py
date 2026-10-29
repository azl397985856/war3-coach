#!/usr/bin/env python3
"""从 1.27 TFT UnitBalance/UnitUI SLK 提取对战单位 ID 映射表 -> parser/data/units.json"""
import json, re, sys

def parse_slk(path):
    header, rows = {}, {}
    cur = 1  # 当前行号, Y1=表头
    with open(path, 'r', encoding='latin-1') as f:
        for line in f:
            line = line.rstrip('\r\n')
            if not line.startswith('C;'): continue
            x = re.search(r'X(\d+)', line); y = re.search(r'Y(\d+)', line)
            k = re.search(r'K(?:"(.*)"|(.+))$', line)
            if not k: continue
            val = k.group(1) if k.group(1) is not None else k.group(2)
            if y: cur = int(y.group(1))
            target = header if cur == 1 else rows.setdefault(cur, {})
            target[int(x.group(1))] = val
    return [{header.get(x, f'col{x}'): v for x, v in d.items()} for _, d in sorted(rows.items())]

bal = parse_slk('/tmp/slk_tft_UnitBalance.slk')
ui  = parse_slk('/tmp/slk_tft_UnitUI.slk')
uimap = {r.get('unitUIID'): r for r in ui if 'unitUIID' in r}

units = {}
for r in bal:
    uid = r.get('unitBalanceID')
    if not uid: continue
    u = uimap.get(uid, {})
    units[uid] = {
        'name': u.get('name', ''),
        'race': r.get('sort2', ''), 'level': r.get('level', ''),
        'isbldg': r.get('isbldg', ''),
        'gold': r.get('goldcost', ''), 'lumber': r.get('lumbercost', ''),
    }
json.dump(units, open(sys.argv[1] if len(sys.argv)>1 else 'parser/data/units.json','w'), ensure_ascii=False, indent=0)
print('total:', len(units))
for pre, label in [('h','HUM'),('o','ORC'),('u','UD'),('e','NE')]:
    ids = [k for k,v in sorted(units.items()) if k.startswith(pre)]
    print(f'{label}: {len(ids)}')
