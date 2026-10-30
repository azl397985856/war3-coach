#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云端信箱: 用用户的 GitHub 私有仓库做回放+对手库中转。

仓库布局:
  state/opponents.json     对手库 (真源)
  replays/YYYY-MM-DD/x.w3g 回放归档

API 全走 Git Data API (blobs/trees/commits/refs), 文件大小不受
Contents API 1MB 限制; 空仓库自动建首个 commit。
配置文件 sync.txt (工具根目录, Mac 侧默认 ~/war3-coach-sync.txt):
  token=github_pat_xxx
  repo=用户名/war3-coach-sync
token 用 fine-grained PAT: 只勾这个仓库 + Contents 读写, 被偷也只影响这一个仓。
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request

API = 'https://api.github.com'
UA = 'war3-coach/0.2'
DB_PATH = 'state/opponents.json'


def load_conf(*roots):
    """从候选目录找 sync.txt -> ({token,repo}, path) 或 (None, None)"""
    for d in roots:
        if not d:
            continue
        p = os.path.join(d, 'sync.txt')
        if os.path.exists(p):
            conf = {}
            with open(p, encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        k, v = line.split('=', 1)
                        conf[k.strip()] = v.strip()
            if conf.get('token') and conf.get('repo'):
                return conf, p
    return None, None


class GH:
    def __init__(self, token, repo):
        self.token = token
        self.repo = repo

    def _req(self, method, path, payload=None, tries=3):
        url = API + path
        data = json.dumps(payload).encode() if payload is not None else None
        last = None
        for i in range(tries):
            try:
                req = urllib.request.Request(url, data=data, method=method, headers={
                    'Authorization': 'Bearer ' + self.token,
                    'User-Agent': UA,
                    'Accept': 'application/vnd.github+json',
                    'Content-Type': 'application/json',
                })
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read()
                return json.loads(body) if body else None
            except urllib.error.HTTPError as e:
                if e.code in (401,):
                    raise RuntimeError('token 无效或权限不够 (HTTP 401)')
                if e.code in (404, 409, 422):
                    raise
                last = e
                time.sleep(2 * (i + 1))
            except Exception as e:            # 网络抖动
                last = e
                time.sleep(2 * (i + 1))
        raise RuntimeError('github 连不上: %s' % last)

    # ---- 读 ----
    def get_ref(self):
        try:
            r = self._req('GET', '/repos/%s/git/ref/heads/main' % self.repo)
            return r['object']['sha']
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def tree(self):
        """全仓库文件清单 -> {path: blob_sha}"""
        ref = self.get_ref()
        if ref is None:
            return {}
        c = self._req('GET', '/repos/%s/git/commits/%s' % (self.repo, ref))
        t = self._req('GET', '/repos/%s/git/trees/%s?recursive=1' % (self.repo, c['tree']['sha']))
        return {e['path']: e['sha'] for e in t.get('tree', []) if e['type'] == 'blob'}

    def blob(self, sha):
        r = self._req('GET', '/repos/%s/git/blobs/%s' % (self.repo, sha))
        return base64.b64decode(r['content'])

    # ---- 写 ----
    def push_files(self, files, message):
        """files: {path: bytes}。一次 commit 全部提交。"""
        assert files, 'nothing to push'
        ref = self.get_ref()
        base_tree = None
        parents = []
        if ref:
            c = self._req('GET', '/repos/%s/git/commits/%s' % (self.repo, ref))
            base_tree = c['tree']['sha']
            parents = [ref]
        tree_entries = []
        for path, data in files.items():
            b = self._req('POST', '/repos/%s/git/blobs' % self.repo,
                          {'content': base64.b64encode(data).decode(),
                           'encoding': 'base64'})
            tree_entries.append({'path': path, 'mode': '100644',
                                 'type': 'blob', 'sha': b['sha']})
        tpayload = {'tree': tree_entries}
        if base_tree:
            tpayload['base_tree'] = base_tree
        t = self._req('POST', '/repos/%s/git/trees' % self.repo, tpayload)
        c = self._req('POST', '/repos/%s/git/commits' % self.repo,
                      {'message': message, 'tree': t['sha'], 'parents': parents})
        if ref is None:
            self._req('POST', '/repos/%s/git/refs' % self.repo,
                      {'ref': 'refs/heads/main', 'sha': c['sha']})
        else:
            self._req('PATCH', '/repos/%s/git/refs/heads/main' % self.repo,
                      {'sha': c['sha'], 'force': False})


def merge_db(local_path, remote_bytes):
    """远端 DB 合并进本地 (按 游戏键 去重), 返回 (合并后dict, 新增局数)"""
    def load(b):
        if not b:
            return {'games': []}
        try:
            return json.loads(b)
        except Exception:
            return {'games': []}

    def key(g):
        names = ','.join(sorted(p['name'] for p in g.get('players', [])))
        return '%s|%s|%s' % (g.get('ts'), g.get('file'), names)

    local = load(open(local_path, 'rb').read() if os.path.exists(local_path) else b'')
    remote = load(remote_bytes)
    seen = {key(g) for g in local.get('games', [])}
    added = 0
    for g in remote.get('games', []):
        if key(g) not in seen:
            local['games'].append(g)
            added += 1
    local['games'].sort(key=lambda g: g.get('ts', 0))
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, 'w', encoding='utf-8') as f:
        json.dump(local, f, ensure_ascii=False, indent=1)
    return local, added


def pull_db_merge(conf, local_db_path):
    """拉远端 DB 合并进本地。返回新增局数 (远端无 DB 返回 -1)"""
    gh = GH(conf['token'], conf['repo'])
    blobs = gh.tree()
    if DB_PATH not in blobs:
        return -1
    _, added = merge_db(local_db_path, gh.blob(blobs[DB_PATH]))
    return added


def push(conf, files, message):
    """files: {repo相对路径: bytes}"""
    gh = GH(conf['token'], conf['repo'])
    gh.push_files(files, message)


def pull_all(conf, replays_dir, local_db_path):
    """Mac 侧全量拉取: DB 合并 + replays/** 落盘。返回 (新增局数, 新增回放数)"""
    gh = GH(conf['token'], conf['repo'])
    blobs = gh.tree()
    db_added = 0
    if DB_PATH in blobs:
        _, db_added = merge_db(local_db_path, gh.blob(blobs[DB_PATH]))
    n_rep = 0
    for path, sha in blobs.items():
        if not path.startswith('replays/'):
            continue
        dst = os.path.join(replays_dir, path[len('replays/'):])
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(gh.blob(sha))
        n_rep += 1
        print('  拉回', path)
    return db_added, n_rep


def make_setup_text():
    return (
        '在工具目录建一个 sync.txt 文件 (记事本即可), 内容两行:\n'
        '  token=你的令牌\n'
        '  repo=azl397985856/war3-coach-sync\n'
        '\n'
        '令牌获取 (一次两分钟, 手机上也能操作):\n'
        '  1. 登录 github.com -> 右上角头像 -> Settings\n'
        '  2. 左栏最底 Developer settings -> Personal access tokens -> Fine-grained tokens\n'
        '  3. Generate new token: 名字随意, 有效期 90 天\n'
        '  4. Repository access 选 Only select repositories -> 选 war3-coach-sync\n'
        '  5. Permissions -> Repository permissions -> Contents: Read and write\n'
        '  6. Generate token -> 复制 github_pat_ 开头的一长串\n'
        '这个令牌只能读写这一个私有仓库, 别的什么都干不了; 不放心随时在'
        '同页面 Revoke 作废重发。'
    )
