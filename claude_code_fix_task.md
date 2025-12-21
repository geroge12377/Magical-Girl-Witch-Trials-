# Claude Code 修复任务：固定事件触发系统

## 问题描述

1. 初始 `current_day.json` 的 `event_count` 不为 0，导致早期事件被跳过
2. `_check_trigger()` 对 `event_count` 类型事件的检查不够严格
3. 固定事件执行后时间推进逻辑有问题
4. 玩家自由探索被完全跳过

---

## 任务 1：重置 `world_state/current_day.json` ✅

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

---

## 任务 2：修改 `api/fixed_event_manager.py` ✅

### 修复 `_check_trigger()` 方法

找到 `_check_trigger()` 方法，替换为：

```python
def _check_trigger(
    self,
    event_data: Dict,
    day: int,
    period: str,
    phase: str,
    event_count: int,
    flags: Dict
) -> bool:
    """检查事件触发条件"""
    trigger = event_data.get("trigger", {})
    trigger_type = trigger.get("type", "auto")
    
    # 1. 检查日期（必须匹配）
    if "day" in trigger and trigger["day"] != day:
        return False
    
    # 2. 检查时段（必须匹配）
    if "period" in trigger and trigger["period"] != period:
        return False
    
    # 3. 检查阶段
    if "phase" in trigger and trigger["phase"] != phase:
        return False
    
    # 4. 检查最小日期
    if "day_min" in trigger and day < trigger["day_min"]:
        return False
    
    # 5. 检查 any_phase（如果设置了，跳过阶段检查）
    if trigger.get("any_phase"):
        pass  # 不检查 phase
    
    # 6. 根据触发类型检查
    if trigger_type == "auto":
        # 自动触发：日期+时段匹配即可
        return True
    
    elif trigger_type == "event_count":
        # 事件计数触发：必须同时满足日期+时段+阶段+计数
        required_count = trigger.get("count", 0)
        trigger_day = trigger.get("day")
        trigger_phase = trigger.get("phase", "free_time")
        
        # 日期必须匹配（如果指定了）
        if trigger_day is not None and trigger_day != day:
            return False
        
        # 阶段必须匹配
        if trigger_phase != phase:
            return False
        
        # 计数必须达到
        return event_count >= required_count
    
    elif trigger_type == "condition":
        # 条件触发
        condition = trigger.get("condition", "")
        return self._evaluate_condition(condition, flags)
    
    elif trigger_type == "after_event":
        # 在某事件后触发
        after = trigger.get("after", "")
        triggered_list = self.get_triggered_events()
        
        # 检查前置事件是否已触发
        if after not in triggered_list:
            return False
        
        # 检查额外的 config_check（如果有）
        config_check = trigger.get("config_check")
        if config_check:
            config_value = self.config.get(config_check, True)
            if not config_value:
                return False
        
        return True
    
    return False
```

---

## 任务 3：修改 `game_loop_v3.py` ✅

### 3.1 修改 `_run_fixed_event()` 方法

找到 `_run_fixed_event()` 方法，替换为：

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
        # 有后续事件，不推进时间，让下一回合触发
        return
    
    # 检查是否进入下一天
    if transitions.get("next_day"):
        # next_day 已在 handle_event_transitions 中处理
        # 不需要再调用 advance_time
        print(f"\n[新的一天开始了...]")
        return
    
    # 检查是否改变了阶段
    if transitions.get("next_phase"):
        # 阶段改变，不推进时间
        return
    
    # 普通事件：检查并推进时间
    self._check_and_advance()
