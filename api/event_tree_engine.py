"""
事件树引擎 - 管理故事分支和条件触发
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from .world_loader import WorldLoader, get_world_loader


@dataclass
class DayPlan:
    """日计划"""
    day: int
    arc: str
    theme: str
    tension_template: str
    fixed_events: List[Dict]
    possible_scenes: Dict
    focus: str


@dataclass
class TriggerResult:
    """触发结果"""
    trigger_id: str
    trigger_type: str
    description: str
    should_trigger: bool
    probability: float
    data: Dict


@dataclass
class ArcUpdate:
    """角色弧线更新"""
    character: str
    arc_name: str
    stage: str
    description: str
    player_can_notice: bool


@dataclass
class SceneParams:
    """场景参数"""
    participants: str  # solo/duo/small_group/crowd
    activity: str
    mood: str
    player_role: str
    info_value: str


class EventTreeEngine:
    """事件树引擎 - 管理故事分支和条件触发"""

    def __init__(self, world_loader: WorldLoader = None, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = project_root

        if world_loader is None:
            self.world = get_world_loader(project_root=project_root)
        else:
            self.world = world_loader

        self.structure = self.world.load_structure()
        self.triggers = self.world.load_triggers()
        self.scene_types = self.world.load_scene_types()
        self.character_arcs = self.world.load_character_arcs()
        self.endings = self.world.load_endings()

    def get_day_plan(self, day: int) -> DayPlan:
        """获取指定日期的事件计划"""
        day_key = f"day_{day}"
        day_data = self.structure.get('days', {}).get(day_key, {})

        arc = day_data.get('arc', self.world.get_arc_for_day(day))
        theme = day_data.get('theme', '')
        tension_template = day_data.get('tension_template', 'peaceful_day')
        fixed_events = day_data.get('fixed_events', [])
        possible_scenes = day_data.get('possible_scenes', {})
        focus = possible_scenes.get('focus', '')

        return DayPlan(
            day=day,
            arc=arc,
            theme=theme,
            tension_template=tension_template,
            fixed_events=fixed_events,
            possible_scenes=possible_scenes,
            focus=focus
        )

    def load_game_context(self) -> Dict:
        """加载游戏上下文"""
        context = {}

        # 加载current_day
        current_day_path = self.project_root / "world_state" / "current_day.json"
        if current_day_path.exists():
            with open(current_day_path, 'r', encoding='utf-8') as f:
                context['current_day'] = json.load(f)
        else:
            context['current_day'] = {'day': 1, 'period': 'dawn', 'event_count': 0, 'flags': {}}

        # 加载character_states
        char_states_path = self.project_root / "world_state" / "character_states.json"
        if char_states_path.exists():
            with open(char_states_path, 'r', encoding='utf-8') as f:
                context['character_states'] = json.load(f)
        else:
            context['character_states'] = {}

        # 加载scene_history
        scene_history_path = self.project_root / "world_state" / "scene_history.json"
        if scene_history_path.exists():
            with open(scene_history_path, 'r', encoding='utf-8') as f:
                context['scene_history'] = json.load(f)
        else:
            context['scene_history'] = {'scenes': [], 'location_last_used': {}, 'character_last_focus': {}, 'activity_last_used': {}}

        return context

    def check_triggers(self, context: Dict) -> List[TriggerResult]:
        """检查所有触发条件，返回应触发的事件"""
        results = []
        trigger_templates = self.triggers.get('trigger_templates', {})

        for trigger_id, trigger_data in trigger_templates.items():
            conditions = trigger_data.get('conditions', [])
            probability = trigger_data.get('probability', 1.0)
            description = trigger_data.get('description', '')

            # 检查所有条件
            all_met = True
            for condition in conditions:
                if not self.evaluate_condition(condition, context):
                    all_met = False
                    break

            if all_met:
                results.append(TriggerResult(
                    trigger_id=trigger_id,
                    trigger_type=trigger_id,
                    description=description,
                    should_trigger=True,
                    probability=probability,
                    data=trigger_data
                ))

        return results

    def evaluate_condition(self, condition: str, context: Dict) -> bool:
        """评估条件表达式"""
        try:
            current_day = context.get('current_day', {})
            character_states = context.get('character_states', {})

            # 替换变量
            condition = condition.strip()

            # 处理简单的变量替换
            # day相关
            condition = condition.replace('day', str(current_day.get('day', 1)))

            # 处理角色状态 {char}.xxx
            char_pattern = r'\{(\w+)\}\.(\w+)'
            matches = re.findall(char_pattern, condition)
            for char_id, attr in matches:
                char_state = character_states.get(char_id, {})
                value = char_state.get(attr, 0)
                condition = condition.replace(f'{{{char_id}}}.{attr}', str(value))

            # 处理flag
            flag_pattern = r'flag\.(\w+)'
            flag_matches = re.findall(flag_pattern, condition)
            for flag_name in flag_matches:
                flag_value = current_day.get('flags', {}).get(flag_name, False)
                condition = condition.replace(f'flag.{flag_name}', str(flag_value).lower())

            # 尝试评估
            # 将python布尔值转换
            condition = condition.replace('true', 'True').replace('false', 'False')

            # 安全评估
            result = eval(condition, {"__builtins__": {}}, {})
            return bool(result)

        except Exception as e:
            # 如果条件无法评估，返回False
            return False

    def get_available_scene_types(self, day: int, history: List) -> List[str]:
        """获取可用场景类型（排除最近用过的）"""
        constraints = self.world.get_scene_constraints(day)
        arc = constraints['arc']

        # 获取arc约束的allowed_moods
        arc_constraints = self.scene_types.get('generation_rules', {}).get('arc_constraints', {}).get(arc, {})
        allowed_moods = arc_constraints.get('allowed_moods', ['peaceful', 'relaxed'])

        # 获取anti_repetition规则
        anti_rep = self.scene_types.get('generation_rules', {}).get('anti_repetition', {})
        activity_cooldown = anti_rep.get('same_activity_cooldown', 2)

        # 获取最近用过的活动
        recent_activities = []
        for scene in history[-activity_cooldown:]:
            if 'scene_type' in scene:
                recent_activities.append(scene['scene_type'])

        # 获取所有活动类型
        activities = self.scene_types.get('dimensions', {}).get('activity', {})
        all_activities = []
        for category, activity_list in activities.items():
            if isinstance(activity_list, list):
                for item in activity_list:
                    if isinstance(item, dict):
                        all_activities.extend(item.keys())
                    else:
                        all_activities.append(item)

        # 过滤掉最近用过的
        available = [a for a in all_activities if a not in recent_activities]

        return available if available else all_activities

    def select_scene_parameters(self, day: int, context: Dict) -> SceneParams:
        """选择场景参数组合"""
        constraints = self.world.get_scene_constraints(day)
        history = context.get('scene_history', {}).get('scenes', [])

        # 基于arc选择参数
        arc = constraints['arc']
        arc_constraints = self.scene_types.get('generation_rules', {}).get('arc_constraints', {}).get(arc, {})

        allowed_moods = arc_constraints.get('allowed_moods', ['peaceful'])
        allowed_roles = arc_constraints.get('allowed_player_roles', ['spectator'])
        info_weights = arc_constraints.get('info_value_weights', {'none': 0.7, 'hint': 0.3, 'clue': 0})

        # 简单选择（可以后续改为加权随机）
        mood = allowed_moods[0] if allowed_moods else 'peaceful'
        player_role = allowed_roles[0] if allowed_roles else 'spectator'

        # 根据权重选择info_value
        max_weight = 0
        info_value = 'none'
        for iv, weight in info_weights.items():
            if weight > max_weight:
                max_weight = weight
                info_value = iv

        # 获取可用活动
        available_activities = self.get_available_scene_types(day, history)
        activity = available_activities[0] if available_activities else 'idle'

        # 参与人数（根据场景类型推断）
        participants = 'duo'  # 默认

        return SceneParams(
            participants=participants,
            activity=activity,
            mood=mood,
            player_role=player_role,
            info_value=info_value
        )

    def check_character_arcs(self, context: Dict) -> List[ArcUpdate]:
        """检查角色弧线进度"""
        updates = []
        arcs = self.character_arcs.get('arcs', {})
        current_day = context.get('current_day', {})
        day = current_day.get('day', 1)
        character_states = context.get('character_states', {})

        for arc_name, arc_data in arcs.items():
            character = arc_data.get('character', '')
            prerequisites = arc_data.get('prerequisites', [])
            stages = arc_data.get('stages', [])

            # 检查前置条件
            prereqs_met = True
            for prereq in prerequisites:
                if not self.evaluate_condition(prereq, context):
                    prereqs_met = False
                    break

            if not prereqs_met:
                continue

            # 检查每个阶段
            for stage in stages:
                stage_name = stage.get('stage', '')
                day_range = stage.get('day_range', [1, 7])
                trigger_condition = stage.get('trigger', '')
                player_can_notice = stage.get('player_can_notice', False)

                # 检查是否在日期范围内
                if day < day_range[0] or day > day_range[1]:
                    continue

                # 检查触发条件
                if trigger_condition:
                    # 替换角色变量
                    trigger_condition = trigger_condition.replace('{char}', character)
                    if not self.evaluate_condition(trigger_condition, context):
                        continue

                # 检查是否已触发过
                arc_flag = f"{character}_arc_{stage_name}"
                if current_day.get('flags', {}).get(arc_flag, False):
                    continue

                # 满足条件，添加更新
                updates.append(ArcUpdate(
                    character=character,
                    arc_name=arc_name,
                    stage=stage_name,
                    description=stage.get('description', ''),
                    player_can_notice=player_can_notice
                ))

        return updates

    def get_ending_path(self, context: Dict) -> Optional[str]:
        """检查是否满足某个结局条件"""
        endings_data = self.endings.get('endings', {})
        ending_priority = self.endings.get('ending_priority', {}).get('order', [])
        current_day = context.get('current_day', {})
        character_states = context.get('character_states', {})

        # 按优先级检查
        for ending_id in ending_priority:
            if ending_id not in endings_data:
                continue

            ending = endings_data[ending_id]
            triggers = ending.get('trigger', [])

            # 检查所有触发条件
            all_met = True
            for trigger in triggers:
                if not self._check_ending_trigger(trigger, context):
                    all_met = False
                    break

            if all_met:
                return ending_id

        return None

    def _check_ending_trigger(self, trigger: str, context: Dict) -> bool:
        """检查单个结局触发条件"""
        current_day = context.get('current_day', {})
        character_states = context.get('character_states', {})

        # 处理特殊条件
        if trigger.startswith('flag.'):
            flag_name = trigger.replace('flag.', '')
            return current_day.get('flags', {}).get(flag_name, False)

        if trigger.startswith('NOT '):
            inner = trigger[4:].strip()
            return not self._check_ending_trigger(inner, context)

        if trigger == 'day == 7':
            return current_day.get('day', 1) == 7

        if trigger == 'alive_count == 13':
            # 检查存活人数
            alive = sum(1 for char_id, state in character_states.items()
                        if state.get('alive', True))
            return alive == 13

        if trigger.startswith('trial_result =='):
            # 检查审判结果
            result = trigger.split('==')[1].strip()
            return current_day.get('flags', {}).get('trial_result', '') == result

        if trigger.startswith('player.madness >='):
            threshold = int(trigger.split('>=')[1].strip())
            player_state = character_states.get('player', {})
            return player_state.get('madness', 0) >= threshold

        if trigger.startswith('avg(all_characters.affection) >='):
            threshold = int(trigger.split('>=')[1].strip())
            total = 0
            count = 0
            for char_id, state in character_states.items():
                if char_id != 'player':
                    total += state.get('affection', 50)
                    count += 1
            avg = total / count if count > 0 else 0
            return avg >= threshold

        # 默认尝试评估
        return self.evaluate_condition(trigger, context)

    def get_anti_repetition_warnings(self, location: str, characters: List[str], context: Dict) -> List[str]:
        """获取防重复警告"""
        warnings = []
        scene_history = context.get('scene_history', {})
        anti_rep = self.scene_types.get('generation_rules', {}).get('anti_repetition', {})

        location_cooldown = anti_rep.get('same_location_cooldown', 2)
        character_cooldown = anti_rep.get('same_character_focus_cooldown', 3)

        # 检查地点
        location_last = scene_history.get('location_last_used', {}).get(location)
        if location_last:
            scenes = scene_history.get('scenes', [])
            scene_ids = [s.get('scene_id') for s in scenes]
            if location_last in scene_ids:
                idx = scene_ids.index(location_last)
                scenes_since = len(scenes) - idx - 1
                if scenes_since < location_cooldown:
                    warnings.append(f"地点「{location}」刚用过（{scenes_since}场景前），建议换活动类型")

        # 检查角色焦点
        for char in characters[:2]:
            char_last = scene_history.get('character_last_focus', {}).get(char)
            if char_last:
                scenes = scene_history.get('scenes', [])
                scene_ids = [s.get('scene_id') for s in scenes]
                if char_last in scene_ids:
                    idx = scene_ids.index(char_last)
                    scenes_since = len(scenes) - idx - 1
                    if scenes_since < character_cooldown:
                        warnings.append(f"角色「{char}」最近是焦点（{scenes_since}场景前），建议换其他角色")

        return warnings
