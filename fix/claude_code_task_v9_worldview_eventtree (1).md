# Claude Code 任务：世界观库 & 事件树重构 v9

## 目标

1. 建立「世界观库」结构，将设定从代码/prompt中分离
2. 实现「事件树」驱动的故事生成，替代当前碎片化场景
3. 支持 7天×多周目 的故事结构
4. **每个场景都是一个完整的小故事，有起承转合**

---

## 零、核心设计原则：场景即故事

> ⚠️ **最重要的改变**：每个场景不是「几句对话」，而是「一个完整的小故事」

### 0.1 当前问题 vs 目标

```
❌ 当前（碎片）：
汉娜：「...你在看什么？」
【选项ABC】
汉娜：「没什么...」
（结束，共3句话）

✅ 目标（故事）：
【开场】走廊尽头，汉娜独自站在窗边。阳光照在她侧脸上，她似乎在看着什么。
【铺垫】你走近时，她的肩膀微微一颤。手里的纸被匆忙藏到身后。
【发展】「啊...是你啊。」她转过身，笑容有些僵硬。
        窗外的风吹进来，她裙摆轻轻晃动。
        「这里的风景...意外地不错呢。」
【转折】一阵风，她手中的纸片飘落。
        你看到上面的字迹——那是某个人的名字，被反复划掉又重写。
【选择点】她弯腰去捡，动作有些慌乱。
        【A】假装没看到
        【B】帮她捡起来
        【C】「那是什么？」
【收尾】她把纸紧紧攥在手里，垂下眼睛。
        「...谢谢你没有问。」（如果选A）
        阳光渐渐西斜。她转身离开，脚步比来时更轻。
（完整情节，有画面、有悬念、有情感弧线）
```

### 0.2 单场景结构模板

每个场景必须包含以下结构（无论长短）：

```yaml
scene_structure:
  # 1. 开场（10-15%）- 建立画面
  opening:
    purpose: "让玩家进入场景，建立氛围"
    content:
      - 环境描写（光线、声音、气味）
      - 角色状态（在做什么、表情、姿态）
      - 时间感（什么时段的感觉）
    example: "午后的图书室很安静。灰尘在阳光中漂浮。角落里，诺亚正对着画布发呆，笔尖的颜料已经干了。"
    
  # 2. 铺垫（15-20%）- 引入张力
  setup:
    purpose: "让玩家感到「有什么事要发生」"
    content:
      - 角色的小动作、反应
      - 暗示某种情绪/秘密
      - 玩家的介入（靠近、被发现）
    example: "你的脚步声让她回过神。她看了你一眼，又迅速移开目光。画布上空空如也。"
    
  # 3. 发展（30-40%）- 展开互动
  development:
    purpose: "角色之间的实质互动"
    content:
      - 对话（但不是纯对话，穿插动作描写）
      - 情绪变化
      - 信息透露（可以是暗示）
    example: |
      「...你也画画吗？」她的声音很轻。
      诺亚拿起一支干掉的笔，又放下。
      「我在想，什么样的画才值得被完成。」
      她的手指无意识地抚过画布边缘，那里有几道划痕。
    
  # 4. 转折/高潮（15-20%）- 关键时刻
  turning_point:
    purpose: "场景的核心事件，给玩家留下印象"
    content:
      - 意外发生（打断、发现、情绪爆发）
      - 或者：关键信息揭露
      - 或者：关系变化的瞬间
    example: "她突然握紧了笔。指节发白。「你见过完美的东西被毁掉吗？」她问，眼睛没有看你。"
    
  # 5. 选择点（如果有）
  choice_point:
    purpose: "玩家参与，影响走向"
    placement: "通常在转折后"
    design_principle: "选项反映态度，不是对错"
    
  # 6. 收尾（10-15%）- 余韵
  resolution:
    purpose: "让场景有完结感，但留下回味"
    content:
      - 角色的最后反应
      - 环境变化（时间流逝、光线变化）
      - 悬念或情感落点
    example: "诺亚没有再说话。你离开时，她已经重新面对画布。但那支笔，始终没有落下。"
```

### 0.3 场景长度标准

| 场景类型 | 最小长度 | 建议长度 | 结构要求 |
|----------|:--------:|:--------:|----------|
| 静默观察 | 150字 | 200-300字 | 开场+铺垫+收尾（无对话/极少对话） |
| 日常片段 | 250字 | 350-500字 | 完整五段式，对话3-6轮 |
| 互动场景 | 400字 | 500-800字 | 完整五段式+选择点，对话5-10轮 |
| 关键场景 | 600字 | 800-1200字 | 完整五段式+多选择点，对话8-15轮 |

### 0.4 对话与叙述比例

```yaml
dialogue_narrative_ratio:
  # 不是纯对话，要有「画面」
  bad_example: |
    汉娜：「你好。」
    艾玛：「你好。」
    汉娜：「今天天气不错。」
    艾玛：「是啊。」
    （纯对话，没有画面，像剧本初稿）
    
  good_example: |
    汉娜端着茶杯走来，裙摆在膝盖处轻轻晃动。
    「今天的阳光真好呢。」她在你对面坐下，动作优雅得像是练习过无数次。
    你注意到她的茶杯是空的。
    「...是啊。」
    她似乎没有察觉你的目光，只是望着窗外。
    茶杯在她手中微微发抖。
    （对话穿插动作、观察、细节）
    
  ratio_guideline:
    静默观察: "叙述90% : 对话10%"
    日常片段: "叙述50% : 对话50%"
    互动场景: "叙述40% : 对话60%"
    关键场景: "叙述30% : 对话70%"
```

### 0.5 Beat 重新定义

当前的 Beat 太短，需要重新定义：

```yaml
beat_redesign:
  # 旧定义：Beat = 几句对话
  # 新定义：Beat = 场景结构的一个阶段
  
  old_beat:
    content: "2-3句对话"
    problem: "太碎，无法形成故事"
    
  new_beat:
    opening_beat:
      content: "环境描写 + 角色初始状态"
      min_length: 50字
      dialogue_lines: 0-1
      
    development_beat:
      content: "互动展开 + 情绪铺垫"
      min_length: 100字
      dialogue_lines: 2-4
      
    climax_beat:
      content: "转折/高潮 + 关键信息"
      min_length: 80字
      dialogue_lines: 2-3
      
    choice_beat:
      content: "选择点 + 分支处理"
      min_length: 60字
      options: 3-4个
      
    resolution_beat:
      content: "收尾 + 余韵"
      min_length: 40字
      dialogue_lines: 0-2

# DirectorPlanner 输出的 ScenePlan 应包含 4-6 个 Beat
# 每个 Beat 对应场景结构的一个阶段
```

### 0.6 Prompt 中的故事性要求

```
【场景故事性要求】★★★ 最重要 ★★★

每个场景必须是一个完整的小故事，不是几句对话。

必须包含：
1. 【开场】环境描写，建立画面感（光线、声音、氛围）
2. 【铺垫】角色状态，暗示即将发生的事
3. 【发展】实质互动，对话+动作+细节
4. 【转折】关键时刻，给玩家留下印象
5. 【收尾】余韵，时间流逝感，悬念或情感落点

对话要求：
- 不是纯对话剧本，每2-3句对话穿插一次动作/神态/环境描写
- 角色说话时要有「在做什么」「表情如何」「小动作」
- 沉默也是表达，用「...」和动作描写代替

长度要求：
- 最短场景（纯观察）：150字以上
- 普通场景（日常）：350字以上
- 互动场景（有选项）：500字以上

禁止：
- 「你好」「再见」式的无意义寒暄
- 纯对话无描写
- 3句话就结束的场景
- 没有画面感的文字
```

---

## 一、新增目录结构

