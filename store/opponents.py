#!/usr/bin/env python3
"""对手库: 跨局累积记录 + 查询。

记录一局 -> data/opponents.json; 下次匹配到老对手先查历史
(他用什么种族/什么战术/我赢过几次), 开局前 30 秒决策用。
"""
import json
import os
import time
from collections import Counter, defaultdict

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'opponents.json')

# LeftGame resultflag (w3g.py 语义 + KK 实测校准 2026-11-03)
FLAG_LOST = 0x08
FLAG_WON = 0x09
# KK 平台 1v1 实测: 败者退出走 flag=0x0d 且游戏随即(<5s)结束;
# 用"离场即终局"约束防误判中途退出(多人局普通退出也是 0x0d)。
FLAG_KK_LOST = 0x0D
_END_WIN_MS = 5000


def game_result(replay):
    """从 LeftGame 事件推断各 pid 胜负 -> {pid: 'win'|'loss'|None}"""
    result = {}
    events = list(replay.events)
    if not events:
        return result
    end_ms = events[-1].time
    for e in events:
        if type(e).__name__ == 'LeftGame':
            if e.resultflag == FLAG_LOST:
                result[e.player_id] = 'loss'
            elif e.resultflag == FLAG_WON:
                result[e.player_id] = 'win'
            elif (e.resultflag == FLAG_KK_LOST
                  and end_ms - e.time <= _END_WIN_MS):
                result[e.player_id] = 'loss'
    # 败者已判 -> 同局其余人判胜 (1v1 语义; 多人局保守不判)
    losers = [pid for pid, r in result.items() if r == 'loss']
    if losers:
        n_players = len(replay.real_players())
        if n_players == 2:
            for p in replay.real_players():
                if result.get(p.pid) is None:
                    result[p.pid] = 'win'
    return result


def summarize_bo(bo, limit=8):
    """BO 压缩成对手库摘要: 关键节点序列。"""
    keep = [e for e in bo if e['kind'] in ('build', 'tech', 'hero')
            and e['t'] <= 360]
    seen, out = set(), []
    for e in keep:
        if e['id'] in seen and e['kind'] in ('tech', 'hero'):
            continue
        seen.add(e['id'])
        out.append(f"{int(e['t']//60)}:{int(e['t']%60):02d} {e['cn']}")
        if len(out) >= limit:
            break
    return ' -> '.join(out)


class OpponentDB:
    def __init__(self, path=DEFAULT_DB):
        self.path = path
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                self.db = json.load(f)
        else:
            self.db = {'games': [], 'version': 1}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.db, f, ensure_ascii=False, indent=1)

    def record(self, replay, my_name, analysis=None, won=None):
        """录入一局。won 缺省时用回放胜负信号。"""
        result = game_result(replay)
        meta = replay.summary()
        date = time.strftime('%Y-%m-%d %H:%M', time.localtime())
        rec = {
            'file': os.path.basename(replay.path),
            'map': (meta['map'] or '').split('\\')[-1],
            'date': date,
            'ts': int(time.time()),
            'length_s': meta['length_s'],
            'players': [],
        }
        for pid, p in analysis['players'].items():
            pl = replay.by_pid.get(int(pid))
            res = result.get(int(pid))
            if won is not None and pl and pl.name == my_name:
                res = 'win' if won else 'loss'
            entry = {
                'pid': pid, 'name': p['name'], 'race': p['race'],
                'result': res,
                'apm': p['apm_total'],
                'tech': p['tech'],
                'heroes': [h['cn'] for h in p['heroes']],
                'bo_summary': summarize_bo(p['bo']),
            }
            rec['players'].append(entry)
        self.db['games'].append(rec)
        self.save()
        return rec

    def lookup(self, name):
        """某对手的全部交手记录。"""
        return [g for g in self.db['games']
                if any(p['name'] == name and p['result'] is not None
                       for p in g['players'])]

    def faceoffs(self, my_name, opp_name):
        """我与某对手的交手。"""
        out = []
        for g in self.db['games']:
            me = next((p for p in g['players'] if p['name'] == my_name), None)
            opp = next((p for p in g['players'] if p['name'] == opp_name), None)
            if me and opp and me['result']:
                out.append({
                    'date': g['date'], 'map': g['map'],
                    'my_race': me['race'], 'opp_race': opp['race'],
                    'won': me['result'] == 'win',
                    'opp_heroes': opp['heroes'], 'opp_bo': opp['bo_summary'],
                })
        return out

    def my_stats(self, my_name):
        """我的跨局统计。"""
        games = [g for g in self.db['games']
                 if any(p['name'] == my_name and p['result'] for p in g['players'])]
        total = wins = 0
        by_race = defaultdict(lambda: [0, 0])   # race -> [win, total]
        streak = []
        for g in sorted(games, key=lambda x: x['ts']):
            me = next(p for p in g['players']
                      if p['name'] == my_name and p['result'])
            opp = next((p for p in g['players']
                        if p['name'] != my_name and p.get('result')), None)
            won = me['result'] == 'win'
            total += 1
            wins += won
            streak.append(won)
            race = (opp or {}).get('race') or '?'
            by_race[race][0] += won
            by_race[race][1] += 1
        return {
            'total': total, 'wins': wins,
            'winrate': round(wins / total * 100, 1) if total else 0,
            'by_race': {r: f'{w}/{t} ({round(w/t*100)}%)' for r, (w, t) in by_race.items()},
            'streak': ''.join('✓' if s else '✗' for s in streak[-15:]),
        }
