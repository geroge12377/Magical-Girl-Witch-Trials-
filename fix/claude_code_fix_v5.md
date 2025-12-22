# Claude Code 任务：修复游戏流程问题 v5

## 问题描述

根据最新测试日志，发现以下问题：

### 问题 1：时段卡在 morning
```
[第1天 - 上午] event_count: 5  <- 自由探索开始
[第1天 - 上午] event_count: 6  <- day1_lunch 触发
[第1天 - 上午] event_count: 7  <- day1_dinner 触发
...一直到 event_count: 11 才进入 night
```

**原因**：自由探索场景结束后，`advance_time()` 被调用但只显示了 `[时间流逝]`，实际 `period` 没有被正确更新到 JSON 文件，或者固定事件触发后覆盖了时段。

### 问题 2：午餐/晚餐触发时机错误
- `day1_lunch` 应该在 `noon` 时段触发，但在 `morning` 就触发了
- `day1_dinner` 应该在 `evening` 时段触发，但也在 `morning` 触发了

**原因**：`event_count` 类型事件只检查计数，没有同时检查时段。

### 问题 3：场景规划与地点不匹配
```
你来到了 食堂...
[场景规划] 图书馆的异常发现  <- 场景名称与地点不符
```

**原因**：DirectorPlanner 的 prompt 没有强调必须根据实际地点生成场景。

---

## 任务 1：修复 `game_loop_v3.py` 的时段推进逻辑

### 1.1 确保 `advance_time()` 正确保存到文件

```python
def advance_time(self):
    """推进时间到下一个时段"""
    day_path = self.project_root / "world_state" / "current_day.json"
    current_day_data = load_json(day_path)
    
    current_period = current_day_data.get("period", "dawn")
    
    # 时段顺序
    period_order = ["dawn", "morning", "noon", "afternoon", "evening", "night"]
    period_names = {
        "dawn": "黎明", "morning": "上午", "noon": "正午",
        "afternoon": "下午", "evening": "傍晚", "night": "夜晚"
    }
    
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
            next_period = period_order[next_index]
            current_day_data["period"] = next_period
            print(f"\n[时间流逝] -> {period_names.get(next_period, next_period)}")
    except ValueError:
        current_day_data["period"] = "morning"
        print(f"\n[时间流逝] -> 上午")
    
    # ★ 关键：确保保存到文件
    save_json(day_path, current_day_data)
    
    # ★ 刷新内存中的状态
    self.current_day_data = current_day_data
```

### 1.2 在自由探索场景结束后调用 `advance_time()`

检查 `game_turn()` 中的流程，确保：
1. 固定事件执行后，如果没有 `next_event`，才调用 `advance_time()`
2. 自由探索场景结束后，必须调用 `advance_time()`

```python
def game_turn(self):
    """一个游戏回合"""
    # ... 显示状态 ...
    
    # 1. 检查固定事件
    fixed_event = self.fixed_event_manager.get_pending_fixed_event()
    if fixed_event:
        self._run_fixed_event(fixed_event)
        return  # 固定事件内部处理时间推进
    
    # 2. 显示地点菜单，玩家选择
    location = self._get_player_location_choice()
    if location is None:
        return
    
    # 3. 规划并执行自由场景
    self._run_free_scene(location)
    
    # 4. ★ 自由场景结束后推进时间
    self.advance_time()
```

---

## 任务 2：修复 `events/fixed_events.yaml` 中的触发条件

### 2.1 午餐需要同时满足 event_count 和 period

```yaml
day1_lunch:
  id: "day1_lunch"
  name: "第一天午餐"
  trigger:
    type: condition
    condition: "event_count >= 3 and period == 'noon'"
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
```

### 2.2 晚餐需要同时满足 event_count 和 period

```yaml
day1_dinner:
  id: "day1_dinner"
  name: "第一天晚餐"
  trigger:
    type: condition
    condition: "event_count >= 6 and period == 'evening'"
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
```

### 2.3 或者使用组合触发类型

如果 `condition` 类型不支持复杂表达式，可以改用：

```yaml
day1_lunch:
  id: "day1_lunch"
  name: "第一天午餐"
  trigger:
    type: auto
    day: 1
    period: "noon"
    min_event_count: 3  # 新增字段
  priority: 90
  # ...
```

然后在 `_check_trigger()` 中支持 `min_event_count`：

```python
elif trigger_type == "auto":
    day_match = trigger.get("day") == current_day
    period_match = trigger.get("period") == current_period
    
    # 检查最小事件计数（可选）
    min_count = trigger.get("min_event_count", 0)
    count_match = current_event_count >= min_count
    
    return day_match and period_match and count_match
```

---

## 任务 3：修复 `api/fixed_event_manager.py` 的 `_evaluate_condition()`

确保支持 `period` 变量：

```python
def _evaluate_condition(self, condition: str) -> bool:
    """评估条件字符串"""
    day_path = self.project_root / "world_state" / "current_day.json"
    current_day_data = load_json(day_path)
    
    # 构建评估上下文
    context = {
        "day": current_day_data.get("day", 1),
        "period": current_day_data.get("period", "dawn"),
        "phase": current_day_data.get("phase", "free_time"),
        "event_count": current_day_data.get("event_count", 0),
        "flags": current_day_data.get("flags", {}),
    }
    
    # 添加角色状态
    char_states_path = self.project_root / "world_state" / "character_states.json"
    char_states = load_json(char_states_path)
    
    for char_id, state in char_states.items():
        context[f"{char_id}_stress"] = state.get("stress", 0)
        context[f"{char_id}_madness"] = state.get("madness", 0)
        context[f"{char_id}_alive"] = state.get("alive", True)
    
    try:
        # 安全评估
        result = eval(condition, {"__builtins__": {}}, context)
        return bool(result)
    except Exception as e:
        print(f"[FixedEventManager] 条件评估失败: {condition}, 错误: {e}")
        return False
```

