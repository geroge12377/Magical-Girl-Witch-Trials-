# ============================================================================
# 第1天完整体验 v2 - 日常为主
# ============================================================================
# 设计原则：
# 1. 日常占80-90%，加强代入感
# 2. 玩家是观察者，不是主角
# 3. 大部分场景无选项或轻选项
# 4. 重要选择很少，但有重量
# ============================================================================

import anthropic
import json
import yaml
import random
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ============================================================================
# 配置
# ============================================================================

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024

def get_api_key():
    key_file = Path("api_key.txt")
    if key_file.exists():
        return key_file.read_text().strip()
    import os
    return os.environ.get("ANTHROPIC_API_KEY", "")

# ============================================================================
# 数据工具
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

# ============================================================================
# 角色数据
# ============================================================================

CHAR_NAMES = {
    "hiro": "二阶堂寻",
    "meruru": "冰上梅露露",
    "anan": "夏目安安",
    "noah": "城崎诺亚",
    "reia": "莲见蕾雅",
    "miria": "佐伯米莉亚",
    "margo": "宝生玛尔戈",
    "nanoka": "黑部菜乃香",
    "arisa": "紫藤爱丽莎",
    "sherry": "橘雪莉",
    "hannah": "远野汉娜",
    "coco": "泽渡可可",
    "yuki": "月代雪",
    "warden": "典狱长",
    "narrator": "",
    "player": "你"
}

def get_name(char_id: str) -> str:
    return CHAR_NAMES.get(char_id, char_id)

def load_char_data(char_id: str) -> Optional[dict]:
    try:
        path = Path(f"characters/{char_id}")
        return {
            "core": load_yaml(path / "core.yaml"),
            "personality": load_yaml(path / "personality.yaml"),
            "speech": load_yaml(path / "speech.yaml")
        }
    except:
        return None

# ============================================================================
# 显示函数
# ============================================================================

def print_slow(text: str, delay: float = 0.02):
    """逐字显示（可选）"""
    print(text)  # 简化版直接打印
    # for char in text:
    #     print(char, end='', flush=True)
    #     time.sleep(delay)
    # print()

def print_header(text: str):
    print("\n" + "=" * 50)
    print(f"  {text}")
    print("=" * 50)

def print_scene(text: str):
    """场景描写"""
    print(f"\n{text}")

def print_dialogue(speaker: str, text: str):
    """角色对话"""
    name = get_name(speaker)
    if name:
        print(f"\n{name}「{text}」")
    else:
        print(f"\n「{text}」")

def print_narration(text: str):
    """旁白"""
    print(f"\n  {text}")

def print_choices(choices: List[dict]):
    """显示选项"""
    print("\n" + "-" * 30)
    for c in choices:
        print(f"  {c['id']}. {c['text']}")
    print("-" * 30)

def wait_continue():
    input("\n  [Enter继续]")

def get_input(prompt: str, valid: List[str]) -> str:
    while True:
        choice = input(f"\n{prompt}").strip().upper()
        if choice in valid or choice.lower() in [v.lower() for v in valid]:
            return choice
        print("  无效输入")

# ============================================================================
# 游戏状态
# ============================================================================

@dataclass
class GameState:
    day: int = 1
    phase: str = "dawn"
    event_count: int = 0
    triggered_events: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)
    
    def save(self):
        save_json("world_state/current_day.json", {
            "day": self.day,
            "phase": self.phase,
            "event_count": self.event_count,
            "triggered_events": self.triggered_events,
            "flags": self.flags
        })

# ============================================================================
# 日常事件生成器
# ============================================================================