```
test_project/
├── worlds/                          # 世界观库根目录
│   └── witch_trial/                 # 魔女审判世界观
│       ├── manifest.yaml            # 元信息（天数、节奏、主题）
│       ├── core/                    # 核心设定（按需加载）
│       │   ├── rules.yaml           # 世界规则（魔女因子、杀人机制）
│       │   ├── prison_rules.yaml    # 监牢日常规则
│       │   └── tone.yaml            # 氛围基调（起承转合指导）
│       ├── locations/               # 地点库（按需加载）
│       │   ├── _index.yaml          # 地点索引
│       │   └── {location}.yaml      # 各地点详情
│       └── event_tree/              # 事件树
│           ├── structure.yaml       # 7天起承转合结构
│           ├── scene_types.yaml     # 场景类型维度定义
│           ├── daily_patterns.yaml  # 日常模式模板
│           ├── triggers.yaml        # 触发条件库
│           └── branches/            # 分支事件
│               ├── murder_paths.yaml
│               ├── character_arcs.yaml
│               └── endings.yaml
│
├── api/
│   ├── world_loader.py              # 新增：世界观加载器
│   ├── event_tree_engine.py         # 新增：事件树引擎
│   └── ...（现有文件）
│
└── ...（现有文件）
```

---

## 二、核心文件模板

### 2.1 manifest.yaml（世界观元信息）

```yaml
# worlds/witch_trial/manifest.yaml

id: witch_trial
name: 魔法少女的魔女审判
version: "1.0"

# 结构参数
structure:
  total_days: 7              # 总天数
  periods_per_day: 6         # dawn/morning/noon/afternoon/evening/night
  scenes_per_day: 4-6        # 每天场景数范围

# 起承转合节奏
arc:
  起:
    days: [1, 2]
    theme: "日常确立"
    tension_range: [1, 4]
    event_density: sparse    # 事件稀疏
    silence_ratio: 0.5       # 50%静默/观察场景
    forbidden: ["魔女化", "杀人", "崩溃"]
    
  承:
    days: [3, 4]
    theme: "生活展开"
    tension_range: [2, 6]
    event_density: normal
    silence_ratio: 0.35
    allowed: ["小冲突", "秘密暗示", "关系变化"]
    
  转:
    days: [5, 6]
    theme: "暗流与破局"
    tension_range: [4, 9]
    event_density: dense
    silence_ratio: 0.2
    allowed: ["魔女化", "事件", "崩溃", "杀人"]
    
  合:
    days: [7]
    theme: "收束"
    tension_range: [3, 10]
    event_density: focused
    silence_ratio: 0.1
    content: ["审判", "结局", "真相"]

# 设计原则（AI生成时参考）
principles:
  - 生活感：不是任务，是生活
  - 观察者视角：玩家看别人的日常
  - 选项无压力：大部分选什么都可以
  - 沉默也是内容：留白比填满重要
```

---

### 2.2 core/rules.yaml（世界规则）

```yaml
# worlds/witch_trial/core/rules.yaml

# ═══════════════════════════════════════════
# 魔女因子系统
# ═══════════════════════════════════════════

witch_factor:
  description: |
    感染魔女因子的少女会获得魔法，成为「预备魔女」。
    负面情感和心理创伤会滋养因子，加深「魔女化」。
    魔女化到极限会变成「残骸」，失去理智。

  stages:
    normal:
      madness_range: [0, 30]
      description: "日常状态，魔法稳定"
      behavior: "正常社交，偶尔情绪波动"
      
    unstable:
      madness_range: [31, 60]
      description: "情绪波动，魔法不稳"
      behavior: "易怒/易哭，魔法偶尔失控"
      signs: ["独处时自言自语", "对特定话题反应过激"]
      
    critical:
      madness_range: [61, 80]
      description: "临界状态，杀意萌芽"
      behavior: "回避社交，盯着某人看，梦话"
      signs: ["深夜徘徊", "收集「工具」", "写奇怪的东西"]
      
    witch:
      madness_range: [81, 100]
      description: "魔女化，随时可能杀人"
      behavior: "失控边缘，需要极小的触发"
      trigger_threshold: 0.7  # 70%概率在合适条件下行动

# ═══════════════════════════════════════════
# 魔女化触发条件
# ═══════════════════════════════════════════

witch_triggers:
  base_requirements:
    - "madness >= 80"
    - "has_target == true"      # 有杀意对象
    - "opportunity == true"     # 有机会（独处/夜晚）
  
  probability_modifiers:
    trauma_activated: +0.20     # 创伤被触发
    target_present: +0.15       # 目标在场
    isolated_2_days: +0.15      # 连续2天独处
    night_time: +0.10           # 夜晚
    conflict_recent: +0.10      # 最近发生冲突
    witnessed_violence: +0.05   # 目睹暴力
    
  prevention_factors:
    has_supporter: -0.20        # 有支持者/朋友
    stress_released: -0.15      # 压力得到释放
    player_intervened: -0.25    # 玩家成功介入

# ═══════════════════════════════════════════
# 杀人机制
# ═══════════════════════════════════════════

murder:
  core_principle: |
    杀人不是玩家「选错」导致，而是魔女化累积到临界点。
    玩家只能「看到」「来不及阻止」或「事后发现」。
    
  requirements:
    killer:
      - "madness >= 80"
      - "has_motive == true"    # 有动机
      - "魔女化阶段 == witch"
    opportunity:
      - "target_alone OR night_time"
      - "no_witness OR can_silence_witness"
    
  execution_window:
    preferred: ["night", "dawn"]
    possible: ["any_isolated_moment"]
    
  aftermath:
    discovery_delay: "0-12 hours"
    evidence_types: ["physical", "magical", "testimony", "alibi_hole"]

# ═══════════════════════════════════════════
# 审判机制
# ═══════════════════════════════════════════

trial:
  trigger: "尸体被发现 + 调查完成"
  duration: "1小时（游戏内）"
  
  phases:
    - name: "证据陈述"
      description: "展示收集到的证据"
    - name: "质询"
      description: "玩家可以质问嫌疑人"
    - name: "辩论"
      description: "角色之间争论"
    - name: "投票"
      description: "13人投票决定处刑对象"
      
  outcomes:
    correct_vote:
      result: "真凶被处刑"
      ending_path: "normal_end 或 good_end"
    wrong_vote:
      result: "无辜者被处刑"
      ending_path: "bad_end"
    no_consensus:
      result: "无人被处刑，凶手逍遥"
      ending_path: "继续游戏，可能二次杀人"
```

---

### 2.3 core/tone.yaml（氛围基调）

