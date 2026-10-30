#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单局战报: 渲染成单文件 HTML (无外部依赖, 本地双击打开)。

风格沿用 war3-lab: 深底金字卡片。结构:
  头部(地图/时长/日期) -> 教练点评卡 -> 双方对比条 -> BO 时间轴(左右对齐)
  -> APM 曲线 -> 部队统计
"""
import html
import os
from datetime import datetime

INK = '#141414'
CARD = '#1e1e1e'
GOLD = '#ffd23f'
TXT = '#e8e4d8'
SUB = '#9a958a'
LINE = '#333'
GOOD = '#4caf7d'
WARN = '#e07b39'
INFO = '#5b8dd9'

_MARK = {'build': '建', 'train': '训', 'tech': '升', 'hero': '英雄',
         'skill': '技能', 'item': '道具', 'research': '研'}

_RACE = {'orc': '兽族 ORC', 'human': '人族 HUM', 'undead': '不死族 UD',
         'nightelf': '暗夜 NE', 'random': '随机'}


def _esc(s):
    return html.escape(str(s))


def _fmt(sec):
    return '%02d:%02d' % (int(sec // 60), int(sec % 60))


_CSS = f"""
body {{ background:{INK}; color:{TXT}; font:14px/1.6 -apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
        margin:0; padding:24px; max-width:980px; margin-inline:auto; }}
