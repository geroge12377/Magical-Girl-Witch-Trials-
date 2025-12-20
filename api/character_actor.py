# ============================================================================
# 角色演出层 (Character Actor)
# ============================================================================
# 职责：
# 1. 根据导演规划层的Beat指令生成具体对话
# 2. 确保对话符合角色性格、口癖、说话方式
# 3. 根据情绪目标和张力等级调整对话语气
# 4. 生成玩家选项的预生成回应
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

# 导入Beat类型
from .director_planner import Beat, ScenePlan

# 导入公共工具函数
from .utils import parse_json_with_diagnostics


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class DialogueLine:
    """单行对话"""
    speaker: str  # 角色ID或"narrator"
    text_cn: str  # 中文对话
    emotion: str  # 情绪
    action: Optional[str] = None  # 伴随动作（可选）

@dataclass
class DialogueOutput:
    """对话输出"""
    beat_id: str
    dialogue: List[DialogueLine]
    effects: Dict[str, Any]  # 状态变化效果

@dataclass
class ChoiceResponse:
    """选项回应"""
    choice_id: str
    dialogue: List[DialogueLine]
    effects: Dict[str, Any]


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
# 角色演出层
# ============================================================================

class CharacterActor:
    """角色演出层 - 根据Beat生成对话"""

    def __init__(self, project_root: Path = None):
        self.client = anthropic.Anthropic(api_key=get_api_key("character"))
        self.project_root = project_root or Path(__file__).parent.parent
        self.prompt_template = self._load_prompt_template()
        self._character_cache = {}  # 角色数据缓存

    def _load_prompt_template(self) -> str:
        """加载prompt模板"""
        prompt_path = self.project_root / "prompts" / "character_actor_prompt.txt"
        if prompt_path.exists():
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """默认prompt模板"""
        return """你是一位专业的视觉小说对话编剧。根据导演指示生成角色对话。

【角色信息】
{character_info}

【导演指示】
{beat_info}

【任务】
生成符合角色性格的对话，注意：
1. 使用角色特定的第一人称
2. 体现角色口癖和说话习惯
3. 情绪要符合目标情绪
4. 张力要符合指定等级

【输出格式】JSON
{output_format}
"""

    def load_character_data(self, char_id: str) -> Dict:
        """加载角色数据（带缓存）"""
        if char_id in self._character_cache:
            return self._character_cache[char_id]

        char_path = self.project_root / "characters" / char_id

        try:
            core = load_yaml(char_path / "core.yaml")
            personality = load_yaml(char_path / "personality.yaml")
            speech = load_yaml(char_path / "speech.yaml")

            data = {
                "core": core,
                "personality": personality,
                "speech": speech
            }
            self._character_cache[char_id] = data
            return data
        except Exception as e:
            print(f"[CharacterActor] 加载角色数据失败 {char_id}: {e}")
            return {
                "core": {"name": {"zh": char_id}},
                "personality": {"versions": {"simple": "性格未知"}},
                "speech": {"first_person": "我", "verbal_tics": []}
            }

    def load_character_state(self, char_id: str) -> Dict:
        """加载角色当前状态"""
        try:
            states = load_json(self.project_root / "world_state" / "character_states.json")
            return states.get(char_id, {
                "stress": 50,
                "madness": 0,
                "emotion": "neutral",
                "location": "未知"
            })
        except:
            return {"stress": 50, "madness": 0, "emotion": "neutral"}

    def generate_dialogue_for_beat(self, beat: Beat) -> DialogueOutput:
        """根据Beat生成对话"""

        if not beat.characters:
            # 无角色，生成旁白
            return DialogueOutput(
                beat_id=beat.beat_id,
                dialogue=[DialogueLine(
                    speaker="narrator",
                    text_cn="四周静悄悄的...",
                    emotion="neutral"
                )],
                effects={}
            )

        # 收集角色信息
        characters_info = {}
        for char_id in beat.characters:
            char_data = self.load_character_data(char_id)
            char_state = self.load_character_state(char_id)

            characters_info[char_id] = {
                "name": char_data["core"].get("name", {}).get("zh", char_id),
                "personality": char_data["personality"].get("versions", {}).get("simple", ""),
                "first_person": char_data["speech"].get("first_person", "我"),
                "verbal_tics": char_data["speech"].get("verbal_tics", [])[:3],
                "tone": char_data["speech"].get("tone_by_emotion", {}),
                "stress": char_state.get("stress", 50),
                "emotion": char_state.get("emotion", "neutral"),
                "target_emotion": beat.emotion_targets.get(char_id, "neutral")
            }

        # 构建prompt
        prompt = self._build_actor_prompt(beat, characters_info)

        # 调用API
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            raw_text = response.content[0].text
            # 使用公共函数解析 JSON（三次尝试：原始→清理→修复）
            result = parse_json_with_diagnostics(raw_text, "对话生成", "CharacterActor")
            return self._parse_dialogue_output(beat.beat_id, result)

        except json.JSONDecodeError as e:
            print(f"[CharacterActor] JSON 解析最终失败，使用回退对话")
            return self._create_fallback_dialogue(beat, characters_info)
        except Exception as e:
            print(f"[CharacterActor] API调用失败: {type(e).__name__}: {e}")
            return self._create_fallback_dialogue(beat, characters_info)

    def generate_choice_responses(
        self,
        choice_point: Dict,
        characters: List[str]
    ) -> Dict[str, ChoiceResponse]:
        """预生成玩家选项的回应"""

        if not choice_point or not characters:
            return {}

        main_char = characters[0]
        char_data = self.load_character_data(main_char)
        char_state = self.load_character_state(main_char)

        # 构建prompt
        prompt = self._build_choice_response_prompt(
            choice_point,
            main_char,
            char_data,
            char_state
        )

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            raw_text = response.content[0].text
            # 使用公共函数解析 JSON（三次尝试：原始→清理→修复）
            result = parse_json_with_diagnostics(raw_text, "选项回应", "CharacterActor")
            return self._parse_choice_responses(result)

        except json.JSONDecodeError as e:
            print(f"[CharacterActor] JSON 解析最终失败，使用回退回应")
            return self._create_fallback_responses(choice_point, main_char)
        except Exception as e:
            print(f"[CharacterActor] 预生成回应失败: {type(e).__name__}: {e}")
            return self._create_fallback_responses(choice_point, main_char)

    def _build_actor_prompt(self, beat: Beat, characters_info: Dict) -> str:
        """构建演出层prompt"""

        # 格式化角色信息
        chars_str = ""
        for char_id, info in characters_info.items():
            chars_str += f"""
【{info['name']}】({char_id})
  性格: {info['personality'][:80]}
  第一人称: 「{info['first_person']}」
  口癖: {', '.join(info['verbal_tics']) if info['verbal_tics'] else '无'}
  当前情绪: {info['emotion']} → 目标情绪: {info['target_emotion']}
  压力: {info['stress']}/100
"""

        # 输出格式
        output_format = """{
  "dialogue": [
    {"speaker": "角色ID", "text_cn": "对话内容", "emotion": "情绪", "action": "动作描述(可选)"}
  ],
  "effects": {
    "角色ID": {"stress": 变化值, "emotion": "新情绪"}
  }
}"""

        prompt = f"""你是一位专业的视觉小说对话编剧。根据导演指示生成角色对话。

【游戏背景】
《魔法少女的魔女审判》- 13名少女被关在孤岛监牢的推理解谜游戏。

【Beat信息】
类型: {beat.beat_type}
描述: {beat.description}
说话顺序: {' → '.join(beat.speaker_order)}
张力等级: {beat.tension_level}/10
目标对话数: {beat.dialogue_count}行
导演指示: {beat.direction_notes}

【角色信息】
{chars_str}

【任务】
按照说话顺序生成{beat.dialogue_count}行对话。要求：
1. 每个角色使用其专属第一人称
2. 适当融入角色口癖（不要每句都用）
3. 情绪从当前情绪自然过渡到目标情绪
4. 张力{beat.tension_level}/10：{"平静舒缓" if beat.tension_level <= 3 else "略有紧张" if beat.tension_level <= 5 else "紧张升级" if beat.tension_level <= 7 else "情绪激动"}
5. 对话要自然、符合角色性格

【输出格式】严格JSON：
{output_format}

情绪只能用: happy/sad/angry/scared/nervous/calm/surprised/conflicted/neutral

请直接输出JSON，不要使用markdown代码块。"""

        return prompt

    def _build_choice_response_prompt(
        self,
        choice_point: Dict,
        char_id: str,
        char_data: Dict,
        char_state: Dict
    ) -> str:
        """构建选项回应prompt"""

        name = char_data["core"].get("name", {}).get("zh", char_id)
        personality = char_data["personality"].get("versions", {}).get("simple", "")
        first_person = char_data["speech"].get("first_person", "我")
        verbal_tics = char_data["speech"].get("verbal_tics", [])[:3]

        options = choice_point.get("options", [])
        options_str = "\n".join([f"  {opt['id']}. {opt['text']} ({opt.get('leads_to', '未知')})" for opt in options])

        prompt = f"""你是一位专业的视觉小说对话编剧。为玩家的每个选项预生成角色回应。

【角色】{name} ({char_id})
性格: {personality[:80]}
第一人称: 「{first_person}」
口癖: {', '.join(verbal_tics) if verbal_tics else '无'}
当前压力: {char_state.get('stress', 50)}/100
当前情绪: {char_state.get('emotion', 'neutral')}

【玩家选项】
提示: {choice_point.get('prompt', '你要怎么回应？')}
{options_str}

【任务】
为每个选项生成角色的回应对话（1-2句）和效果。
- A选项通常是正面选择，角色反应积极
- B选项通常是中性选择，角色反应平淡
- C选项通常是负面/危险选择，角色反应消极或紧张

【输出格式】严格JSON：
{{
  "A": {{
    "dialogue": [{{"speaker": "{char_id}", "text_cn": "回应内容", "emotion": "情绪"}}],
    "effects": {{"stress": -5, "affection": 3}}
  }},
  "B": {{
    "dialogue": [...],
    "effects": {{"stress": 0, "affection": 0}}
  }},
  "C": {{
    "dialogue": [...],
    "effects": {{"stress": 10, "madness": 3, "affection": -5}}
  }}
}}

请直接输出JSON。"""

        return prompt

    def _parse_dialogue_output(self, beat_id: str, result: Dict) -> DialogueOutput:
        """解析对话输出"""
        dialogue = []
        for line in result.get("dialogue", []):
            dialogue.append(DialogueLine(
                speaker=line.get("speaker", "narrator"),
                text_cn=line.get("text_cn", "..."),
                emotion=line.get("emotion", "neutral"),
                action=line.get("action")
            ))

        return DialogueOutput(
            beat_id=beat_id,
            dialogue=dialogue,
            effects=result.get("effects", {})
        )

    def _parse_choice_responses(self, result: Dict) -> Dict[str, ChoiceResponse]:
        """解析选项回应"""
        responses = {}

        for choice_id in ["A", "B", "C"]:
            if choice_id in result:
                choice_data = result[choice_id]
                dialogue = []
                for line in choice_data.get("dialogue", []):
                    dialogue.append(DialogueLine(
                        speaker=line.get("speaker", "unknown"),
                        text_cn=line.get("text_cn", "..."),
                        emotion=line.get("emotion", "neutral"),
                        action=line.get("action")
                    ))

                responses[choice_id] = ChoiceResponse(
                    choice_id=choice_id,
                    dialogue=dialogue,
                    effects=choice_data.get("effects", {})
                )

        return responses

    def _create_fallback_dialogue(self, beat: Beat, characters_info: Dict) -> DialogueOutput:
        """创建回退对话（API失败时）"""
        dialogue = []

        for i, speaker in enumerate(beat.speaker_order[:beat.dialogue_count]):
            if speaker == "narrator":
                dialogue.append(DialogueLine(
                    speaker="narrator",
                    text_cn="...",
                    emotion="neutral"
                ))
            elif speaker in characters_info:
                info = characters_info[speaker]
                dialogue.append(DialogueLine(
                    speaker=speaker,
                    text_cn="......",
                    emotion=info.get("target_emotion", "neutral")
                ))

        return DialogueOutput(
            beat_id=beat.beat_id,
            dialogue=dialogue if dialogue else [DialogueLine("narrator", "...", "neutral")],
            effects={}
        )

    def _create_fallback_responses(
        self,
        choice_point: Dict,
        char_id: str
    ) -> Dict[str, ChoiceResponse]:
        """创建回退选项回应"""
        return {
            "A": ChoiceResponse("A", [DialogueLine(char_id, "...嗯。", "calm")], {"stress": -5}),
            "B": ChoiceResponse("B", [DialogueLine(char_id, "......", "neutral")], {}),
            "C": ChoiceResponse("C", [DialogueLine(char_id, "...什么？", "nervous")], {"stress": 5})
        }

    def generate_scene_dialogue(self, scene_plan: ScenePlan) -> List[DialogueOutput]:
        """生成整个场景的对话"""
        all_dialogue = []

        for beat in scene_plan.beats:
            print(f"  [CharacterActor] 生成 {beat.beat_id} 对话...")
            dialogue_output = self.generate_dialogue_for_beat(beat)
            all_dialogue.append(dialogue_output)

        return all_dialogue


