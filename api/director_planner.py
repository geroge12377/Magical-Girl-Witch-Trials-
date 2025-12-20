# ============================================================================
# 导演规划层 (Director Planner)
# ============================================================================
# 职责：
# 1. 分析当前游戏状态和上下文
# 2. 生成场景规划(ScenePlan)，包含多个beat
# 3. 为每个beat指定参与角色、情绪目标、张力曲线
# 4. 不生成具体对话，只生成剧本大纲
# ============================================================================

import anthropic
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import sys

# 添加父目录到路径以导入config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_api_key, MODEL, MAX_TOKENS

# 导入公共工具函数
from .utils import clean_json_response, fix_truncated_json, parse_json_with_diagnostics


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class Beat:
    """场景中的一个戏剧节拍"""
    beat_id: str
    beat_type: str  # "opening" | "development" | "tension" | "climax" | "resolution"
    description: str  # 这个beat要表达什么
    characters: List[str]  # 参与角色
    speaker_order: List[str]  # 说话顺序
    emotion_targets: Dict[str, str]  # 各角色情绪目标
    tension_level: int  # 1-10张力等级
    dialogue_count: int  # 建议对话行数
    direction_notes: str  # 导演指示

@dataclass
class ScenePlan:
    """场景规划"""
    scene_id: str
    scene_name: str
    location: str
    time_estimate_minutes: int  # 预计5-10分钟
    total_beats: int
    beats: List[Beat]
    overall_arc: str  # 整体情感弧线描述
    key_moments: List[str]  # 关键时刻
    player_choice_point: Optional[Dict]  # 玩家选择点
    outcomes: Dict[str, Any]  # 可能的结果
    recommended_bgm: str


# ============================================================================
# 工具函数
# ============================================================================

