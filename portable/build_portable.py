#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 Mac 上构建 U盘便携版 zip (给 Windows 游戏电脑/网吧用)。

产物: dist/war3-coach-portable.zip, 解压即用, 无需安装任何东西。
结构:
  runtime/  = python.org 官方 embeddable python (纯官方, 无安装器)
  app/      = 本项目代码 + w3g.py + units.json
  *.bat     = GBK 编码的中文入口 (cmd 在 cp936 下直接双击)
"""
import os
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(REPO, 'dist')
STAGE = os.path.join(DIST, 'war3-coach')
PY_VER = '3.12.10'
PY_URL = f'https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-embed-amd64.zip'
PY_ZIP = os.path.join(DIST, f'python-{PY_VER}-embed-amd64.zip')

BATS = {
    # 文件名一律 ASCII: 网吧机器的解压工具对中文 zip 文件名支持参差, 内容才是中文
    '1-collect.bat': (
        '@echo off\r\n'
        'echo war3-coach 收集并分析 (自动找录像 -> 出摘要 -> 打包发邮箱)\r\n'
        'set "SELFDIR=%~dp0"\r\n'
        '"%~dp0runtime\\python.exe" "%~dp0app\\collect.py"\r\n'
        'pause\r\n'
    ),
    '2-lookup.bat': (
        '@echo off\r\n'
        'echo war3-coach 查对手历史\r\n'
        'set /p opp=对手游戏ID: \r\n'
        '"%~dp0runtime\\python.exe" "%~dp0app\\cli.py" lookup "%opp%"\r\n'
        'pause\r\n'
    ),
    '3-stats.bat': (
        '@echo off\r\n'
        'echo war3-coach 我的战绩统计\r\n'
        '"%~dp0runtime\\python.exe" "%~dp0app\\cli.py" stats\r\n'
        'pause\r\n'
    ),
}

README = """war3-coach 随身版 — 魔兽训练辅助 (回放分析+对手库+邮箱直发回家)
================================================================

【第一次用 (在家弄好)】
1. 准备一个邮箱当"信箱" (建议专用小号), 在邮箱网页设置里开通 SMTP 服务,
   拿到"授权码" (不是登录密码):
     QQ邮箱: 设置 -> 账号 -> POP3/IMAP/SMTP -> 开启 -> 生成授权码
     163邮箱: 设置 -> POP3/SMTP/IMAP -> 开启 -> 授权码
2. 在本文件夹建一个 mail.txt (记事本), 写三行:
     user=信箱@qq.com
     pass=授权码
     me=你的KK游戏ID
   (可选第4行: to=收件邮箱, 不填就发给自己)
3. 把整个 war3-coach 文件夹存到网盘/微信收藏 —— 网吧每次从那下载

【网吧/游戏电脑上每次的流程】
1. 下载 war3-coach 文件夹, 解压到桌面
2. 把网盘里的 mail.txt 放进文件夹
3. 正常打天梯
4. 下机前双击 1-collect.bat:
   自动找本机录像 -> 分析摘要 -> 打包 -> 发回你的邮箱, 完事关机走人

【平时可选】
- 2-lookup.bat : 输对手ID, 查他跟你历次交手、英雄、开局 (邮箱方案下
  网吧首次运行拉不到历史, 历史查询主要在家用)
- 3-stats.bat  : 本机已收录局数的胜率统计

【回家后】
邮箱里收到的附件 (war3-coach-日期.zip) 下载下来丢给 Mac 上的助手,
或者告诉助手跑 pull-mail 自动拉取 (需在 Mac 配 IMAP 授权码)。

【找不到录像时】
- 游戏内 选项 -> 游戏性 -> 看「自动保存的录像」路径, 确认那里有没有 .w3g 文件
- KK 客户端更新到最新版 (2024-10 之前有本地录像不保存的 bug)

【安全说明】
- 授权码只用于发件 (SMTP), 发不出也收不了你的信箱; 建议信箱用专用小号,
  里面只有录像邮件, 万一泄露也无损失, 随时可在邮箱设置里作废授权码
- 回家的只是录像数据文件 (解析用, 从不执行), 不存在带毒回家
- 不碰游戏进程 / 不碰内存, 平台无感
"""


def sh(cmd):
    print('$', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def main():
    os.makedirs(DIST, exist_ok=True)
    if os.path.exists(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)

    # 1. 内嵌 python (带缓存)
    if not os.path.exists(PY_ZIP):
        curl = ['curl', '-fL', '--retry', '3', '-o', PY_ZIP, PY_URL]
        if subprocess.call(['curl', '-sfL', '-o', '/dev/null',
                            'https://www.python.org'] ) != 0:
            curl.insert(1, '--proxy')
            curl.insert(2, 'http://127.0.0.1:7890')
        sh(curl)
    rt = os.path.join(STAGE, 'runtime')
    os.makedirs(rt)
    with zipfile.ZipFile(PY_ZIP) as z:
        z.extractall(rt)

    # 2. 改 _pth: 把 app 目录加进 sys.path (embeddable 是隔离模式, 全靠这个)
    pth = [f for f in os.listdir(rt) if f.endswith('._pth')][0]
    with open(os.path.join(rt, pth)) as f:
        lines = f.read().splitlines()
    if 'app' not in lines:
        lines.append('app')
    with open(os.path.join(rt, pth), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('patched', pth, '->', lines)

    # 3. app/ = 代码 + w3g.py + 单位表
    app = os.path.join(STAGE, 'app')
    os.makedirs(app)
    for name in ('cli.py', 'parser', 'analyzer', 'store', 'sync.py', 'report'):
        src = os.path.join(REPO, name)
        if os.path.isfile(src):
            shutil.copy2(src, app)
        else:
            shutil.copytree(src, os.path.join(app, name))
    shutil.copy2(os.path.join(REPO, 'portable', 'collect.py'), app)
    w3g_src = os.path.expanduser(
        '~/Library/Python/3.11/lib/python/site-packages/w3g.py')
    shutil.copy2(w3g_src, os.path.join(app, 'w3g.py'))
    # 清 app 内无关物
    shutil.rmtree(os.path.join(app, 'data', 'opponents.json'), ignore_errors=True)
    for root, dirs, files in os.walk(app):
        dirs[:] = [d for d in dirs if d != '__pycache__']

    # 4. bat (GBK) + README (GBK, 兼容老记事本)
    for name, content in BATS.items():
        with open(os.path.join(STAGE, name), 'wb') as f:
            f.write(content.encode('gbk'))
    with open(os.path.join(STAGE, 'README.txt'), 'wb') as f:
        f.write(README.encode('gbk'))

    # 5. 冒烟: 本机 python 直接跑 app/cli.py (Windows 才有 runtime/, 逻辑等价)
    env = dict(os.environ, PYTHONPATH=app)
    r = subprocess.run([sys.executable, os.path.join(app, 'cli.py'), 'stats',
                        '--me', 'x'], capture_output=True, text=True, env=env)
    assert '共 0 局' in r.stdout or 'stats' in r.stdout, (r.stdout, r.stderr)
    print('smoke test ok:', r.stdout.strip().splitlines()[:1])

    # 6. zip
    out = os.path.join(DIST, 'war3-coach-portable.zip')
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(STAGE):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, DIST))
    size = os.path.getsize(out)
    md5 = subprocess.run(['md5', '-q', out], capture_output=True,
                         text=True).stdout.strip()
    print(f'\n{out}\n  {size/1048576:.1f} MB  MD5 {md5}')


if __name__ == '__main__':
    main()