```yaml
# worlds/witch_trial/core/tone.yaml

# ═══════════════════════════════════════════
# 场景氛围指导
# ═══════════════════════════════════════════

scene_guidance:
  # 【起】Day 1-2：日常确立
  起:
    主基调: "平静、陌生、好奇"
    氛围词: ["阳光", "新鲜", "试探", "观察"]
    
    场景比例:
      静默观察: 50%    # 看别人做事，不参与
      日常片段: 40%    # 吃饭、散步、闲聊
      可互动: 10%      # 简单对话选项
      关键时刻: 0%     # 无
      
    对话指导:
      density: sparse
      avg_lines: 3-5
      player_options: "大多是观察，少量简单回应"
      
    禁止内容:
      - 任何角色崩溃
      - 魔女化描写
      - 杀人暗示
      - 高张力对峙
      
  # 【承】Day 3-4：生活展开
  承:
    主基调: "熟悉、日常、暗流"
    氛围词: ["习惯", "熟络", "私语", "微妙"]
    
    场景比例:
      静默观察: 35%
      日常片段: 35%
      可互动: 25%
      关键时刻: 5%
      
    对话指导:
      density: normal
      avg_lines: 5-8
      player_options: "更多对话选项，开始影响关系"
      
    允许内容:
      - 小冲突（争吵但和好）
      - 秘密暗示（某人藏着什么）
      - 关系微妙变化
      - 角色独处时的异常
      
  # 【转】Day 5-6：暗流与破局
  转:
    主基调: "紧张、变化、临界"
    氛围词: ["不安", "秘密", "崩塌", "选择"]
    
    场景比例:
      静默观察: 15%
      日常片段: 25%
      可互动: 35%
      关键时刻: 25%
      
    对话指导:
      density: normal-dense
      avg_lines: 6-12
      player_options: "关键选择出现，可能影响结局"
      
    允许内容:
      - 角色崩溃
      - 魔女化迹象
      - 冲突升级
      - 杀人事件（如果条件满足）
      - 真相片段揭露
      
  # 【合】Day 7：收束
  合:
    主基调: "收束、结果、余韵"
    氛围词: ["审判", "真相", "告别", "希望/绝望"]
    
    场景比例:
      静默观察: 10%
      日常片段: 20%
      可互动: 30%
      关键时刻: 40%
      
    对话指导:
      density: dense
      avg_lines: 8-15
      player_options: "最终选择，决定结局"
      
    内容:
      - 审判（如果有杀人）
      - 真相揭露
      - 结局分支
      - 角色命运收束

# ═══════════════════════════════════════════
# 张力曲线模板
# ═══════════════════════════════════════════

tension_templates:
  # 单日张力曲线
  peaceful_day:
    description: "平静的一天"
    curve: [2, 3, 3, 2, 2, 1]  # dawn→night
    
  building_day:
    description: "逐渐紧张"
    curve: [2, 3, 4, 5, 6, 4]
    
  climax_day:
    description: "高潮日"
    curve: [4, 5, 7, 8, 9, 6]
    
  aftermath_day:
    description: "事件之后"
    curve: [6, 5, 4, 4, 3, 3]
```

---

### 2.4 event_tree/structure.yaml（7天结构）

```yaml
# worlds/witch_trial/event_tree/structure.yaml

# ═══════════════════════════════════════════
# 7天故事结构
# ═══════════════════════════════════════════

days:
  day_1:
    arc: 起
    theme: "陌生的监牢"
    tension_template: peaceful_day
    
    fixed_events:
      - id: awakening
        period: dawn
        type: auto
        
      - id: morning_assembly
        period: morning
        type: chain  # 接 awakening
        
      - id: rules_announcement
        type: chain
        
      - id: first_free_time
        type: chain
        triggers: [npc_scatter]
        
    possible_scenes:
      count: 3-4
      types: [observation, daily, simple_interaction]
      focus: "认识环境和角色"
      
    day_end:
      - id: first_night
        period: night
        content: "各自回房，第一夜的不安"
        
  day_2:
    arc: 起
    theme: "逐渐熟悉"
    tension_template: peaceful_day
    
    possible_scenes:
      count: 4-5
      types: [observation, daily, interaction]
      focus: "建立日常，发现角色习惯"
      
    hints_allowed:
      - "某角色独处时表情不同"
      - "两人之间的微妙气氛"
      
  day_3:
    arc: 承
    theme: "日常的裂痕"
    tension_template: building_day
    
    possible_scenes:
      count: 4-5
      types: [daily, interaction, minor_conflict]
      
    events_unlocked:
      - small_conflict
      - secret_glimpse
      - relationship_shift
      
  day_4:
    arc: 承
    theme: "暗流涌动"
    tension_template: building_day
    
    possible_scenes:
      count: 4-6
      types: [interaction, tension, observation]
      
    murder_prep_check: true  # 检查是否有人接近魔女化
    
  day_5:
    arc: 转
    theme: "临界点"
    tension_template: climax_day
    
    possible_scenes:
      count: 5-6
      types: [tension, confrontation, revelation]
      
    events_unlocked:
      - witch_signs
      - breakdown
      - murder_attempt  # 如果条件满足
      
  day_6:
    arc: 转
    theme: "破局"
    tension_template: climax_day
    
    branch_point: true  # 根据之前选择分支
    
    paths:
      murder_occurred:
        content: "调查阶段"
        scenes: [investigation, interrogation, evidence]
        
      murder_prevented:
        content: "危机解除？"
        scenes: [aftermath, relief, hidden_danger]
        
      no_murder_risk:
        content: "平静继续"
        scenes: [daily, interaction, preparation]
        
  day_7:
    arc: 合
    theme: "审判与结局"
    tension_template: aftermath_day
    
    paths:
      trial_path:
        trigger: "murder_occurred"
        content: "魔女审判"
        leads_to: [bad_end, normal_end]
        
      peaceful_path:
        trigger: "no_murder"
        content: "最后的日常"
        leads_to: [good_end, true_end]
        
      hidden_path:
        trigger: "all_secrets_found"
        content: "真相揭露"
        leads_to: [true_end]
```

---

### 2.5 event_tree/scene_types.yaml（场景类型维度）

```yaml
# worlds/witch_trial/event_tree/scene_types.yaml

# ═══════════════════════════════════════════
# 场景维度定义（AI组合生成）
# ═══════════════════════════════════════════

# 不是穷举所有场景，而是定义维度让AI自由组合
# 理论组合：4×15×5×4×3 = 3600种

dimensions:
  # 参与人数
  participants:
    solo: "独处（玩家观察某人独自行动）"
    duo: "二人（两个角色互动）"
    small_group: "小群（3-4人）"
    crowd: "多人（5人以上）"
    
  # 活动类型
  activity:
    静止类:
      - idle: "发呆"
      - thinking: "沉思"
      - sleeping: "睡觉"
      - crying: "哭泣"
      - staring: "盯着某处看"
      
    日常类:
      - eating: "吃饭"
      - reading: "看书"
      - walking: "散步"
      - cleaning: "整理"
      - exercising: "活动身体"
      
    社交类:
      - chatting: "闲聊"
      - arguing: "争论"
      - comforting: "安慰"
      - confiding: "倾诉"
      - teasing: "打趣"
      
    特殊类:
      - whispering: "密谈"
      - watching: "监视"
      - hiding: "躲藏"
      - searching: "寻找"
      - practicing_magic: "练习魔法"
      
  # 氛围
  mood:
    peaceful: "平静"
    relaxed: "轻松"
    tense: "紧张"
    sad: "悲伤"
    eerie: "诡异"
    
  # 玩家角色
  player_role:
    spectator: "旁观（只看不参与）"
    passerby: "偶遇（路过撞见）"
    participant: "可参与（有选项）"
    involved: "被卷入（无法回避）"
    
  # 信息价值
  info_value:
    none: "纯日常，无信息"
    hint: "暗示某事"
    clue: "明确线索"

# ═══════════════════════════════════════════
# 场景生成规则
# ═══════════════════════════════════════════

generation_rules:
  # 根据arc阶段限制可用组合
  arc_constraints:
    起:
      allowed_moods: [peaceful, relaxed]
      allowed_player_roles: [spectator, passerby]
      info_value_weights: {none: 0.7, hint: 0.3, clue: 0}
      
    承:
      allowed_moods: [peaceful, relaxed, tense]
      allowed_player_roles: [spectator, passerby, participant]
      info_value_weights: {none: 0.5, hint: 0.4, clue: 0.1}
      
    转:
      allowed_moods: [tense, sad, eerie, peaceful]
      allowed_player_roles: [participant, involved, spectator]
      info_value_weights: {none: 0.2, hint: 0.4, clue: 0.4}
      
    合:
      allowed_moods: [tense, sad, eerie]
      allowed_player_roles: [involved, participant]
      info_value_weights: {none: 0.1, hint: 0.3, clue: 0.6}
      
  # 避免重复
  anti_repetition:
    same_location_cooldown: 2      # 同一地点间隔2场景
    same_character_focus_cooldown: 3  # 同一角色为焦点间隔3场景
    same_activity_cooldown: 2      # 同一活动类型间隔2场景
```

---

### 2.6 event_tree/triggers.yaml（触发条件库）

