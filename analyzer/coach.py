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

# ============ v2: 根因分析 ============

# 农民 fourCC (断档分析对象)
PEASANTS = {'opeo', 'hpea', 'uaco', 'ewsp'}
# 农民训练时长+点击容差 (间隔超过它=生产队列空过)
GAP_THRESHOLD = 19


def peasant_gaps(p, until=720):
    """农民生产断档: 相邻训练事件间隔超过训练时长 => 生产队列空了一段时间。
    返回 [(gap_seconds, gap_end_t), ...] 按时间序。注意: 被杀农民也会造成
    断档, 文案要区分「忘补」与「被骚扰」。"""
    ts = [e['t'] for e in p['bo']
          if e['kind'] == 'train' and e['id'] in PEASANTS and e['t'] <= until]
    return [(round(b - a), round(b)) for a, b in zip(ts, ts[1:])
            if b - a > GAP_THRESHOLD]


def hero_level_timeline(p):
    """队伍英雄总等级时间线: 每次学技能=升 1 级 (War3 每级 1 技能点)。
    返回 [(t, level), ...]。杀怪/杀英雄经验都汇到这条曲线——练级效率
    与交战收益的综合量化。"""
    ts = sorted(e['t'] for e in p['hero_skills'])
    return [(round(t, 1), i + 1) for i, t in enumerate(ts)]


def level_at(tl, t):
    lv = 0
    for tt, l in tl:
        if tt <= t:
            lv = l
        else:
            break
    return lv


def infer_tailside(p, opp, end_s):
    """尾盘盘面推断 (无官方信号局的兜底): 终局等级差 + 尾盘生产停摆。
    返回 {'guess': 'win'|'loss', 'confidence': 'high'|'medium', 'evidence': [..]}
    或 None (证据不充分)。 guess 是 p 的结果。"""
    if not opp:
        return None
    ev = []
    my_tl, op_tl = hero_level_timeline(p), hero_level_timeline(opp)
    lv_gap = level_at(my_tl, end_s) - level_at(op_tl, end_s)
    if abs(lv_gap) >= 3:
        ev.append(('level', lv_gap, f'终局英雄等级差 {abs(lv_gap)} 级 (你 Lv{level_at(my_tl,end_s)} vs 对面 Lv{level_at(op_tl,end_s)})'))
    def late_acts(x):
        return sum(1 for e in x.get('bo', []) if e['t'] >= end_s - 180)
    my_a, op_a = late_acts(p), late_acts(opp)
    def last_prod(x):
        ts = [e['t'] for e in x.get('bo', []) if e['kind'] in ('train', 'build')]
        return (end_s - ts[-1]) if ts else end_s
    my_last, op_last = last_prod(p), last_prod(opp)
    stall = None
    if my_last - op_last > 120 and my_a <= op_a:
        stall = ('me', f'尾盘生产停摆 (你 {int(my_last//60)}:{int(my_last%60):02d} 前就停了, 对面一直有动作)')
    elif op_last - my_last > 120 and op_a <= my_a:
        stall = ('opp', f'尾盘生产停摆 (对面 {int(op_last//60)}:{int(op_last%60):02d} 前就停了, 你一直有动作)')
    if stall:
        ev.append(('stall', stall[0], stall[1]))
    votes = [x[1] for x in ev]
    votes += [lv_gap > 0]
    votes = ([x[1] for x in ev])
    # 汇总: level(负值=对面高=我输) 与 stall 指向一致才给结论
    level_points_to = None
    if lv_gap <= -3: level_points_to = 'loss'
    elif lv_gap >= 3: level_points_to = 'win'
    if level_points_to and stall and stall[0] == ('me' if level_points_to=='loss' else 'opp'):
        return {'guess': level_points_to, 'confidence': 'high',
                'evidence': [x[2] for x in ev]}
    if stall:
        return {'guess': 'loss' if stall[0] == 'me' else 'win',
                'confidence': 'medium', 'evidence': [x[2] for x in ev]}
    if level_points_to:
        return {'guess': level_points_to, 'confidence': 'medium',
                'evidence': [x[2] for x in ev]}
    return None


def export_metrics(p):
    """训练指标 (跨局趋势的地基): 断档/等级曲线/升本时点/APM。
    全部从单局分析导出, record 时存进对手库。
    断档只统计前 12 分钟 (开局补农意识; 后期不补农是战术选择不是失误)。"""
    gaps = peasant_gaps(p, until=720)
    tl = hero_level_timeline(p)
    return {
        'gap_s': sum(g[0] for g in gaps),      # 农民断档总秒数
        'gap_n': len(gaps),                     # 断档次数
        'lvl5': level_at(tl, 300),              # 5 分钟英雄总等级
        'lvl10': level_at(tl, 600),
        'lvl15': level_at(tl, 900),
        't2': p.get('tech', {}).get('tier2'),   # 升二本时点(秒)
        'apm': p.get('apm_total'),
    }


