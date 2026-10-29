#!/usr/bin/env python3
"""fourCC -> 中文名映射。核心对战单位/英雄/技能/道具人工映射,
未收录的规则化兜底 (R*=研究, A*=技能, 其余查 units.json 英文名)。"""

UNIT_CN = {
    # ---- ORC (SLK 已核对) ----
    'opeo': '苦工', 'ogru': '步兵', 'ohun': '猎头者', 'otbk': '狂战士',
    'orai': '狼骑兵', 'okod': '科多兽', 'owyv': '飞龙', 'otbr': '蝙蝠骑士',
    'ocat': '投石车', 'oshm': '萨满', 'odoc': '巫医', 'ospw': '灵魂行者',
    'ospm': '灵魂行者(实体化)', 'otau': '牛头人', 'oeye': '岗哨守卫',
    'ogre': '大厅', 'ostr': '要塞(升本二)', 'ofrt': '堡垒(升本三)',
    'oalt': '祭坛', 'obar': '兵营', 'ofor': '战争磨坊', 'otrb': '地洞',
    'owtw': '了望塔', 'obea': '兽栏', 'osld': '灵魂归宿', 'ovln': '巫毒小屋',
    'otto': '牛头人图腾',
    # ---- UD ----
    'uaco': '侍僧', 'ugho': '食尸鬼', 'ucry': '蜘蛛', 'ugar': '石像鬼',
    'umtw': '绞肉车', 'uabo': '憎恶', 'unec': '男巫', 'uban': '女妖',
    'uobs': '十胜石雕像', 'ubsp': '毁灭者', 'udes': '毁灭者', 'ufro': '冰龙',
    'uske': '骷髅战士', 'uskm': '骷髅法师', 'ushd': '阴影',
    'unpl': '大墓地', 'unp1': '亡者大厅(升本二)', 'unp2': '黑色城堡(升本三)',
    'uaod': '黑暗祭坛', 'usep': '地穴', 'uslh': '屠宰场', 'ugrv': '坟场',
    'utod': '诅咒神庙', 'utom': '遗物之墓', 'usap': '献祭之坑',
    'ubon': '骨龙巢穴', 'uzig': '通灵塔', 'uzg1': '蛛网塔(升二)',
    'uzg2': '冰霜塔(升三)',
    # ---- NE ----
    'ewsp': '小精灵', 'earc': '弓箭手', 'esen': '女猎手', 'edry': '树妖(小鹿)',
    'edoc': '熊德', 'edcm': '熊德(变身)', 'edot': '鸟德', 'edtm': '鸟德(变身)',
    'emtg': '山岭巨人', 'efdr': '精灵龙', 'ehip': '角鹰兽', 'ehpr': '角鹰骑士',
    'echm': '奇美拉', 'ebal': '弩车',
    'etol': '生命之树', 'etoa': '岁月之树(升本二)', 'etoe': '永恒之树(升本三)',
    'eate': '长者祭坛', 'eaom': '战争古树', 'eaoe': '知识古树',
    'eaow': '风之古树', 'edos': '奇美拉栖木', 'edob': '猎手大厅',
    'etrp': '远古守护者', 'egol': '缠绕金矿', 'emow': '月亮井',
    'eden': '奇迹古树(商店)',
    # ---- HUM ----
    'hpea': '农民', 'hfoo': '步兵', 'hrif': '火枪手', 'hspt': '破法者',
    'hkni': '骑士', 'hgry': '狮鹫骑士', 'hgyr': '飞行机器', 'hsor': '女巫',
    'hmpr': '牧师', 'hmtm': '迫击炮小队', 'hmtt': '蒸汽坦克', 'hdhw': '龙鹰',
    'hmil': '民兵',
    'htow': '大厅', 'hkee': '主城(升本二)', 'hcas': '城堡(升本三)',
    'halt': '国王祭坛', 'hbar': '兵营', 'hhou': '农场', 'hbla': '铁匠铺',
    'hlum': '伐木场', 'hars': '神秘圣地', 'harm': '车间', 'hgra': '狮鹫笼',
    'hgtw': '防御塔', 'hctw': '炮塔', 'hatw': '神秘之塔', 'hwtw': '哨塔',
}