```yaml
# worlds/witch_trial/event_tree/triggers.yaml

# ═══════════════════════════════════════════
# 条件变量定义
# ═══════════════════════════════════════════

variables:
  # 时间相关
  day: "当前天数 (1-7)"
  period: "当前时段 (dawn/morning/noon/afternoon/evening/night)"
  event_count: "当天已发生事件数"
  
  # 角色状态（char_id.xxx）
  "{char}.stress": "压力值 (0-100)"
  "{char}.madness": "魔女化程度 (0-100)"
  "{char}.affection": "对玩家好感 (0-100)"
  "{char}.location": "当前位置"
  "{char}.is_alone": "是否独处"
  
  # 关系（rel.char1.char2.xxx）
  "rel.{a}.{b}.trust": "信任度 (-100 to 100)"
  "rel.{a}.{b}.conflict": "冲突计数"
  
  # 标记
  "flag.xxx": "布尔标记"
  "seen.xxx": "玩家是否见过某事件"
  
  # 统计
  "interactions.{char}": "与某角色互动次数"
  "scenes_today": "今日场景数"

# ═══════════════════════════════════════════
# 通用触发条件模板
# ═══════════════════════════════════════════

trigger_templates:
  # 角色崩溃
  character_breakdown:
    description: "角色情绪崩溃"
    conditions:
      - "{char}.stress >= 80"
      - "{char}.madness >= 50"
      - "trigger_event occurred"  # 某个触发事件发生
    probability: 0.7
    cooldown: "once_per_playthrough"
    
  # 秘密暴露
  secret_revealed:
    description: "角色秘密被揭穿"
    conditions:
      - "day >= 3"
      - "interactions.{char} >= 5"
      - "flag.{char}_secret_hint"
    probability: 0.5
    
  # 冲突升级
  conflict_escalation:
    description: "两角色冲突升级"
    conditions:
      - "rel.{a}.{b}.conflict >= 2"
      - "rel.{a}.{b}.trust <= -30"
      - "{a}.stress >= 60 OR {b}.stress >= 60"
    probability: 0.6
    
  # 魔女化临界
  witch_critical:
    description: "某角色接近魔女化"
    conditions:
      - "{char}.madness >= 80"
      - "day >= 5"
    probability: 1.0  # 必定触发警告
    
  # 杀意形成
  murder_intent:
    description: "杀意形成"
    conditions:
      - "{killer}.madness >= 80"
      - "rel.{killer}.{target}.trust <= -50"
      - "flag.{killer}_motive"
    probability: 0.8
    
  # 玩家介入窗口
  intervention_window:
    description: "玩家可以介入阻止"
    conditions:
      - "flag.murder_prep_active"
      - "player.location == {danger_location}"
      - "period in [evening, night]"
    probability: 1.0
```

---

### 2.7 event_tree/branches/character_arcs.yaml（角色线）

```yaml
# worlds/witch_trial/event_tree/branches/character_arcs.yaml

# ═══════════════════════════════════════════
# 角色弧线模板（不是写死剧本，是可能性）
# ═══════════════════════════════════════════

# 每个角色有潜在的「弧线」，AI根据条件选择是否触发

arcs:
  hannah_collapse:
    character: hannah
    description: "汉娜的身份崩溃线"
    
    prerequisites:
      - "interactions.hannah >= 3"  # 至少互动3次
      - "day >= 3"
      
    trigger_conditions:
      - "有人提到贵族/身份话题"
      - "汉娜被孤立超过1天"
      - "有人质疑她的行为"
      
    stages:
      - stage: hint
        day_range: [2, 3]
        description: "汉娜对某些话题反应过激"
        player_can_notice: true
        
      - stage: crack
        day_range: [3, 4]
        description: "伪装出现裂痕，私下哭泣"
        trigger: "hannah.stress >= 60"
        
      - stage: breakdown
        day_range: [4, 6]
        description: "崩溃，真相暴露"
        trigger: "hannah.stress >= 80 AND flag.hannah_confronted"
        
      - stage: aftermath
        description: "崩溃后的状态"
        branches:
          supported: "有人安慰 → 关系加深，压力下降"
          abandoned: "被孤立 → madness上升"
          
    outcomes:
      if_supported:
        - "hannah.affection += 30"
        - "flag.hannah_ally = true"
      if_abandoned:
        - "hannah.madness += 20"
        - "potential_victim = true"
        
  # ───────────────────────────────────────
  
  hiro_redemption:
    character: hiro
    description: "希罗的救赎线"
    
    prerequisites:
      - "interactions.hiro >= 4"
      - "flag.hiro_past_revealed"
      
    trigger_conditions:
      - "玩家选择相信希罗"
      - "希罗有机会证明自己"
      
    stages:
      - stage: distrust
        day_range: [1, 3]
        description: "对玩家冷淡，戒备"
        
      - stage: test
        day_range: [3, 5]
        description: "试探玩家是否值得信任"
        player_choice: true
        
      - stage: reveal
        day_range: [4, 6]
        description: "透露过去的事情"
        trigger: "hiro.trust >= 50"
        
      - stage: ally
        day_range: [5, 7]
        description: "成为可靠同伴"
        trigger: "flag.hiro_trusted"
        
    outcomes:
      if_allied:
        - "flag.hiro_ally = true"
        - "unlock.investigation_help"  # 调查阶段帮助
      if_rejected:
        - "hiro.affection -= 30"
        - "hiro 独自行动，可能错过线索"

# ═══════════════════════════════════════════
# 弧线冲突处理
# ═══════════════════════════════════════════

conflict_resolution:
  # 当多个弧线同时触发时
  priority_rules:
    - "murder_arc > character_arc"      # 杀人线优先
    - "player_involved > background"    # 玩家参与的优先
    - "earlier_stage > later_stage"     # 先进入的优先
    
  merge_rules:
    - "同一天最多2个角色进入breakdown阶段"
    - "如果有murder_arc，其他breakdown延后"
```

---

### 2.8 event_tree/branches/endings.yaml（结局分支）

```yaml
# worlds/witch_trial/event_tree/branches/endings.yaml

# ═══════════════════════════════════════════
# 结局条件与分支
# ═══════════════════════════════════════════

endings:
  bad_end_wrong_vote:
    type: bad_end
    name: "错误的审判"
    
    trigger:
      - "flag.murder_occurred"
      - "flag.trial_completed"
      - "trial_result == wrong_person"
      
    description: "投票处死了无辜者，真凶逍遥法外"
    
    aftermath:
      - "无辜者死亡"
      - "真凶可能继续杀人"
      - "周目结束"
      
  bad_end_player_witch:
    type: bad_end
    name: "玩家魔女化"
    
    trigger:
      - "player.madness >= 100"
      
    description: "玩家自己失控，成为魔女"
    
  # ───────────────────────────────────────
    
  normal_end:
    type: normal_end
    name: "正义的审判"
    
    trigger:
      - "flag.murder_occurred"
      - "flag.trial_completed"
      - "trial_result == correct_person"
      
    description: "找出真凶，但有人死亡"
    
    unlocks:
      - "角色档案完整版"
      - "第二周目可用"
      
  # ───────────────────────────────────────
    
  good_end:
    type: good_end
    name: "无人死亡"
    
    trigger:
      - "day == 7"
      - "NOT flag.murder_occurred"
      - "alive_count == 13"
      
    description: "成功阻止悲剧，全员存活"
    
    how_to_achieve:
      - "识别高危角色"
      - "在关键时刻介入"
      - "帮助角色释放压力"
      
    unlocks:
      - "隐藏剧情提示"
      - "角色好感度可视化"
      
  # ───────────────────────────────────────
    
  true_end:
    type: true_end
    name: "真相"
    
    trigger:
      - "good_end条件满足"
      - "flag.library_secret_found"
      - "flag.yuki_truth_known"
      - "avg(all_characters.affection) >= 70"
      
    description: "揭露监牢的真相，13人联合觉醒"
    
    how_to_achieve:
      - "需要多周目收集信息"
      - "发现图书馆隐藏房间"
      - "了解大魔女月代雪的计划"
      - "全员高好感"

# ═══════════════════════════════════════════
# 周目继承
# ═══════════════════════════════════════════

playthrough_inheritance:
  always_keep:
    - "已解锁的角色档案"
    - "已发现的秘密标记"
    - "已达成的结局记录"
    
  reset:
    - "所有角色状态"
    - "时间"
    - "事件进度"
    - "关系值"
    
  unlock_by_ending:
    normal_end:
      - "压力/madness可视化"
      - "部分角色隐藏信息"
      
    good_end:
      - "好感度可视化"
      - "选项影响提示"
      - "更多互动选项解锁"
      
    true_end:
      - "完整角色心声"
      - "隐藏场景"
      - "最终真相"
```

