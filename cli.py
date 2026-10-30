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
    p5 = sub.add_parser('pull', help='从云端信箱拉回录像+对手库 (Mac 侧)')
    p5.add_argument('--conf', default=os.path.expanduser('~/war3-coach-sync.txt'))
    p5.add_argument('--into', default=None, help='回放落盘目录 (缺省 本仓 replays/)')
    p6 = sub.add_parser('pull-mail', help='从邮箱拉取 war3-coach 邮件附件 (Mac 侧)')
    p6.add_argument('--conf', default=os.path.expanduser('~/war3-coach-mail.txt'))
    p6.add_argument('--days', type=int, default=30, help='拉取最近 N 天的邮件')
    p7 = sub.add_parser('report', help='生成单局 HTML 战报 (含教练点评)')
    p7.add_argument('replay')
    p7.add_argument('--me', default=None, help='以哪个玩家视角点评 (缺省第一个)')
    p7.add_argument('-o', '--out', default=None, help='输出路径 (缺省 replay 旁 .report.html)')
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
    elif args.cmd == 'pull':
        import sync
        conf, _ = sync.load_conf(os.path.dirname(args.conf))
        if not conf and os.path.exists(args.conf):
            # 直接给的是文件路径, load_conf 只找目录, 这里手工读
            conf = {}
            for line in open(args.conf, encoding='utf-8-sig'):
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    conf[k.strip()] = v.strip()
        if not (conf and conf.get('token') and conf.get('repo')):
            print(f'配置文件没有读到: {args.conf} (两行: token=... / repo=用户名/war3-coach-sync)')
            sys.exit(1)
        here = os.path.dirname(os.path.abspath(__file__))
        into = args.into or os.path.join(here, 'replays')
        db_local = os.path.join(here, 'data', 'opponents.json')
        db_added, rep_added = sync.pull_all(conf, into, db_local)
        print(f'\n拉取完成: 对手库新增 {db_added} 局, 回放新增 {rep_added} 个 ({into})')
        s = OpponentDB(db_local).my_stats(args.me) if args.me else None
        if s and s['total']:
            print(f"当前累计: {s['total']} 局, 胜率 {s['winrate']}%, 最近 {s['streak']}")
    elif args.cmd == 'pull-mail':
        _pull_mail(args)
    elif args.cmd == 'report':
        _report(args)


def _report(args):
    from report.html import render
    r = Replay(args.replay)
    result = analyze(r)
    doc = render(result, args.replay, me_name=args.me)
    out = args.out or (args.replay.rsplit('.', 1)[0] + '.report.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(doc)
    print(f'战报已生成: {out}')
    # 顺带打印教练点评纯文本版
    from analyzer.coach import coach_player
    me = next((p for p in result['players'].values() if p['name'] == (args.me or '')), None)
    if me is None:
        me = next(iter(result['players'].values()))
    opp = next((p for p in result['players'].values() if p is not me), None)
    for c in coach_player(me, [opp] if opp else [], r.length_ms // 1000):
        mark = {'good': '✓', 'warn': '!', 'info': '·'}.get(c['level'], '·')
        print(f'  [{mark}] {c["title"]}')
        print(f'        {c["body"]}')


def _pull_mail(args):
    """Mac 侧: IMAP 拉取 war3-coach 邮件的 zip 附件 -> 落盘回放 + 合并对手库"""
    import imaplib
    import email
    import time as _time
    import zipfile
    import io as _io
    import sync

    conf = {}
    if os.path.exists(args.conf):
        for line in open(args.conf, encoding='utf-8-sig'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                conf[k.strip()] = v.strip()
    if not (conf.get('user') and conf.get('pass')):
        print(f'配置缺失: {args.conf} (三行: user=邮箱 / pass=IMAP授权码 / host=可省)')
        sys.exit(1)
    hosts = {'qq.com': 'imap.qq.com', 'foxmail.com': 'imap.qq.com',
             '163.com': 'imap.163.com', '126.com': 'imap.126.com'}
    host = conf.get('host') or hosts.get(conf['user'].split('@')[-1].lower())
    if not host:
        print('mail 配置缺 host (IMAP 服务器)')
        sys.exit(1)

    here = os.path.dirname(os.path.abspath(__file__))
    into = os.path.join(here, 'replays')
    db_local = os.path.join(here, 'data', 'opponents.json')

    M = imaplib.IMAP4_SSL(host, 993)
    M.login(conf['user'], conf['pass'])
    if '163' in host or '126' in host:      # 163/126 IMAP 必须发 ID, 否则拒绝
        M._simple_command('ID', '("name" "war3-coach" "version" "1.0")')
        M._untagged_response('OK', [], 'ID')
    M.select('INBOX')
    since = _time.strftime('%d-%b-%Y', _time.gmtime(_time.time() - args.days * 86400))
    typ, data = M.search(None, f'(SINCE "{since}" SUBJECT "war3-coach")')
    ids = data[0].split()
    print(f'找到 {len(ids)} 封 war3-coach 邮件')
    zips = 0
    for num in ids:
        typ, d = M.fetch(num, '(RFC822)')
        msg = email.message_from_bytes(d[0][1])
        for part in msg.walk():
            fn = part.get_filename() or ''
            if not fn.lower().endswith('.zip'):
                continue
            raw = part.get_payload(decode=True)
            zips += 1
            with zipfile.ZipFile(_io.BytesIO(raw)) as z:
                for name in z.namelist():
                    blob = z.read(name)
                    if name.startswith('replays/'):
                        dst = os.path.join(into, name[len('replays/'):])
                        if os.path.exists(dst) and os.path.getsize(dst) == len(blob):
                            continue
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        with open(dst, 'wb') as f:
                            f.write(blob)
                        print('  收到', name)
                    elif name == 'state/opponents.json':
                        _, added = sync.merge_db(db_local, blob)
                        print(f'  对手库合并: +{added} 局')
    M.logout()
    print(f'\n完成: {zips} 个包。之后说一声我就能分析最新这几局。')


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
