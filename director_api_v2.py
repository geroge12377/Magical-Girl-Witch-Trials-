# ============================================================================
# 导演API v2 - 整合事件系统、地点系统
# ============================================================================
# 职责：
# 1. 判断并触发固定事件
# 2. 根据条件选择自由事件模板
# 3. 填充模板槽位，生成具体事件
# 4. 生成对话剧本和玩家选项
# 5. 预生成选项回应（零延迟）
# ============================================================================

import anthropic
import json
import yaml
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from config import get_api_key, MODEL, MAX_TOKENS, ENABLE_CACHE


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class GameContext:
    """游戏上下文"""
    day: int
    phase: str
    event_count: int
    flags: Dict[str, bool]
    player_location: str
    
@dataclass
class EventResult:
    """事件结果"""
    event_id: str
    event_type: str  # "fixed" | "free"
    dialogue: List[Dict]
    choices: Optional[Dict]
    outcomes: Dict[str, Dict]
    next_event: Optional[str]
    next_phase: Optional[str]
    flags_set: List[str] = field(default_factory=list)
    game_over: bool = False
    ending_type: Optional[str] = None


# ============================================================================
# 工具函数
# ============================================================================

def load_json(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath: str, data: dict):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_yaml(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def clean_json_response(text: str) -> str:
    """清理API返回的JSON"""
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()


# ============================================================================
# 条件评估器
# ============================================================================

class ConditionEvaluator:
    """条件评估器 - 解析并评估事件触发条件"""
    
    def __init__(self, character_states: Dict, current_day: Dict, locations: Dict):
        self.chars = character_states
        self.day = current_day
        self.locations = locations
    
    def evaluate(self, condition: str) -> bool:
        """评估条件字符串"""
        # 解析条件
        if condition == "default":
            return True
        
        # highest_madness_above_70
        if condition == "highest_madness_above_70":
            max_madness = max(c.get("madness", 0) for c in self.chars.values())
            return max_madness > 70
        
        # player_madness_above_80
        if condition == "player_madness_above_80":
            # 假设player不在character_states中，或者用特殊处理
            return False  # 需要具体实现
        
        # flag检查
        if condition.startswith("flag_"):
            flag_name = condition[5:]  # 去掉"flag_"前缀
            return self.day.get("flags", {}).get(flag_name, False)
        
        # day3_night_no_murder
        if condition == "day3_night_no_murder":
            is_day3 = self.day.get("day") == 3
            is_night = self.day.get("phase") == "night"
            no_murder = not self.day.get("flags", {}).get("murder_occurred", False)
            max_madness = max(c.get("madness", 0) for c in self.chars.values())
            return is_day3 and is_night and no_murder and max_madness <= 70
        
        # all_stress_70_to_85_and_library_clue_and_all_alive
        if condition == "all_stress_70_to_85_and_library_clue_and_all_alive":
            all_alive = all(c.get("status") == "alive" for c in self.chars.values())
            library_clue = self.day.get("flags", {}).get("library_clue_found", False)
            all_stress_ok = all(70 <= c.get("stress", 0) <= 85 for c in self.chars.values())
            return all_alive and library_clue and all_stress_ok
        
        # 投票相关条件
        if condition in ["vote_result_correct", "vote_result_player", "vote_result_wrong"]:
            # 这些需要在审判阶段由代码设置
            return self.day.get("flags", {}).get(condition, False)
        
        # debate_finished
        if condition == "debate_finished":
            return self.day.get("flags", {}).get("debate_finished", False)
        
        # investigation_count_zero_or_time_expired
        if condition == "investigation_count_zero_or_time_expired":
            return self.day.get("investigation_count", 5) <= 0
        
        # player_at_library
        if condition == "player_at_library":
            return self.day.get("player_location") == "图书室"
        
        # 默认返回False
        print(f"⚠️ 未知条件: {condition}")
        return False
    
    def check_trigger(self, trigger: Dict) -> bool:
        """检查事件触发条件"""
        trigger_type = trigger.get("type")
        
        if trigger_type == "auto":
            # 自动触发：检查day和phase
            required_day = trigger.get("day")
            required_phase = trigger.get("phase")
            
            day_match = required_day is None or self.day.get("day") == required_day
            phase_match = required_phase is None or self.day.get("phase") == required_phase
            
            return day_match and phase_match
        
        elif trigger_type == "event_count":
            # 事件计数触发
            required_day = trigger.get("day")
            required_count = trigger.get("count")
            required_phase = trigger.get("phase")
            
            day_match = required_day is None or self.day.get("day") == required_day
            count_match = self.day.get("event_count", 0) >= required_count
            phase_match = required_phase is None or self.day.get("phase") == required_phase
            
            return day_match and count_match and phase_match
        
        elif trigger_type == "condition":
            # 条件触发
            condition = trigger.get("condition")
            return self.evaluate(condition)
        
        elif trigger_type == "after_event":
            # 事件链触发：检查前置事件是否已触发
            after_event = trigger.get("after")
            triggered_events = self.day.get("triggered_events", [])
            
            # 检查config开关
            config_check = trigger.get("config_check")
            if config_check:
                # 需要检查配置
                # 这里简化处理，实际应该从config中读取
                pass
            
            return after_event in triggered_events
        
        return False


# ============================================================================
# 事件管理器
# ============================================================================

class EventManager:
    """事件管理器 - 管理固定事件和自由事件"""
    
    def __init__(self):
        self.fixed_events = load_yaml("events/fixed_events.yaml")
        self.free_templates = load_yaml("events/free_event_templates.yaml")
        self.locations = load_yaml("world_state/locations.yaml")
        self.character_states = load_json("world_state/character_states.json")
        self.current_day = load_json("world_state/current_day.json")
        
        self.evaluator = ConditionEvaluator(
            self.character_states, 
            self.current_day,
            self.locations
        )
    
    def reload_state(self):
        """重新加载状态"""
        self.character_states = load_json("world_state/character_states.json")
        self.current_day = load_json("world_state/current_day.json")
        self.evaluator = ConditionEvaluator(
            self.character_states,
            self.current_day,
            self.locations
        )
    
    def get_pending_fixed_event(self) -> Optional[Dict]:
        """获取待触发的固定事件（优先级最高的）"""
        triggered = self.current_day.get("triggered_events", [])
        candidates = []
        
        fixed_events = self.fixed_events.get("fixed_events", {})
        
        for event_id, event_data in fixed_events.items():
            # 跳过已触发的
            if event_id in triggered:
                continue
            
            # 检查触发条件
            trigger = event_data.get("trigger", {})
            if self.evaluator.check_trigger(trigger):
                priority = event_data.get("priority", 0)
                candidates.append((priority, event_id, event_data))
        
        if not candidates:
            return None
        
        # 按优先级排序，返回最高的
        candidates.sort(key=lambda x: -x[0])
        _, event_id, event_data = candidates[0]
        
        return {"id": event_id, **event_data}
    
    def check_branch(self, event_data: Dict) -> Optional[str]:
        """检查分歧事件，返回下一个事件ID"""
        branches = event_data.get("branch", [])
        
        for branch in branches:
            condition = branch.get("condition")
            if self.evaluator.evaluate(condition):
                return branch.get("next_event")
        
        return None
    
    def select_free_event_template(self, player_location: str) -> Optional[Dict]:
        """选择合适的自由事件模板"""
        templates = self.free_templates.get("templates", {})
        weights = self.free_templates.get("selection_weights", {})
        
        # 计算当前环境的权重调整
        avg_stress = sum(c.get("stress", 0) for c in self.character_states.values()) / len(self.character_states)
        
        weight_adjustments = {}
        if avg_stress > 50:
            weight_adjustments = weights.get("high_stress_environment", {})
        elif avg_stress < 30:
            weight_adjustments = weights.get("low_stress_environment", {})
        
        # 根据天数调整
        day = self.current_day.get("day", 1)
        day_weights = weights.get(f"day{day}", {})
        
        # 筛选可用模板
        candidates = []
        for tmpl_id, tmpl_data in templates.items():
            # 检查地点限制
            loc_filter = tmpl_data.get("location_filter", [])
            if loc_filter:
                # 将中文地点名转换为ID
                loc_id = self._get_location_id(player_location)
                if loc_id and loc_id not in loc_filter:
                    continue
            
            # 计算权重
            base_weight = 1.0
            base_weight *= weight_adjustments.get(tmpl_id, 1.0)
            base_weight *= day_weights.get(tmpl_id, 1.0)
            
            candidates.append((tmpl_id, tmpl_data, base_weight))
        
        if not candidates:
            # 默认返回normal模板
            return {"id": "normal", **templates.get("normal", {})}
        
        # 加权随机选择
        total_weight = sum(c[2] for c in candidates)
        r = random.random() * total_weight
        
        cumulative = 0
        for tmpl_id, tmpl_data, weight in candidates:
            cumulative += weight
            if r <= cumulative:
                return {"id": tmpl_id, **tmpl_data}
        
        return {"id": candidates[0][0], **candidates[0][1]}
    
    def _get_location_id(self, location_name: str) -> Optional[str]:
        """根据中文名获取地点ID"""
        locations = self.locations.get("locations", {})
        for loc_id, loc_data in locations.items():
            if loc_data.get("name_cn") == location_name:
                return loc_id
        return None
    
    def get_characters_at_location(self, location_name: str) -> List[str]:
        """获取指定地点的角色列表"""
        return [
            char_id for char_id, state in self.character_states.items()
            if state.get("location") == location_name and state.get("can_interact", True)
        ]
    
    def mark_event_triggered(self, event_id: str):
        """标记事件为已触发"""
        triggered = self.current_day.get("triggered_events", [])
        if event_id not in triggered:
            triggered.append(event_id)
        self.current_day["triggered_events"] = triggered
        save_json("world_state/current_day.json", self.current_day)
    
    def set_flag(self, flag_name: str, value: bool = True):
        """设置标记"""
        flags = self.current_day.get("flags", {})
        flags[flag_name] = value
        self.current_day["flags"] = flags
        save_json("world_state/current_day.json", self.current_day)
    
    def increment_event_count(self):
        """增加事件计数"""
        self.current_day["event_count"] = self.current_day.get("event_count", 0) + 1
        save_json("world_state/current_day.json", self.current_day)
    
    def set_phase(self, phase: str):
        """设置当前阶段"""
        self.current_day["phase"] = phase
        save_json("world_state/current_day.json", self.current_day)
    
    def next_day(self):
        """进入下一天"""
        self.current_day["day"] = self.current_day.get("day", 1) + 1
        self.current_day["phase"] = "dawn"
        self.current_day["event_count"] = 0
        self.current_day["daily_event_count"] = 0
        save_json("world_state/current_day.json", self.current_day)


# ============================================================================
# 导演API v2
# ============================================================================

class DirectorAPIv2:
    """导演API v2 - 整合事件系统"""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=get_api_key("director"))
        self.event_manager = EventManager()
    
    def process_turn(self, player_location: str) -> EventResult:
        """处理一个回合，返回事件结果"""
        
        # 1. 检查是否有待触发的固定事件
        fixed_event = self.event_manager.get_pending_fixed_event()
        
        if fixed_event:
            print(f"📌 触发固定事件: {fixed_event['name']}")
            return self._process_fixed_event(fixed_event)
        
        # 2. 没有固定事件，选择自由事件模板
        template = self.event_manager.select_free_event_template(player_location)
        print(f"🎲 选择自由事件模板: {template['name_cn']}")
        
        return self._process_free_event(template, player_location)
    
    def _process_fixed_event(self, event: Dict) -> EventResult:
        """处理固定事件"""
        event_id = event.get("id")
        
        # 检查是否是分歧事件
        if event.get("branch"):
            next_event = self.event_manager.check_branch(event)
            if next_event:
                # 标记当前事件，然后触发下一个
                self.event_manager.mark_event_triggered(event_id)
                # 递归处理下一个事件
                next_event_data = self.event_manager.fixed_events.get("fixed_events", {}).get(next_event)
                if next_event_data:
                    return self._process_fixed_event({"id": next_event, **next_event_data})
        
        # 处理脚本对话
        script = event.get("script", [])
        dialogue = self._convert_script_to_dialogue(script)
        
        # 处理选项（如果有）
        choices = None
        if event.get("player_action"):
            choices = self._generate_choices_for_fixed_event(event)
        
        # 处理结果
        outcomes = event.get("outcomes", {})
        
        # 标记事件为已触发
        self.event_manager.mark_event_triggered(event_id)
        
        # 设置标记
        for flag in event.get("flags_set", []):
            self.event_manager.set_flag(flag)
        
        # 检查阶段变化
        next_phase = event.get("next_phase")
        if next_phase:
            self.event_manager.set_phase(next_phase)
        
        # 检查是否进入下一天
        if event.get("next_day"):
            self.event_manager.next_day()
        
        # 检查游戏结束
        game_over = event.get("game_over", False)
        ending_type = event.get("ending_type")
        
        return EventResult(
            event_id=event_id,
            event_type="fixed",
            dialogue=dialogue,
            choices=choices,
            outcomes=outcomes,
            next_event=event.get("next_event"),
            next_phase=next_phase,
            flags_set=event.get("flags_set", []),
            game_over=game_over,
            ending_type=ending_type
        )
    
    def _process_free_event(self, template: Dict, player_location: str) -> EventResult:
        """处理自由事件"""
        template_id = template.get("id")
        
        # 获取该地点的角色
        chars_at_location = self.event_manager.get_characters_at_location(player_location)
        
        if not chars_at_location:
            # 没有角色，返回空闲事件
            return self._generate_idle_event(player_location)
        
        # 选择角色填充槽位
        slots = self._fill_template_slots(template, chars_at_location, player_location)
        
        # 调用API生成对话
        dialogue, choices, pregenerated = self._generate_dialogue_from_template(
            template, slots, player_location
        )
        
        # 增加事件计数
        self.event_manager.increment_event_count()
        
        return EventResult(
            event_id=f"free_{template_id}_{self.event_manager.current_day.get('event_count')}",
            event_type="free",
            dialogue=dialogue,
            choices={"prompt_cn": "你要怎么做？", "options": choices},
            outcomes={},
            next_event=None,
            next_phase=None
        )
    
    def _convert_script_to_dialogue(self, script: List[Dict]) -> List[Dict]:
        """将固定事件脚本转换为对话格式"""
        dialogue = []
        for line in script:
            dialogue.append({
                "speaker": line.get("speaker", "narrator"),
                "text_cn": line.get("text_cn", ""),
                "emotion": "neutral"
            })
        return dialogue
    
    def _generate_choices_for_fixed_event(self, event: Dict) -> Dict:
        """为固定事件生成选项（如投票）"""
        action = event.get("player_action")
        
        if action == "select_suspect":
            # 投票选择嫌疑人
            chars = self.event_manager.character_states
            options = []
            for char_id, state in chars.items():
                if state.get("status") == "alive":
                    options.append({
                        "id": char_id,
                        "text_cn": f"投票给 {char_id}",
                        "leads_to_badend": False  # 需要代码判断
                    })
            return {
                "prompt_cn": "你要投票给谁？",
                "options": options
            }
        
        return None
    
    def _fill_template_slots(self, template: Dict, chars: List[str], location: str) -> Dict:
        """填充模板槽位"""
        slots = template.get("slots", {})
        filled = {}
        
        available_chars = chars.copy()
        
        for slot_name, slot_def in slots.items():
            if isinstance(slot_def, dict):
                slot_type = slot_def.get("type")
                
                if slot_type in ["character_id", "character_id_or_player"]:
                    if available_chars:
                        char = random.choice(available_chars)
                        available_chars.remove(char)
                        filled[slot_name] = char
                    elif slot_type == "character_id_or_player":
                        filled[slot_name] = "player"
                
                elif slot_type == "location_id":
                    filled[slot_name] = location
                
                elif slot_type == "enum":
                    values = slot_def.get("values", [])
                    if values:
                        filled[slot_name] = random.choice(values)
                
                elif slot_type == "string":
                    examples = slot_def.get("examples", [])
                    if examples:
                        filled[slot_name] = random.choice(examples)
        
        return filled
    
    def _generate_dialogue_from_template(
        self, 
        template: Dict, 
        slots: Dict, 
        location: str
    ) -> tuple:
        """调用API生成对话"""
        
        template_name = template.get("name_cn", "事件")
        main_char = slots.get("character") or slots.get("character_a")
        
        if not main_char or main_char == "player":
            # 没有NPC，返回简单描述
            return [{"speaker": "narrator", "text_cn": f"你在{location}四处查看...", "emotion": "neutral"}], [], {}
        
        # 加载角色数据
        char_data = self._load_character_data(main_char)
        char_state = self.event_manager.character_states.get(main_char, {})
        
        # 构建prompt
        prompt = self._build_director_prompt(template, slots, char_data, char_state, location)
        
        # 调用API
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result = json.loads(clean_json_response(response.content[0].text))
            
            dialogue = result.get("dialogue", [])
            choices = result.get("choice_point", {}).get("options", [])
            pregenerated = result.get("pregenerated_responses", {})
            
            return dialogue, choices, pregenerated
            
        except Exception as e:
            print(f"❌ API调用失败: {e}")
            # 返回默认对话
            return [
                {"speaker": main_char, "text_cn": "......", "emotion": "neutral"}
            ], [], {}
    
    def _load_character_data(self, char_id: str) -> Dict:
        """加载角色数据"""
        char_path = Path(f"characters/{char_id}")
        
        try:
            core = load_yaml(char_path / "core.yaml")
            personality = load_yaml(char_path / "personality.yaml")
            speech = load_yaml(char_path / "speech.yaml")
            return {"core": core, "personality": personality, "speech": speech}
        except:
            return {
                "core": {"name": {"zh": char_id}},
                "personality": {"versions": {"simple": "性格不明"}},
                "speech": {"first_person": "我", "verbal_tics": []}
            }
    
    def _build_director_prompt(
        self, 
        template: Dict, 
        slots: Dict, 
        char_data: Dict, 
        char_state: Dict,
        location: str
    ) -> str:
        """构建导演API prompt"""
        
        core = char_data.get("core", {})
        personality = char_data.get("personality", {})
        speech = char_data.get("speech", {})
        
        char_name = core.get("name", {}).get("zh", slots.get("character", "角色"))
        
        prompt = f"""你是导演AI，为视觉小说游戏生成对话剧本。

【事件类型】{template.get('name_cn', '自由事件')}
【事件描述】{template.get('description', '')}

【主要角色】{char_name}
性格: {personality.get('versions', {}).get('simple', '未知')}
说话方式: 第一人称"{speech.get('first_person', '我')}"
口癖: {', '.join(speech.get('verbal_tics', [])[:3])}

【当前状态】
位置: {location}
压力: {char_state.get('stress', 50)}/100
情绪: {char_state.get('emotion', 'neutral')}
行为: {char_state.get('action', '站着')}

【槽位信息】
{json.dumps(slots, ensure_ascii=False, indent=2)}

【任务】
1. 生成3-5句符合角色性格的对话
2. 生成3个玩家选项（A正面、B中性、C危险）
3. 预生成每个选项的角色回应

【输出格式】严格JSON：
{{
  "dialogue": [
    {{"speaker": "{slots.get('character', 'character')}", "text_cn": "对话内容", "emotion": "情绪"}}
  ],
  "choice_point": {{
    "prompt_cn": "你要怎么回应？",
    "options": [
      {{"id": "A", "text_cn": "正面选项", "leads_to_badend": false}},
      {{"id": "B", "text_cn": "中性选项", "leads_to_badend": false}},
      {{"id": "C", "text_cn": "危险选项", "leads_to_badend": true}}
    ]
  }},
  "pregenerated_responses": {{
    "A": {{"dialogue": [{{"speaker": "{slots.get('character', 'character')}", "text_cn": "回应", "emotion": "情绪"}}], "effects": {{"stress": 0}}}},
    "B": {{"dialogue": [...], "effects": {{}}}},
    "C": {{"dialogue": [...], "effects": {{"stress": 10, "madness": 5}}}}
  }},
  "recommended_bgm": "推荐BGM名称"
}}

情绪只能用: happy/sad/angry/scared/nervous/calm/surprised/conflicted/neutral

请直接输出JSON，不要markdown标记。"""

        return prompt
    
    def _generate_idle_event(self, location: str) -> EventResult:
        """生成空闲事件（没有角色时）"""
        return EventResult(
            event_id="idle",
            event_type="free",
            dialogue=[
                {"speaker": "narrator", "text_cn": f"你在{location}四处张望，但没有看到任何人。", "emotion": "neutral"}
            ],
            choices=None,
            outcomes={},
            next_event=None,
            next_phase=None
        )
    
    def apply_outcomes(self, outcomes: Dict):
        """应用事件结果到角色状态"""
        chars = self.event_manager.character_states
        
        for target, effects in outcomes.items():
            if target == "all":
                # 应用到所有角色
                for char_id in chars:
                    self._apply_effects(char_id, effects)
            elif target == "all_present":
                # 应用到在场角色（需要知道位置）
                pass
            elif target.startswith("${"):
                # 变量引用，需要解析
                pass
            elif target in chars:
                self._apply_effects(target, effects)
        
        save_json("world_state/character_states.json", chars)
    
    def _apply_effects(self, char_id: str, effects: Dict):
        """应用效果到单个角色"""
        char = self.event_manager.character_states.get(char_id)
        if not char:
            return
        
        for key, value in effects.items():
            if key in ["stress", "madness"]:
                current = char.get(key, 0)
                char[key] = max(0, min(100, current + value))
            elif key == "status":
                char[key] = value
            elif key == "emotion":
                char[key] = value


