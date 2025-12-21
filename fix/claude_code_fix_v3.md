# Claude Code 任务：修复游戏流程问题 v3

## 问题描述

根据最新测试日志，发现以下问题：

### 问题 1：时段跳跃
- `day1_awakening` (dawn) 触发后，直接跳到 `noon`
- 跳过了 `morning` 时段

### 问题 2：事件链断裂
| 应触发事件 | 触发条件 | 实际状态 |
|-----------|---------|:--------:|
| day1_awakening | dawn | ✅ |
| day1_morning_assembly | morning | ❌ 跳过 |
| day1_rules | after day1_morning_assembly | ❌ 跳过 |
| day1_hiro | after day1_rules | ❌ 跳过 |
| day1_intro | after_event | ❌ 跳过 |
| day1_lunch | event_count >= 3 | ✅ 但在 evening |
| day1_dinner | event_count >= 6 | ❌ 未触发 |
| day1_night | night | ❌ 未触发 |

### 问题 3：角色没分散
- 所有13人始终在"牢房区"
- 玩家去其他地点时显示"空旷的场所"

### 问题 4：时间推进问题
- `advance_time()` 在 dawn 后直接跳到 noon，跳过 morning

---

## 任务 1：修复 `game_loop_v3.py` 的 `advance_time()` 方法

确保时段按正确顺序推进：

```python
def advance_time(self):
    """推进时间到下一个时段"""
    current_day_data = load_json(self.project_root / "world_state" / "current_day.json")
    
    current_period = current_day_data.get("period", "dawn")
    
    # 时段顺序：dawn -> morning -> noon -> afternoon -> evening -> night -> (下一天 dawn)
    period_order = ["dawn", "morning", "noon", "afternoon", "evening", "night"]
    
    try:
        current_index = period_order.index(current_period)
        next_index = current_index + 1
        
        if next_index >= len(period_order):
            # 进入下一天
            current_day_data["day"] = current_day_data.get("day", 1) + 1
            current_day_data["period"] = "dawn"
            current_day_data["daily_event_count"] = 0
            print(f"\n[新的一天] 第{current_day_data['day']}天开始了...")
        else:
            current_day_data["period"] = period_order[next_index]
            print(f"\n[时间流逝] -> {self._period_to_chinese(current_day_data['period'])}")
    except ValueError:
        # 如果当前时段不在列表中，重置为 morning
        current_day_data["period"] = "morning"
        print(f"\n[时间流逝] -> 上午")
    
    save_json(self.project_root / "world_state" / "current_day.json", current_day_data)

def _period_to_chinese(self, period: str) -> str:
    """将时段转换为中文"""
    period_names = {
        "dawn": "黎明",
        "morning": "上午",
        "noon": "正午",
        "afternoon": "下午",
        "evening": "傍晚",
        "night": "夜晚"
    }
    return period_names.get(period, period)
```

---

## 任务 2：修复 `events/fixed_events.yaml` 中的事件定义

确保 `day1_awakening` 正确设置 `next_event`：

