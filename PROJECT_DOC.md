# 魔法少女的魔女审判 - AI对话系统项目文档

## 项目概述

基于Claude API的视觉小说AI对话系统，支持动态剧情生成、角色互动、多周目游戏。

---

## 一、当前完成状态

### ✅ 已完成

| 模块 | 文件 | 说明 |
|-----|------|------|
| 角色数据 | `characters/*/` | 14个角色完整YAML |
| 中控API | `game_loop.py` | 调度13人位置和行为 |
| 导演API v1 | `game_loop.py` | 生成对话+3选项+预生成回应 |
| 角色API | `game_loop.py` | 自由对话回复（选D时） |
| 世界状态 | `world_state/` | current_day, character_states, events_log, pending_events |
| 游戏主循环 | `game_loop.py` | 基础版可运行 |
| 自由事件模板 | `events/free_event_templates.yaml` | 8种事件模板 |
| 固定事件 | `events/fixed_events.yaml` | 全部固定事件定义 |

### ⏳ 未完成

| 模块 | 优先级 | 说明 |
|-----|--------|------|
| 导演API v2 | 高 | 高自由度版prompt |
| 状态机 | 高 | free_time → event → investigation → trial |
| 事件验证器 | 高 | 检查导演输出合法性 |
| 调查阶段逻辑 | 中 | 搜证、询问、线索收集 |
| 审判系统逻辑 | 中 | 投票、辩论、处刑 |
| 周目系统 | 低 | 工具继承、多周目存档 |
| Unity对接 | 低 | JSON接口导出 |

---

## 二、角色列表

### 13囚犯
| ID | 日文名 | 中文名 | 囚人番号 |
|----|--------|--------|----------|
| aima | 桜羽エマ | 艾玛 | 658 |
| hiro | 二階堂ヒロ | 寻 | 659 |
| anan | 夏目アンアン | 安安 | 660 |
| noah | 城ヶ崎ノア | 诺亚 | 661 |
| reia | 蓮見レイア | 蕾雅 | 662 |
| miria | 佐伯ミリア | 米莉亚 | 663 |
| margo | 宝生マーゴ | 玛尔戈 | 664 |
| nanoka | 黒部ナノカ | 菜乃香 | 665 |
| arisa | 紫藤アリサ | 爱丽莎 | 666 |
| sherry | 橘シェリー | 雪莉 | 667 |
| hannah | 遠野ハンナ | 汉娜 | 668 |
| coco | 沢渡ココ | 可可 | 669 |
| meruru | 氷上メルル | 梅露露 | 670 |

### 特殊角色
| ID | 日文名 | 说明 |
|----|--------|------|
| yuki | 月代ユキ | 大魔女，幕后策划者 |

---

## 三、文件结构

```
test_project/
├── characters/
│   ├── aima/
│   │   ├── core.yaml        # 基础信息
│   │   ├── personality.yaml # 性格特质
│   │   ├── speech.yaml      # 说话方式
│   │   └── relationships.yaml # 人际关系
│   ├── hiro/
│   ├── anan/
│   ├── noah/
│   ├── reia/
│   ├── miria/
│   ├── margo/
│   ├── nanoka/
│   ├── arisa/
│   ├── sherry/
│   ├── hannah/
│   ├── coco/
│   ├── meruru/
│   └── yuki/
├── world_state/
│   ├── current_day.json     # 当前时间、阶段、状态
│   ├── character_states.json # 13人实时状态
│   └── events_log.json      # 事件日志
├── config.py                # API配置
├── game_loop.py             # 游戏主循环
├── test_api.py              # API测试
├── test_director_api.py
├── test_controller_api.py
└── README.md
```

---

## 四、角色数据格式

### core.yaml
```yaml
name:
  zh: 中文名
  ja: 日文名
age: 年龄
prisoner_number: 囚人番号
role: 身份描述
```

### personality.yaml
```yaml
versions:
  minimal: 一句话描述
  simple: 2-3句（API prompt用）
  full: 完整性格分析
traits: [特质列表]
triggers:
  stress_increase: [压力增加触发]
  stress_decrease: [压力减少触发]
hidden_truth: 隐藏秘密
```