---

## 三、新增 API 模块

### 3.1 api/world_loader.py

```python
"""
世界观加载器 - 按需加载世界观数据
"""

class WorldLoader:
    def __init__(self, world_id: str = "witch_trial"):
        self.world_id = world_id
        self.world_path = PROJECT_ROOT / "worlds" / world_id
        self._cache = {}
        
    def load_manifest(self) -> Dict:
        """加载世界观元信息（始终加载）"""
        
    def load_core_rules(self) -> Dict:
        """加载核心规则"""
        
    def load_tone_for_arc(self, arc: str) -> Dict:
        """根据当前arc加载氛围指导"""
        
    def load_location(self, location_id: str) -> Dict:
        """按需加载地点详情"""
        
    def get_arc_for_day(self, day: int) -> str:
        """获取指定日期所属的arc（起/承/转/合）"""
        
    def get_scene_constraints(self, day: int) -> Dict:
        """获取当天的场景生成约束"""
```

### 3.2 api/event_tree_engine.py

```python
"""
事件树引擎 - 管理故事分支和条件触发
"""

class EventTreeEngine:
    def __init__(self, world_loader: WorldLoader):
        self.world = world_loader
        self.structure = self._load_structure()
        self.triggers = self._load_triggers()
        
    def get_day_plan(self, day: int) -> DayPlan:
        """获取指定日期的事件计划"""
        
    def check_triggers(self, context: GameContext) -> List[TriggerResult]:
        """检查所有触发条件，返回应触发的事件"""
        
    def evaluate_condition(self, condition: str, context: GameContext) -> bool:
        """评估条件表达式"""
        
    def get_available_scene_types(self, day: int, history: List) -> List[str]:
        """获取可用场景类型（排除最近用过的）"""
        
    def select_scene_parameters(self, day: int, context: GameContext) -> SceneParams:
        """AI辅助选择场景参数组合"""
        
    def check_character_arcs(self, context: GameContext) -> List[ArcUpdate]:
        """检查角色弧线进度"""
        
    def get_ending_path(self, context: GameContext) -> Optional[str]:
        """检查是否满足某个结局条件"""
```

---

## 四、修改现有文件（关键：让故事连贯）

> ⚠️ **核心问题**：光有 YAML 配置没用，必须修改代码让 DirectorPlanner **读取并遵守**这些约束。否则仍然是碎片化场景。

### 4.1 新增 world_state/scene_history.json

```json
{
  "scenes": [
    {
      "scene_id": "day1_scene3",
      "day": 1,
      "period": "morning",
      "location": "走廊",
      "scene_type": "observation",
      "participants": ["hannah"],
      "mood": "peaceful",
      "tension": 2,
      "summary": "汉娜独自站在窗边发呆",
      "info_value": "hint",
      "hint_content": "汉娜对「贵族」话题敏感"
    },
    {
      "scene_id": "day1_scene4",
      "day": 1,
      "period": "noon",
      "location": "食堂",
      "scene_type": "daily",
      "participants": ["all"],
      "mood": "relaxed",
      "tension": 3,
      "summary": "午餐时间，众人闲聊"
    }
  ],
  "location_last_used": {
    "走廊": "day1_scene3",
    "食堂": "day1_scene4"
  },
  "character_last_focus": {
    "hannah": "day1_scene3"
  },
  "activity_last_used": {
    "observation": "day1_scene3",
    "daily": "day1_scene4"
  }
}
```

### 4.2 修改 DirectorPlanner - 完整改造

