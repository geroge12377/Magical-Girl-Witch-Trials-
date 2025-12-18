# ============================================================================
# 第1天完整体验 - day1_experience.py
# ============================================================================
# 专注于第1天的完整游戏流程：
# - 序章固定事件（觉醒→集合→规则→希罗→介绍）
# - 自由时间（3次互动）
# - 午餐固定事件
# - 自由时间（3次互动）
# - 晚餐固定事件
# - 自由时间（3次互动）
# - 就寝，结束第1天
# ============================================================================

import anthropic
import json
import yaml
import random
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

# ============================================================================
# 配置
# ============================================================================

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024

def get_api_key():
    """获取API密钥"""
    key_file = Path("api_key.txt")
    if key_file.exists():
        return key_file.read_text().strip()
    import os
    return os.environ.get("ANTHROPIC_API_KEY", "")

# ============================================================================
# 数据加载
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
# 游戏状态
# ============================================================================

@dataclass
class GameState:
    """游戏状态"""
    day: int = 1
    phase: str = "dawn"
    event_count: int = 0
    triggered_events: List[str] = None
    flags: Dict[str, bool] = None
    player_location: str = "牢房区"
    
    def __post_init__(self):
        if self.triggered_events is None:
            self.triggered_events = []
        if self.flags is None:
            self.flags = {}
    
    def save(self):
        save_json("world_state/current_day.json", {
            "day": self.day,
            "phase": self.phase,
            "event_count": self.event_count,
            "triggered_events": self.triggered_events,
            "flags": self.flags
        })
    
    @classmethod
    def load(cls):
        data = load_json("world_state/current_day.json")
        return cls(
            day=data.get("day", 1),
            phase=data.get("phase", "dawn"),
            event_count=data.get("event_count", 0),
            triggered_events=data.get("triggered_events", []),
            flags=data.get("flags", {})
        )

# ============================================================================
# 显示函数
# ============================================================================

def clear_screen():
    """清屏（可选）"""
    # print("\033[2J\033[H")  # 取消注释启用清屏
    pass

def print_header(text: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def print_divider():
    print("-" * 60)

def print_narrator(text: str):
    """旁白"""
    print(f"\n  {text}")

def print_dialogue(speaker: str, text: str, emotion: str = ""):
    """角色对话"""
    emotion_mark = f" [{emotion}]" if emotion else ""
    print(f"\n【{speaker}{emotion_mark}】")
    print(f"  「{text}」")

def print_choices(choices: List[dict]):
    """显示选项"""
    print("\n" + "-" * 40)
    for opt in choices:
        mark = " ⚠️" if opt.get("danger") else ""
        print(f"  {opt['id']}. {opt['text']}{mark}")
    print("-" * 40)

def wait_for_continue():
    """等待继续"""
    input("\n  [按Enter继续...]")

def get_choice(prompt: str, valid: List[str]) -> str:
    """获取玩家选择"""
    while True:
        choice = input(f"\n{prompt}").strip().upper()
        if choice in valid or choice.lower() in valid:
            return choice
        print("  无效输入，请重试")

# ============================================================================
# 角色数据
# ============================================================================

# 简化的角色名称映射
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
    "narrator": "旁白",
    "player": "你"
}

def get_char_name(char_id: str) -> str:
    return CHAR_NAMES.get(char_id, char_id)

def load_character_data(char_id: str) -> dict:
    """加载角色完整数据"""
    char_path = Path(f"characters/{char_id}")
    try:
        core = load_yaml(char_path / "core.yaml")
        personality = load_yaml(char_path / "personality.yaml")
        speech = load_yaml(char_path / "speech.yaml")
        return {"core": core, "personality": personality, "speech": speech}
    except:
        return None

# ============================================================================
# 固定事件播放
# ============================================================================

