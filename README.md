# war3-coach

魔兽争霸 III 训练辅助：回放分析 + 对手库。**纯回放解析，不碰游戏进程——KK 平台零封号风险。**

面向 KK 平台 1.27 天梯冲榜（主战场），分析你自己的每局对局、记住每个对手。

## 已验证能力

- 格式：经典 .w3g（1.26/1.29 实测通过）+ 网易包装 .nwg（GRBN 头自动剥离）
- 每局战报：建造顺序（精确到秒）、分分钟 APM、升本时点、开矿时点、
  英雄出场与技能加点序列、道具购买、部队训练统计
- 对手库：录入/查询/跨局统计（胜率、对各族胜率、连败线）
- 单位 ID 表：从本机 1.27 TFT MPQ 的 UnitBalance/UnitUI SLK 提取（836 单位），
  核心 150 单位/英雄/技能/道具已映射中文名

## 用法

```bash
pip3 install --user w3g

# 单局分析
python3 cli.py analyze samples/ced_vs_lyn.w3g

# 录入对手库（打完一局跑一次；胜负自动判定，拿不准用 --won win/loss 补）
python3 cli.py record <回放> --me <我的KK ID>
python3 cli.py stats --me <我的KK ID>
python3 cli.py lookup <对手ID> --me <我的KK ID>
```

## 结构

```
parser/replay.py   回放加载 (w3g/nwg) + 玩家/槽位/事件流
parser/names.py    fourCC -> 中文名 (单位/英雄/技能/道具/研究)
parser/data/       units.json (SLK 提取的单位表)
analyzer/game.py   BO/APM/升本开矿/技能加点/部队构成
store/opponents.py 对手库 (JSON 存储)
cli.py             命令行入口
tools/extract_ids.py  SLK -> units.json 提取脚本
samples/           测试回放 (w3gjs 开源样例)
```

## 已知限制 / 待办

- **1.32+ (Reforged) 格式未支持**：w3gjs 新 action 表 + protobuf 元数据，等需要时再投入
  （KK 重制版天梯是另一条线；1.27 主线不受影响）
- **胜负自动判定待校准**：经典信号 resultflag 0x08=败/0x09=胜，但 KK 客户端的
  实际离场信号需用真实回放核对；期间用 `--won` 手动补
- 战损统计：经典回放不含单位死亡事件，精确战损做不了；
  部队构成时间线（训练累积）已可用
- 道具/技能/研究中文名只覆盖核心集合，其余显示英文 ID 兜底；
  补全路线 = AbilityData.slk + 字符串表提取（tools/ 下扩展）
- war3-lab 复盘 tab 对接、打完自动录入（监控回放目录）为下一步

## 红线

不做任何读内存/注入/画面篡改——KK 反作弊会检测，冲榜账号不值得冒险。
本工具只读回放文件（游戏本来就写给你的数据）。
