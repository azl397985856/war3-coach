#!/usr/bin/env python3
"""w3g/nwg 回放解析封装。

- 标准经典格式 .w3g (1.00-1.29 系列, 覆盖 KK 平台 1.27)
- 网易包装 .nwg (GRBN 头, 内嵌标准 w3g)
底层用 pip 的 w3g 库 (经典 action 表, 分版正确), 这里只做接口整形。
"""
import io
import json
import os

import w3g as _w3g

_UNITS_JSON = os.path.join(os.path.dirname(__file__), 'data', 'units.json')
_MAPHASH_JSON = os.path.join(os.path.dirname(__file__), 'data', 'map_hash.json')


def _load_units():
    with open(_UNITS_JSON, encoding='utf-8') as f:
        return json.load(f)


UNITS = _load_units()


def _load_maphash():
    try:
        with open(_MAPHASH_JSON, encoding='utf-8') as f:
            return json.load(f)
    except OSError:
        return {}


MAPHASH = _load_maphash()


class Player:
    def __init__(self, pid, name, is_host):
        self.pid = pid
        self.name = name
        self.is_host = is_host
        self.race = None      # 从 slot record join
        self.team = None
        self.color = None
        self.is_observer = False

    def __repr__(self):
        r = self.race or '?'
        return f'<Player {self.pid} {self.name} {r}>'


class Replay:
    """一局回放的完整数据: 元数据 + 有序事件流。"""

    def __init__(self, path):
        with open(path, 'rb') as fh:
            data = fh.read()
        if data[:4] == b'GRBN':  # 网易 nwg: GRBN 前缀 + 标准 w3g
            idx = data.find(b'Warcraft III recorded game')
            if idx < 0:
                raise ValueError('nwg 里找不到内嵌 w3g 签名')
            data = data[idx:]
        self.path = path
        self._f = _w3g.File(io.BytesIO(data))
        self._load_meta()
        self.events = self._f.events

    def _load_meta(self):
        f = self._f
        players = {p.id: Player(p.id, p.name, p.ishost) for p in f.players}
        for s in getattr(f, 'slot_records', None) or []:
            pl = players.get(s.player_id)
            if pl is None:
                continue
            pl.race = s.race
            pl.team = s.team
            pl.color = s.color
            pl.is_observer = s.team in (12, 24) or getattr(s, 'status', '') == 'observer'
        self.players = list(players.values())
        self.by_pid = players
        self.map = _pretty_map(f.mapname)
        self.game_name = f.game_name
        self.version = f.version_num          # 主版本号 26/29/32...
        self.build = f.build_num
        self.length_ms = f.replay_length

    def real_players(self):
        """本局实际对局者 (排除观察者)。"""
        return [p for p in self.players if not p.is_observer]

    def winner_name(self):
        w = getattr(self._f, 'winner', None)
        if not w:
            return None
        return w

    def summary(self):
        return {
            'map': self.map,
            'game_name': self.game_name,
            'version': self.version,
            'build': self.build,
            'length_s': round(self.length_ms / 1000),
            'players': [
                {'pid': p.pid, 'name': p.name, 'race': p.race,
                 'team': p.team, 'host': p.is_host, 'observer': p.is_observer}
                for p in self.players
            ],
        }

def _pretty_map(mapname):
    """KK 天梯图是 hash 文件名, 映射表里查得到就显示名。"""
    if not mapname:
        return mapname
    base = mapname.replace('/', '\\').split('\\')[-1]
    stem = base.rsplit('.', 1)[0].lower()
    if stem in MAPHASH:
        return MAPHASH[stem]
    return base
