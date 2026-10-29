#!/usr/bin/env python3
"""单局分析: BO 时间轴 / APM / 升本开矿时点 / 英雄技能加点 / 部队构成 / 道具。

事件分类依据 (经典 1.27 格式, 已对样例验证):
  Ability(无目标)         -> 训练单位 / 升本 / 研究 / 学技能 / 买英雄
  AbilityPosition(+Object)-> 造建筑(带坐标) / 施法
  数值 fourCC (\r\x00 尾) -> 移动/攻击等普通指令, 不进 BO
"""
from collections import Counter, defaultdict

from parser.names import UNIT_CN, HERO_CN, fmt_ability

# 判定数值型指令 (移动/攻击/简单命令, fourCC 是小端数值)
def _is_numeric(ab):
    if not ab or len(ab) != 4:
        return True
    if ab[-2:] == b'\r\x00':
        return True
    return ab[:1].isdigit()

_BUILDINGS = {k for k, v in UNIT_CN.items() if v and (
    '升本' in v or k in (
        'oalt', 'obar', 'ofor', 'otrb', 'owtw', 'obea', 'osld', 'ovln', 'otto',
        'uaod', 'usep', 'uslh', 'ugrv', 'utod', 'utom', 'usap', 'ubon',
        'uzig', 'uzg1', 'uzg2',
        'eate', 'eaom', 'eaoe', 'eaow', 'edos', 'edob', 'etrp', 'egol', 'emow', 'eden',
        'halt', 'hbar', 'hhou', 'hbla', 'hlum', 'hars', 'harm', 'hgra',
        'hgtw', 'hctw', 'hatw', 'hwtw',
    ))}
_T2 = {'ostr': 2, 'unp1': 2, 'etoa': 2, 'hkee': 2}
_T3 = {'ofrt': 3, 'unp2': 3, 'etoe': 3, 'hcas': 3}
_MAIN_HALLS = {'ogre', 'ostr', 'ofrt', 'unpl', 'unp1', 'unp2', 'htow', 'hkee', 'hcas',
               'etol', 'etoa', 'etoe'}
_ITEMS = {'bspd', 'plcl', 'dust', 'shas', 'shea', 'cnob', 'spro', 'pnvl', 'stwp',
          'ssan', 'phea', 'pman', 'ckng', 'evtl', 'infs', 'belv', 'crys',
          'ofir', 'oli2', 'olig', 'odef', 'gcel', 'whwd'}


def _try_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


class PlayerAnalysis:
    def __init__(self, player):
        self.player = player
        self.apm_by_minute = []          # [n0, n1, ...]
        self.bo = []                     # [{t, kind, id, cn}]
        self.tech = {}                   # {'tier2': 秒, 'tier3': 秒}
        self.expansions = []             # [{t, loc}]
        self.hero_skills = []            # [{t, id, cn}] 按时间序=加点顺序
        self.heroes = []                 # 出场的英雄 id 序列
        self.items_bought = Counter()    # id -> 次数
        self.units_trained = Counter()   # id -> 次数
        self.actions_total = 0
        self.first_base_loc = None


