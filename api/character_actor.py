# ============================================================================
# 角色演出层 (Character Actor)
# ============================================================================
# 职责：
# 1. 根据导演规划层的Beat指令生成具体对话
# 2. 确保对话符合角色性格、口癖、说话方式
# 3. 根据情绪目标和张力等级调整对话语气
# 4. 生成玩家选项的预生成回应
# 5. 【v10新增】空内容检测+重试、幻觉角色名修正、地点一致性验证
# ============================================================================

import anthropic
import json
import yaml
import re
import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
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
    """单行对话（双语）"""
    speaker: str  # 角色ID或"narrator"
    text_cn: str  # 中文对话（显示用，第一人称统一用「我」）
    text_jp: str  # 日文对话（TTS用，保留原口癖）
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

    # ============================================================================
    # 【v10新增】角色名白名单 - 防止幻觉角色名
    # ============================================================================
    VALID_CHARACTERS = {
        # ID: (中文名, 日文名, 别名列表)
        "aima": ("艾玛", "エマ", ["桜羽艾玛", "艾玛酱"]),
        "hiro": ("希罗", "ヒロ", ["寻", "二階堂希罗", "希罗酱"]),
        "anan": ("安安", "アンアン", ["夏目安安", "安安酱"]),
        "noah": ("诺亚", "ノア", ["城ヶ崎诺亚", "诺亚酱"]),
        "reia": ("蕾雅", "レイア", ["蓮見蕾雅", "蕾雅酱"]),
        "miria": ("米莉亚", "ミリア", ["佐伯米莉亚", "米莉亚酱"]),
        "margo": ("玛尔戈", "マーゴ", ["玛格", "宝生玛尔戈", "玛尔戈酱"]),
        "nanoka": ("菜乃香", "ナノカ", ["黒部菜乃香", "菜乃香酱"]),
        "arisa": ("爱丽莎", "アリサ", ["紫藤爱丽莎", "爱丽莎酱"]),
        "sherry": ("雪莉", "シェリー", ["橘雪莉", "雪莉酱"]),
        "hannah": ("汉娜", "ハンナ", ["遠野汉娜", "汉娜酱"]),
        "coco": ("可可", "ココ", ["沢渡可可", "可可酱"]),
        "meruru": ("梅露露", "メルル", ["冰上梅露露", "梅露露酱"]),
        "yuki": ("月代雪", "ユキ", ["典狱长"]),
    }

    # 所有有效名字的集合（用于快速查找）
    VALID_NAMES = set()
    for char_id, (cn, jp, aliases) in VALID_CHARACTERS.items():
        VALID_NAMES.add(cn)
        VALID_NAMES.add(jp)
        VALID_NAMES.add(char_id)
        VALID_NAMES.update(aliases)

    # 常见幻觉角色名（日系名字模式）
    HALLUCINATION_PATTERNS = [
        "美咲", "亚美", "千夏", "真由", "沙织", "花子", "樱", "雪菜",
        "彩香", "美月", "优子", "理沙", "惠", "麻衣", "由纪", "明日香",
        "香织", "友美", "智子", "加奈", "美穗", "纯子", "裕子", "京子",
    ]

    # ============================================================================
    # 【v10新增】地点关键词映射 - 防止地点描写不匹配
    # ============================================================================
    LOCATION_KEYWORDS = {
        "食堂": ["食堂", "餐桌", "饭菜", "餐具", "厨房", "用餐", "餐盘", "筷子"],
        "牢房区": ["牢房", "铁栏", "牢门", "囚室", "床铺", "狭小", "铁门", "牢笼"],
        "图书室": ["图书室", "书架", "书本", "阅读", "书页", "书籍", "图书", "翻阅"],
        "庭院": ["庭院", "阳光", "花草", "树木", "天空", "户外", "草地", "微风"],
        "走廊": ["走廊", "长廊", "通道", "脚步声", "回响", "窗户", "过道"],
    }

    # 地点冲突词（出现这些词说明地点描写错了）
    LOCATION_CONFLICTS = {
        "食堂": ["书架", "书本", "牢房", "铁栏", "花草", "草地"],
        "牢房区": ["餐桌", "饭菜", "书架", "阳光", "花草", "书本"],
        "图书室": ["餐桌", "饭菜", "铁栏", "牢房", "花草", "草地"],
        "庭院": ["书架", "餐桌", "铁栏", "牢房", "走廊里"],
        "走廊": ["书架", "餐桌", "牢房里", "庭院里", "花草"],
    }

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
                    text_jp="辺りは静まり返っている...",
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
        """解析对话输出（双语）"""
        dialogue = []
        for line in result.get("dialogue", []):
            text_cn = line.get("text_cn", "...")
            text_jp = line.get("text_jp", text_cn)  # 如果没有日文，使用中文
            dialogue.append(DialogueLine(
                speaker=line.get("speaker", "narrator"),
                text_cn=text_cn,
                text_jp=text_jp,
                emotion=line.get("emotion", "neutral"),
                action=line.get("action")
            ))

        return DialogueOutput(
            beat_id=beat_id,
            dialogue=dialogue,
            effects=result.get("effects", {})
        )

    def _parse_choice_responses(self, result: Dict) -> Dict[str, ChoiceResponse]:
        """解析选项回应（双语）"""
        responses = {}

        for choice_id in ["A", "B", "C"]:
            if choice_id in result:
                choice_data = result[choice_id]
                dialogue = []
                for line in choice_data.get("dialogue", []):
                    text_cn = line.get("text_cn", "...")
                    text_jp = line.get("text_jp", text_cn)
                    dialogue.append(DialogueLine(
                        speaker=line.get("speaker", "unknown"),
                        text_cn=text_cn,
                        text_jp=text_jp,
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
                    text_jp="...",
                    emotion="neutral"
                ))
            elif speaker in characters_info:
                info = characters_info[speaker]
                dialogue.append(DialogueLine(
                    speaker=speaker,
                    text_cn="......",
                    text_jp="......",
                    emotion=info.get("target_emotion", "neutral")
                ))

        return DialogueOutput(
            beat_id=beat.beat_id,
            dialogue=dialogue if dialogue else [DialogueLine("narrator", "...", "...", "neutral")],
            effects={}
        )

    def _create_fallback_responses(
        self,
        choice_point: Dict,
        char_id: str
    ) -> Dict[str, ChoiceResponse]:
        """创建回退选项回应（双语）"""
        return {
            "A": ChoiceResponse("A", [DialogueLine(char_id, "...嗯。", "...うん。", "calm")], {"stress": -5}),
            "B": ChoiceResponse("B", [DialogueLine(char_id, "......", "......", "neutral")], {}),
            "C": ChoiceResponse("C", [DialogueLine(char_id, "...什么？", "...何？", "nervous")], {"stress": 5})
        }

    # ============================================================================
    # 【v10新增】空内容检测与回退
    # ============================================================================

    def _check_empty_beats(self, outputs: List[DialogueOutput]) -> List[str]:
        """【v11改进】检查哪些 Beat 内容为空或过短"""
        empty = []
        for output in outputs:
            # 检查对话列表是否为空
            if not output.dialogue:
                empty.append(output.beat_id)
                continue

            # 检查是否只有空字符串或过短内容（至少10个字符）
            has_content = any(
                line.text_cn and line.text_cn.strip() and len(line.text_cn.strip()) > 10
                for line in output.dialogue
            )
            if not has_content:
                empty.append(output.beat_id)

        return empty

    def _fill_empty_beats_with_fallback(
        self,
        outputs: List[DialogueOutput],
        empty_beats: List[str],
        beats: List,  # List[Beat]
        location: str = None  # 【v11新增】传入地点
    ) -> List[DialogueOutput]:
        """【v11改进】用回退内容填充空 Beat"""
        for output in outputs:
            if output.beat_id in empty_beats:
                # 找到对应的 Beat 信息
                beat_info = next(
                    (b for b in beats if b.beat_id == output.beat_id),
                    None
                )
                if beat_info:
                    # 【v11改进】生成更丰富的回退内容
                    output.dialogue = self._generate_fallback_narration(beat_info, location)
        return outputs

    # ============================================================================
    # 【v11改进】地点感知的回退内容生成
    # ============================================================================

    # 地点环境描写模板
    LOCATION_DESCRIPTIONS = {
        "食堂": "食堂里弥漫着淡淡的饭菜香气，长桌上整齐地摆放着餐具。窗外的阳光斜斜地照进来，在地板上投下明亮的光斑。",
        "图书室": "图书室里很安静，阳光透过窗户洒在书架上，灰尘在光线中轻轻飘浮。书页翻动的沙沙声偶尔响起。",
        "庭院": "庭院里微风轻拂，午后的阳光温暖而柔和。远处传来鸟鸣声，空气中弥漫着青草的气息。",
        "走廊": "长长的走廊寂静无声，窗外的光线在地板上投下斑驳的影子。脚步声在空旷的走廊里回响。",
        "牢房区": "牢房区的空气有些沉闷，铁栏杆在昏暗的光线中泛着冷光。这里的寂静令人感到压抑。",
    }

    def _generate_fallback_narration(self, beat, location: str = None) -> List[DialogueLine]:
        """【v11改进】根据 Beat 信息生成更丰富的回退叙述"""

        # 获取环境描写
        env_desc = self.LOCATION_DESCRIPTIONS.get(
            location, "这里很安静，空气中弥漫着微妙的紧张感。"
        )

        # 根据 Beat 类型生成不同内容
        if beat.beat_type == "opening":
            lines = [
                DialogueLine(
                    speaker="narrator",
                    text_cn=env_desc,
                    text_jp=env_desc,
                    emotion="neutral"
                ),
                DialogueLine(
                    speaker="narrator",
                    text_cn=beat.description if beat.description else "你环顾四周，观察着周围的一切。",
                    text_jp=beat.description if beat.description else "あなたは周りを見回し、周囲の様子を観察している。",
                    emotion="neutral"
                )
            ]
        elif beat.beat_type == "resolution":
            lines = [
                DialogueLine(
                    speaker="narrator",
                    text_cn=f"时间静静流逝。{beat.description}" if beat.description else "时间静静流逝，这段插曲就此结束。",
                    text_jp=f"時間は静かに流れていく。{beat.description}" if beat.description else "時間は静かに流れ、このひと時は終わりを迎える。",
                    emotion="neutral"
                )
            ]
        else:
            # development, tension, climax
            lines = [
                DialogueLine(
                    speaker="narrator",
                    text_cn=beat.description if beat.description else "气氛变得微妙起来。",
                    text_jp=beat.description if beat.description else "雰囲気が微妙になってきた。",
                    emotion="neutral"
                )
            ]

            # 如果有角色，添加一句简单对话
            if beat.characters:
                char = beat.characters[0]
                lines.append(DialogueLine(
                    speaker=char,
                    text_cn="......",
                    text_jp="......",
                    emotion="neutral",
                    action="沉默着"
                ))

        return lines

    # ============================================================================
    # 【v10新增】幻觉角色名检测与修正
    # ============================================================================

    def _validate_character_names(self, text: str) -> Tuple[bool, List[str]]:
        """检查文本中是否有无效角色名"""
        invalid_names = []
        for pattern in self.HALLUCINATION_PATTERNS:
            if pattern in text:
                invalid_names.append(pattern)
        return len(invalid_names) == 0, invalid_names

    def _fix_invalid_names(self, text: str, context_characters: List[str]) -> str:
        """替换无效角色名为上下文中的有效角色"""
        # 获取上下文角色的名字
        valid_replacements = []
        for char_id in context_characters:
            if char_id in self.VALID_CHARACTERS:
                cn_name = self.VALID_CHARACTERS[char_id][0]
                valid_replacements.append(cn_name)

        if not valid_replacements:
            valid_replacements = ["某人", "那个人", "她"]

        # 替换无效名字
        result = text
        for pattern in self.HALLUCINATION_PATTERNS:
            if pattern in result:
                replacement = random.choice(valid_replacements + ["她", "那个人"])
                result = result.replace(pattern, replacement)

        return result

    def _validate_speaker(self, speaker: str) -> str:
        """验证说话者ID是否有效"""
        valid_speakers = ["narrator", "player", "warden"] + list(self.VALID_CHARACTERS.keys())
        if speaker in valid_speakers:
            return speaker
        # 尝试匹配中文名
        for char_id, (cn, jp, aliases) in self.VALID_CHARACTERS.items():
            if speaker == cn or speaker == jp or speaker in aliases:
                return char_id
        # 无法识别，返回narrator
        print(f"⚠️ 无效说话者: {speaker}，改为narrator")
        return "narrator"

    # ============================================================================
    # 【v10新增】地点一致性检测与修正
    # ============================================================================

    def _validate_location_consistency(self, text: str, target_location: str) -> Tuple[bool, List[str]]:
        """检查文本是否与目标地点一致"""
        conflicts = self.LOCATION_CONFLICTS.get(target_location, [])
        found_conflicts = []
        for conflict_word in conflicts:
            if conflict_word in text:
                found_conflicts.append(conflict_word)
        return len(found_conflicts) == 0, found_conflicts

    def _fix_location_references(self, text: str, correct_location: str) -> str:
        """替换错误的地点引用"""
        # 地点替换映射
        replacements = {
            "图书馆": {"食堂": "食堂", "牢房区": "牢房", "庭院": "庭院", "走廊": "走廊"},
            "图书室": {"食堂": "食堂", "牢房区": "牢房", "庭院": "庭院", "走廊": "走廊"},
            "书架": {"食堂": "餐桌", "牢房区": "墙壁", "庭院": "长椅", "走廊": "窗户"},
            "书本": {"食堂": "餐盘", "牢房区": "床铺", "庭院": "花草", "走廊": "窗户"},
        }
        result = text
        for wrong_word, location_map in replacements.items():
            if wrong_word in result and correct_location in location_map:
                result = result.replace(wrong_word, location_map[correct_location])
        return result

    # ============================================================================
    # 【v10新增】综合验证与修正
    # ============================================================================

    def _validate_and_fix_dialogue(
        self,
        outputs: List[DialogueOutput],
        scene_characters: List[str],
        location: str
    ) -> List[DialogueOutput]:
        """验证并修正对话内容"""
        for output in outputs:
            for line in output.dialogue:
                # 1. 验证说话者
                line.speaker = self._validate_speaker(line.speaker)

                # 2. 检查幻觉角色名
                is_valid, invalid_names = self._validate_character_names(line.text_cn)
                if not is_valid:
                    print(f"⚠️ 检测到幻觉角色名: {invalid_names}")
                    line.text_cn = self._fix_invalid_names(line.text_cn, scene_characters)

                # 3. 检查地点一致性
                is_valid, conflicts = self._validate_location_consistency(line.text_cn, location)
                if not is_valid:
                    print(f"⚠️ 检测到地点冲突: {conflicts}（当前地点：{location}）")
                    line.text_cn = self._fix_location_references(line.text_cn, location)

        return outputs

    def generate_scene_dialogue(
        self,
        scene_plan: ScenePlan
    ) -> Tuple[List[DialogueOutput], Optional[Dict[str, ChoiceResponse]]]:
        """
        一次性生成整个场景的所有对话和预选回应（优化延迟）

        输入：ScenePlan（包含所有 Beat）
        输出：Tuple[List[DialogueOutput], Optional[Dict[str, ChoiceResponse]]]
            - 整场景的对话列表
            - 预选回应字典（如果有选择点），否则为 None
        """
        if not scene_plan.beats:
            return [], None

        # 收集所有角色信息
        all_characters = set()
        for beat in scene_plan.beats:
            all_characters.update(beat.characters)

        characters_info = {}
        for char_id in all_characters:
            char_data = self.load_character_data(char_id)
            char_state = self.load_character_state(char_id)
            characters_info[char_id] = {
                "name": char_data["core"].get("name", {}).get("zh", char_id),
                "personality": char_data["personality"].get("versions", {}).get("simple", ""),
                "first_person": char_data["speech"].get("first_person", "我"),
                "verbal_tics": char_data["speech"].get("verbal_tics", [])[:3],
                "stress": char_state.get("stress", 50),
                "emotion": char_state.get("emotion", "neutral")
            }

        # 构建整场景的 prompt
        prompt = self._build_scene_prompt(scene_plan, characters_info)

        # 单次 API 调用生成对话（带重试）
        dialogue_outputs = []
        max_retries = 2
        scene_characters = list(all_characters)

        for attempt in range(max_retries + 1):
            try:
                print(f"  [CharacterActor] 正在生成 {len(scene_plan.beats)} 个 Beat 的对话...")
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=4096,  # 增大 token 限制以容纳整场对话
                    messages=[{"role": "user", "content": prompt}]
                )

                raw_text = response.content[0].text
                print(f"  [CharacterActor] 对话生成完成 (响应长度: {len(raw_text)} 字符)")

                # 解析整场对话
                result = parse_json_with_diagnostics(raw_text, "场景对话", "CharacterActor")
                dialogue_outputs = self._parse_scene_dialogue(result, scene_plan.beats)

                # 【v10新增】验证空内容
                empty_beats = self._check_empty_beats(dialogue_outputs)
                if empty_beats:
                    if attempt < max_retries:
                        print(f"⚠️ 检测到 {len(empty_beats)} 个空 Beat，重试中... ({attempt+1}/{max_retries})")
                        continue  # 重试
                    else:
                        print(f"⚠️ 重试后仍有空 Beat，使用回退内容填充")
                        dialogue_outputs = self._fill_empty_beats_with_fallback(
                            dialogue_outputs, empty_beats, scene_plan.beats
                        )

                # 【v10新增】验证并修正对话内容
                dialogue_outputs = self._validate_and_fix_dialogue(
                    dialogue_outputs,
                    scene_characters,
                    scene_plan.location
                )
                break  # 成功，跳出重试循环

            except json.JSONDecodeError as e:
                print(f"[CharacterActor] JSON 解析失败，使用回退对话")
                dialogue_outputs = self._create_fallback_scene_dialogue(scene_plan.beats, characters_info)
                break
            except Exception as e:
                print(f"[CharacterActor] API 调用失败: {type(e).__name__}: {e}")
                dialogue_outputs = self._create_fallback_scene_dialogue(scene_plan.beats, characters_info)
                break

        # ★ 新增：如果有选择点，同时生成预选回应
        choice_responses = None
        if scene_plan.player_choice_point:
            print(f"  [CharacterActor] 正在生成预选回应...")
            # 获取选择点后的主要角色
            characters = self._get_choice_responders(scene_plan)
            choice_responses = self.generate_choice_responses(
                scene_plan.player_choice_point,
                characters
            )
            print(f"  [CharacterActor] 预选回应生成完成")

        return dialogue_outputs, choice_responses

    def _get_choice_responders(self, scene_plan: ScenePlan) -> List[str]:
        """获取选择点的回应角色"""
        # 找到选择点之后的 beat，获取其角色
        choice_point = scene_plan.player_choice_point
        after_beat = choice_point.get("after_beat", "")

        # 遍历 beats 找到对应的角色
        for i, beat in enumerate(scene_plan.beats):
            if beat.beat_id == after_beat and beat.characters:
                return beat.characters

        # 回退：使用最后一个 beat 的角色
        if scene_plan.beats and scene_plan.beats[-1].characters:
            return scene_plan.beats[-1].characters

        # 最后回退：使用所有出现过的角色
        all_chars = []
        for beat in scene_plan.beats:
            for char in beat.characters:
                if char not in all_chars:
                    all_chars.append(char)
        return all_chars[:1] if all_chars else []

    def _build_scene_prompt(self, scene_plan: ScenePlan, characters_info: Dict) -> str:
        """构建整场景的 prompt（双语输出）"""

        # 格式化角色信息（包含日文口癖）
        chars_str = ""
        for char_id, info in characters_info.items():
            verbal_tics_jp = info.get('verbal_tics_jp', info['verbal_tics'])
            chars_str += f"""
【{info['name']}】({char_id})
  性格: {info['personality'][:80]}
  日文第一人称: 「{info['first_person']}」
  日文口癖: {', '.join(verbal_tics_jp) if verbal_tics_jp else '无'}
  口癖中文翻译: {', '.join(info['verbal_tics']) if info['verbal_tics'] else '无'}
  当前情绪: {info['emotion']} | 压力: {info['stress']}/100
"""

        # 格式化 Beat 列表
        beats_str = ""
        for i, beat in enumerate(scene_plan.beats, 1):
            emotion_targets_str = ", ".join([f"{k}→{v}" for k, v in beat.emotion_targets.items()])
            beats_str += f"""
Beat {i} ({beat.beat_id}): {beat.beat_type}
  描述: {beat.description}
  角色: {', '.join(beat.characters)}
  说话顺序: {' → '.join(beat.speaker_order)}
  情绪目标: {emotion_targets_str}
  张力等级: {beat.tension_level}/10
  对话数: {beat.dialogue_count}行
  导演指示: {beat.direction_notes}
"""

        # 输出格式（双语）
        output_format = """{
  "beats": [
    {
      "beat_id": "beat_1",
      "dialogue": [
        {
          "speaker": "角色ID",
          "text_cn": "中文对话（第一人称统一用「我」，口癖翻译成中文）",
          "text_jp": "日本語の台詞（一人称とキャラ口癖をそのまま保持）",
          "emotion": "情绪",
          "action": "动作(可选)"
        }
      ],
      "effects": {"角色ID": {"stress": 变化值, "emotion": "新情绪"}}
    }
  ]
}"""

        # 【v10新增】获取地点关键词
        location = scene_plan.location
        location_keywords = self.LOCATION_KEYWORDS.get(location, [])
        location_conflicts = self.LOCATION_CONFLICTS.get(location, [])

        prompt = f"""你是一位专业的视觉小说对话编剧。根据导演的场景规划，一次性生成整个场景的所有对话。

【重要：角色名白名单】
本游戏只有13名角色：艾玛、希罗、安安、诺亚、蕾雅、米莉亚、玛尔戈、菜乃香、爱丽莎、雪莉、汉娜、可可、梅露露
❌ 禁止使用：美咲、亚美、千夏、真由、沙织、花子等任何其他名字
✅ 泛指他人时用：「她」「那个人」「某人」「其他人」

【重要：地点一致性】
当前地点是「{location}」，所有描写必须与此地点相关。
✅ 应该出现的元素：{', '.join(location_keywords)}
❌ 不应该出现：{', '.join(location_conflicts)}
例如：如果在「走廊」，不要写"图书馆深处"或"书架旁边"

【游戏背景】
《魔法少女的魔女审判》- 13名少女被关在孤岛监牢的推理解谜游戏。

【场景信息】
场景名: {scene_plan.scene_name}
地点: {location}（必须一致！）
整体弧线: {scene_plan.overall_arc}
Beat数量: {len(scene_plan.beats)}

【参与角色】
{chars_str}

【Beat大纲】
{beats_str}

【重要：双语输出要求】
每句对话必须同时输出 text_cn 和 text_jp：

1. text_cn（中文显示用）：
   - 第一人称统一用「我」
   - 口癖翻译成自然的中文表达
   - 例：「我觉得...唔，怎么说呢...」

2. text_jp（日文TTS用）：
   - 保留角色原本的第一人称（私/俺/ウチ/あたし等）
   - 保留原汁原味的口癖
   - 例：「あたしは...えっと、なんていうか...」

【任务】
为每个 Beat 生成双语对话。要求：
1. 情绪按张力曲线自然变化
2. 对话要连贯，前后 Beat 要有呼应
3. 张力等级：1-3平静 / 4-5略紧张 / 6-7紧张 / 8-10激动
4. 中日文内容要对应，但表达方式可以各自自然
5. 【重要】每个Beat必须有实质内容，不能只有"..."

【输出格式】严格 JSON：
{output_format}

情绪只能用: happy/sad/angry/scared/nervous/calm/surprised/conflicted/neutral

请直接输出JSON，不要使用markdown代码块。"""

        return prompt

    def _parse_scene_dialogue(self, result: Dict, beats: List[Beat]) -> List[DialogueOutput]:
        """解析整场对话结果（双语）"""
        all_dialogue = []
        beats_data = result.get("beats", [])

        for i, beat in enumerate(beats):
            if i < len(beats_data):
                beat_data = beats_data[i]
                dialogue = []
                for line in beat_data.get("dialogue", []):
                    text_cn = line.get("text_cn", "...")
                    text_jp = line.get("text_jp", text_cn)  # 如果没有日文，使用中文
                    dialogue.append(DialogueLine(
                        speaker=line.get("speaker", "narrator"),
                        text_cn=text_cn,
                        text_jp=text_jp,
                        emotion=line.get("emotion", "neutral"),
                        action=line.get("action")
                    ))
                all_dialogue.append(DialogueOutput(
                    beat_id=beat_data.get("beat_id", beat.beat_id),
                    dialogue=dialogue,
                    effects=beat_data.get("effects", {})
                ))
            else:
                # Beat 数据不足，使用空对话
                all_dialogue.append(DialogueOutput(
                    beat_id=beat.beat_id,
                    dialogue=[DialogueLine("narrator", "...", "...", "neutral")],
                    effects={}
                ))

        return all_dialogue

    def _create_fallback_scene_dialogue(self, beats: List[Beat], characters_info: Dict) -> List[DialogueOutput]:
        """创建整场回退对话"""
        all_dialogue = []
        for beat in beats:
            all_dialogue.append(self._create_fallback_dialogue(beat, characters_info))
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