```yaml
day1_awakening:
  id: "day1_awakening"
  name: "第一天 - 觉醒"
  trigger:
    type: auto
    day: 1
    period: "dawn"
  priority: 100
  scene:
    location: "牢房区"
    description: "你在陌生的牢房中醒来..."
  script:
    - speaker: narrator
      text_cn: "你睁开眼睛，发现自己躺在一张陌生的床上。"
      text_jp: "目を開けると、見知らぬベッドの上にいた。"
    - speaker: narrator
      text_cn: "头痛欲裂，记忆模糊。这里是...监狱？"
      text_jp: "頭が割れるように痛い。記憶がぼんやりする。ここは...監獄？"
  outcomes:
    all:
      stress: 10
      madness: 5
  flags_set:
    - "day1_started"
    - "awakening_complete"
  next_period: "morning"
  next_event: "day1_morning_assembly"

day1_morning_assembly:
  id: "day1_morning_assembly"
  name: "第一天 - 集合"
  trigger:
    type: auto
    day: 1
    period: "morning"
  priority: 100
  scene:
    location: "食堂"
    description: "典狱长召集所有人集合..."
  script:
    - speaker: warden
      text_cn: "早安，各位魔女候补。"
      text_jp: "おはよう、魔女候補たち。"
    - speaker: warden
      text_cn: "欢迎来到魔女监狱。从现在开始，你们将以囚犯的身份在这里生活。"
      text_jp: "魔女監獄へようこそ。これから君たちは囚人としてここで暮らすことになる。"
    - speaker: narrator
      text_cn: "少女们被带到食堂集合。一只奇怪的猫头鹰站在讲台上。"
      text_jp: "少女たちは食堂に集められた。奇妙なフクロウが演壇に立っている。"
  outcomes:
    all:
      stress: 15
  flags_set:
    - "assembly_complete"
  next_event: "day1_rules"

day1_rules:
  id: "day1_rules"
  name: "第一天 - 规则宣布"
  trigger:
    type: after_event
    after: "day1_morning_assembly"
  priority: 95
  script:
    - speaker: warden
      text_cn: "现在宣布魔女监狱的规则。"
      text_jp: "これから魔女監獄のルールを発表する。"
    - speaker: warden
      text_cn: "第一，你们的身体里都携带着【魔女因子】。"
      text_jp: "第一、君たちの体には【魔女因子】が宿っている。"
    - speaker: warden
      text_cn: "第二，魔女因子会随着压力增长。当它完全觉醒，你们就会变成【魔女】。"
      text_jp: "第二、魔女因子はストレスとともに成長する。完全に覚醒すると、君たちは【魔女】になる。"
    - speaker: warden
      text_cn: "第三，魔女会产生无法抑制的杀人冲动。"
      text_jp: "第三、魔女は抑えられない殺人衝動を持つようになる。"
    - speaker: warden
      text_cn: "第四，如果发生杀人事件，将举行【魔女审判】，投票决定处刑对象。"
      text_jp: "第四、殺人事件が起きた場合、【魔女裁判】を開き、投票で処刑対象を決める。"
  outcomes:
    all:
      stress: 20
      madness: 5
  flags_set:
    - "rules_announced"
  next_event: "day1_intro"

day1_intro:
  id: "day1_intro"
  name: "第一天 - 自我介绍"
  trigger:
    type: after_event
    after: "day1_rules"
  priority: 90
  script:
    - speaker: warden
      text_cn: "接下来，请各位自我介绍。"
      text_jp: "では、自己紹介をしてもらおう。"
    - speaker: narrator
      text_cn: "少女们依次站起来，紧张地介绍自己..."
      text_jp: "少女たちは順番に立ち上がり、緊張しながら自己紹介をする..."
  outcomes:
    all:
      stress: 5
  flags_set:
    - "intro_complete"
  trigger_npc_scatter: true

day1_lunch:
  id: "day1_lunch"
  name: "第一天午餐"
  trigger:
    type: event_count
    count: 3
    day: 1
  priority: 90
  script:
    - speaker: narrator
      text_cn: "午餐时间到了，所有人聚集在食堂..."
      text_jp: "昼食の時間だ。全員が食堂に集まる..."
    - speaker: narrator
      text_cn: "简陋的饭菜被端上桌，气氛依然沉重。"
      text_jp: "粗末な食事がテーブルに並ぶ。雰囲気はまだ重い。"
  outcomes:
    all:
      stress: -5

day1_dinner:
  id: "day1_dinner"
  name: "第一天晚餐"
  trigger:
    type: event_count
    count: 6
    day: 1
  priority: 90
  script:
    - speaker: narrator
      text_cn: "晚餐时间。今天的第一天即将结束..."
      text_jp: "夕食の時間。今日という一日がもうすぐ終わる..."
    - speaker: narrator
      text_cn: "少女们的脸上写满疲惫与不安。"
      text_jp: "少女たちの顔には疲れと不安が浮かんでいる。"
  outcomes:
    all:
      stress: 5
      madness: 3

day1_night:
  id: "day1_night"
  name: "第一天就寝"
  trigger:
    type: auto
    day: 1
    period: "night"
  priority: 100
  script:
    - speaker: narrator
      text_cn: "熄灯时间到了。铃声响起，催促着所有人回到牢房。"
      text_jp: "消灯時間だ。鐘が鳴り、全員が牢房に戻るよう促される。"
    - speaker: narrator
      text_cn: "沉重的铁门被锁上，黑暗笼罩了一切。"
      text_jp: "重い鉄の扉が施錠され、闇が全てを包み込む。"
    - speaker: narrator
      text_cn: "第一天结束了。"
      text_jp: "一日目が終わった。"
  outcomes:
    all:
      stress: 10
  next_day: true
```

