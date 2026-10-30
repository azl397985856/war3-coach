#!/usr/bin/env python3
"""war3-coach: 回放分析 + 对手库

  python3 cli.py analyze <replay.w3g|.nwg>          单局分析摘要
  python3 cli.py record <replay> --me <我的ID>       录入对手库 (自动判胜负)
  python3 cli.py stats --me <我的ID>                 我的跨局统计
  python3 cli.py lookup <对手ID> --me <我的ID>        查某对手交手史
"""
import argparse
import os
import sys

from parser.replay import Replay
from analyzer.game import analyze
from store.opponents import OpponentDB


def default_me():
    """U盘便携模式: --me 省略时读 我的ID.txt (app 目录或其上一级)。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, '我的ID.txt'),
                 os.path.join(os.path.dirname(here), '我的ID.txt')):
        if os.path.exists(cand):
            try:
                s = open(cand, encoding='utf-8-sig').read().strip()
                if s:
                    return s
            except OSError:
                pass
    return None


def fmt_t(sec):
    return f'{int(sec // 60):02d}:{int(sec % 60):02d}'


def print_player(idx, p):
    print(f"\n{'='*62}")
    print(f"[{idx}] {p['name']}  种族={p['race']}  队伍={p['team']}  "
          f"总APM={p['apm_total']}  平均={p['apm_avg']}")
    if p['apm_by_minute']:
        print('分分钟APM:', ' '.join(str(n) for n in p['apm_by_minute']))
    tech = p['tech']
    if tech:
        parts = [f"{k}={fmt_t(v)}" for k, v in sorted(tech.items())]
        print('升本时点:', ', '.join(parts))
    if p['expansions']:
        print('开矿:', ', '.join(fmt_t(x['t']) for x in p['expansions']))
    if p['heroes']:
        print('英雄:', ' -> '.join(h['cn'] for h in p['heroes']))
    skills = [f"{fmt_t(s['t'])} {s['cn'] or s['id']}" for s in p['hero_skills']]
    if skills:
        print('技能加点:', ' | '.join(skills))
    units = {k: v for k, v in sorted(p['units_trained'].items(), key=lambda x: -x[1])}
    if units:
        print('训练统计:', ', '.join(f'{k}x{v}' for k, v in units.items()))
    print('\n-- 建造顺序 (前12分钟) --')
    shown = 0
    for e in p['bo']:
        if e['t'] > 720:
            break
        cn = e['cn'] or e['id']
        mark = {'build': '建', 'train': '训', 'tech': '升', 'hero': '英雄',
                'skill': '技能', 'item': '道具', 'research': '研'}.get(e['kind'], '?')
        print(f"  {fmt_t(e['t'])} [{mark}] {cn}")
        shown += 1
        if shown >= 40:
            print('  ...(截断, 详见 JSON)')
            break


def main():
    ap = argparse.ArgumentParser(prog='war3-coach')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p1 = sub.add_parser('analyze', help='单局分析')
    p1.add_argument('replay')
    p2 = sub.add_parser('record', help='录入对手库')
    p2.add_argument('replay')
    p2.add_argument('--me', default=None, help='我的游戏 ID (缺省读 U盘 我的ID.txt)')
    p2.add_argument('--won', choices=['win', 'loss'], default=None,
                    help='手动指定胜负 (缺省自动判定)')
    p3 = sub.add_parser('stats', help='跨局统计')
    p3.add_argument('--me', default=None)
    p4 = sub.add_parser('lookup', help='查对手交手史')
    p4.add_argument('name')
    p4.add_argument('--me', default=None)
    args = ap.parse_args()
    if getattr(args, 'me', None) is None:
        args.me = default_me()
    if args.cmd in ('record', 'stats', 'lookup') and not args.me:
        print('缺 我的ID: 命令加 --me <ID>, 或在工具目录放 我的ID.txt 文件')
        sys.exit(1)

    if args.cmd == 'analyze':
        _analyze(args.replay)
    elif args.cmd == 'record':
        r = Replay(args.replay)
        result = analyze(r)
        db = OpponentDB()
        rec = db.record(r, args.me, result, None if args.won is None else args.won == 'win')
        me = next((p for p in rec['players'] if p['name'] == args.me), None)
        opp = next((p for p in rec['players'] if p['name'] != args.me), None)
        res_str = {'win': '胜', 'loss': '败', None: '未知(回放无胜负信号, 用 --won 补录)'}.get(
            me['result'] if me else None, '?')
        print(f"已录入: {rec['map']} vs {opp['name'] if opp else '?'}"
              f" ({opp['race'] if opp else '?'}) -> {res_str}")
        print(f"对手英雄: {' -> '.join(opp['heroes']) or '?'}")
        print(f"对手BO: {opp['bo_summary']}")
    elif args.cmd == 'stats':
        s = OpponentDB().my_stats(args.me)
        print(f"共 {s['total']} 局  胜率 {s['winrate']}%  最近: {s['streak']}")
        for r, t in s['by_race'].items():
            print(f"  vs {r}: {t}")
    elif args.cmd == 'lookup':
        rows = OpponentDB().faceoffs(args.me, args.name)
        if not rows:
            print(f"对手库中没有与 {args.name} 的交手记录")
            return
        wins = sum(1 for x in rows if x['won'])
        print(f"与 {args.name} 交手 {len(rows)} 次, 我 {wins} 胜 {len(rows)-wins} 负")
        for x in rows:
            print(f"  {x['date']}  {x['map']}  我{x['my_race']} vs {x['opp_race']}"
                  f"  {'胜' if x['won'] else '负'}  他: {'->'.join(x['opp_heroes'])}")


def _analyze(path):
    r = Replay(path)
    m = r.summary()
    print(f"地图: {m['map']}  版本: 1.{m['version']}  时长: {fmt_t(m['length_s'])}")
    result = analyze(r)
    for i, pid in enumerate(sorted(result['players']), 1):
        print_player(i, result['players'][pid])
    import json
    out = path + '.analysis.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"\n[JSON 已存 {out}]")


if __name__ == '__main__':
    main()