```python
# api/director_planner.py 改造

class DirectorPlanner:
    def __init__(self, ...):
        self.world_loader = WorldLoader()
        self.event_engine = EventTreeEngine(self.world_loader)
        self.scene_history = self._load_scene_history()
        
    def _load_scene_history(self) -> Dict:
        """加载场景历史"""
        path = self.project_root / "world_state" / "scene_history.json"
        if path.exists():
            return load_json(path)
        return {"scenes": [], "location_last_used": {}, "character_last_focus": {}, "activity_last_used": {}}
        
    def _save_scene_history(self):
        """保存场景历史"""
        path = self.project_root / "world_state" / "scene_history.json"
        save_json(path, self.scene_history)
        
    def _get_recent_scenes_summary(self, count: int = 5) -> str:
        """获取最近N个场景的摘要（用于prompt）"""
        recent = self.scene_history["scenes"][-count:]
        if not recent:
            return "（这是第一个场景）"
        
        lines = []
        for s in recent:
            lines.append(f"- {s['location']}：{s['summary']}（张力{s['tension']}）")
        return "\n".join(lines)
        
    def _check_repetition(self, location: str, characters: List[str]) -> Dict:
        """检查是否有重复风险"""
        warnings = []
        
        # 检查地点冷却
        if location in self.scene_history["location_last_used"]:
            last = self.scene_history["location_last_used"][location]
            scenes_since = len(self.scene_history["scenes"]) - self._get_scene_index(last)
            if scenes_since < 2:
                warnings.append(f"地点「{location}」刚用过，建议换活动类型")
                
        # 检查角色焦点冷却
        for char in characters[:2]:  # 主要角色
            if char in self.scene_history["character_last_focus"]:
                last = self.scene_history["character_last_focus"][char]
                scenes_since = len(self.scene_history["scenes"]) - self._get_scene_index(last)
                if scenes_since < 3:
                    warnings.append(f"角色「{char}」最近是焦点，建议换其他角色")
                    
        return {"warnings": warnings, "should_vary": len(warnings) > 0}
        
    def _build_dynamic_constraints(self, day: int, context: Dict) -> str:
        """构建动态约束文本（注入prompt）"""
        
        # 获取arc信息
        arc = self.world_loader.get_arc_for_day(day)
        tone = self.world_loader.load_tone_for_arc(arc)
        
        constraints = f"""
【当前阶段】{arc}（Day {day}）
【今日主题】{tone.get('主基调', '')}
【氛围词】{', '.join(tone.get('氛围词', []))}

【张力范围】{tone['张力范围'][0]} - {tone['张力范围'][1]}（严格遵守，不得超出）
【对话密度】{tone.get('对话密度', 'normal')}
【静默比例】{int(tone.get('静默比例', 0.3) * 100)}%

【场景比例指导】
"""
        for scene_type, ratio in tone.get('场景比例', {}).items():
            constraints += f"  - {scene_type}: {ratio}\n"
            
        # 禁止内容
        if '禁止内容' in tone:
            constraints += f"\n【禁止内容】（本阶段绝对不能出现）\n"
            for item in tone['禁止内容']:
                constraints += f"  ❌ {item}\n"
                
        # 允许内容
        if '允许内容' in tone:
            constraints += f"\n【允许内容】（本阶段可以出现）\n"
            for item in tone['允许内容']:
                constraints += f"  ✓ {item}\n"
                
        # 最近场景（避免重复）
        constraints += f"\n【最近场景】（避免重复）\n{self._get_recent_scenes_summary()}\n"
        
        return constraints
        
    def _build_story_context(self, day: int) -> str:
        """构建故事上下文（让AI知道大局）"""
        
        structure = self.event_engine.get_day_plan(day)
        
        context = f"""
【故事进度】
- 当前：第 {day} 天 / 共 7 天
- 阶段：{structure.arc}（{structure.theme}）
- 今日目标：{structure.focus}

【已发生的重要事件】
"""
        # 提取重要事件
        important = [s for s in self.scene_history["scenes"] if s.get("info_value") in ["hint", "clue"]]
        for s in important[-5:]:
            context += f"- Day{s['day']}：{s['summary']}\n"
            
        # 角色状态摘要
        context += "\n【当前关注角色状态】\n"
        # TODO: 提取高压力/高madness角色
        
        return context
        
    def plan_scene(self, location: str, scene_type: str = "free", ...):
        """生成场景规划（核心方法）"""
        
        day = self._get_current_day()
        context = self.load_game_context()
        
        # 1. 构建动态约束
        constraints = self._build_dynamic_constraints(day, context)
        
        # 2. 构建故事上下文
        story_context = self._build_story_context(day)
        
        # 3. 检查重复风险
        characters = self.get_characters_at_location(location)
        repetition_check = self._check_repetition(location, characters)
        
        # 4. 检查是否有触发事件
        triggered_events = self.event_engine.check_triggers(context)
        
        # 5. 构建完整prompt
        prompt = self._build_prompt(
            location=location,
            characters=characters,
            constraints=constraints,           # 新增
            story_context=story_context,       # 新增
            repetition_warnings=repetition_check["warnings"],  # 新增
            triggered_events=triggered_events  # 新增
        )
        
        # 6. 调用API
        result = self._call_api(prompt)
        scene_plan = self._parse_scene_plan(result)
        
        # 7. 验证输出是否符合约束
        scene_plan = self._validate_and_fix(scene_plan, day)
        
        # 8. 记录到历史
        self._record_scene(scene_plan)
        
        return scene_plan
        
    def _validate_and_fix(self, scene_plan: ScenePlan, day: int) -> ScenePlan:
        """验证并修正场景是否符合约束"""
        
        arc = self.world_loader.get_arc_for_day(day)
        tone = self.world_loader.load_tone_for_arc(arc)
        
        # 检查张力范围
        min_t, max_t = tone['张力范围']
        for beat in scene_plan.beats:
            if beat.tension_level > max_t:
                print(f"⚠️ 张力超出范围，从 {beat.tension_level} 修正为 {max_t}")
                beat.tension_level = max_t
            if beat.tension_level < min_t:
                beat.tension_level = min_t
                
        # 检查禁止内容（关键词过滤）
        forbidden = tone.get('禁止内容', [])
        for beat in scene_plan.beats:
            for keyword in forbidden:
                if keyword in beat.description:
                    print(f"⚠️ 检测到禁止内容「{keyword}」，需要重新生成")
                    # TODO: 重新生成或修改
                    
        return scene_plan
        
    def _record_scene(self, scene_plan: ScenePlan):
        """记录场景到历史"""
        
        record = {
            "scene_id": scene_plan.scene_id,
            "day": self._get_current_day(),
            "period": self._get_current_period(),
            "location": scene_plan.location,
            "scene_type": self._infer_scene_type(scene_plan),
            "participants": [c for beat in scene_plan.beats for c in beat.characters],
            "mood": self._infer_mood(scene_plan),
            "tension": max(beat.tension_level for beat in scene_plan.beats),
            "summary": scene_plan.overall_arc[:50],  # 截取摘要
            "info_value": "none"  # TODO: AI判断
        }
        
        self.scene_history["scenes"].append(record)
        self.scene_history["location_last_used"][scene_plan.location] = scene_plan.scene_id
        
        # 记录焦点角色
        main_chars = self._get_main_characters(scene_plan)
        for char in main_chars:
            self.scene_history["character_last_focus"][char] = scene_plan.scene_id
            
        self._save_scene_history()
```

### 4.3 修改 prompts/director_planner_prompt.txt

```
# 原prompt开头添加：

{story_context}

{constraints}

【重复警告】
{repetition_warnings}

【本场景要求】
- 地点：{location}
- 在场角色：{characters}
- 触发事件：{triggered_events}

---

# 原有prompt内容...

---

【输出要求补充】
- tension_level 必须在 {min_tension} - {max_tension} 范围内
- 如果是「起」阶段，禁止出现崩溃、魔女化、高张力对峙
- 场景类型建议：{suggested_scene_type}
- 如果最近场景有同地点/同角色，必须有明显变化
```

### 4.4 修改 game_loop_v3.py

```python
# game_loop_v3.py 改造

class GameLoopV3:
    def __init__(self):
        self.world_loader = WorldLoader()
        self.event_engine = EventTreeEngine(self.world_loader)
        self.planner = DirectorPlanner(...)  # planner 现在会用 world_loader
        self.actor = CharacterActor(...)
        
    def run(self):
        self.reset_game_state()
        
        # 显示当前阶段信息
        day = self._get_current_day()
        arc = self.world_loader.get_arc_for_day(day)
        print(f"\n{'='*50}")
        print(f"第 {day} 天 - {arc}阶段")
        print(f"{'='*50}\n")
        
        while True:
            result = self.game_turn()
            if result == "game_over":
                break
                
    def game_turn(self):
        day = self._get_current_day()
        context = self._build_game_context()
        
        # 1. 检查结局条件
        ending = self.event_engine.get_ending_path(context)
        if ending:
            return self._run_ending(ending)
            
        # 2. 检查角色弧线更新
        arc_updates = self.event_engine.check_character_arcs(context)
        if arc_updates:
            self._apply_arc_updates(arc_updates)
            self._display_arc_hints(arc_updates)  # 给玩家提示
            
        # 3. 检查是否有触发事件
        triggered = self.event_engine.check_triggers(context)
        if triggered:
            for event in triggered:
                self._run_triggered_event(event)
                
        # 4. 正常场景流程
        # ... 现有逻辑
        
    def _display_arc_hints(self, arc_updates: List):
        """显示角色弧线提示（微妙暗示，不直接说）"""
        for update in arc_updates:
            if update.stage == "hint":
                # 细微描述，不直接说
                print(f"\n（你注意到{update.character}似乎有些不同...）\n")
                
    def _display_day_transition(self, new_day: int):
        """显示天数切换（带阶段信息）"""
        arc = self.world_loader.get_arc_for_day(new_day)
        theme = self.event_engine.get_day_plan(new_day).theme
        
        print(f"\n{'='*50}")
        print(f"第 {new_day} 天")
        print(f"「{theme}」")
        if arc == "转":
            print(f"（气氛似乎有些不一样了...）")
        print(f"{'='*50}\n")
```

### 4.5 新增 api/scene_validator.py