class FixedEventPlayer:
    """固定事件播放器"""
    
    def __init__(self):
        self.events = load_yaml("events/fixed_events.yaml").get("fixed_events", {})
    
    def play(self, event_id: str, game_state: GameState) -> dict:
        """播放固定事件"""
        event = self.events.get(event_id)
        if not event:
            print(f"❌ 事件不存在: {event_id}")
            return {}
        
        # 显示事件名称
        print_header(event.get("name", event_id))
        
        # 播放脚本
        script = event.get("script", [])
        for line in script:
            speaker = line.get("speaker", "narrator")
            text = line.get("text_cn", "")
            
            if speaker == "narrator":
                print_narrator(text)
            else:
                print_dialogue(get_char_name(speaker), text)
            
            time.sleep(0.3)  # 短暂停顿
        
        wait_for_continue()
        
        # 标记已触发
        game_state.triggered_events.append(event_id)
        
        # 设置标记
        for flag in event.get("flags_set", []):
            game_state.flags[flag] = True
        
        # 返回事件数据
        return event

# ============================================================================
# 自由事件生成器
# ============================================================================

class FreeEventGenerator:
    """自由事件生成器"""
    
    def __init__(self):
        self.client = None  # 延迟初始化
        self.templates = load_yaml("events/free_event_templates.yaml").get("templates", {})
        self.char_states = load_json("world_state/character_states.json")
    
    def _get_client(self):
        if self.client is None:
            api_key = get_api_key()
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
        return self.client
    
    def reload_states(self):
        self.char_states = load_json("world_state/character_states.json")
    
    def get_chars_at_location(self, location: str) -> List[str]:
        """获取指定地点的角色"""
        return [
            char_id for char_id, state in self.char_states.items()
            if state.get("location") == location
        ]
    
    def generate_encounter(self, location: str, char_id: str) -> dict:
        """生成遭遇事件"""
        
        # 加载角色数据
        char_data = load_character_data(char_id)
        char_state = self.char_states.get(char_id, {})
        
        if not char_data:
            # 无角色数据，返回简单事件
            return self._simple_encounter(char_id, location)
        
        # 尝试调用API
        client = self._get_client()
        if not client:
            return self._simple_encounter(char_id, location)
        
        return self._api_encounter(char_id, char_data, char_state, location)
    
    def _simple_encounter(self, char_id: str, location: str) -> dict:
        """简单遭遇（无API）"""
        name = get_char_name(char_id)
        
        # 随机对话
        dialogues = [
            f"你在{location}遇到了{name}。",
            f"{name}注意到了你的存在。",
            f"{name}似乎在思考什么。"
        ]
        
        responses = [
            f"...你好。",
            f"有什么事吗？",
            f"......"
        ]
        
        return {
            "dialogue": [
                {"speaker": "narrator", "text": random.choice(dialogues)},
                {"speaker": char_id, "text": random.choice(responses), "emotion": "neutral"}
            ],
            "choices": [
                {"id": "A", "text": "友好地打招呼", "effect": {"stress": -2, "affection": 2}},
                {"id": "B", "text": "点头示意", "effect": {"stress": 0, "affection": 0}},
                {"id": "C", "text": "无视对方", "effect": {"stress": 2, "affection": -3}, "danger": True}
            ],
            "responses": {
                "A": {"text": "...嗯，你好。", "emotion": "calm"},
                "B": {"text": "......", "emotion": "neutral"},
                "C": {"text": "......", "emotion": "sad"}
            }
        }
    
    def _api_encounter(self, char_id: str, char_data: dict, char_state: dict, location: str) -> dict:
        """API生成遭遇"""
        core = char_data.get("core", {})
        personality = char_data.get("personality", {})
        speech = char_data.get("speech", {})
        
        name = core.get("name", {}).get("zh", char_id)
        
        prompt = f"""你是视觉小说游戏的导演AI。生成一段简短的遭遇对话。

【角色】{name}
性格: {personality.get('versions', {}).get('simple', '未知')}
说话方式: 第一人称"{speech.get('first_person', '我')}"
口癖: {', '.join(speech.get('verbal_tics', [])[:3])}

【场景】{location}，第1天自由时间
角色状态: 压力{char_state.get('stress', 50)}/100，情绪{char_state.get('emotion', 'neutral')}

【任务】生成：
1. 旁白描述（1句）
2. 角色台词（1-2句，符合性格）
3. 三个玩家选项（A友好/B中性/C冷淡）
4. 每个选项的角色回应（1句）

【输出格式】严格JSON：
{{
  "narration": "旁白描述",
  "dialogue": "角色台词",
  "emotion": "情绪",
  "choices": [
    {{"id": "A", "text": "选项文字", "response": "角色回应", "response_emotion": "情绪"}}
  ]
}}

直接输出JSON，不要markdown。"""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            
            data = json.loads(text)
            
            return {
                "dialogue": [
                    {"speaker": "narrator", "text": data.get("narration", f"你遇到了{name}。")},
                    {"speaker": char_id, "text": data.get("dialogue", "......"), "emotion": data.get("emotion", "neutral")}
                ],
                "choices": [
                    {
                        "id": c["id"],
                        "text": c["text"],
                        "effect": {"stress": -2 if c["id"]=="A" else (2 if c["id"]=="C" else 0)},
                        "danger": c["id"] == "C"
                    }
                    for c in data.get("choices", [])
                ],
                "responses": {
                    c["id"]: {"text": c.get("response", "..."), "emotion": c.get("response_emotion", "neutral")}
                    for c in data.get("choices", [])
                }
            }
            
        except Exception as e:
            print(f"  (API调用失败: {e})")
            return self._simple_encounter(char_id, location)