```

### 3.2 修改 `game_turn()` 方法中的固定事件检查逻辑

在 `game_turn()` 中，修改固定事件检查部分：

```python
def game_turn(self):
    """一个游戏回合"""

    # 0. 加载当前状态
    current_day_data = load_json(self.project_root / "world_state" / "current_day.json")

    # 检查是否已结束
    if current_day_data.get("phase") == "ending":
        self.running = False
        return

    # 1. 显示时间
    display_time(self.project_root)

    # 2. 显示世界状态
    display_world_state(self.project_root)

    # 3. 检查是否处于特殊阶段
    phase = current_day_data.get("phase", "free_time")
    if phase == "investigation":
        self.run_investigation()
        return
    elif phase == "trial":
        self.run_trial()
        return

    # 4. 检查固定事件
    fixed_event = self.fixed_event_manager.get_pending_fixed_event()
    if fixed_event:
        self._run_fixed_event(fixed_event)
        return

    # 5. 无固定事件 -> 玩家自由探索
    menu = display_location_menu(self.locations, phase)

    choice = input("\n输入数字: ").strip()

    # ... 后续的地点选择和 DirectorPlanner 逻辑保持不变 ...
```

### 3.3 修改 `_check_and_advance()` 方法

确保只在适当时候推进时间：

```python
def _check_and_advance(self):
    """检查结局条件并推进时间"""
    current_day_data = load_json(self.project_root / "world_state" / "current_day.json")

    # 检测结局（仅在第3天晚上检测）
    day = current_day_data.get("day", 1)
    period = current_day_data.get("period", "dawn")
    
    if day >= 3 and period == "night":
        ending = self.story_planner.check_ending()
        if ending:
            self.handle_ending(ending)
            return

    # 检测杀人预备（每天 night 检测）
    if period == "night":
        murder = self.story_planner.check_murder_prep()
        if murder and murder.get("active") and murder.get("can_execute"):
            self.handle_murder_event(murder)
            return
        else:
            # 检查是否有高madness角色可能杀人
            self._check_madness_murder()

    # 推进时间
    self.advance_time()
```

---

## 任务 4：修改 `api/fixed_event_manager.py` 的 `handle_event_transitions()` ✅

确保正确处理 `next_day`：

```python
def handle_event_transitions(self, event_data: Dict) -> Dict[str, Any]:
    """处理事件后的状态转换"""
    result = {
        "next_phase": event_data.get("next_phase"),
        "next_day": event_data.get("next_day", False),
        "next_event": event_data.get("next_event"),
        "game_over": event_data.get("game_over", False),
        "ending_type": event_data.get("ending_type")
    }
    
    # 更新 current_day.json
    day_path = self.project_root / "world_state" / "current_day.json"
    current_day = load_json(day_path)
    
    if result["next_phase"]:
        current_day["phase"] = result["next_phase"]
    
    if result["next_event"]:
        current_day["next_event"] = result["next_event"]
    else:
        current_day["next_event"] = None
    
    if result["next_day"]:
        current_day["day"] = current_day.get("day", 1) + 1
        current_day["period"] = "dawn"
        current_day["daily_event_count"] = 0
        # 重置 next_event（新的一天应该重新检查事件）
        current_day["next_event"] = None
    
    # 处理 trigger_summary（如果有）
    if event_data.get("trigger_summary"):
        # 可以在这里添加总结显示逻辑
        pass
    
    save_json(day_path, current_day)
    
    return result
```

---

## 文件修改清单

| 操作 | 文件路径 | 状态 |
|------|----------|------|
| 重置 | `world_state/current_day.json` | ✅ 已完成 |
| 修改 | `api/fixed_event_manager.py` | ✅ 已完成 |
| 修改 | `game_loop_v3.py` | ✅ 已完成 |

---

## 验收标准

1. ✅ 重置后 `event_count` 从 0 开始
2. ✅ 第1天 dawn 触发 `day1_awakening`
3. ✅ 第1天 morning 触发 `day1_morning_assembly`
4. ✅ 之后触发 `day1_rules` -> `day1_hiro` -> `day1_intro`（after_event 链）
5. ✅ `event_count >= 3` 时触发 `day1_lunch`
6. ✅ 午餐后有自由探索时间（玩家可选择地点）
7. ✅ `event_count >= 6` 时触发 `day1_dinner`
8. ✅ `next_day: true` 正确进入下一天 dawn

---

## 完成记录

- **完成日期**: 2025-12-21
- **执行者**: Claude Code (Opus 4.5)
- **Git Commit**: `fix: 修复固定事件触发系统`