```python
"""
场景验证器 - 确保输出符合约束
"""

class SceneValidator:
    def __init__(self, world_loader: WorldLoader):
        self.world = world_loader
        
    def validate(self, scene_plan: ScenePlan, day: int) -> ValidationResult:
        """验证场景是否符合当天约束"""
        
        errors = []
        warnings = []
        
        arc = self.world.get_arc_for_day(day)
        tone = self.world.load_tone_for_arc(arc)
        
        # 1. 张力检查
        min_t, max_t = tone['张力范围']
        for beat in scene_plan.beats:
            if beat.tension_level > max_t:
                errors.append(f"Beat {beat.beat_id} 张力 {beat.tension_level} 超出上限 {max_t}")
            if beat.tension_level < min_t:
                warnings.append(f"Beat {beat.beat_id} 张力 {beat.tension_level} 低于下限 {min_t}")
                
        # 2. 禁止内容检查
        forbidden_keywords = tone.get('禁止内容', [])
        scene_text = self._extract_all_text(scene_plan)
        for keyword in forbidden_keywords:
            if keyword in scene_text:
                errors.append(f"检测到禁止内容：「{keyword}」")
                
        # 3. 角色行为检查（起阶段不能崩溃）
        if arc == "起":
            for beat in scene_plan.beats:
                if any(e in ["崩溃", "失控", "魔女化"] for e in beat.emotion_targets.values()):
                    errors.append(f"起阶段不允许角色崩溃/失控")
                    
        # 4. 对话密度检查
        expected_density = tone.get('对话密度', 'normal')
        actual_lines = sum(beat.dialogue_count for beat in scene_plan.beats)
        if expected_density == "sparse" and actual_lines > 8:
            warnings.append(f"对话过多（{actual_lines}行），建议减少")
            
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
        
    def auto_fix(self, scene_plan: ScenePlan, day: int) -> ScenePlan:
        """自动修正不符合约束的内容"""
        
        arc = self.world.get_arc_for_day(day)
        tone = self.world.load_tone_for_arc(arc)
        min_t, max_t = tone['张力范围']
        
        # 修正张力
        for beat in scene_plan.beats:
            beat.tension_level = max(min_t, min(max_t, beat.tension_level))
            
        # 修正情绪（起阶段降级）
        if arc == "起":
            emotion_downgrade = {
                "崩溃": "不安",
                "失控": "紧张",
                "绝望": "担忧",
                "暴怒": "不满"
            }
            for beat in scene_plan.beats:
                for char, emotion in beat.emotion_targets.items():
                    if emotion in emotion_downgrade:
                        beat.emotion_targets[char] = emotion_downgrade[emotion]
                        
        return scene_plan
```

### 4.6 修改 CharacterActor - 故事性输出

```python
# api/character_actor.py 关键修改

class CharacterActor:
    """角色演出层 - 生成有故事性的场景内容"""
    
    def generate_scene_dialogue(self, scene_plan: ScenePlan) -> Tuple[List[DialogueOutput], ...]:
        """生成整场对话（重点：故事性）"""
        
        # 构建强调故事性的prompt
        prompt = self._build_story_prompt(scene_plan)
        
        # API调用
        response = self._call_api(prompt)
        
        # 解析并验证
        outputs = self._parse_story_response(response)
        
        # 验证长度
        outputs = self._validate_story_length(outputs, scene_plan)
        
        return outputs
        
    def _build_story_prompt(self, scene_plan: ScenePlan) -> str:
        """构建强调故事性的prompt"""
        
        prompt = f"""
# 场景演出任务

你要为这个场景生成完整的故事内容。不是几句对话，而是一个有画面感的小故事。

## 场景信息
- 地点：{scene_plan.location}
- 参与角色：{', '.join(self._get_all_characters(scene_plan))}
- 整体氛围：{scene_plan.overall_arc}

## Beat 列表
{self._format_beats(scene_plan.beats)}

## ★★★ 输出要求 ★★★

### 1. 结构要求
每个 Beat 必须包含：
- 【环境/动作描写】至少1-2句，建立画面
- 【对话】如果有，穿插动作神态
- 【内心/氛围】角色的微妙状态

### 2. 叙述要求
- 用第二人称「你」描述玩家视角
- 环境描写要有感官细节（光线、声音、温度、气味）
- 角色动作要具体（不是「她动了动」而是「她的手指无意识地绕着发梢」）

### 3. 对话要求
- 每2-3句对话后，插入一段动作/神态描写
- 角色说话时描述「怎么说的」（语气、表情、小动作）
- 沉默用「...」+动作描写，不要空白

### 4. 长度要求（重要！）
- opening_beat: 50-80字
- development_beat: 100-150字
- climax_beat: 80-120字
- resolution_beat: 40-60字
- 整场总计：400字以上

### 5. 输出格式
```json
{{
  "beats": [
    {{
      "beat_id": "opening",
      "narration": "环境和动作描写...",
      "dialogue": [
        {{"speaker": "narrator", "text": "叙述文字"}},
        {{"speaker": "hannah", "text": "对话内容", "action": "说话时的动作"}}
      ]
    }}
  ]
}}
```

## 角色资料
{self._format_character_data(scene_plan)}

现在开始生成这个场景的完整内容：
"""
        return prompt

    def _validate_story_length(self, outputs: List[DialogueOutput], scene_plan: ScenePlan) -> List[DialogueOutput]:
        """验证故事长度，太短则警告或补充"""
        
        total_length = sum(
            len(line.text_cn) 
            for output in outputs 
            for line in output.dialogue
        )
        
        scene_type = self._infer_scene_type(scene_plan)
        min_lengths = {
            "observation": 150,
            "daily": 350,
            "interaction": 500,
            "key_moment": 800
        }
        
        min_len = min_lengths.get(scene_type, 350)
        
        if total_length < min_len:
            print(f"⚠️ 场景内容过短（{total_length}字 < {min_len}字），需要补充")
            # TODO: 可以调用API补充，或返回警告
            
        return outputs
```

### 4.7 修改 prompts/character_actor_prompt.txt

```
# 角色演出层 Prompt

你是一个专业的视觉小说编剧。你的任务是把场景大纲变成有画面感的故事内容。

## 核心原则

1. **这是故事，不是对话记录**
   - 每个场景都要有开头、发展、结尾
   - 读者要能「看到」画面，不只是「听到」对话
   
2. **用细节建立真实感**
   - 光线怎么照进来
   - 角色的小动作（玩头发、看窗外、握紧拳头）
   - 声音（脚步声、翻书声、沉默）
   - 气味（食物、花香、灰尘）

3. **对话要「演」出来**
   ❌ 错误：
   汉娜：「你好。」
   艾玛：「你好。」
   
   ✅ 正确：
   汉娜端着空茶杯走过来，在你对面坐下。她的动作优雅，像是练习过无数次。
   「今天的阳光真好呢。」
   你注意到她的眼睛没有看你，而是望着窗外某个地方。

4. **沉默比说话更有力**
   - 用「...」表示停顿
   - 用动作描写填充沉默
   - 「她没有回答。只是转过身，肩膀微微颤抖。」

## 输出长度要求

| Beat类型 | 最少字数 | 对话轮数 |
|----------|:--------:|:--------:|
| opening | 50字 | 0-1轮 |
| development | 100字 | 2-4轮 |
| climax | 80字 | 2-3轮 |
| choice | 60字 | 选项描述 |
| resolution | 40字 | 0-2轮 |

**整场最少400字，普通场景建议500-800字**

## 格式要求

{format_instructions}

## 当前任务

{scene_plan}

{character_data}

开始生成：
```

---

## 五、验收标准

### 5.1 世界观库

- [ ] `worlds/witch_trial/manifest.yaml` 存在且可解析
- [ ] `worlds/witch_trial/core/rules.yaml` 包含魔女因子系统
- [ ] `worlds/witch_trial/core/tone.yaml` 包含起承转合指导
- [ ] `WorldLoader` 能按需加载数据
- [ ] `WorldLoader.get_arc_for_day()` 正确返回起/承/转/合

### 5.2 事件树

- [ ] `event_tree/structure.yaml` 定义7天结构
- [ ] `event_tree/scene_types.yaml` 定义场景维度
- [ ] `event_tree/triggers.yaml` 定义触发条件
- [ ] `EventTreeEngine` 能评估条件表达式
- [ ] 能根据历史避免场景重复
- [ ] 能检查角色弧线进度

### 5.3 场景历史与防重复

- [ ] `world_state/scene_history.json` 正确记录每个场景
- [ ] 同一地点间隔至少2个场景才能再次出现
- [ ] 同一角色为焦点间隔至少3个场景
- [ ] DirectorPlanner 在 prompt 中包含最近场景摘要

### 5.4 约束注入与验证

- [ ] DirectorPlanner prompt 动态包含当前arc约束
- [ ] prompt 包含张力范围限制
- [ ] prompt 包含禁止内容列表
- [ ] SceneValidator 能检测违规内容
- [ ] 违规张力被自动修正到范围内