def load_json(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_yaml(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# ============================================================================
# 导演规划层
# ============================================================================

class DirectorPlanner:
    """导演规划层 - 生成场景规划(ScenePlan)"""

    def __init__(self, project_root: Path = None):
        self.client = anthropic.Anthropic(api_key=get_api_key("director"))
        self.project_root = project_root or Path(__file__).parent.parent
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """加载prompt模板"""
        prompt_path = self.project_root / "prompts" / "director_planner_prompt.txt"
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """默认prompt模板"""
        return """你是一位经验丰富的视觉小说导演。你的任务是规划一个场景的剧本大纲。

【当前状态】
{context}

【在场角色】
{characters_info}

【任务】
请规划一个5-10分钟的场景，包含3-5个beat（戏剧节拍）。
每个beat应该有明确的情绪目标和张力曲线。

【输出格式】严格JSON：
{output_format}
"""

    def load_game_context(self) -> Dict:
        """加载游戏上下文"""
        current_day = load_json(self.project_root / "world_state" / "current_day.json")
        character_states = load_json(self.project_root / "world_state" / "character_states.json")

        return {
            "day": current_day.get("day", 1),
            "phase": current_day.get("phase", "free_time"),
            "event_count": current_day.get("event_count", 0),
            "flags": current_day.get("flags", {}),
            "triggered_events": current_day.get("triggered_events", []),
            "character_states": character_states
        }

    def load_character_data(self, char_id: str) -> Dict:
        """加载角色完整数据"""
        char_path = self.project_root / "characters" / char_id

        try:
            core = load_yaml(char_path / "core.yaml")
            personality = load_yaml(char_path / "personality.yaml")
            speech = load_yaml(char_path / "speech.yaml")
            relationships = load_yaml(char_path / "relationships.yaml") if (char_path / "relationships.yaml").exists() else {}

            return {
                "core": core,
                "personality": personality,
                "speech": speech,
                "relationships": relationships
            }
        except Exception as e:
            print(f"[DirectorPlanner] 加载角色数据失败 {char_id}: {e}")
            return {
                "core": {"name": {"zh": char_id}},
                "personality": {"versions": {"simple": "性格未知"}},
                "speech": {"first_person": "我"},
                "relationships": {}
            }

    def get_characters_at_location(self, location: str) -> List[str]:
        """获取指定地点的角色列表"""
        character_states = load_json(self.project_root / "world_state" / "character_states.json")
        return [
            char_id for char_id, state in character_states.items()
            if state.get("location") == location
            and state.get("status") == "alive"
            and state.get("can_interact", True)
        ]

    def plan_scene(
        self,
        location: str,
        scene_type: str = "free",  # "free" | "fixed" | "investigation" | "trial"
        fixed_event_data: Optional[Dict] = None,
        player_location: str = None
    ) -> ScenePlan:
        """生成场景规划"""

        # 1. 加载上下文
        context = self.load_game_context()

        # 2. 获取在场角色
        chars_at_location = self.get_characters_at_location(location)
        if not chars_at_location:
            return self._create_empty_scene(location)

        # 3. 加载角色数据
        characters_info = {}
        for char_id in chars_at_location[:6]:  # 最多6个角色
            char_data = self.load_character_data(char_id)
            state = context["character_states"].get(char_id, {})

            characters_info[char_id] = {
                "name": char_data["core"].get("name", {}).get("zh", char_id),
                "personality": char_data["personality"].get("versions", {}).get("simple", "未知"),
                "stress": state.get("stress", 50),
                "madness": state.get("madness", 0),
                "emotion": state.get("emotion", "neutral"),
                "action": state.get("action", "站着")
            }

        # 4. 构建prompt
        prompt = self._build_planner_prompt(context, characters_info, location, scene_type, fixed_event_data)

        # 5. 调用API
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            raw_text = response.content[0].text
            print(f"[DirectorPlanner] API 响应长度: {len(raw_text)} 字符")

            # 使用公共函数解析 JSON（三次尝试：原始→清理→修复）
            result = parse_json_with_diagnostics(raw_text, "场景规划", "DirectorPlanner")
            return self._parse_scene_plan(result, location)

        except json.JSONDecodeError as e:
            print(f"[DirectorPlanner] JSON 解析最终失败，使用回退场景")
            return self._create_fallback_scene(location, chars_at_location)
        except Exception as e:
            print(f"[DirectorPlanner] API调用失败: {type(e).__name__}: {e}")
            return self._create_fallback_scene(location, chars_at_location)

    def _build_planner_prompt(
        self,
        context: Dict,
        characters_info: Dict,
        location: str,
        scene_type: str,
        fixed_event_data: Optional[Dict]
    ) -> str:
        """构建规划层prompt"""

        # 格式化上下文
        context_str = f"""第{context['day']}天 - {context['phase']}阶段
事件计数: {context['event_count']}
已触发事件: {', '.join(context['triggered_events'][-5:]) if context['triggered_events'] else '无'}
当前位置: {location}
场景类型: {scene_type}"""

        # 格式化角色信息
        chars_str = ""
        for char_id, info in characters_info.items():
            chars_str += f"""
【{info['name']}】({char_id})
  性格: {info['personality'][:100]}...
  压力: {info['stress']}/100 | 疯狂: {info['madness']}/100
  情绪: {info['emotion']} | 行为: {info['action']}
"""

        # 输出格式
        output_format = """{
  "scene_id": "场景ID",
  "scene_name": "场景名称",
  "location": "地点",
  "time_estimate_minutes": 5-10,
  "overall_arc": "整体情感弧线描述",
  "beats": [
    {
      "beat_id": "beat_1",
      "beat_type": "opening|development|tension|climax|resolution",
      "description": "这个beat要表达什么",
      "characters": ["char_id1", "char_id2"],
      "speaker_order": ["char_id1", "char_id2", "char_id1"],
      "emotion_targets": {"char_id1": "情绪", "char_id2": "情绪"},
      "tension_level": 1-10,
      "dialogue_count": 3-6,
      "direction_notes": "导演指示"
    }
  ],
  "key_moments": ["关键时刻1", "关键时刻2"],
  "player_choice_point": {
    "after_beat": "beat_id",
    "prompt": "提示语",
    "options": [
      {"id": "A", "text": "选项A", "leads_to": "正面"},
      {"id": "B", "text": "选项B", "leads_to": "中性"},
      {"id": "C", "text": "选项C", "leads_to": "危险"}
    ]
  },
  "outcomes": {
    "stress_changes": {"char_id": 变化值},
    "relationship_changes": {},
    "flags_to_set": []
  },
  "recommended_bgm": "BGM名称"
}"""

        # 组合prompt
        prompt = f"""你是一位经验丰富的视觉小说导演。你的任务是规划一个场景的剧本大纲。

【游戏背景】
《魔法少女的魔女审判》是一款推理解谜视觉小说。
13名少女被关在孤岛监牢中，如果发生杀人事件需要进行魔女审判投票。
压力(stress)和疯狂(madness)值会影响角色行为，madness>70可能触发杀人。

【当前状态】
{context_str}

【在场角色】
{chars_str}

【任务】
请规划一个5-10分钟的场景，包含3-5个beat（戏剧节拍）。
- opening: 场景开场，建立氛围
- development: 发展，角色互动深入
- tension: 紧张，冲突或压力升级
- climax: 高潮，情感爆发点
- resolution: 收尾，情绪缓和

张力曲线建议：开场3 → 发展5 → 紧张7 → 高潮8-9 → 收尾4

【输出格式】严格JSON：
{output_format}

请直接输出JSON，不要使用markdown代码块。"""

        return prompt

    def _parse_scene_plan(self, result: Dict, location: str) -> ScenePlan:
        """解析API返回的场景规划"""
        beats = []
        for beat_data in result.get("beats", []):
            beat = Beat(
                beat_id=beat_data.get("beat_id", "unknown"),
                beat_type=beat_data.get("beat_type", "development"),
                description=beat_data.get("description", ""),
                characters=beat_data.get("characters", []),
                speaker_order=beat_data.get("speaker_order", []),
                emotion_targets=beat_data.get("emotion_targets", {}),
                tension_level=beat_data.get("tension_level", 5),
                dialogue_count=beat_data.get("dialogue_count", 3),
                direction_notes=beat_data.get("direction_notes", "")
            )
            beats.append(beat)

        return ScenePlan(
            scene_id=result.get("scene_id", f"scene_{location}"),
            scene_name=result.get("scene_name", "未命名场景"),
            location=location,
            time_estimate_minutes=result.get("time_estimate_minutes", 5),
            total_beats=len(beats),
            beats=beats,
            overall_arc=result.get("overall_arc", ""),
            key_moments=result.get("key_moments", []),
            player_choice_point=result.get("player_choice_point"),
            outcomes=result.get("outcomes", {}),
            recommended_bgm=result.get("recommended_bgm", "ambient_tension")
        )

    def _create_empty_scene(self, location: str) -> ScenePlan:
        """创建空场景（无角色时）"""
        return ScenePlan(
            scene_id=f"empty_{location}",
            scene_name="空旷的场所",
            location=location,
            time_estimate_minutes=1,
            total_beats=1,
            beats=[
                Beat(
                    beat_id="beat_empty",
                    beat_type="opening",
                    description="玩家独自在场，没有其他人",
                    characters=[],
                    speaker_order=["narrator"],
                    emotion_targets={},
                    tension_level=2,
                    dialogue_count=1,
                    direction_notes="简短描述空旷的环境"
                )
            ],
            overall_arc="平静的独处时刻",
            key_moments=[],
            player_choice_point=None,
            outcomes={},
            recommended_bgm="ambient_quiet"
        )

    def _create_fallback_scene(self, location: str, characters: List[str]) -> ScenePlan:
        """创建回退场景（API失败时）"""
        main_char = characters[0] if characters else "unknown"

        return ScenePlan(
            scene_id=f"fallback_{location}",
            scene_name="偶遇",
            location=location,
            time_estimate_minutes=3,
            total_beats=2,
            beats=[
                Beat(
                    beat_id="beat_1",
                    beat_type="opening",
                    description="玩家在此遇到角色",
                    characters=[main_char],
                    speaker_order=[main_char],
                    emotion_targets={main_char: "neutral"},
                    tension_level=3,
                    dialogue_count=2,
                    direction_notes="简单的问候交流"
                ),
                Beat(
                    beat_id="beat_2",
                    beat_type="resolution",
                    description="简短交流后结束",
                    characters=[main_char],
                    speaker_order=[main_char],
                    emotion_targets={main_char: "neutral"},
                    tension_level=2,
                    dialogue_count=2,
                    direction_notes="告别或转移话题"
                )
            ],
            overall_arc="简短的偶遇和交流",
            key_moments=[],
            player_choice_point={
                "after_beat": "beat_1",
                "prompt": "你要怎么回应？",
                "options": [
                    {"id": "A", "text": "友好地回应", "leads_to": "正面"},
                    {"id": "B", "text": "保持距离", "leads_to": "中性"},
                    {"id": "C", "text": "冷淡以对", "leads_to": "负面"}
                ]
            },
            outcomes={},
            recommended_bgm="ambient_neutral"
        )


# ============================================================================
# 测试
# ============================================================================

def test_director_planner():
    """测试导演规划层"""
    print("=" * 60)
    print("🎬 导演规划层测试")
    print("=" * 60)

    planner = DirectorPlanner()

    # 测试规划场景
    print("\n📋 规划食堂场景...")
    scene_plan = planner.plan_scene(location="食堂", scene_type="free")

    print(f"\n【场景规划】")
    print(f"场景ID: {scene_plan.scene_id}")
    print(f"场景名: {scene_plan.scene_name}")
    print(f"预计时长: {scene_plan.time_estimate_minutes}分钟")
    print(f"Beat数量: {scene_plan.total_beats}")
    print(f"整体弧线: {scene_plan.overall_arc}")

    print(f"\n【Beat列表】")
    for beat in scene_plan.beats:
        print(f"  {beat.beat_id} ({beat.beat_type})")
        print(f"    描述: {beat.description[:50]}...")
        print(f"    角色: {beat.characters}")
        print(f"    张力: {beat.tension_level}/10")
        print(f"    对话数: {beat.dialogue_count}")

    if scene_plan.player_choice_point:
        print(f"\n【玩家选择点】")
        print(f"  位置: {scene_plan.player_choice_point.get('after_beat')}")
        for opt in scene_plan.player_choice_point.get('options', []):
            print(f"  {opt['id']}. {opt['text']}")

    print("\n✅ 测试完成")
    return scene_plan


if __name__ == "__main__":
    test_director_planner()