HERO_CN = {
    # 常规
    'Hamg': '大法师', 'Hmkg': '山丘之王', 'Hpal': '圣骑士', 'Hblm': '血法师',
    'Obla': '剑圣', 'Ofar': '先知', 'Otch': '牛头人酋长', 'Oshd': '暗影猎手',
    'Udea': '死亡骑士', 'Ucrl': '恐惧魔王', 'Ulic': '巫妖', 'Uclr': '地穴领主',
    'Edem': '恶魔猎手', 'Ekee': '丛林守护者', 'Emoo': '月之女祭司', 'Ewar': '守望者',
    # 中立酒馆
    'Nngs': '娜迦海妖', 'Npbm': '熊猫酒仙', 'Nbrn': '黑暗游侠', 'Nbst': '兽王',
    'Ntin': '地精修补匠', 'Nfir': '火焰领主', 'Nalc': '炼金术士', 'Nplh': '深渊领主',
}

SKILL_CN = {
    # 剑圣
    'AOwk': '疾风步', 'AOcr': '致命一击', 'AOmi': '镜象', 'AOww': '剑刃风暴',
    # 先知
    'AOcl': '闪电链', 'AOsf': '幽灵狼', 'AOfs': '透视', 'AOeq': '地震',
    # 牛头
    'AOsh': '冲击波', 'AOws': '战争践踏', 'AOae': '耐久光环', 'AOre': '重生',
    # 小Y
    'AOhw': '治疗波', 'AOhx': '妖术', 'AOss': '毒蛇守卫', 'AOvd': '巫毒',
    # DK
    'AUdc': '死亡缠绕', 'AUau': '邪恶光环', 'AUdp': '操纵死尸',
    # Lich
    'AUfn': '霜冻新星', 'AUfa': '霜冻护甲', 'AUdr': '黑暗仪式',
    # MK
    'AHtb': '风暴之锤', 'AHtc': '雷霆一击', 'AHab': '重击', 'AHav': '天神下凡',
    # AM
    'AHbz': '暴风雪', 'AHwe': '水元素', 'AHbr': '辉煌光环',
    # DH
    'AEmb': '法力燃烧', 'AEim': '献祭', 'AEev': '闪避', 'AEme': '变身',
    # 其他常见
    'AEfk': '刀扇', 'AEbl': '闪烁', 'AHds': '神圣之光',
    'ANba': '醉酒云雾', 'ANbf': '火焰呼吸',
}

ITEM_CN = {
    'bspd': '速度之靴', 'plcl': '清晰药水', 'dust': '显影之尘',
    'shas': '治疗卷轴', 'shea': '治疗药膏', 'cnob': '头环',
    'spro': '防护卷轴', 'pnvl': '抗魔项链', 'stwp': '回城卷轴',
    'ssan': '隐身药水', 'phea': '治疗药水', 'pman': '魔法药水',
    'ckng': '国王之冠', 'evtl': '护身符', 'infs': '小型无敌药水',
    'whwd': '治疗守卫', 'belv': '吸血药水', 'crys': '水晶球',
    'ofir': '火球', 'oli2': '毒球', 'olig': '闪电球', 'odef': '腐蚀球',
    'gcel': '群体治疗卷轴',
}

RESEARCH_CN = {
    'Ropg': '掠夺', 'Robs': '狂战士升级', 'Roen': '夜视',
    'Rowt': '了望塔升级',
}


def fmt_ability(ab):
    """ability bytes -> 人类可读名"""
    if not ab:
        return None
    try:
        s = ab.decode('latin-1')
    except Exception:
        return None
    if s in UNIT_CN: return UNIT_CN[s]
    if s in HERO_CN: return HERO_CN[s]
    if s in SKILL_CN and SKILL_CN[s]: return SKILL_CN[s]
    if s in ITEM_CN and ITEM_CN[s]: return ITEM_CN[s]
    if s in RESEARCH_CN and RESEARCH_CN[s]: return RESEARCH_CN[s]
    if s.startswith('R') and s[1:2].isupper(): return f'研究({s})'
    if s.startswith('A') and s[1:2].isupper(): return f'技能({s})'
    return None