### 5.5 ★ 故事性验收（最重要）

| 检查项 | 要求 | 验证方法 |
|--------|------|----------|
| 场景长度 | 普通场景 ≥400字 | 统计输出字数 |
| 结构完整 | 有开场/发展/收尾 | 检查 beat 类型 |
| 画面感 | 有环境描写 | 搜索光线/声音/动作关键词 |
| 对话比例 | 叙述≥30% | 统计 narrator vs 角色对话 |
| 动作穿插 | 每3句对话有1句动作 | 检查 action 字段 |

**具体测试用例：**

```python
def test_scene_storytelling():
    """测试场景故事性"""
    
    # 生成一个普通场景
    scene = planner.plan_scene("走廊", scene_type="daily")
    outputs = actor.generate_scene_dialogue(scene)
    
    # 1. 长度检查
    total_chars = sum(len(line.text_cn) for o in outputs for line in o.dialogue)
    assert total_chars >= 400, f"场景太短：{total_chars}字"
    
    # 2. 结构检查
    beat_types = [o.beat_id for o in outputs]
    assert "opening" in beat_types, "缺少开场"
    assert any("development" in b or "climax" in b for b in beat_types), "缺少发展"
    
    # 3. 叙述比例检查
    narrator_lines = sum(1 for o in outputs for line in o.dialogue if line.speaker == "narrator")
    total_lines = sum(len(o.dialogue) for o in outputs)
    narrator_ratio = narrator_lines / total_lines
    assert narrator_ratio >= 0.25, f"叙述太少：{narrator_ratio:.0%}"
    
    # 4. 画面感检查
    all_text = " ".join(line.text_cn for o in outputs for line in o.dialogue)
    scene_words = ["阳光", "灰尘", "脚步", "沉默", "窗", "声音", "目光", "肩膀"]
    found = [w for w in scene_words if w in all_text]
    assert len(found) >= 2, f"缺乏画面感词汇，仅找到：{found}"
    
    print("✅ 场景故事性验收通过")
```

### 5.6 arc阶段测试

| 测试项 | Day 1-2 (起) | Day 3-4 (承) | Day 5-6 (转) | Day 7 (合) |
|--------|:------------:|:------------:|:------------:|:----------:|
| 张力范围 | 1-4 | 2-6 | 4-9 | 3-10 |
| 崩溃/魔女化 | ❌禁止 | ⚠️暗示可 | ✅允许 | ✅允许 |
| 静默场景比例 | ~50% | ~35% | ~20% | ~10% |
| 玩家选项 | 少 | 中 | 多 | 关键 |
| 场景最小长度 | 300字 | 400字 | 500字 | 600字 |

- [ ] Day 1 连续5个场景，无一出现崩溃/高张力
- [ ] Day 1 至少2个场景是纯观察（无对话选项）
- [ ] Day 1 每个场景都有环境描写开场
- [ ] 同一地点两次出现时，活动类型不同
- [ ] Day 5 能触发角色弧线的 "crack" 阶段
- [ ] 结局条件正确判定

### 5.7 输出示例对比

**❌ 不合格输出：**
```
汉娜站在窗边。
汉娜：「你来了。」
艾玛：「嗯。」
汉娜：「今天天气不错。」
【选项ABC】
（总计30字，无画面，无故事）
```

**✅ 合格输出：**
```
午后的走廊很安静。阳光从高窗洒下，在地板上画出长长的光带。

走廊尽头，汉娜背对着你站在窗边。她的肩膀微微绷紧，像是在看着什么。或者，在想着什么。

你的脚步声在空旷的走廊里回响。她似乎听到了，肩膀微微一颤，但没有回头。

「...今天的云很低呢。」

她的声音很轻，像是在自言自语。你走近一些，看到她的手指无意识地在窗框上划着什么。

「你也觉得这里的天空...有些不一样吗？」

她终于转过身。阳光照在她的侧脸上，让她的表情有些看不清楚。但你注意到，她的眼角有一点红。

【A】「你还好吗？」
【B】「是有些不一样。」
【C】「...」（默默站在她身边）

（总计280字，有画面，有氛围，有悬念）
```

---

## 六、实施顺序

### Phase 1：基础设施（先让系统能读配置）

1. **创建目录结构**
   ```bash
   mkdir -p worlds/witch_trial/core
   mkdir -p worlds/witch_trial/locations
   mkdir -p worlds/witch_trial/event_tree/branches
   ```

2. **编写核心 YAML 文件**
   - `manifest.yaml` - 直接复制模板
   - `core/rules.yaml` - 直接复制模板
   - `core/tone.yaml` - 直接复制模板

3. **实现 WorldLoader** (`api/world_loader.py`)
   - `load_manifest()`
   - `load_tone_for_arc()`
   - `get_arc_for_day()`
   - 先不实现复杂方法，确保基础能跑

4. **测试 WorldLoader**
   ```python
   loader = WorldLoader()
   print(loader.get_arc_for_day(1))  # 应输出 "起"
   print(loader.get_arc_for_day(5))  # 应输出 "转"
   ```

### Phase 2：场景历史（防重复）

5. **创建 scene_history.json**
   - 初始为空 `{"scenes": [], ...}`

6. **修改 DirectorPlanner**
   - 添加 `_load_scene_history()`
   - 添加 `_save_scene_history()`
   - 添加 `_get_recent_scenes_summary()`
   - 添加 `_record_scene()`

7. **测试场景记录**
   - 运行一个场景，检查 history 是否更新

### Phase 3：约束注入（关键）

8. **修改 DirectorPlanner.plan_scene()**
   - 添加 `_build_dynamic_constraints()`
   - 添加 `_build_story_context()`
   - 修改 `_build_prompt()` 接受新参数

9. **修改 prompt 模板**
   - 在 `prompts/director_planner_prompt.txt` 添加占位符
   - `{constraints}`, `{story_context}`, `{repetition_warnings}`

10. **实现 SceneValidator**
    - `validate()` - 检查
    - `auto_fix()` - 自动修正

11. **测试约束生效**
    - Day 1 场景，检查张力是否 ≤4
    - 检查 prompt 是否包含约束文本

### Phase 4：事件树（进阶）

12. **编写事件树 YAML**
    - `event_tree/structure.yaml`
    - `event_tree/scene_types.yaml`
    - `event_tree/triggers.yaml`

13. **实现 EventTreeEngine**
    - `get_day_plan()`
    - `check_triggers()`
    - `evaluate_condition()`

14. **编写角色弧线**
    - `event_tree/branches/character_arcs.yaml`
    - `check_character_arcs()`

15. **编写结局分支**
    - `event_tree/branches/endings.yaml`
    - `get_ending_path()`

### Phase 5：集成与测试

16. **修改 game_loop_v3.py**
    - 集成 WorldLoader
    - 集成 EventTreeEngine
    - 添加天数切换显示

17. **完整流程测试**
    - 跑完 Day 1-2，验证「起」阶段约束
    - 跳到 Day 5，验证「转」阶段允许高张力

---

## 七、快速启动（最小可行版）

如果想先快速看到效果，可以只做 Phase 1-3：

```
最小实现：
✅ manifest.yaml + tone.yaml（约束来源）
✅ WorldLoader.get_arc_for_day()（知道今天是什么阶段）
✅ DirectorPlanner._build_dynamic_constraints()（注入prompt）
✅ scene_history.json（防重复）

暂时跳过：
⏸️ 完整的 EventTreeEngine
⏸️ 角色弧线检查
⏸️ 结局判定
```

这样改动量小，但能立即解决「每个场景都高张力」「内容重复」的问题。

---

*任务版本：v9.2*
*创建日期：2024-12-24*
*更新：*
- *v9.1：补充 DirectorPlanner 完整改造、场景历史、验证器*
- *v9.2：补充「场景即故事」核心原则、长度标准、CharacterActor故事性生成*