# ============================================================================
# 测试
# ============================================================================

def test_director_v2():
    """测试导演API v2"""
    print("=" * 60)
    print("🎬 导演API v2 测试")
    print("=" * 60)
    
    director = DirectorAPIv2()
    
    # 测试1: 检查固定事件
    print("\n📌 检查待触发的固定事件...")
    fixed = director.event_manager.get_pending_fixed_event()
    if fixed:
        print(f"   发现固定事件: {fixed.get('name')} (优先级: {fixed.get('priority')})")
    else:
        print("   无待触发的固定事件")
    
    # 测试2: 选择自由事件模板
    print("\n🎲 选择自由事件模板...")
    template = director.event_manager.select_free_event_template("食堂")
    print(f"   选中模板: {template.get('name_cn')}")
    
    # 测试3: 获取地点角色
    print("\n👥 获取食堂的角色...")
    chars = director.event_manager.get_characters_at_location("食堂")
    print(f"   食堂角色: {chars}")
    
    # 测试4: 处理一个回合
    print("\n🎮 处理一个回合...")
    result = director.process_turn("食堂")
    
    print(f"\n【事件结果】")
    print(f"事件ID: {result.event_id}")
    print(f"事件类型: {result.event_type}")
    print(f"游戏结束: {result.game_over}")
    
    print(f"\n【对话】")
    for line in result.dialogue[:3]:  # 只显示前3行
        print(f"  {line['speaker']}: {line['text_cn'][:50]}...")
    
    if result.choices:
        print(f"\n【选项】")
        for opt in result.choices.get("options", [])[:3]:
            print(f"  {opt['id']}. {opt['text_cn']}")
    
    print("\n✅ 测试完成")


if __name__ == "__main__":
    test_director_v2()
