#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""游戏电脑上运行: 搜索本机魔兽录像 → 拷入本工具 replays/ → 自动分析摘要。

搜索策略 (从快到慢):
  1. 注册表 InstallPath (HKCU/HKLM/WOW6432Node, 含 KK 等平台装的目录)
  2. 各分区浅扫 (深度<=4): 目录名像魔兽游戏目录 → 找其下的 Replay 文件夹
  3. 深扫兜底: 全盘 *.w3g/*.nwg 近 60 天修改的 (限时 90 秒)
去重规则: 目标已有同名且同大小的文件 → 跳过。
"""
import os
import re
import shutil
import subprocess
import sys
import time

APP = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP)                    # U盘根 (app 的上一级)
sys.path.insert(0, APP)

OUT_BASE = os.path.join(ROOT, 'replays')
ME_FILE = os.path.join(ROOT, '我的ID.txt')
SELFDIR = os.environ.get('SELFDIR', '').strip().lower()
EXTS = ('.w3g', '.nwg')
PRUNE = {'$recycle.bin', 'system volume information', 'windows', 'msocache'}
GAME_HINT = re.compile(r'(warcraft|war3|wc3|冰封|魔兽|frozen)', re.I)
REPLAY_SUBDIRS = ('Replay', 'Replays', 'Replay\\')
DAYS_KEEP = 60


def fixed_drives():
    out = []
    for i in range(67, 91):                      # C..Z
        d = chr(i) + ':\\'
        if os.path.exists(d):
            out.append(d)
    return out


def registry_paths():
    paths = []
    keys = (r'HKCU\Software\Blizzard Entertainment\Warcraft III',
            r'HKLM\Software\Blizzard Entertainment\Warcraft III',
            r'HKLM\Software\WOW6432Node\Blizzard Entertainment\Warcraft III')
    for key in keys:
        try:
            r = subprocess.run(['reg', 'query', key], capture_output=True,
                               text=True, timeout=10)
            for line in (r.stdout or '').splitlines():
                m = re.search(r'InstallPath\s+REG_SZ\s+(.*)', line)
                if m:
                    paths.append(m.group(1).strip())
        except Exception:
            pass
    return paths


def shallow_find(drives, limit_s=45):
    """浅扫各分区: 目录名像游戏目录 → 其下 Replay 文件夹。返回 {文件夹: None}"""
    t0 = time.monotonic()
    found = {}
    for d in drives:
        base = d.rstrip('\\')
        for dirpath, dirnames, filenames in os.walk(base):
            if time.monotonic() - t0 > limit_s:
                return found, True
            dirnames[:] = [x for x in dirnames if x.lower() not in PRUNE]
            depth = dirpath[len(base):].count(os.sep)
            if depth >= 4:
                dirnames[:] = []
                continue
            low = os.path.basename(dirpath).lower()
            if GAME_HINT.search(low):
                for rd in REPLAY_SUBDIRS:
                    p = os.path.join(dirpath, rd)
                    if os.path.isdir(p):
                        found[p] = None
            if 'replay' in low:
                for fn in filenames:
                    if fn.lower().endswith(EXTS):
                        found[dirpath] = None
    return found, False


def deep_find(drives, since_ts, limit_s=90, cap=1500):
    """深扫兜底: 全盘近期改动的 w3g/nwg。返回 {文件路径: size}"""
    t0 = time.monotonic()
    n = 0
    found = {}
    for d in drives:
        base = d.rstrip('\\')
        for dirpath, dirnames, filenames in os.walk(base):
            if time.monotonic() - t0 > limit_s or n >= cap:
                return found, True
            dirnames[:] = [x for x in dirnames if x.lower() not in PRUNE]
            for fn in filenames:
                if fn.lower().endswith(EXTS):
                    p = os.path.join(dirpath, fn)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    if st.st_mtime >= since_ts and st.st_size < 60 * 1024 * 1024:
                        found[p] = st.st_size
                        n += 1
    return found, False


def collect():
    drives = fixed_drives()
    # 排除工具自己所在的盘 (U盘自身)
    if SELFDIR:
        drives = [d for d in drives if not SELFDIR.startswith(d.lower())]

    dirs, timed_out = {}, False
    # 注册表候选: InstallPath 本身 + 向下两层子目录都找 Replay* (KK 平台的
    # InstallPath 可能指向客户端目录, 游戏和 Replay 在其子目录里)
    reg = registry_paths()
    if reg:
        print('[1/3] 注册表找到魔兽目录:')
        for p in reg:
            print('   ', p)
        for ip in reg:
            for rd in REPLAY_SUBDIRS:
                p = os.path.join(ip, rd)
                if os.path.isdir(p):
                    dirs[p] = None
            try:
                lvl1 = [os.path.join(ip, x) for x in os.listdir(ip)
                        if os.path.isdir(os.path.join(ip, x))]
            except OSError:
                lvl1 = []
            for d1 in lvl1:
                for rd in REPLAY_SUBDIRS:
                    p = os.path.join(d1, rd)
                    if os.path.isdir(p):
                        dirs[p] = None
                try:
                    lvl2 = [os.path.join(d1, x) for x in os.listdir(d1)
                            if os.path.isdir(os.path.join(d1, x))]
                except OSError:
                    continue
                for d2 in lvl2:
                    for rd in REPLAY_SUBDIRS:
                        p = os.path.join(d2, rd)
                        if os.path.isdir(p):
                            dirs[p] = None
    # 浅扫总是执行并与注册表候选合并 (单靠注册表会漏 KK 自装目录)
    print('[2/3] 浅扫各分区找游戏 Replay 目录 (45 秒内)...')
    shallow, timed_out = shallow_find(drives)
    for p in shallow:
        dirs[p] = None

    files = {}
    if dirs:
        print('候选 Replay 目录 (括号内=搜到的录像数):')
        for dp in sorted(dirs):
            n = 0
            try:
                for fn in os.listdir(dp):
                    if fn.lower().endswith(EXTS):
                        p = os.path.join(dp, fn)
                        try:
                            files[p] = os.path.getsize(p)
                            n += 1
                        except OSError:
                            pass
            except OSError:
                pass
            print('   %s  (%d)' % (dp, n))
    if not files:
        print('自动搜索没找到录像 (注册表+浅扫都空), 深扫全盘近 60 天 (90 秒内)...')
        files, timed_out = deep_find(drives, time.time() - DAYS_KEEP * 86400)
    if not files:
        # 手动路径兜底: 网吧环境路径千奇百怪, 游戏内看一眼路径手输最快
        try:
            manual = input('手动输入游戏 Replay 文件夹完整路径 (直接回车跳过): ').strip().strip('"')
        except EOFError:
            manual = ''
        if manual and os.path.isdir(manual):
            for dirpath, dirnames, filenames in os.walk(manual):
                for fn in filenames:
                    if fn.lower().endswith(EXTS):
                        p = os.path.join(dirpath, fn)
                        try:
                            files[p] = os.path.getsize(p)
                        except OSError:
                            pass

    if timed_out:
        print('   (搜索到时限, 如有遗漏下次再跑或机器太慢属正常)')
    return files


def copy_in(files):
    """拷入 U盘 replays/YYYY-MM-DD/, 去重。返回新建文件列表"""
    day = time.strftime('%Y-%m-%d')
    outdir = os.path.join(OUT_BASE, day)
    os.makedirs(outdir, exist_ok=True)
    made = []
    for src, size in sorted(files.items(), key=lambda x: x[0].lower()):
        name = os.path.basename(src)
        dst = os.path.join(outdir, name)
        if os.path.exists(dst) and os.path.getsize(dst) == size:
            continue
        if os.path.exists(dst):                      # 同名不同局
            stem, ext = os.path.splitext(name)
            dst = os.path.join(outdir, '%s_%s%s' % (
                stem, time.strftime('%H%M%S'), ext))
        try:
            shutil.copy2(src, dst)
            made.append(dst)
            print('  收进U盘: %s  (%.1f MB)' % (name, size / 1048576))
        except OSError as e:
            print('  !! 拷贝失败 %s: %s' % (name, e))
    return made


def me_name():
    # 优先级: mail.txt 的 me= (网吧还原后配置只需带一个文件) > 我的ID.txt > 现场输入
    mconf = load_conf_file(ROOT, MAIL_FILE) or load_conf_file(APP, MAIL_FILE)
    if mconf and mconf.get('me'):
        return mconf['me']
    if os.path.exists(ME_FILE):
        try:
            s = open(ME_FILE, encoding='utf-8-sig').read().strip()
            if s:
                return s
        except OSError:
            pass
    print('\n第一次使用: 请输入你的KK游戏ID (只输一次, 存在本工具目录)')
    try:
        s = input('> ').strip()
    except EOFError:
        return None
    if s:
        with open(ME_FILE, 'w', encoding='utf-8') as f:
            f.write(s)
    return s or None


def fmt_t(sec):
    return '%02d:%02d' % (int(sec // 60), int(sec % 60))


def resolve_me(result, me):
    """把配置的 me 对到本局玩家名。KK 账号是数字, 游戏内显示名是昵称——
    对不上时让用户从本局参与者里选一次 (选中后自动改写 我的ID.txt)。"""
    players = result['players']
    if me in players:
        return me, True
    names = [p['name'] for p in players.values()]
    print('\n  [ID 对不上] 我的ID.txt 里写的是「%s」, 但这局参与者是:' % me)
    for i, n in enumerate(names, 1):
        p = players[[k for k, v in players.items() if v['name'] == n][0]]
        print('   %d) %s (%s)' % (i, n, p['race']))
    try:
        pick = input('哪一个是你的对战昵称? 输入序号 (回车跳过本局): ').strip()
    except EOFError:
        pick = ''
    if pick.isdigit() and 1 <= int(pick) <= len(names):
        me = names[int(pick) - 1]
        try:
            with open(ME_FILE, 'w', encoding='utf-8') as f:
                f.write(me)
            print('  已把 我的ID.txt 更新为「%s」, 以后不再问。' % me)
        except OSError:
            pass
        return me, True
    return None, False


def summarize(path, me):
    from parser.replay import Replay
    from analyzer.game import analyze

    r = Replay(path)
    result = analyze(r)
    me, ok = resolve_me(result, me)
    if not ok:
        return None
    players = result['players']
    mine = players[[k for k, v in players.items() if v['name'] == me][0]]
    opps = [p for p in players.values() if p['name'] != me]
    head = os.path.basename(path)
    line = '%s(%s)' % (me, mine['race'])
    for o in opps:
        line += '  vs %s(%s)' % (o['name'], o['race'])
    tech = ','.join('%s=%s' % (k, fmt_t(v)) for k, v in sorted(mine['tech'].items()))
    print('  %s | %s | 升本 %s' % (head, line, tech or '-'))
    heroes = next((p for p in opps), None)
    if heroes and heroes['heroes']:
        print('  对手英雄: %s' % ' -> '.join(h['cn'] for h in heroes['heroes']))
    return r, result, me


DB_LOCAL = os.path.join(APP, 'data', 'opponents.json')
MAIL_FILE = 'mail.txt'


def load_conf_file(directory, name):
    """读 name 配置文件 (key=value 行) -> dict 或 None"""
    p = os.path.join(directory, name)
    if not os.path.exists(p):
        return None
    conf = {}
    with open(p, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                conf[k.strip()] = v.strip()
    return conf or None


def bundle_zip(made, me, stats_line):
    """把今天新回放+对手库+原始分析打成一个包, 存工具目录 (微信/网盘/邮箱随便传)"""
    if not made:
        return None
    import zipfile
    day = time.strftime('%Y-%m-%d')
    out = os.path.join(ROOT, 'war3-coach-%s.zip' % day)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in made:
            z.write(p, 'replays/%s/%s' % (day, os.path.basename(p)))
            aj = p + '.analysis.json'
            if os.path.exists(aj):
                z.write(aj, 'state/analyses/%s.analysis.json' % os.path.basename(p))
        if os.path.exists(DB_LOCAL):
            z.write(DB_LOCAL, 'state/opponents.json')
        if me:
            z.writestr('state/me.txt', me)
    print('已打包: %s (%.1f MB) — 微信/网盘/邮箱发给自己都行' % (
        os.path.basename(out), os.path.getsize(out) / 1048576))
    return out


SMTP_HOSTS = {'qq.com': 'smtp.qq.com', 'foxmail.com': 'smtp.qq.com',
              '163.com': 'smtp.163.com', '126.com': 'smtp.126.com'}


def mail_send(mconf, zip_path, subject):
    """把打包 zip 发到自己的邮箱 (SMTP 授权码, 只发不收)"""
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    user = mconf['user']
    to = mconf.get('to', user)
    host = mconf.get('host') or SMTP_HOSTS.get(user.split('@')[-1].lower())
    if not host:
        raise RuntimeError('mail.txt 缺 host (smtp 服务器)')
    msg = MIMEMultipart()
    msg['From'] = user
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText('war3-coach 自动信件: 回放与对手库打包。可转发本邮件存档。', 'plain', 'utf-8'))
    with open(zip_path, 'rb') as f:
        att = MIMEApplication(f.read())
    att.add_header('Content-Disposition', 'attachment',
                   filename=os.path.basename(zip_path))
    msg.attach(att)
    with smtplib.SMTP_SSL(host, 465, timeout=30) as s:
        s.login(user, mconf['pass'])
        s.sendmail(user, [to], msg.as_string())


def main():
    print('=' * 60)
    print('war3-coach 收集器 — 找本机录像 -> 分析 -> 同步云端信箱')
    print('=' * 60)

    # 云端: 有 sync.txt 才启用 (先拉对手库, 网吧也能查老对手)
    conf, cpath = None, None
    try:
        import sync as SYNC
        conf, cpath = SYNC.load_conf(ROOT, APP)
        if conf:
            added = SYNC.pull_db_merge(conf, DB_LOCAL)
            print('[云端] 对手库已拉取合并' +
                  (' (新增 %d 局)' % added if added > 0 else
                   ' (云端还没有库, 本局开始建立)' if added == 0 else ''))
    except Exception as e:
        print('[云端] 拉取失败(不影响本地): %s' % e)

    files = collect()
    if not files:
        print('\n没有找到 .w3g/.nwg 录像。两个自查办法:')
        print('  1) 游戏内 选项->游戏性 看「自动保存的录像」路径, 确认目录里有没有文件')
        print('  2) KK 客户端请更新到最新版 (2024-10 前版本有本地录像不保存的 bug)')
        print('若游戏内确认有文件但这里没找到, 把该路径记下来告诉我。')
        return
    print('[3/3] 共发现 %d 个录像文件, 开始拷入本目录...' % len(files))
    made = copy_in(files)
    if not made:
        print('没有新录像 (都已收过)。')
    total = len(made)
    print('\n新收录 %d 局, 开始分析...' % total)
    me = me_name()
    db = None
    ok = 0
    import json as _json
    for i, path in enumerate(made, 1):
        print('[%d/%d]' % (i, total))
        try:
            out = summarize(path, me)
        except Exception as e:
            print('  解析失败(%s), 文件已保存, 回家再处理' % e)
            out = None
        r = result = None
        if out:
            r, result, me = out
        # 原始分析 JSON 永远落盘 (ID 没配对也不丢数据, 回家后可补处理)
        try:
            if result is not None:
                with open(path + '.analysis.json', 'w', encoding='utf-8') as f:
                    _json.dump(result, f, ensure_ascii=False)
        except OSError:
            pass
        if out is None:
            continue
        try:
            if db is None:
                from store.opponents import OpponentDB
                db = OpponentDB(DB_LOCAL)
            db.record(r, me, result)
            ok += 1
        except Exception as e:
            print('  入库失败(不影响保存): %s' % e)
    if db is not None and ok:
        s = db.my_stats(me)
        stats_line = '累计: %d 局, 胜率 %s%%, 最近 %s' % (
            s['total'], s['winrate'], s['streak'] or '-')
        print('\n入对手库 %d 局。%s' % (ok, stats_line))
    else:
        stats_line = '本局未入库(ID 对不上也会把分析数据带回家, 不丢)'

    # 万能兜底: 打成一个 zip, 微信/网盘/邮箱随便传
    zip_path = bundle_zip(made, me, stats_line)

    # 邮箱直发 (有 mail.txt 才启用; 授权码只发不收, 建议用专用小号)
    mconf = load_conf_file(ROOT, MAIL_FILE) or load_conf_file(APP, MAIL_FILE)
    if mconf and zip_path:
        try:
            day = time.strftime('%m-%d')
            mail_send(mconf, zip_path, 'war3-coach %s: %d 局 (%s)' % (
                day, len(made), stats_line))
            print('[邮箱] 已发送到 %s — 回家打开邮箱下载附件即可' % mconf.get('to', mconf['user']))
        except Exception as e:
            print('[邮箱] 发送失败 (%s), zip 还在本目录, 手动发也行' % e)
    elif not mconf:
        print('\n[邮箱直发未配置] 想打完自动发回自己邮箱: 在本目录建 mail.txt 三行:')
        print('  user=你的邮箱@qq.com')
        print('  pass=SMTP授权码 (邮箱设置里开, 只发不收; 建议专用小号)')
        print('  to=收件邮箱 (默认发给自己可省)')

    # 云端: 推本局录像 + 最新对手库
    if conf:
        try:
            import sync as SYNC
            day = time.strftime('%Y-%m-%d')
            files_up = {}
            with open(DB_LOCAL, 'rb') as f:
                files_up[SYNC.DB_PATH] = f.read()
            for p in made:
                with open(p, 'rb') as f:
                    files_up['replays/%s/%s' % (day, os.path.basename(p))] = f.read()
            SYNC.push(conf, files_up, 'collect %s: +%d replays' % (day, len(made)))
            print('[云端] 已同步到私有仓库 %s (录像 %d 局 + 对手库)' % (
                conf['repo'], len(made)))
        except Exception as e:
            print('[云端] 推送失败, 数据已在本目录, 网络好了再跑一次 1-collect 即可: %s' % e)
    else:
        print('\n[云端信箱未配置] 想免去U盘、打完自动同步回家, 按使用说明配置')
        print('sync.txt (GitHub 令牌两行) 即可; 不配也不影响本地功能。')


if __name__ == '__main__':
    main()