# ============================================================================
# NPC位置管理
# ============================================================================

class NPCManager:
    """NPC位置管理"""
    
    def __init__(self):
        self.char_states = load_json("world_state/character_states.json")
        self.locations = ["食堂", "庭院", "图书室", "走廊", "牢房区"]
    
    def update_positions(self, phase: str):
        """更新NPC位置"""
        # 根据时段设置分布
        if phase in ["dawn", "morning"]:
            weights = {"食堂": 0.4, "庭院": 0.2, "牢房区": 0.2, "走廊": 0.1, "图书室": 0.1}
        elif phase == "meal_time":
            weights = {"食堂": 0.9, "走廊": 0.1}
        elif phase == "night":
            weights = {"牢房区": 0.9, "走廊": 0.1}
        else:  # free_time
            weights = {"食堂": 0.25, "庭院": 0.25, "图书室": 0.15, "牢房区": 0.2, "走廊": 0.15}
        
        # 角色偏好
        preferences = {
            "nanoka": {"图书室": 0.6},
            "arisa": {"庭院": 0.5},
            "noah": {"牢房区": 0.6},
            "meruru": {"食堂": 0.5},
            "coco": {"图书室": 0.5}
        }
        
        # 分配位置
        for char_id in self.char_states:
            char_weights = weights.copy()
            
            # 应用偏好
            if char_id in preferences:
                for loc, bonus in preferences[char_id].items():
                    if loc in char_weights:
                        char_weights[loc] += bonus
            
            # 归一化
            total = sum(char_weights.values())
            
            # 加权随机
            r = random.random() * total
            cumulative = 0
            selected = self.locations[0]
            
            for loc, w in char_weights.items():
                cumulative += w
                if r <= cumulative:
                    selected = loc
                    break
            
            self.char_states[char_id]["location"] = selected
            
            # 随机行为
            actions = ["四处张望", "低头沉思", "靠墙站着", "来回踱步", "发呆"]
            self.char_states[char_id]["action"] = random.choice(actions)
        
        save_json("world_state/character_states.json", self.char_states)
    
    def get_location_summary(self) -> dict:
        """获取各地点人数"""
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
# 第1天完整流程
# ============================================================================

