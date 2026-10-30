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
    if not dirs:
        print('[1/3] 浅扫各分区找游戏 Replay 目录 (45 秒内)...')
        dirs, timed_out = shallow_find(drives)

    if dirs:
        print('[2/3] 找到 %d 个 Replay 目录:' % len(dirs))
        for p in dirs:
            print('   ', p)
        files = {}
        for dp in dirs:
            try:
                for fn in os.listdir(dp):
                    if fn.lower().endswith(EXTS):
                        p = os.path.join(dp, fn)
                        try:
                            files[p] = os.path.getsize(p)
                        except OSError:
                            pass
            except OSError:
                pass
    else:
        print('[2/3] 目标搜索没找到, 深扫全盘近 60 天的 .w3g (90 秒内)...')
        files, timed_out = deep_find(drives, time.time() - DAYS_KEEP * 86400)

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
    if os.path.exists(ME_FILE):
        try:
            s = open(ME_FILE, encoding='utf-8-sig').read().strip()
            if s:
                return s
        except OSError:
            pass
    print('\n第一次使用: 请输入你的KK游戏ID (只输一次, 存在U盘上)')
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


def summarize(path, me):
    from parser.replay import Replay
    from analyzer.game import analyze

    r = Replay(path)
    result = analyze(r)
    players = result['players']
    mine = next((p for p in players.values() if p['name'] == me), None)
    opps = [p for p in players.values() if p['name'] != me]
    head = os.path.basename(path)
    if mine is None:
        print('  [未识别到 %s] 参与者: %s' % (
            me, ', '.join('%s(%s)' % (p['name'], p['race']) for p in players.values())))
        return None
    line = '%s(%s)' % (me, mine['race'])
    for o in opps:
        line += '  vs %s(%s)' % (o['name'], o['race'])
    tech = ','.join('%s=%s' % (k, fmt_t(v)) for k, v in sorted(mine['tech'].items()))
    print('  %s | %s | 升本 %s' % (head, line, tech or '-'))
    heroes = next((p for p in opps), None)
    if heroes and heroes['heroes']:
        print('  对手英雄: %s' % ' -> '.join(h['cn'] for h in heroes['heroes']))
    return r, result


def main():
    print('=' * 60)
    print('war3-coach 收集器 — 找本机录像 → 存进U盘 → 顺手分析')
    print('=' * 60)
    files = collect()
    if not files:
        print('\n没有找到 .w3g/.nwg 录像。两个自查办法:')
        print('  1) 游戏内 选项->游戏性 看「自动保存的录像」路径, 确认目录里有没有文件')
        print('  2) KK 客户端请更新到最新版 (2024-10 前版本有本地录像不保存的 bug)')
        print('若游戏内确认有文件但这里没找到, 把该路径记下来告诉我。')
        return
    print('[3/3] 共发现 %d 个录像文件, 开始拷入U盘...' % len(files))
    made = copy_in(files)
    if not made:
        print('没有新录像 (都已收过)。')
    total = len(made)
    print('\n新收录 %d 局, 开始分析...' % total)
    me = me_name()
    db = None
    ok = 0
    for i, path in enumerate(made, 1):
        print('[%d/%d]' % (i, total))
        try:
            out = summarize(path, me)
        except Exception as e:
            print('  解析失败(%s), 文件已保存, 带回家处理' % e)
            continue
        if out is None:
            continue
        r, result = out
        try:
            if db is None:
                from store.opponents import OpponentDB
                db = OpponentDB()
            db.record(r, me, result)
            ok += 1
        except Exception as e:
            print('  入库失败(不影响保存): %s' % e)
    if db is not None:
        s = db.my_stats(me)
        print('\n入对手库 %d 局。U盘累计: %d 局, 胜率 %s%%, 最近 %s' % (
            ok, s['total'], s['winrate'], s['streak'] or '-'))
    print('\n完成。录像都在 U盘 replays\\ 下, 带回家插到 Mac 上跟我说一声即可。')


if __name__ == '__main__':
    main()