class DailyEventGenerator:
    """日常事件生成器"""
    
    def __init__(self):
        self.client = None
        self.char_states = load_json("world_state/character_states.json")
        self.templates = load_yaml("events/free_event_templates_v2.yaml")
        
        # 事件类型权重
        self.type_weights = {
            "pure_daily": 50,
            "daily_chat": 35,
            "meaningful": 15
        }
    
    def _get_client(self):
        if self.client is None:
            key = get_api_key()
            if key:
                self.client = anthropic.Anthropic(api_key=key)
        return self.client
    
    def reload(self):
        self.char_states = load_json("world_state/character_states.json")
    
    def get_chars_at(self, location: str) -> List[str]:
        return [c for c, s in self.char_states.items() if s.get("location") == location]
    
    def pick_event_type(self) -> str:
        """根据权重随机选择事件类型"""
        total = sum(self.type_weights.values())
        r = random.random() * total
        cumulative = 0
        for etype, weight in self.type_weights.items():
            cumulative += weight
            if r <= cumulative:
                return etype
        return "pure_daily"
    
    def generate(self, location: str) -> dict:
        """生成一个日常事件"""
        chars = self.get_chars_at(location)
        
        if not chars:
            return self._empty_scene(location)
        
        # 选择事件类型
        event_type = self.pick_event_type()
        
        # 选择角色
        char1 = random.choice(chars)
        char2 = random.choice([c for c in chars if c != char1]) if len(chars) > 1 else None
        
        # 尝试API生成
        client = self._get_client()
        if client:
            return self._api_generate(event_type, location, char1, char2)
        else:
            return self._fallback_generate(event_type, location, char1, char2)
    
    def _empty_scene(self, location: str) -> dict:
        """空场景"""
        texts = [
            f"你来到{location}，这里空无一人。",
            f"{location}里很安静，没有其他人在。",
            f"你在{location}待了一会儿，没有遇到任何人。"
        ]
        return {
            "type": "pure_daily",
            "scenes": [{"type": "narration", "text": random.choice(texts)}],
            "choices": None
        }
    
    def _api_generate(self, event_type: str, location: str, char1: str, char2: str = None) -> dict:
        """API生成事件"""
        
        # 构建prompt
        if event_type == "pure_daily":
            prompt = self._build_pure_daily_prompt(location, char1, char2)
        elif event_type == "daily_chat":
            prompt = self._build_daily_chat_prompt(location, char1)
        else:
            prompt = self._build_meaningful_prompt(location, char1)
        
        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text.strip()
            return self._parse_response(text, event_type)
            
        except Exception as e:
            print(f"  (API错误: {e})")
            return self._fallback_generate(event_type, location, char1, char2)
    
    def _build_pure_daily_prompt(self, location: str, char1: str, char2: str = None) -> str:
        """构建纯日常prompt"""
        name1 = get_name(char1)
        char1_data = load_char_data(char1)
        personality1 = char1_data["personality"]["versions"]["simple"] if char1_data else "性格不明"
        
        if char2:
            name2 = get_name(char2)
            char2_data = load_char_data(char2)
            personality2 = char2_data["personality"]["versions"]["simple"] if char2_data else "性格不明"
            
            return f"""生成一段玩家旁观两个角色的日常场景。

地点：{location}
角色A：{name1}（{personality1}）
角色B：{name2}（{personality2}）

要求：
- 5-6句话
- 两人在闲聊或各做各的事
- 玩家只是旁观，不参与
- 日常、平淡、生活感
- 不要冲突，不要戏剧性

输出格式（严格JSON）：
{{
  "scenes": [
    {{"type": "narration", "text": "旁白描写"}},
    {{"type": "dialogue", "speaker": "{char1}", "text": "台词"}},
    {{"type": "dialogue", "speaker": "{char2}", "text": "台词"}},
    {{"type": "narration", "text": "结尾描写"}}
  ]
}}

直接输出JSON。"""
        
        else:
            return f"""生成一段玩家观察角色独处的日常场景。

地点：{location}
角色：{name1}（{personality1}）

要求：
- 3-4句话
- 角色在发呆、做小事、或自言自语
- 玩家只是路过观察
- 安静、日常、不打扰

输出格式（严格JSON）：
{{
  "scenes": [
    {{"type": "narration", "text": "描写1"}},
    {{"type": "narration", "text": "描写2"}},
    {{"type": "narration", "text": "结尾"}}
  ]
}}

直接输出JSON。"""
    
    def _build_daily_chat_prompt(self, location: str, char1: str) -> str:
        """构建日常闲聊prompt"""
        name1 = get_name(char1)
        char1_data = load_char_data(char1)
        personality1 = char1_data["personality"]["versions"]["simple"] if char1_data else "性格不明"
        speech = char1_data["speech"] if char1_data else {}
        first_person = speech.get("first_person", "我")
        
        return f"""生成一段玩家和角色简单闲聊的场景。

地点：{location}
角色：{name1}
性格：{personality1}
第一人称：{first_person}

要求：
- 4-5句铺垫
- 角色和玩家简单打招呼或闲聊
- 3个选项，都是普通的回应方式（不影响数值）
- 无论选什么，对话都自然结束
- 日常、轻松

输出格式（严格JSON）：
{{
  "scenes": [
    {{"type": "narration", "text": "场景描写"}},
    {{"type": "dialogue", "speaker": "{char1}", "text": "角色台词"}}
  ],
  "choices": [
    {{"id": "A", "text": "选项A"}},
    {{"id": "B", "text": "选项B"}},
    {{"id": "C", "text": "选项C"}}
  ],
  "responses": {{
    "A": "{name1}「回应A」",
    "B": "{name1}「回应B」",
    "C": "{name1}「回应C」"
  }}
}}

直接输出JSON。"""
    
    def _build_meaningful_prompt(self, location: str, char1: str) -> str:
        """构建有意义选择的prompt"""
        name1 = get_name(char1)
        char1_data = load_char_data(char1)
        personality1 = char1_data["personality"]["versions"]["simple"] if char1_data else "性格不明"
        
        return f"""生成一个有轻微选择意义的日常场景。

地点：{location}
角色：{name1}（{personality1}）

要求：
- 5-6句铺垫
- 角色遇到小困难或聊到某个话题
- 3个选项，有轻微的好感度影响
  - A: 友善/帮忙 (好感+2)
  - B: 普通/中性 (无变化)
  - C: 冷淡/拒绝 (好感-2)
- 不要太戏剧化，只是日常小事

输出格式（严格JSON）：
{{
  "scenes": [
    {{"type": "narration", "text": "场景描写"}},
    {{"type": "dialogue", "speaker": "{char1}", "text": "台词"}}
  ],
  "choices": [
    {{"id": "A", "text": "友善选项", "effect": {{"affection": 2}}}},
    {{"id": "B", "text": "中性选项", "effect": {{}}}},
    {{"id": "C", "text": "冷淡选项", "effect": {{"affection": -2}}}}
  ],
  "responses": {{
    "A": "{name1}「感谢的回应」",
    "B": "{name1}「普通回应」",
    "C": "{name1}「失望的回应」"
  }}
}}

直接输出JSON。"""
    
    def _parse_response(self, text: str, event_type: str) -> dict:
        """解析API响应"""
        try:
            # 清理JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text.strip())
            data["type"] = event_type
            return data
            
        except:
            return {
                "type": event_type,
                "scenes": [{"type": "narration", "text": "（场景生成失败）"}],
                "choices": None
            }
    
    def _fallback_generate(self, event_type: str, location: str, char1: str, char2: str = None) -> dict:
        """无API时的fallback生成"""
        name1 = get_name(char1)
        
        if event_type == "pure_daily":
            if char2:
                name2 = get_name(char2)
                return {
                    "type": "pure_daily",
                    "scenes": [
                        {"type": "narration", "text": f"你在{location}看到{name1}和{name2}。"},
                        {"type": "narration", "text": "她们似乎在聊着什么。"},
                        {"type": "narration", "text": "你没有打扰，从旁边走过。"}
                    ],
                    "choices": None
                }
            else:
                return {
                    "type": "pure_daily",
                    "scenes": [
                        {"type": "narration", "text": f"{name1}一个人在{location}。"},
                        {"type": "narration", "text": "她似乎在发呆。"},
                        {"type": "narration", "text": "你没有打扰她。"}
                    ],
                    "choices": None
                }
        
        elif event_type == "daily_chat":
            return {
                "type": "daily_chat",
                "scenes": [
                    {"type": "narration", "text": f"你在{location}遇到了{name1}。"},
                    {"type": "dialogue", "speaker": char1, "text": "...你好。"}
                ],
                "choices": [
                    {"id": "A", "text": "点头示意"},
                    {"id": "B", "text": "「你好」"},
                    {"id": "C", "text": "「在忙吗？」"}
                ],
                "responses": {
                    "A": f"{name1}也点了点头。",
                    "B": f"{name1}「嗯。」",
                    "C": f"{name1}「没有...就随便待着。」"
                }
            }
        
        else:  # meaningful
            return {
                "type": "meaningful",
                "scenes": [
                    {"type": "narration", "text": f"{name1}似乎有些困扰。"},
                    {"type": "dialogue", "speaker": char1, "text": "那个...能帮我个忙吗？"}
                ],
                "choices": [
                    {"id": "A", "text": "「什么事？」", "effect": {"affection": 2}},
                    {"id": "B", "text": "「看情况」", "effect": {}},
                    {"id": "C", "text": "「我很忙」", "effect": {"affection": -2}}
                ],
                "responses": {
                    "A": f"{name1}「谢谢你愿意听...」",
                    "B": f"{name1}「嗯...也是。」",
                    "C": f"{name1}「...抱歉打扰了。」"
                }
            }