class Day1Experience:
    """第1天完整体验"""
    
    def __init__(self):
        self.state = GameState(day=1, phase="dawn", event_count=0)
        self.fixed_player = FixedEventPlayer()
        self.free_generator = FreeEventGenerator()
        self.npc_manager = NPCManager()
    
    def run(self):
        """运行第1天"""
        print_header("🌙 魔法少女的魔女审判 - 第1天")
        print_narrator("新的一天开始了...")
        wait_for_continue()
        
        # ====== 序章固定事件 ======
        self.play_prologue()
        
        # ====== 自由时间 1 (3次互动) ======
        self.state.phase = "free_time"
        self.play_free_time(3, "上午")
        
        # ====== 午餐 ======
        self.play_fixed_event("day1_lunch")
        
        # ====== 自由时间 2 (3次互动) ======
        self.play_free_time(3, "下午")
        
        # ====== 晚餐 ======
        self.play_fixed_event("day1_dinner")
        
        # ====== 自由时间 3 (3次互动) ======
        self.play_free_time(3, "傍晚")
        
        # ====== 就寝 ======
        self.play_fixed_event("day1_night")
        
        # ====== 第1天结束 ======
        print_header("🌙 第1天结束")
        print_narrator("漫长的一天终于结束了...")
        print_narrator("在这个陌生的监牢中，你度过了第一个夜晚。")
        print_narrator("明天，又会发生什么呢...")
        
        self.show_day_summary()
    
    def play_prologue(self):
        """播放序章"""
        prologue_events = [
            "day1_awakening",
            "day1_morning_assembly",
            "day1_rules_announcement",
            "day1_hiro_incident",
            "day1_introduction"
        ]
        
        for event_id in prologue_events:
            self.fixed_player.play(event_id, self.state)
            self.state.save()
    
    def play_fixed_event(self, event_id: str):
        """播放单个固定事件"""
        self.fixed_player.play(event_id, self.state)
        self.state.save()
    
    def play_free_time(self, count: int, period_name: str):
        """自由时间"""
        print_header(f"☀️ 自由时间 - {period_name}")
        print_narrator(f"你有一些自由活动的时间。（{count}次行动）")
        
        # 更新NPC位置
        self.npc_manager.update_positions("free_time")
        
        for i in range(count):
            print(f"\n【行动 {i+1}/{count}】")
            self.free_time_turn()
            self.state.event_count += 1
            self.state.save()
        
        print_narrator(f"{period_name}的自由时间结束了。")
        wait_for_continue()
    
    def free_time_turn(self):
        """自由时间单次行动"""
        # 显示地点选择
        locations = ["食堂", "庭院", "图书室", "走廊", "牢房区"]
        summary = self.npc_manager.get_location_summary()
        
        print("\n你要去哪里？")
        print_divider()
        
        for i, loc in enumerate(locations, 1):
            chars = summary.get(loc, [])
            char_names = [get_char_name(c)[:4] for c in chars[:3]]
            extra = f"...等{len(chars)}人" if len(chars) > 3 else f"({len(chars)}人)"
            names_str = ", ".join(char_names) if char_names else "无人"
            print(f"  {i}. {loc} - {names_str} {extra if len(chars) > 3 else ''}")
        
        print(f"  0. 待在原地休息")
        print_divider()
        
        choice = get_choice("输入数字: ", ["0", "1", "2", "3", "4", "5"])
        
        if choice == "0":
            print_narrator("你决定在原地休息一会...")
            return
        
        idx = int(choice) - 1
        if 0 <= idx < len(locations):
            target_loc = locations[idx]
            self.visit_location(target_loc)
    
    def visit_location(self, location: str):
        """访问地点"""
        print_narrator(f"你来到了{location}...")
        
        # 获取该地点的角色
        self.npc_manager.reload()
        self.free_generator.reload_states()
        
        chars = self.free_generator.get_chars_at_location(location)
        
        if not chars:
            print_narrator("这里没有其他人。你四处看了看，然后离开了。")
            return
        
        # 随机选择一个角色遭遇
        char_id = random.choice(chars)
        char_name = get_char_name(char_id)
        
        print_narrator(f"你注意到{char_name}在这里。")
        
        # 选择是否互动
        print("\n你要和ta交谈吗？")
        print_divider()
        print(f"  1. 上前搭话")
        print(f"  2. 在一旁观察")
        print(f"  0. 离开")
        print_divider()
        
        choice = get_choice("输入数字: ", ["0", "1", "2"])
        
        if choice == "0":
            print_narrator("你决定离开这里。")
            return
        
        if choice == "2":
            print_narrator(f"你在一旁默默观察{char_name}...")
            print_narrator(f"{char_name}似乎没有注意到你。")
            return
        
        # 生成遭遇事件
        print_narrator(f"你走向{char_name}...")
        
        event = self.free_generator.generate_encounter(location, char_id)
        
        # 播放对话
        for line in event.get("dialogue", []):
            speaker = line.get("speaker", "narrator")
            text = line.get("text", "")
            emotion = line.get("emotion", "")
            
            if speaker == "narrator":
                print_narrator(text)
            else:
                print_dialogue(get_char_name(speaker), text, emotion)
        
        # 显示选项
        choices = event.get("choices", [])
        if choices:
            print_choices(choices)
            
            valid = [c["id"] for c in choices]
            player_choice = get_choice("你的选择: ", valid)
            
            # 显示回应
            responses = event.get("responses", {})
            response = responses.get(player_choice, {})
            
            if response:
                print_dialogue(
                    get_char_name(char_id),
                    response.get("text", "..."),
                    response.get("emotion", "")
                )
            
            # 应用效果
            chosen = next((c for c in choices if c["id"] == player_choice), None)
            if chosen and chosen.get("effect"):
                self.apply_effect(char_id, chosen["effect"])
                
                if chosen.get("danger"):
                    print_narrator("（这个选择似乎不太好...）")
        
        wait_for_continue()
    
    def apply_effect(self, char_id: str, effect: dict):
        """应用效果"""
        char_states = load_json("world_state/character_states.json")
        
        if char_id in char_states:
            state = char_states[char_id]
            state["stress"] = max(0, min(100, state.get("stress", 50) + effect.get("stress", 0)))
            # affection暂时不处理
            save_json("world_state/character_states.json", char_states)
    
    def show_day_summary(self):
        """显示第1天总结"""
        print_header("📊 第1天总结")
        
        char_states = load_json("world_state/character_states.json")
        
        print("\n【角色状态】")
        print_divider()
        
        # 按压力排序
        sorted_chars = sorted(
            char_states.items(),
            key=lambda x: x[1].get("stress", 0),
            reverse=True
        )
        
        for char_id, state in sorted_chars[:5]:
            name = get_char_name(char_id)
            stress = state.get("stress", 0)
            emotion = state.get("emotion", "neutral")
            bar = "█" * (stress // 10) + "░" * (10 - stress // 10)
            print(f"  {name:12} [{bar}] {stress:3}% {emotion}")
        
        print_divider()
        print(f"\n  总互动次数: {self.state.event_count}")
        print(f"  触发事件数: {len(self.state.triggered_events)}")
        
        wait_for_continue()

# ============================================================================
# 重置游戏状态
# ============================================================================

def reset_game_state():
    """重置到第1天开始"""
    # 重置current_day
    save_json("world_state/current_day.json", {
        "day": 1,
        "phase": "dawn",
        "event_count": 0,
        "triggered_events": [],
        "flags": {}
    })
    
    # 重置角色状态
    char_states = load_json("world_state/character_states.json")
    for char_id in char_states:
        char_states[char_id]["stress"] = 30
        char_states[char_id]["madness"] = 0
        char_states[char_id]["emotion"] = "neutral"
        char_states[char_id]["location"] = "牢房区"
    save_json("world_state/character_states.json", char_states)
    
    print("✅ 游戏状态已重置")

# ============================================================================
# 入口
# ============================================================================

def main():
    """主入口"""
    print("\n" + "=" * 60)
    print("  🌙 魔法少女的魔女审判 - 第1天体验版")
    print("=" * 60)
    print("\n  1. 开始新游戏")
    print("  2. 继续游戏")
    print("  0. 退出")
    
    choice = get_choice("\n选择: ", ["0", "1", "2"])
    
    if choice == "0":
        print("\n👋 再见！")
        return
    
    if choice == "1":
        reset_game_state()
    
    # 开始第1天
    day1 = Day1Experience()
    day1.run()
    
    print("\n👋 感谢游玩第1天体验版！")

if __name__ == "__main__":
    main()