def analyze_player(replay, pid):
    a = PlayerAnalysis(replay.by_pid[pid])
    minutes_bucket = defaultdict(int)

    for e in replay.events:
        if e.player_id != pid:
            continue
        t = e.time / 1000.0
        if getattr(e, 'apm', False):
            minutes_bucket[int(t // 60)] += 1
            a.actions_total += 1

        cls = type(e).__name__
        if cls not in ('Ability', 'AbilityPosition', 'AbilityPositionObject', 'DoubleAbility'):
            continue
        ab = getattr(e, 'ability', None)
        if _is_numeric(ab):
            continue
        s = ab.decode('latin-1')
        loc = getattr(e, 'loc', None)

        # 道具使用 (商店购买或使用)
        if s in _ITEMS:
            a.items_bought[s] += 1
            a.bo.append({'t': round(t, 1), 'kind': 'item', 'id': s,
                         'cn': fmt_ability(ab)})
            continue

        # 英雄相关
        if s in HERO_CN:
            if not a.heroes or a.heroes[-1]['id'] != s:
                a.heroes.append({'t': round(t, 1), 'id': s, 'cn': HERO_CN[s]})
            a.bo.append({'t': round(t, 1), 'kind': 'hero', 'id': s, 'cn': HERO_CN[s]})
            continue

        # 学技能 (A 开头)
        if s.startswith('A') and s[1:2].isupper():
            a.hero_skills.append({'t': round(t, 1), 'id': s, 'cn': fmt_ability(ab)})
            a.bo.append({'t': round(t, 1), 'kind': 'skill', 'id': s, 'cn': fmt_ability(ab)})
            continue

        # 升本
        if s in _T2:
            a.tech.setdefault('tier2', round(t, 1))
            a.bo.append({'t': round(t, 1), 'kind': 'tech', 'id': s, 'cn': UNIT_CN[s]})
            continue
        if s in _T3:
            a.tech.setdefault('tier3', round(t, 1))
            a.bo.append({'t': round(t, 1), 'kind': 'tech', 'id': s, 'cn': UNIT_CN[s]})
            continue

        # 造建筑 / 训练单位
        if s in UNIT_CN:
            a.units_trained[s] += 1
            kind = 'build' if s in _BUILDINGS else 'train'
            if s in _MAIN_HALLS and loc:
                # 开矿: 远离首个主基地坐标的新主基地
                if a.first_base_loc is None:
                    a.first_base_loc = loc
                else:
                    dx = loc[0] - a.first_base_loc[0]
                    dy = loc[1] - a.first_base_loc[1]
                    if (dx * dx + dy * dy) ** 0.5 > 2500:
                        a.expansions.append({'t': round(t, 1), 'loc': [round(loc[0]), round(loc[1])]})
            a.bo.append({'t': round(t, 1), 'kind': kind, 'id': s, 'cn': UNIT_CN[s]})
            continue

        # 研究 (R 开头); 其余未收录 fourCC 是无分析价值的噪音指令, 丢弃
        if s.startswith('R') and s[1:2].isupper():
            a.bo.append({'t': round(t, 1), 'kind': 'research', 'id': s,
                         'cn': fmt_ability(ab)})

    a.apm_by_minute = [minutes_bucket[m] for m in range(max(minutes_bucket) + 1)] if minutes_bucket else []
    a.bo = _dedupe_bo(a.bo)
    return a


# 同一动作的确认连点合并窗口 (秒): build/tech/hero/item 连点重复 -> 1 条;
# train 队列连点 (间隔远小于真实出兵周期) -> 1 条, 计数已在 units_trained 保留。
_DEDUPE_WIN = {'build': 6, 'tech': 10, 'hero': 6, 'item': 4, 'train': 2.5,
               'skill': 0.8, 'research': 2}


def _dedupe_bo(bo):
    out = []
    last = {}
    for e in bo:
        win = _DEDUPE_WIN.get(e['kind'])
        key = (e['kind'], e['id'])
        if win is not None and key in last and e['t'] - last[key] < win:
            continue
        if win is not None:
            last[key] = e['t']
        out.append(e)
    return out


def analyze(replay):
    """整局分析 -> dict。"""
    out = {'meta': replay.summary(), 'players': {}}
    real = replay.real_players()
    # team 映射: team 12/24 已在 replay 层标为观察者
    for p in real:
        a = analyze_player(replay, p.pid)
        out['players'][p.pid] = {
            'name': p.name, 'race': p.race, 'team': p.team,
            'host': p.is_host,
            'apm_total': a.actions_total,
            'apm_avg': round(a.actions_total / max(1, _try_float(replay.length_ms) / 60000), 1),
            'apm_by_minute': a.apm_by_minute,
            'bo': a.bo,
            'tech': a.tech,
            'expansions': a.expansions,
            'heroes': a.heroes,
            'hero_skills': a.hero_skills,
            'units_trained': dict(a.units_trained),
            'items': dict(a.items_bought),
        }
    return out