---

## 任务 4：修复 `api/director_planner.py` 的场景生成

### 4.1 在 prompt 中强调地点

修改 `prompts/director_planner_prompt.txt`，在开头添加：

```
【重要】场景必须发生在指定地点：{location}
- 场景名称必须与地点相关
- 对话内容必须反映该地点的特征
- 不要生成与其他地点相关的内容

当前地点: {location}
该地点的角色: {characters}
```

### 4.2 在 `plan_scene()` 中验证结果

```python
def plan_scene(self, location: str, ...) -> ScenePlan:
    # ... API 调用 ...
    
    scene_plan = self._parse_response(response)
    
    # ★ 验证场景地点
    if scene_plan.location != location:
        print(f"[DirectorPlanner] 警告: 场景地点不匹配，强制修正 {scene_plan.location} -> {location}")
        scene_plan.location = location
    
    # ★ 验证场景名称不包含其他地点
    other_locations = ["图书室", "图书馆", "食堂", "庭院", "走廊", "牢房区"]
    other_locations.remove(location) if location in other_locations else None
    
    for other in other_locations:
        if other in scene_plan.scene_name:
            print(f"[DirectorPlanner] 警告: 场景名称包含其他地点，需要重新生成或修正")
            # 可以选择重新生成或简单修正
            scene_plan.scene_name = f"{location}的场景"
            break
    
    return scene_plan
```

---

## 任务 5：添加调试日志

在关键位置添加日志，方便排查：

```python
# game_loop_v3.py

def advance_time(self):
    print(f"[DEBUG] advance_time() 调用前: period={current_day_data.get('period')}")
    # ... 推进逻辑 ...
    print(f"[DEBUG] advance_time() 调用后: period={current_day_data.get('period')}")
    save_json(day_path, current_day_data)

def game_turn(self):
    current_day = load_json(...)
    print(f"[DEBUG] game_turn() 开始: day={current_day['day']}, period={current_day['period']}, event_count={current_day['event_count']}")
```

---

## 更新项目文档

### STATUS.md 更新（在"更新日志"最顶部添加）

```markdown
### 2025-12-22 - 游戏流程问题修复 v5 ⭐ 最新

**修改文件**: `game_loop_v3.py`, `api/fixed_event_manager.py`, `events/fixed_events.yaml`, `prompts/director_planner_prompt.txt`

**问题**:
1. 时段卡在 morning：自由探索后时段没有正确推进
2. 午餐/晚餐触发时机错误：只检查 event_count，没有检查 period
3. 场景规划与地点不匹配：DirectorPlanner 生成的场景名称与实际地点无关

**修复内容**:

1. **game_loop_v3.py**:
   - `advance_time()`: 确保时段变更正确保存到 JSON 文件
   - `game_turn()`: 自由场景结束后必须调用 `advance_time()`

2. **fixed_events.yaml**:
   - `day1_lunch`: 触发条件改为 `event_count >= 3 AND period == 'noon'`
   - `day1_dinner`: 触发条件改为 `event_count >= 6 AND period == 'evening'`

3. **fixed_event_manager.py**:
   - `_evaluate_condition()`: 支持 `period` 变量

4. **director_planner_prompt.txt**:
   - 强调场景必须发生在指定地点
   - 场景名称必须与地点相关

**预期流程**:
```
morning: 固定事件链 → NPC分散 → 自由探索 → advance_time()
noon: 自由探索 → day1_lunch (event_count>=3) → 自由探索 → advance_time()
afternoon: 自由探索 → advance_time()
evening: 自由探索 → day1_dinner (event_count>=6) → advance_time()
night: day1_night → next_day
```

**验收标准**:
- ✅ 自由探索后时段正确推进 (morning→noon→afternoon→evening→night)
- ✅ day1_lunch 在 noon 时段触发
- ✅ day1_dinner 在 evening 时段触发
- ✅ 场景规划名称与实际地点匹配

---
```

---

## 验收标准

1. ✅ 自由探索场景结束后，时段正确推进到下一个
2. ✅ `day1_lunch` 只在 `period == "noon"` 且 `event_count >= 3` 时触发
3. ✅ `day1_dinner` 只在 `period == "evening"` 且 `event_count >= 6` 时触发
4. ✅ 去食堂时，场景规划名称包含"食堂"而非"图书馆"
5. ✅ 时间流逝显示与实际 period 一致

---

## 文件修改清单

| 文件 | 操作 |
|------|------|
| `game_loop_v3.py` | 修改 `advance_time()`，确保保存；修改 `game_turn()` 流程 |
| `api/fixed_event_manager.py` | 修改 `_evaluate_condition()` 支持 period |
| `events/fixed_events.yaml` | 修改 `day1_lunch` 和 `day1_dinner` 触发条件 |
| `prompts/director_planner_prompt.txt` | 添加地点强调说明 |
| `api/director_planner.py` | 添加场景地点验证 |
| `STATUS.md` | 添加 v5 更新日志 |