def _fmt(sec):
    return '%02d:%02d' % (int(sec // 60), int(sec % 60))


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
    """对一个玩家出教练点评 [{level, title, body}] (v2: 根因+优先级)。
    opps[0] 用于对比分析 (练级速度/双方等级曲线)。"""
    out = []
    race = (p.get('race') or '').lower()
    if race != 'orc':
        out.append({'level': 'info', 'title': '视角说明',
                    'body': '教练规则目前按兽族(主族)打磨; 本条目以该玩家视角生成, '
                            '非兽族部分只报事实与双方对比。'})
    opp = opps[0] if opps else None
    t2 = p['tech'].get('tier2')
    t3 = p['tech'].get('tier3')
    priority = []   # (severity, title, body) 取前三做「下局重点练」

    # 1. 开局形态 + 升本节拍 (三选一是兽族专属规则, 其他种族不套用)
    key, desc, basis = identify_opening(p) if race == 'orc' else (None, '', '')
    ref = {'double': 161, 'single': 170, 'fasttech': 130}.get(key)
    if key:
        out.append({'level': 'info', 'title': '开局形态: %s' % desc[0],
                    'body': '识别依据: %s。手册标准节拍: %s。' % (basis, desc[1])})
        ref = {'double': 161, 'single': 170, 'fasttech': 130}[key]
        if t2 is not None:
            delta = t2 - ref
            if abs(delta) <= 20:
                out.append({'level': 'good', 'title': '升二本 %s — 与参考节拍相当' % _fmt(t2),
                            'body': '参考 %s (%s), 差 %+d 秒。' % (_fmt(ref), desc[0], delta)})
            elif delta > 20:
                out.append({'level': 'warn', 'title': '升二本 %s — 比参考慢 %d 秒' % (_fmt(t2), delta),
                            'body': '参考 %s (%s)。慢在哪看下面「农民断档」条——'
                                    '大多数慢 30 秒以上的局都是农民断档直接造成的。' % (_fmt(ref), desc[0])})
            else:
                out.append({'level': 'good', 'title': '升二本 %s — 比参考快 %d 秒' % (_fmt(t2), -delta),
                            'body': '快不一定是好事: 确认农民数和防守没有欠账。'})

    # 2. 农民断档 (根因 #1)
    gaps = peasant_gaps(p)
    if gaps:
        total = sum(g[0] for g in gaps)
        worst = max(gaps)
        early = [g for g in gaps if g[1] <= 480]
        lvl = 'warn' if total > 45 or len(gaps) >= 4 else 'info'
        drill = ('每次点完苦工，镜头切回基地看一眼生产队列再走' if race == 'orc'
                 else '每 10 秒扫一眼主基地生产队列')
        out.append({'level': lvl, 'title': '农民断档: %d 次 / 共 %d 秒 (前 12 分钟)' % (len(gaps), total),
                    'body': '最长一次 %d 秒，结束于 %s。断档原因两种：被骚扰杀农(该练防骚扰)或'
                            '忘了点下一轮(纯肌肉记忆)。修法：%s，把「生产队列永远不为空」当成每局唯一目标练 5 局，'
                            '其他都不管。这一条练熟，升本节拍自动到位。'
                            % (worst[0], _fmt(worst[1]), drill)})
        if early and (ref is None or (t2 and t2 > ref + 20)):
            gap_sum = sum(g[0] for g in early)
            slow = ('升本慢 %d 秒的主因' % (t2 - ref)) if (ref and t2) else '升本节奏拖累项'
            priority.append((2, '补齐农民断档 (本局断档 %d 秒, %s)' % (gap_sum, slow),
                             '开局 8 分钟内每 10 秒看一眼主基地生产队列。'))
    else:
        out.append({'level': 'good', 'title': '农民生产: 前 12 分钟无断档',
                    'body': '生产队列意识不错，保持。'})

    # 3. 英雄练级速度对比 (根因 #2)
    my_tl = hero_level_timeline(p)
    opp_tl = hero_level_timeline(opp) if opp else []
    if my_tl and opp_tl:
        marks = []
        for t_check in (300, 600, 900):
            ml = level_at(my_tl, t_check)
            ol = level_at(opp_tl, t_check)
            if ml or ol:
                marks.append('%d分钟 你%d vs 他%d' % (t_check // 60, ml, ol))
        out.append({'level': 'info', 'title': '英雄总等级曲线: %s' % '，'.join(marks),
                    'body': '每次学技能=升 1 级，这条曲线是练级效率+交战收益的总账。'
                            '落后时检查三件事：练级路线有没有走手册的图（2.2 节逐图路线）、'
                            '骚扰花了多少时间值不值、有没有在弱势期硬接团。'})
        lv5 = level_at(my_tl, 600) - level_at(opp_tl, 600)
        if lv5 <= -2:
            priority.append((1, '练级效率: 10 分钟时英雄等级落后 %d 级' % -lv5,
                             '对照手册 2.2 节这张图的推荐路线打一遍野——先练「路线肌肉记忆」，'
                             '再谈随机应变。'))

    # 4. 升本期大 G / 部队断档 (兽族专属节拍)
    if race == 'orc' and key in ('single', 'double') and t2 is not None:
        win = [e for e in p['bo'] if t2 - 90 <= e['t'] <= t2 + 150]
        grunts = sum(1 for e in win if e['id'] == 'ogru')
        expect = 3 if key == 'single' else 4
        out.append({'level': 'info' if grunts >= expect - 1 else 'warn',
                    'title': '升本期大 G: %d 个 (手册参考 %d)' % (grunts, expect),
                    'body': '这批大 G 是升本期的练级保镖——数量不足时英雄等级曲线必然掉队，'
                            '和上面第 3 条是同一件事的两面。断产原因通常是资源被断档吃掉。'})
        if grunts < expect - 1:
            priority.append((3, '升本期部队保产量 (本局 %d/%d)' % (grunts, expect),
                             '升本命令后心里数着出兵：单地洞 3 大 G / 双地洞 4 大 G。'))

    # 5. 二英雄时机 (兽族手册节拍)
    t2_hero = next((h for h in p['heroes'] if t2 and h['t'] > t2 and h['t'] < (t3 or 1e9)), None)
    if race == 'orc' and t2 is not None and t2_hero:
        delay = t2_hero['t'] - t2
        out.append({'level': 'info', 'title': '二英雄 %s: 升本命令后 %d 秒' % (t2_hero['cn'], delay),
                    'body': '手册: 二本好后第一时间出二英雄。150 秒以内=贴标准(酒馆二发可以先买)。'})

    # 6. 胜负归因
    if opp:
        op_units = opp.get('units_trained') or {}
        from parser.names import UNIT_CN
        top_opp = sorted(op_units.items(), key=lambda x: -x[1])[:3]
        out.append({'level': 'info', 'title': '对手部队主线: %s' % '，'.join('%s×%d' % (UNIT_CN.get(k, k), v) for k, v in top_opp),
                    'body': '看清对手在憋什么，你的转型是否针对到了它。赢的局也要归因正确：'
                            '是克制到位、还是对手失误、还是经济差——把偶然的赢变成可复制的方法。'})

    # 7. 道具事实 (保留, 精简)
    items = p.get('items') or {}
    if items:
        nice = {'bspd': '速度之靴', 'plcl': '清晰药水', 'dust': '显影之尘',
                'shas': '治疗卷轴', 'shea': '治疗药膏', 'cnob': '头环',
                'spro': '防护卷轴', 'pnvl': '抗魔项链', 'stwp': '回城卷轴',
                'ssan': '隐身药水', 'phea': '治疗药水', 'pman': '魔法药水',
                'gcel': '群体治疗卷轴', 'oli2': '毒球', 'ofir': '火球'}
        txt = ', '.join('%s x%d' % (nice.get(k, k), v) for k, v in
                        sorted(items.items(), key=lambda x: -x[1]))
        if race == 'orc':
            body = ('手册 5.7: 头环第一目标; 买粉骚扰强于空手; 残血现买现吃。'
                    '注意毒球/电球的使用率——对位 UD/HUM 时球的收益常被低估。')
        else:
            body = '该玩家的实际购买清单 (以对手视角看他的打法习惯: 出门装/续航/保命配比)。'
        out.append({'level': 'info', 'title': '道具: %s' % txt, 'body': body})

    # 8. 下局重点练 (优先级排序, 最多 3 条)
    priority.sort(key=lambda x: x[0])
    if priority:
        lines = '；'.join('(%d) %s' % (i + 1, t) for i, (s, t, b) in enumerate(priority[:3]))
        out.insert(0, {'level': 'warn', 'title': '下局重点练 (一次只练一件)',
                       'body': lines + '。贪多必失：一个习惯练到不用想，再练下一个。'})

    return out


def _fmt(sec):
    return '%02d:%02d' % (int(sec // 60), int(sec % 60))