# ============================================================================
# 测试
# ============================================================================

def test_character_actor():
    """测试角色演出层"""
    print("=" * 60)
    print("🎭 角色演出层测试")
    print("=" * 60)

    actor = CharacterActor()

    # 创建测试Beat
    test_beat = Beat(
        beat_id="test_beat_1",
        beat_type="development",
        description="两个角色在食堂偶遇，简短交谈",
        characters=["aima", "hiro"],
        speaker_order=["aima", "hiro", "aima"],
        emotion_targets={"aima": "nervous", "hiro": "defiant"},
        tension_level=4,
        dialogue_count=3,
        direction_notes="艾玛试图搭话，希罗态度冷淡但不拒绝"
    )

    print("\n📝 测试Beat信息:")
    print(f"  类型: {test_beat.beat_type}")
    print(f"  描述: {test_beat.description}")
    print(f"  角色: {test_beat.characters}")

    print("\n💬 生成对话...")
    dialogue_output = actor.generate_dialogue_for_beat(test_beat)

    print(f"\n【生成的对话】")
    for line in dialogue_output.dialogue:
        action_str = f" *{line.action}*" if line.action else ""
        print(f"  [{line.emotion}] {line.speaker}: {line.text_cn}{action_str}")

    print(f"\n【效果】")
    print(f"  {dialogue_output.effects}")

    # 测试选项回应
    print("\n📋 测试预生成选项回应...")
    test_choice_point = {
        "prompt": "你要怎么回应？",
        "options": [
            {"id": "A", "text": "友好地打招呼", "leads_to": "正面"},
            {"id": "B", "text": "点头示意", "leads_to": "中性"},
            {"id": "C", "text": "无视她", "leads_to": "负面"}
        ]
    }

    responses = actor.generate_choice_responses(test_choice_point, ["hiro"])

    print(f"\n【预生成回应】")
    for choice_id, response in responses.items():
        print(f"  {choice_id}:")
        for line in response.dialogue:
            print(f"    [{line.emotion}] {line.speaker}: {line.text_cn}")
        print(f"    效果: {response.effects}")

    print("\n✅ 测试完成")


if __name__ == "__main__":
    test_character_actor()