### speech.yaml
```yaml
first_person: 第一人称
verbal_tics: [口癖列表]
tone_by_emotion:
  happy/sad/angry/nervous/calm: 语气描述
example_lines:
  情绪:
    zh: 中文台词
    ja: 日文台词
```

### relationships.yaml
```yaml
existing: {}  # 游戏开始时已有关系
potential:    # 可能发展的关系
  角色id:
    type: 关系类型
    hint: 潜在关系描述
```

---

## 五、世界状态格式

### current_day.json
```json
{
  "chapter": 1,
  "day": 1,
  "time": "10:00",
  "period": "morning",
  "phase": "free_time",
  "alive_count": 13,
  "dead_count": 0,
  "murderer_id": null,
  "victim_id": null,
  "case_status": "no_case",
  "investigation_phase": false,
  "trial_phase": false
}
```

### character_states.json
```json
{
  "角色id": {
    "alive": true,
    "stress": 0-100,
    "madness": 0-100,
    "emotion": "情绪",
    "location": "位置",
    "action": "当前行为",
    "can_interact": true/false,
    "is_murderer": false,
    "is_victim": false
  }
}
```

---

## 六、API设计

### 1. 中控API
**职责**：宏观调度、位置管理、固定事件检查

**输入**：
- 当前时间、阶段
- 13人当前状态

**输出**：
```json
{
  "world_state": {
    "角色id": {
      "location": "位置",
      "action": "行为",
      "can_interact": true
    }
  },
  "dynamic_events": [
    {"trigger_time": 5, "event": "事件", "condition": "条件"}
  ]
}
```

### 2. 导演API（当前v1）
**职责**：生成对话、选项、预生成回应

**输入**：
- 角色数据（core/personality/speech）
- 场景信息（地点、时间、状态）

**输出**：
```json
{
  "dialogue": [
    {"speaker": "id", "text_cn": "", "text_jp": "", "emotion": ""}
  ],
  "choice_point": {
    "prompt_cn": "你要怎么回应？",
    "options": [
      {
        "id": "A",
        "text_cn": "选项文本",
        "leads_to_badend": false,
        "response": {
          "dialogue": [...],
          "status_changes": {"stress": -5, "affection": 3, "madness": 0},
          "relationship_hint": ""
        }
      }
    ]
  },
  "recommended_bgm": ""
}
```

### 3. 导演API v2（待开发）
**职责**：高自由度场景生成、事件选择、多角色控制

**新增输入**：
- 在场所有角色
- 可用事件模板
- 约束条件
- pending_events队列

**新增输出**：
```json
{
  "event_type": "conflict/discovery/approach/witness/normal",
  "event_slots": {
    "character_a": "",
    "character_b": "",
    "location": "",
    "reason": ""
  },
  "dialogue": [...],
  "options": [...],
  "npc_actions": [
    {"character": "id", "action": "行为描述"}
  ],
  "status_changes": {
    "角色id": {"stress": 0, "madness": 0, "affection": 0}
  },
  "pacing": "extend/skip/normal",
  "conflict_resolution": "merge/delay/interrupt",
  "delayed_event": {...},
  "importance": "major/minor",
  "summary": "事件摘要"
}
```

**导演API模式**：
| 模式 | 触发 | 输出 |
|-----|------|------|
| scene | free_time互动 | 对话+选项+事件 |
| summary | 每天结束 | 当日总结文字 |
| badend | 玩家魔女化 | Bad End剧情 |

### 4. 角色API
**职责**：自由对话回复（选D时）、多角色对话

**输入**：
- 角色数据
- 玩家输入
- 当前状态

**输出**：
```json
{
  "text_cn": "",
  "text_jp": "",
  "emotion": "",
  "status_changes": {"stress": 0, "affection": 0}
}
```

---

## 七、事件系统设计

### 1. 自由事件模板
```yaml
templates:
  conflict:
    name: "角色冲突"
    slots: [character_a, character_b, location, reason]
    outcome_options: [...]
    
  discovery:
    name: "发现线索"
    slots: [character, location, clue_type]
    
  approach:
    name: "角色示好"
    slots: [character, method]
    
  witness:
    name: "目击可疑"
    slots: [witness, target, action, location]
```

