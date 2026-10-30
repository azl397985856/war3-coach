#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则版教练: 把分析结果对照训练手册(war3-website.md)的既定标准出点评。

原则: 只对有把握的做判定; 手册没有明确数值的不下"及格/不及格"结论,
报事实+手册参考。规则只覆盖兽族(用户主族), 其他种族只报事实。

硬数据来源(手册原文):
- 开局三选一: 单地洞标准(兵营->商店->20人口升本, 升本期3大G) /
  双地洞科技(第二地洞先于升本, 升本期4大G) / 无兵营速科技(约17人口直城)
- 剑圣猎头双地洞参考表: 祭坛0:01 / 地洞0:12 / 兵营0:32 / 磨坊1:05 /
  剑圣1:06 / 大G1:32 / 第二地洞1:55 / 升二本2:41 / 商店3:07 (KK ±2s)
- 万金油: 二本好后第一时间出二英雄; 50人口双英雄3级=强势窗口
"""
from collections import Counter

# 升二本建造时长的粗估窗口(秒), 用于"升本期间"统计; 1.27 实际值待实测校准
_T2_BUILD_WIN = 150

_OPENING_DESC = {
    'single': ('单地洞标准', '兵营→商店→20 人口升本, 升本期间 3 大 G'),
    'double': ('双地洞科技', '第二地洞先于升本, 升本期间 4 大 G'),
    'fasttech': ('无兵营速科技', '约 17 人口直城, 升本期间补战争磨坊'),
}


def _builds(bo, t_max=1e9):
    return [e for e in bo if e['kind'] == 'build' and e['t'] <= t_max]


def identify_opening(p):
    """兽族开局形态识别 -> (key, 描述, 依据)"""
    t2 = p['tech'].get('tier2')
    if t2 is None:
        return None, '未升二本', ''
    b = _builds(p['bo'], t2)
    burrows = [e for e in b if e['id'] == 'otrb']
    has_bar = any(e['id'] == 'obar' for e in b)
    if not has_bar:
        return 'fasttech', _OPENING_DESC['fasttech'], '升本前无兵营'
    if len(burrows) >= 2:
        return 'double', _OPENING_DESC['double'], '升本前有 %d 个地洞' % len(burrows)
    return 'single', _OPENING_DESC['single'], '升本前只有 1 个地洞'


def coach_player(p, opps, game_len_s):
    """对一个玩家出教练点评列表 [{level, title, body}]"""
    out = []
    race = (p.get('race') or '').lower()
    if race != 'orc':
        out.append({'level': 'info', 'title': '非兽族局',
                    'body': '教练规则目前只覆盖兽族(主族), 本局只报事实。'})
        return out

    t2 = p['tech'].get('tier2')
    t3 = p['tech'].get('tier3')

    # 1. 开局形态
    key, desc, basis = identify_opening(p)
    if key:
        out.append({'level': 'info', 'title': '开局形态: %s' % desc[0],
                    'body': '识别依据: %s。手册标准节拍: %s。' % (basis, desc[1])})
        if key == 'double':
            ref = 161  # 2:41 手册参考表(KK ±2s)
        elif key == 'single':
            ref = 170  # 单地洞 20 人口升本, 样例职业 2:26-2:58, 取 ~2:50 参考
        else:
            ref = 130  # 速科技参考, 手册无精确值, 按最快标准科技估
        if t2 is not None:
            delta = t2 - ref
            if abs(delta) <= 20:
                out.append({'level': 'good', 'title': '升二本 %s — 与参考节拍相当' % _fmt(t2),
                            'body': '参考 %s (%s), 差 %+d 秒。' % (_fmt(ref), desc[0], delta)})
            elif delta > 20:
                out.append({'level': 'warn', 'title': '升二本 %s — 比参考慢 %d 秒' % (_fmt(t2), delta),
                            'body': '参考 %s (%s)。慢的原因通常是: 被骚扰/补农民卡资源/'
                                    '造了参考流程外的建筑。回看录像前 3 分钟找断档。' % (_fmt(ref), desc[0])})
            else:
                out.append({'level': 'good', 'title': '升二本 %s — 比参考还快 %d 秒' % (_fmt(t2), -delta),
                            'body': '参考 %s (%s)。快不一定是好事: 确认农民和防守没欠账。' % (_fmt(ref), desc[0])})

    # 2. 升本期间大 G 数 (单地洞3/双地洞4) —— "手里"的概念含升本前90秒出的
    if key in ('single', 'double') and t2 is not None:
        win = [e for e in p['bo']
               if t2 - 90 <= e['t'] <= t2 + _T2_BUILD_WIN]
        grunts = sum(1 for e in win if e['id'] == 'ogru')
        expect = 3 if key == 'single' else 4
        out.append({'level': 'info' if grunts >= expect - 1 else 'warn',
                    'title': '升本期大 G: %d 个 (手册参考 %d)' % (grunts, expect),
                    'body': '统计窗口=升本命令前 90 秒到后 %d 秒(二本建造时长为估算)。'
                            '这批大 G 是升本期的练级保镖, 断产会拖慢到 3 节拍。' % _T2_BUILD_WIN})

    # 3. 二英雄是否"第一时间"
    t2_hero = next((h for h in p['heroes']
                    if h['t'] > (t2 or 0) and h['t'] < (t3 or 1e9)), None)
    if t2 is not None and t2_hero:
        delay = t2_hero['t'] - t2
        out.append({'level': 'info',
                    'title': '二英雄 %s: 升本命令后 %d 秒' % (t2_hero['cn'], delay),
                    'body': '手册: 二本好后第一时间出二英雄(先出英雄再放 BE/BS)。'
                            '二本建造约 2 分半, 所以这个数越小越贴标准; '
                            '若明显大于建造时长, 检查是不是被卡资源或先放了建筑。'})

    # 4. 开矿
    if p['expansions']:
        ex = p['expansions'][0]
        out.append({'level': 'info', 'title': '开矿: %s' % _fmt(ex['t']),
                    'body': '手册: 二本分矿是主流分支——对面压制弱、分矿安全时优先开;'
                            ' 开矿同时别断三本的钱。'})

    # 5. 地洞数量曲线 (防御欠账提醒)
    burrows_all = [e for e in p['bo'] if e['id'] == 'otrb']
    if burrows_all:
        n10 = sum(1 for e in burrows_all if e['t'] <= 600)
        out.append({'level': 'info', 'title': '地洞: 10 分钟前共放 %d 个' % n10,
                    'body': '地洞既是人口又是塔。中期人口顶上限/被拆家局, 优先补洞。'})

    # 6. APM 描述
    apm = p.get('apm_by_minute') or []
    if len(apm) >= 5:
        early = sum(apm[:3]) / 3
        avg = p.get('apm_avg', 0)
        out.append({'level': 'info', 'title': 'APM: 平均 %s, 前 3 分钟 %d' % (avg, early),
                    'body': '开局 3 分钟是操作密度最高的阶段(建农民/放建筑/英雄练级)。'
                            '前 3 分钟明显低于全程均值, 说明开局流程还不够"手熟"。'})

    # 7. 道具事实
    items = p.get('items') or {}
    if items:
        nice = {'bspd': '速度之靴', 'plcl': '清晰药水', 'dust': '显影之尘',
                'shas': '治疗卷轴', 'shea': '治疗药膏', 'cnob': '头环',
                'spro': '防护卷轴', 'pnvl': '抗魔项链', 'stwp': '回城卷轴',
                'ssan': '隐身药水', 'phea': '治疗药水', 'pman': '魔法药水',
                'gcel': '群体治疗卷轴'}
        txt = ', '.join('%s x%d' % (nice.get(k, k), v) for k, v in
                        sorted(items.items(), key=lambda x: -x[1]))
        out.append({'level': 'info', 'title': '道具: %s' % txt,
                    'body': '手册 5.7: 头环是第一目标(偷宝); 粉常备(买粉骚扰强于空手); '
                            '交战期残血现买血瓶蓝瓶, 性价比高于攒大无敌。'})
    return out


def _fmt(sec):
    return '%02d:%02d' % (int(sec // 60), int(sec % 60))