---

## 任务 3：修复 `api/fixed_event_manager.py` 的 `handle_event_transitions()`

添加对 `next_period` 的支持：

```python
def handle_event_transitions(self, event_data: Dict) -> Dict[str, Any]:
    """处理事件后的状态转换"""
    result = {
        "next_phase": event_data.get("next_phase"),
        "next_period": event_data.get("next_period"),
        "next_day": event_data.get("next_day", False),
        "next_event": event_data.get("next_event"),
        "game_over": event_data.get("game_over", False),
        "ending_type": event_data.get("ending_type"),
        "trigger_npc_scatter": event_data.get("trigger_npc_scatter", False)
    }
    
    # 更新 current_day.json
    day_path = self.project_root / "world_state" / "current_day.json"
    current_day = load_json(day_path)
    
    if result["next_phase"]:
        current_day["phase"] = result["next_phase"]
    
    if result["next_period"]:
        current_day["period"] = result["next_period"]
    
    if result["next_event"]:
        current_day["next_event"] = result["next_event"]
    else:
        current_day["next_event"] = None
    
    if result["next_day"]:
        current_day["day"] = current_day.get("day", 1) + 1
        current_day["period"] = "dawn"
        current_day["daily_event_count"] = 0
        current_day["next_event"] = None
    
    save_json(day_path, current_day)
    
    return result
```

---

## 任务 4：添加角色分散逻辑

### 4.1 在 `game_loop_v3.py` 添加 `scatter_npcs()` 方法

```python
def scatter_npcs(self):
    """将NPC分散到各个地点"""
    import random
    
    character_states_path = self.project_root / "world_state" / "character_states.json"
    character_states = load_json(character_states_path)
    
    # 可用地点
    locations = ["食堂", "牢房区", "图书室", "庭院", "走廊"]
    
    # 为每个角色随机分配地点
    for char_id, state in character_states.items():
        if state.get("alive", True):
            state["location"] = random.choice(locations)
    
    save_json(character_states_path, character_states)
    print("[系统] NPC已分散到各个地点")
```

### 4.2 在 `_run_fixed_event()` 中调用

```python
def _run_fixed_event(self, event_data: Dict):
    """执行固定事件"""
    event_id = event_data.get("_event_id", "unknown")
    
    # 显示事件
    self.display_fixed_event(event_data)
    
    # 应用结果
    self.fixed_event_manager.apply_event_outcomes(event_data)
    
    # 标记为已触发
    self.fixed_event_manager.mark_event_triggered(event_id)
    
    # 增加事件计数
    self._increment_event_count()
    
    # 处理转换
    transitions = self.fixed_event_manager.handle_event_transitions(event_data)
    
    # 检查是否需要分散NPC
    if transitions.get("trigger_npc_scatter"):
        self.scatter_npcs()
    
    # 检查游戏结束
    if transitions.get("game_over"):
        ending_type = transitions.get("ending_type", "normal_end")
        self.handle_ending(ending_type)
        return
    
    # 检查分支
    branch = event_data.get("branch")
    if branch:
        self._handle_event_branch(branch)
        return
    
    # 检查是否有后续事件（next_event）
    if transitions.get("next_event"):
        # 有后续事件，不推进时间
        return
    
    # 检查是否改变了时段
    if transitions.get("next_period"):
        # 时段改变，不调用 advance_time
        print(f"\n[时间流逝] -> {self._period_to_chinese(transitions['next_period'])}")
        return
    
    # 检查是否进入下一天
    if transitions.get("next_day"):
        print(f"\n[新的一天开始了...]")
        return
    
    # 检查是否改变了阶段
    if transitions.get("next_phase"):
        print(f"\n[FixedEventManager] 阶段变更: {transitions['next_phase']}")
        return
    
    # 普通事件：检查并推进时间
    self._check_and_advance()
```

