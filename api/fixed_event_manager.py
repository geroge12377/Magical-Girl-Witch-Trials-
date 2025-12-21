# ============================================================================
# 固定事件管理器 (Fixed Event Manager)
# ============================================================================
# 职责：
# 1. 加载 fixed_events.yaml
# 2. 根据当前状态判断应触发哪个固定事件
# 3. 支持多种触发类型：auto, event_count, condition, after_event
# ============================================================================

import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


def load_json(filepath) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data: dict):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_yaml(filepath) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class FixedEventManager:
    """固定事件管理器"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.events = self._load_fixed_events()
        self.config = self.events.get("config", {})

    def _load_fixed_events(self) -> Dict:
        """加载固定事件定义"""
        path = self.project_root / "events" / "fixed_events.yaml"
        if path.exists():
            return load_yaml(path)
        return {"fixed_events": {}}

    def _load_current_state(self) -> Dict:
        """加载当前游戏状态"""
        current_day = load_json(self.project_root / "world_state" / "current_day.json")
        return current_day

    def _load_character_states(self) -> Dict:
        """加载角色状态"""
        return load_json(self.project_root / "world_state" / "character_states.json")

    def get_triggered_events(self) -> List[str]:
        """获取已触发事件列表"""
        state = self._load_current_state()
        return state.get("triggered_events", [])

    def mark_event_triggered(self, event_id: str):
        """标记事件已触发"""
        path = self.project_root / "world_state" / "current_day.json"
        state = load_json(path)
        if "triggered_events" not in state:
            state["triggered_events"] = []
        if event_id not in state["triggered_events"]:
            state["triggered_events"].append(event_id)
        save_json(path, state)

    def get_pending_fixed_event(self) -> Optional[Dict]:
        """
        获取当前应该触发的固定事件

        Returns:
            事件数据字典，如果没有则返回 None
        """
        state = self._load_current_state()
        triggered = self.get_triggered_events()

        day = state.get("day", 1)
        period = state.get("period", "dawn")
        phase = state.get("phase", "free_time")
        event_count = state.get("event_count", 0)
        flags = state.get("flags", {})

        # 检查是否有 next_event 指定
        next_event = state.get("next_event")
        if next_event:
            events = self.events.get("fixed_events", {})
            if next_event in events:
                event_data = events[next_event].copy()
                event_data["_event_id"] = next_event
                return event_data

        # 遍历所有固定事件，找优先级最高的可触发事件
        candidates = []
        events = self.events.get("fixed_events", {})

        for event_id, event_data in events.items():
            # 跳过已触发的事件
            if event_id in triggered:
                continue

            # 检查触发条件
            if self._check_trigger(event_data, day, period, phase, event_count, flags):
                priority = event_data.get("priority", 0)
                candidates.append((priority, event_id, event_data))

        # 按优先级排序，返回最高的
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            _, event_id, event_data = candidates[0]
            result = event_data.copy()
            result["_event_id"] = event_id  # 附加 event_id
            return result

        return None

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

        # 检查日期
        if "day" in trigger and trigger["day"] != day:
            return False

        # 检查时段
        if "period" in trigger and trigger["period"] != period:
            return False

        # 检查阶段
        if "phase" in trigger and trigger["phase"] != phase:
            return False

        # 根据触发类型检查
        if trigger_type == "auto":
            # 自动触发：只要日期和时段匹配
            return True

        elif trigger_type == "event_count":
            # 事件计数触发
            required_count = trigger.get("count", 0)
            return event_count >= required_count

        elif trigger_type == "condition":
            # 条件触发
            condition = trigger.get("condition", "")
            return self._evaluate_condition(condition, flags)

        elif trigger_type == "after_event":
            # 在某事件后触发
            after = trigger.get("after", "")
            triggered_list = self.get_triggered_events()
            return after in triggered_list

        return False

    def _evaluate_condition(self, condition: str, flags: Dict) -> bool:
        """
        评估条件字符串

        支持的条件：
        - flag_xxx: 检查 flags["xxx"] == True
        - highest_madness_above_70: 检查最高 madness > 70
        - day3_night_no_murder: 第三天夜晚且无杀人
        - 等等
        """
        if not condition:
            return True

        # flag 检查
        if condition.startswith("flag_"):
            flag_name = condition[5:]  # 去掉 "flag_" 前缀
            return flags.get(flag_name, False)

        # 特殊条件
        if condition == "highest_madness_above_70":
            states = self._load_character_states()
            max_madness = max(
                (s.get("madness", 0) for s in states.values()
                if s.get("status") == "alive"),
                default=0
            )
            return max_madness > 70

        if condition == "day3_night_no_murder":
            state = self._load_current_state()
            return (
                state.get("day") == 3 and
                state.get("period") == "night" and
                not flags.get("murder_occurred", False)
            )

        if condition == "player_at_library":
            # 需要外部传入玩家位置，这里简化处理
            return False

        # 默认返回 False
        return False

    def apply_event_outcomes(self, event_data: Dict):
        """应用事件结果"""
        outcomes = event_data.get("outcomes", {})
        if not outcomes:
            return

        states_path = self.project_root / "world_state" / "character_states.json"
        states = load_json(states_path)

        for target, effects in outcomes.items():
            if target == "all" or target == "all_characters":
                # 应用到所有角色
                for char_id, char_state in states.items():
                    if char_state.get("status") == "alive":
                        self._apply_effects(char_state, effects)
            elif target in states:
                # 应用到特定角色
                self._apply_effects(states[target], effects)

        save_json(states_path, states)

        # 处理 flags_set
        flags_to_set = event_data.get("flags_set", [])
        if flags_to_set:
            day_path = self.project_root / "world_state" / "current_day.json"
            current_day = load_json(day_path)
            if "flags" not in current_day:
                current_day["flags"] = {}
            for flag in flags_to_set:
                current_day["flags"][flag] = True
            save_json(day_path, current_day)

    def _apply_effects(self, state: Dict, effects: Dict):
        """应用效果到角色状态"""
        if "stress" in effects:
            current = state.get("stress", 50)
            state["stress"] = max(0, min(100, current + effects["stress"]))
        if "madness" in effects:
            current = state.get("madness", 0)
            state["madness"] = max(0, min(100, current + effects["madness"]))
        if "emotion" in effects:
            state["emotion"] = effects["emotion"]

    def handle_event_transitions(self, event_data: Dict) -> Dict[str, Any]:
        """
        处理事件后的状态转换

        Returns:
            包含转换信息的字典：
            - next_phase: 下一阶段
            - next_day: 是否进入下一天
            - next_event: 下一个事件ID
            - game_over: 是否游戏结束
            - ending_type: 结局类型
        """
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

        save_json(day_path, current_day)

        return result