h1 {{ font-size:20px; color:{GOLD}; }} h2 {{ font-size:16px; color:{GOLD}; margin-top:28px; }}
.muted {{ color:{SUB}; font-size:12px; }}
.card {{ background:{CARD}; border:1px solid {LINE}; border-radius:10px; padding:14px 16px; margin:10px 0; }}
.coach .g {{ border-left:4px solid {GOOD}; }} .coach .w {{ border-left:4px solid {WARN}; }}
.coach .i {{ border-left:4px solid {INFO}; }}
.coach .t {{ color:{GOLD}; font-weight:600; }}
.vs {{ display:flex; gap:12px; }} .vs .card {{ flex:1; }}
.kv {{ display:grid; grid-template-columns:88px 1fr; gap:2px 10px; font-size:13px; }}
.kv b {{ color:{SUB}; font-weight:400; }}
table.bo {{ width:100%; border-collapse:collapse; font-size:13px; }}
table.bo td {{ padding:2px 8px; border-bottom:1px solid {LINE}; vertical-align:top; }}
table.bo td.t {{ color:{SUB}; white-space:nowrap; text-align:center; width:64px; }}
table.bo td.r {{ text-align:right; }} table.bo td.m {{ color:{SUB}; text-align:center; width:52px; font-size:11px; }}
.bar {{ background:{LINE}; height:10px; border-radius:5px; overflow:hidden; }}
.bar i {{ display:block; height:100%; background:{GOLD}; }}
.tag {{ display:inline-block; padding:0 8px; border-radius:4px; font-size:12px; margin-right:6px; }}
"""


def _timeline(me, opp, max_s=1800):
    """左右对齐 BO 时间轴"""
    rows = {}
    for side, p in (('l', me), ('r', opp)):
        for e in p['bo']:
            if e['t'] > max_s:
                break
            rows.setdefault(round(e['t']), {'l': [], 'r': []})[side].append(e)
    out = []
    for t in sorted(rows):
        cell = rows[t]
        def render(e):
            mark = _MARK.get(e['kind'], '?')
            return f"[{mark}] {_esc(e['cn'] or e['id'])}"
        ltxt = '<br>'.join(render(e) for e in cell['l'])
        rtxt = '<br>'.join(render(e) for e in cell['r'])
        out.append(f'<tr><td class="r">{ltxt}</td><td class="t">{_fmt(t)}</td>'
                   f'<td>{rtxt}</td></tr>')
    if not out:
        return '<p class="muted">无事件</p>'
    return ('<table class="bo"><tr><th style="text-align:right">%s</th>'
            '<th></th><th style="text-align:left">%s</th></tr>%s</table>') % (
        _esc(me['name']), _esc(opp['name']), ''.join(out))


def _apm_chart(p):
    apm = p.get('apm_by_minute') or []
    if not apm:
        return '<p class="muted">无数据</p>'
    mx = max(apm) or 1
    rows = []
    for i, n in enumerate(apm):
        w = round(n / mx * 100)
        rows.append(f'<div style="display:flex;align-items:center;gap:8px;margin:1px 0;">'
                    f'<span class="muted" style="width:36px">{i:02d}</span>'
                    f'<div class="bar" style="flex:1"><i style="width:{w}%"></i></div>'
                    f'<span class="muted" style="width:36px;text-align:right">{n}</span></div>')
    return ''.join(rows)


def _player_card(p, meta):
    race = _RACE.get((p.get('race') or '').lower(), p.get('race') or '?')
    tech = ', '.join('%s=%s' % (k, _fmt(v)) for k, v in sorted(p['tech'].items())) or '—'
    ex = ', '.join(_fmt(x['t']) for x in p['expansions']) or '—'
    heroes = ' → '.join(h['cn'] for h in p['heroes']) or '—'
    units = p.get('units_trained') or {}
    top = sorted(units.items(), key=lambda x: -x[1])[:12]
    unit_txt = '，'.join('%s×%d' % (_esc(k), v) for k, v in top) or '—'
    return (f'<div class="card"><b style="color:{GOLD}">{_esc(p["name"])}</b> '
            f'<span class="muted">{race}</span>'
            f'<div class="kv">'
            f'<b>总APM</b><span>{p.get("apm_total", 0)} (均值 {p.get("apm_avg", 0)})</span>'
            f'<b>升本</b><span>{tech}</span>'
            f'<b>开矿</b><span>{ex}</span>'
            f'<b>英雄</b><span>{_esc(heroes)}</span>'
            f'<b>训练</b><span>{unit_txt}</span>'
            f'</div></div>')


def render(analysis, replay_path, me_name=None):
    meta = analysis['meta']
    players = analysis['players']
    # 我 = 指定名字 or 第一个玩家; 对手 = 另一个
    me = None
    if me_name:
        me = next((p for p in players.values() if p['name'] == me_name), None)
    if me is None:
        me = next(iter(players.values()))
    opp = next((p for p in players.values() if p is not me and not p.get('observer')), me)

    from analyzer.coach import coach_player
    cards = coach_player(me, [opp], meta['length_s'])

    level_cls = {'good': 'g', 'warn': 'w', 'info': 'i'}
    coach_html = ''.join(
        f'<div class="card {level_cls.get(c["level"], "i")}">'
        f'<div class="t">{_esc(c["title"])}</div><div>{_esc(c["body"])}</div></div>'
        for c in cards)

    date = datetime.now().strftime('%Y-%m-%d %H:%M')
    map_name = (meta['map'] or '').split('\\')[-1]
    doc = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>war3-coach 战报: {map_name}</title><style>{_CSS}</style></head><body>
<h1>战报 · {map_name}</h1>
<p class="muted">{meta['game_name'] or ''} ｜ 版本 1.{meta['version']} ｜ 时长 {_fmt(meta['length_s'])}
｜ 生成于 {date} ｜ {_esc(os.path.basename(replay_path))}</p>

<h2>教练点评</h2>
<div class="coach">{coach_html}</div>

<h2>双方</h2>
<div class="vs">{_player_card(me, meta)}{_player_card(opp, meta)}</div>

<h2>建造顺序时间轴</h2>
<div class="card">{_timeline(me, opp, max_s=min(2400, meta['length_s'] + 60))}</div>

<h2>{_esc(me['name'])} 分分钟 APM</h2>
<div class="card">{_apm_chart(me)}</div>

<p class="muted">war3-coach · 数据来自回放解析，教练规则对照训练手册（lucifer.ren/blog/2025/03/20/war3-website/）</p>
</body></html>"""
    return doc