### 2. 固定事件
```yaml
fixed_events:
  day_1_lunch:
    trigger: "第1天午餐"
    type: "fixed"
    scene: [...]
    outcomes: [...]
    
  murder_event:
    trigger: "第3天后 AND 最高madness > 70"
    type: "fixed"
    scene: [...]
```

### 3. 事件冲突处理
- 固定事件 vs 自由事件 → 固定优先
- 自由事件 vs 自由事件 → 导演决定（merge/delay/interrupt）

---

## 八、状态机设计

```
                ┌─────────────┐
                │  free_time  │ ←──────────────┐
                └──────┬──────┘                │
                       │                       │
                       ▼                       │
                ┌─────────────┐                │
                │   event     │                │
                └──────┬──────┘                │
                       │                       │
      ┌────────────────┼────────────────┐      │
      ▼                ▼                ▼      │
┌──────────┐    ┌───────────┐    ┌─────────┐  │
│ 普通事件  │    │ 发现尸体  │    │  就寝   │──┘
└────┬─────┘    └─────┬─────┘    └─────────┘
     │                │
     │                ▼
     │         ┌─────────────┐
     │         │investigation│
     │         └──────┬──────┘
     │                ▼
     │         ┌─────────────┐
     │         │    trial    │
     │         └──────┬──────┘
     │                │
     └────────────────┴──────→ 回到 free_time 或 Bad End
```

---

## 九、结局系统

### Bad End（重开）
| 类型 | 触发 | 结果 |
|-----|------|------|
| 审判选错 | 投票错误 | 主角死/无辜者死 |
| 玩家魔女化 | 异常行为累积/好感度崩坏 | 玩家死 |

### Good End
- 条件：阻止杀人事件，没人死

### True End
- 条件：全员存活 + 所有人压力70-85% + 发现真相 + 13人联合觉醒

---

## 十、周目系统

| 周目 | 目标 | 继承工具 |
|-----|------|---------|
| 第1周目 | Normal End | 无 |
| 第2周目 | Good End | 角色档案、压力可视化、快速跳过 |
| 第3周目 | True End | 全部工具（洞察之眼、情绪引导等） |

---

## 十一、存档文件更新规则

| 导演输出字段 | 更新到 | 内容 |
|-------------|--------|------|
| status_changes | character_states.json | stress, madness, emotion |
| npc_actions | character_states.json | action字段 |
| delayed_event | pending_events.json | 新增待处理事件 |
| event_type + slots | events_log.json | 记录已发生事件 |
| pacing | current_day.json | 调整互动次数/阶段 |

### 事件记录规则
| 事件类型 | 记录方式 |
|---------|---------|
| 固定事件/死亡/重大线索/Bad End | 完整记录 |
| 普通自由事件/普通对话 | 摘要 |

### 当日总结
- 触发：每天结束（就寝）
- 方式：代码汇总数据 + 导演API(summary模式)生成文字
- 存入：events_log.json

---

## 十二、下一步开发顺序

1. **事件模板YAML** - 定义自由事件和固定事件格式
2. **pending_events.json** - 新增待处理事件队列文件
3. **导演API v2 prompt** - 高自由度版prompt设计
4. **状态机代码** - game_loop改为dispatcher模式
5. **事件验证器** - 检查导演输出合法性
6. **调查阶段** - investigation流程
7. **审判系统** - trial流程
8. **Bad End处理** - 重开逻辑
9. **周目系统** - 工具继承
10. **Unity对接** - JSON接口

---

## 十三、配置说明

### config.py
```python
API_KEYS = {
    "controller": "sk-xxx",  # 中控API
    "director": "sk-xxx",    # 导演API
    "character": "sk-xxx"    # 角色API
}
MODEL = "claude-sonnet-4-20250514"
```

### 运行方式
```bash
cd test_project
python game_loop.py
```

---

## 十四、测试记录

### 2024-12-18 测试通过
- 中控API调度13人位置 ✅
- 导演API生成对话+ABC选项 ✅
- 选A/B/C零延迟显示预生成回应 ✅
- 角色状态正确更新 ✅
- arisa使用「ウチ」第一人称 ✅

---

*文档版本：v1.0*
*最后更新：2024-12-18*