# ============================================================================
# NPC管理
# ============================================================================

class NPCManager:
    def __init__(self):
        self.char_states = load_json("world_state/character_states.json")
        self.locations = ["食堂", "庭院", "图书室", "走廊", "牢房区"]
    
    def update_positions(self):
        """更新NPC位置"""
        weights = {"食堂": 0.25, "庭院": 0.25, "图书室": 0.15, "走廊": 0.15, "牢房区": 0.2}
        
        for char_id in self.char_states:
            total = sum(weights.values())
            r = random.random() * total
            cumulative = 0
            for loc, w in weights.items():
                cumulative += w
                if r <= cumulative:
                    self.char_states[char_id]["location"] = loc
                    break
        
        save_json("world_state/character_states.json", self.char_states)
    
    def get_summary(self) -> dict:
        summary = {}
        for char_id, state in self.char_states.items():
            loc = state.get("location", "未知")
            if loc not in summary:
                summary[loc] = []
            summary[loc].append(char_id)
        return summary
    
    def reload(self):
        self.char_states = load_json("world_state/character_states.json")

# ============================================================================
# 固定事件播放
# ============================================================================

class FixedEventPlayer:
    def __init__(self):
        self.events = load_yaml("events/fixed_events.yaml").get("fixed_events", {})
    
    def play(self, event_id: str, state: GameState):
        event = self.events.get(event_id)
        if not event:
            return
        
        print_header(event.get("name", event_id))
        
        for line in event.get("script", []):
            speaker = line.get("speaker", "narrator")
            text = line.get("text_cn", "")
            
            if speaker == "narrator":
                print_narration(text)
            else:
                print_dialogue(speaker, text)
            
            time.sleep(0.2)
        
        wait_continue()
        state.triggered_events.append(event_id)
        state.save()