---

## 任务 5：修复 `_check_trigger()` 中 `after_event` 的逻辑

确保 `after_event` 类型事件能正确触发：

```python
elif trigger_type == "after_event":
    # 在某事件后触发
    after = trigger.get("after", "")
    triggered_list = self.get_triggered_events()
    
    # 检查前置事件是否已触发
    if after not in triggered_list:
        return False
    
    # after_event 类型不需要检查 period，只要前置事件完成就触发
    return True
```

---

## 任务 6：重置游戏状态

### 6.1 重置 `world_state/current_day.json`

```json
{
  "chapter": 1,
  "day": 1,
  "period": "dawn",
  "phase": "free_time",
  "event_count": 0,
  "daily_event_count": 0,
  "alive_count": 13,
  "dead_count": 0,
  "investigation_count": 0,
  "murderer_id": null,
  "victim_id": null,
  "crime_scene": null,
  "case_status": "no_case",
  "flags": {},
  "triggered_events": [],
  "next_event": null
}
```

### 6.2 重置 `world_state/character_states.json`

所有角色初始位置设为 "牢房区"，stress 和 madness 重置。

---

## 更新项目文档

### STATUS.md 添加更新日志

```markdown
### 2025-12-22 - 游戏流程问题修复 v3

**修改文件**: `game_loop_v3.py`, `api/fixed_event_manager.py`, `events/fixed_events.yaml`, `world_state/*.json`

**问题**:
1. 时段跳跃：dawn 直接跳到 noon，跳过 morning
2. 事件链断裂：after_event 类型事件未触发
3. 角色未分散：所有人始终在牢房区
4. 固定事件缺失：dinner/night 未触发

**修复内容**:

1. **advance_time()**: 修复时段顺序，确保 dawn→morning→noon→afternoon→evening→night
2. **handle_event_transitions()**: 添加 `next_period` 和 `trigger_npc_scatter` 支持
3. **fixed_events.yaml**: 
   - 为 `day1_awakening` 添加 `next_event: day1_morning_assembly`
   - 为 `day1_intro` 添加 `trigger_npc_scatter: true`
4. **scatter_npcs()**: 新增方法，将NPC随机分散到各地点
5. **_check_trigger()**: 修复 `after_event` 类型判断逻辑

**预期流程**:
```
dawn: day1_awakening → (next_event)
morning: day1_morning_assembly → (next_event)
         day1_rules → (after_event)
         day1_intro → (after_event, trigger_npc_scatter)
         [自由探索]
event_count=3: day1_lunch
         [自由探索]
event_count=6: day1_dinner
night: day1_night → (next_day)
```
```

---

## 验收标准

1. ✅ dawn 触发 `day1_awakening` 后进入 morning（不是 noon）
2. ✅ morning 自动触发 `day1_morning_assembly`
3. ✅ `day1_rules` 和 `day1_intro` 通过 after_event 链式触发
4. ✅ `day1_intro` 后 NPC 分散到各地点
5. ✅ 玩家去其他地点能遇到 NPC（不再是"空旷的场所"）
6. ✅ event_count >= 6 触发 `day1_dinner`
7. ✅ night 时段触发 `day1_night`
8. ✅ `day1_night` 后进入第二天 dawn

---

## 文件修改清单

| 文件 | 操作 | 状态 |
|------|------|:----:|
| `game_loop_v3.py` | 新增 `scatter_npcs()`，修改 `_run_fixed_event()` | ✅ |
| `api/fixed_event_manager.py` | 修改 `handle_event_transitions()`，`_check_trigger()` | ✅ |
| `events/fixed_events.yaml` | 添加 `next_event`/`trigger_npc_scatter`，修改 `day1_night` 触发 | ✅ |
| `world_state/current_day.json` | 重置 | ✅ |
| `world_state/character_states.json` | 重置 | ✅ |
| `STATUS.md` | 添加更新日志 | ✅ |

---

## 完成记录

- **完成日期**: 2025-12-22
- **执行者**: Claude Code (Opus 4.5)