# ============================================================================
# 第1天主流程
# ============================================================================

class Day1Experience:
    def __init__(self):
        self.state = GameState()
        self.fixed_player = FixedEventPlayer()
        self.daily_gen = DailyEventGenerator()
        self.npc_mgr = NPCManager()
    
    def run(self):
        print_header("🌙 魔法少女的魔女审判")
        print_narration("第一天...")
        wait_continue()
        
        # 序章
        self._prologue()
        
        # 自由时间1 (上午)
        self._free_time("上午", 3)
        
        # 午餐
        self.fixed_player.play("day1_lunch", self.state)
        
        # 自由时间2 (下午)
        self._free_time("下午", 3)
        
        # 晚餐
        self.fixed_player.play("day1_dinner", self.state)
        
        # 自由时间3 (傍晚)
        self._free_time("傍晚", 3)
        
        # 就寝
        self.fixed_player.play("day1_night", self.state)
        
        # 结束
        self._day_end()
    
    def _prologue(self):
        """序章固定事件"""
        events = [
            "day1_awakening",
            "day1_morning_assembly", 
            "day1_rules_announcement",
            "day1_hiro_incident",
            "day1_introduction"
        ]
        for eid in events:
            self.fixed_player.play(eid, self.state)
    
    def _free_time(self, period: str, count: int):
        """自由时间"""
        print_header(f"自由时间 - {period}")
        self.npc_mgr.update_positions()
        
        for i in range(count):
            print(f"\n【{period} {i+1}/{count}】")
            self._free_turn()
            self.state.event_count += 1
            self.state.save()
    
    def _free_turn(self):
        """单次自由行动"""
        # 显示地点
        summary = self.npc_mgr.get_summary()
        locations = ["食堂", "庭院", "图书室", "走廊", "牢房区"]
        
        print("\n你要去哪里？")
        print("-" * 30)
        for i, loc in enumerate(locations, 1):
            chars = summary.get(loc, [])
            count = len(chars)
            names = ", ".join([get_name(c)[:3] for c in chars[:2]])
            if count > 2:
                names += f"...等{count}人"
            elif count > 0:
                names += f" ({count}人)"
            else:
                names = "无人"
            print(f"  {i}. {loc} - {names}")
        print("  0. 原地休息")
        print("-" * 30)
        
        choice = get_input("选择: ", ["0","1","2","3","4","5"])
        
        if choice == "0":
            print_narration("你决定休息一会儿...")
            return
        
        loc = locations[int(choice)-1]
        self._visit_location(loc)
    
    def _visit_location(self, location: str):
        """访问地点"""
        print_narration(f"你来到了{location}...")
        
        # 生成日常事件
        self.daily_gen.reload()
        event = self.daily_gen.generate(location)
        
        # 播放场景
        for scene in event.get("scenes", []):
            if scene["type"] == "narration":
                print_narration(scene["text"])
            elif scene["type"] == "dialogue":
                print_dialogue(scene["speaker"], scene["text"])
            time.sleep(0.2)
        
        # 处理选项
        choices = event.get("choices")
        if choices:
            print_choices(choices)
            valid = [c["id"] for c in choices]
            choice = get_input("选择: ", valid)
            
            # 显示回应
            responses = event.get("responses", {})
            if choice in responses:
                print_narration(responses[choice])
            
            # 应用效果
            chosen = next((c for c in choices if c["id"] == choice), None)
            if chosen and chosen.get("effect"):
                # TODO: 应用好感度变化
                pass
        
        wait_continue()
    
    def _day_end(self):
        """第1天结束"""
        print_header("第1天结束")
        print_narration("漫长的一天过去了。")
        print_narration("你躺在简陋的床上，思考着今天发生的一切。")
        print_narration("这里的人...这个地方...到底是怎么回事？")
        print_narration("带着这些疑问，你渐渐睡去。")
        wait_continue()

# ============================================================================
# 入口
# ============================================================================

def reset_state():
    """重置状态"""
    save_json("world_state/current_day.json", {
        "day": 1, "phase": "dawn", "event_count": 0,
        "triggered_events": [], "flags": {}
    })
    
    chars = load_json("world_state/character_states.json")
    for c in chars:
        chars[c]["stress"] = 30
        chars[c]["madness"] = 0
        chars[c]["emotion"] = "neutral"
        chars[c]["location"] = "牢房区"
    save_json("world_state/character_states.json", chars)

def main():
    print("\n" + "=" * 50)
    print("  魔法少女的魔女审判 - 第1天")
    print("=" * 50)
    print("\n  1. 新游戏")
    print("  2. 继续")
    print("  0. 退出")
    
    choice = get_input("选择: ", ["0","1","2"])
    
    if choice == "0":
        return
    if choice == "1":
        reset_state()
    
    Day1Experience().run()
    print("\n感谢游玩！")

if __name__ == "__main__":
    main()
