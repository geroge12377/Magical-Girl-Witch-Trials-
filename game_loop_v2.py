# ============================================================================
# 游戏主循环 v2 - 整合导演API v2、事件系统、地点系统
# ============================================================================

import anthropic
import json
import yaml
from pathlib import Path
from config import get_api_key, MODEL, MAX_TOKENS, OUTPUT_DIR
from director_api_v2 import DirectorAPIv2, EventResult, EventManager


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
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()


# ============================================================================
# 显示函数
# ============================================================================

def display_header():
    """显示游戏标题"""
    print("\n" + "=" * 60)
    print("   🌙 魔法少女的魔女审判 - AI对话系统 v2")
    print("=" * 60)

def display_time():
    """显示当前时间"""
    current_day = load_json("world_state/current_day.json")
    phase_names = {
        "dawn": "黎明",
        "morning": "上午",
        "free_time": "自由时间",
        "meal_time": "用餐",
        "night": "夜晚",
        "investigation": "调查阶段",
        "trial": "审判阶段"
    }
    phase_cn = phase_names.get(current_day["phase"], current_day["phase"])
    
    print(f"\n📅 第{current_day['day']}天 - {phase_cn}")
    print(f"   事件计数: {current_day.get('event_count', 0)}")

def display_world_state():
    """显示世界状态"""
    character_states = load_json("world_state/character_states.json")
    locations = load_yaml("world_state/locations.yaml")
    
    # 按地点分组
    loc_chars = {}
    for char_id, state in character_states.items():
        loc = state.get("location", "未知")
        if loc not in loc_chars:
            loc_chars[loc] = []
        loc_chars[loc].append((char_id, state))
    
    print("\n" + "-" * 40)
    print("📍 当前位置分布")
    print("-" * 40)
    
    for loc, chars in sorted(loc_chars.items()):
        print(f"\n【{loc}】({len(chars)}人)")
        for char_id, state in chars[:5]:  # 只显示前5个
            stress = state.get("stress", 0)
            emotion = state.get("emotion", "neutral")
            action = state.get("action", "待机")[:15]
            stress_bar = "█" * (stress // 20) + "░" * (5 - stress // 20)
            print(f"  {char_id:8} [{stress_bar}] {emotion:10} {action}")
        if len(chars) > 5:
            print(f"  ...还有{len(chars)-5}人")

def display_dialogue(dialogue: list):
    """显示对话"""
    print("\n" + "=" * 50)
    print("📖 对话")
    print("=" * 50)
    
    for line in dialogue:
        speaker = line.get("speaker", "???")
        text = line.get("text_cn", "...")
        emotion = line.get("emotion", "")
        
        if speaker == "narrator":
            print(f"\n  {text}")
        else:
            emotion_mark = f" [{emotion}]" if emotion else ""
            print(f"\n【{speaker}{emotion_mark}】")
            print(f"  「{text}」")

def display_choices(choices: dict):
    """显示选项"""
    if not choices:
        return
    
    print("\n" + "=" * 50)
    print(f"❓ {choices.get('prompt_cn', '你要怎么做？')}")
    print("=" * 50)
    
    for opt in choices.get("options", []):
        opt_id = opt.get("id", "?")
        text = opt.get("text_cn", "...")
        badend = " ⚠️" if opt.get("leads_to_badend") else ""
        print(f"\n  {opt_id}. {text}{badend}")
    
    print(f"\n  D. [自由输入]")
    print(f"  Q. [查看状态]")

def display_event_result(result: EventResult):
    """显示事件结果"""
    print(f"\n📌 事件: {result.event_id} ({result.event_type})")
    
    # 显示对话
    display_dialogue(result.dialogue)
    
    # 显示选项
    if result.choices:
        display_choices(result.choices)
    
    # 显示标记变化
    if result.flags_set:
        print(f"\n🚩 标记设置: {', '.join(result.flags_set)}")
    
    # 显示游戏结束
    if result.game_over:
        display_ending(result.ending_type)

def display_ending(ending_type: str):
    """显示结局"""
    print("\n" + "=" * 60)
    
    if ending_type == "bad_end":
        print("💀 BAD END")
    elif ending_type == "good_end":
        print("🌸 GOOD END - 阻止悲剧")
    elif ending_type == "true_end":
        print("✨ TRUE END - 觉醒：打破命运")
    else:
        print(f"📖 结局: {ending_type}")
    
    print("=" * 60)

def display_location_menu(locations: dict, current_phase: str):
    """显示地点选择菜单"""
    print("\n" + "-" * 40)
    print("🚶 你要去哪里？")
    print("-" * 40)
    
    # 获取当前阶段可访问的地点
    phase_access = locations.get("phase_access", {}).get(current_phase, {})
    accessible = phase_access.get("accessible", [])
    
    locs = locations.get("locations", {})
    menu_items = []
    
    for i, (loc_id, loc_data) in enumerate(locs.items(), 1):
        name = loc_data.get("name_cn", loc_id)
        
        # 检查是否可访问
        if loc_data.get("locked", False):
            if loc_id not in accessible:
                continue
        
        menu_items.append((i, loc_id, name))
        print(f"  {i}. {name}")
    
    print(f"\n  0. [跳过/待在原地]")
    
    return menu_items


# ============================================================================
# 中控API - 更新NPC位置
# ============================================================================

def call_controller_api():
    """调用中控API更新NPC位置和行为"""
    print("\n🎮 更新NPC状态...")
    
    current_day = load_json("world_state/current_day.json")
    character_states = load_json("world_state/character_states.json")
    locations = load_yaml("world_state/locations.yaml")
    
    # 获取NPC分布规则
    phase = current_day.get("phase", "free_time")
    if phase in ["dawn", "morning"]:
        dist_phase = "morning"
    elif phase == "night":
        dist_phase = "night"
    else:
        dist_phase = "free_time"
    
    npc_dist = locations.get("npc_distribution", {}).get(dist_phase, {})
    char_prefs = locations.get("npc_distribution", {}).get("character_preferences", {})
    
    # 简单分配（不调用API，用规则）
    import random
    loc_names = {v["name_cn"]: k for k, v in locations.get("locations", {}).items()}
    
    for char_id, state in character_states.items():
        # 检查角色偏好
        prefs = char_prefs.get(char_id, {})
        
        if prefs:
            # 有偏好，按偏好选择
            choices = list(prefs.keys())
            weights = [prefs[c] for c in choices]
        else:
            # 无偏好，按默认分布
            choices = list(npc_dist.keys())
            weights = [npc_dist.get(c, 0.1) for c in choices]
        
        if choices and weights:
            # 加权随机选择
            total = sum(weights)
            r = random.random() * total
            cumulative = 0
            selected_loc_id = choices[0]
            
            for loc_id, weight in zip(choices, weights):
                cumulative += weight
                if r <= cumulative:
                    selected_loc_id = loc_id
                    break
            
            # 转换为中文名
            loc_data = locations.get("locations", {}).get(selected_loc_id, {})
            loc_name = loc_data.get("name_cn", selected_loc_id)
            
            state["location"] = loc_name
        
        # 随机行为
        actions = ["站着发呆", "四处张望", "低头沉思", "靠墙休息", "来回踱步"]
        state["action"] = random.choice(actions)
        state["can_interact"] = True
    
    save_json("world_state/character_states.json", character_states)
    print("✅ NPC状态已更新")


# ============================================================================
# 角色API - 自由对话
# ============================================================================

def call_character_api(char_id: str, player_input: str) -> dict:
    """调用角色API进行自由对话"""
    print(f"\n💬 {char_id} 正在思考...")
    
    character_states = load_json("world_state/character_states.json")
    char_state = character_states.get(char_id, {})
    
    # 加载角色数据
    char_path = Path(f"characters/{char_id}")
    try:
        core = load_yaml(char_path / "core.yaml")
        personality = load_yaml(char_path / "personality.yaml")
        speech = load_yaml(char_path / "speech.yaml")
    except:
        core = {"name": {"zh": char_id}}
        personality = {"versions": {"simple": "性格不明"}}
        speech = {"first_person": "我", "verbal_tics": []}
    
    prompt = f"""【身份】你是{core.get('name', {}).get('zh', char_id)}

【性格】{personality.get('versions', {}).get('simple', '未知')}

【说话方式】第一人称：{speech.get('first_person', '我')}，口癖：{', '.join(speech.get('verbal_tics', [])[:3])}

【当前状态】压力{char_state.get('stress', 50)}/100，情绪{char_state.get('emotion', 'neutral')}

【玩家说】{player_input}

【输出格式】严格JSON：
{{
  "text_cn": "中文回复(50-150字)",
  "emotion": "情绪(happy/sad/angry/scared/nervous/calm)",
  "effects": {{"stress": 变化值, "affection": 变化值}}
}}"""

    try:
        client = anthropic.Anthropic(api_key=get_api_key("character"))
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = json.loads(clean_json_response(response.content[0].text))
        
        # 更新状态
        effects = result.get("effects", {})
        char_state["stress"] = max(0, min(100, char_state.get("stress", 50) + effects.get("stress", 0)))
        char_state["emotion"] = result.get("emotion", char_state.get("emotion"))
        save_json("world_state/character_states.json", character_states)
        
        return result
        
    except Exception as e:
        print(f"❌ API错误: {e}")
        return {"text_cn": "......", "emotion": "neutral", "effects": {}}


# ============================================================================
# 主游戏循环
# ============================================================================

class GameLoopV2:
    """游戏主循环 v2"""
    
    def __init__(self):
        self.director = DirectorAPIv2()
        self.locations = load_yaml("world_state/locations.yaml")
        self.player_location = "牢房区"
        self.running = True
        self.current_event_result = None
    
    def run(self):
        """运行游戏"""
        display_header()
        
        while self.running:
            self.game_turn()
            
            if not self.running:
                break
            
            # 询问继续
            cont = input("\n继续？(y/n): ").strip().lower()
            if cont != 'y':
                print("\n👋 游戏暂停，感谢游玩！")
                break
    
    def game_turn(self):
        """一个游戏回合"""
        
        # 重新加载状态
        self.director.event_manager.reload_state()
        current_day = load_json("world_state/current_day.json")
        
        # 1. 显示时间
        display_time()
        
        # 2. 检查固定事件
        fixed_event = self.director.event_manager.get_pending_fixed_event()
        
        if fixed_event:
            # 有固定事件，直接处理
            print(f"\n📌 触发固定事件: {fixed_event.get('name')}")
            result = self.director._process_fixed_event(fixed_event)
            self.handle_event_result(result)
            return
        
        # 3. 自由时间 - 更新NPC
        if current_day.get("phase") == "free_time":
            call_controller_api()
        
        # 4. 显示世界状态
        display_world_state()
        
        # 5. 玩家选择地点
        menu = display_location_menu(self.locations, current_day.get("phase", "free_time"))
        
        choice = input("\n输入数字: ").strip()
        
        if choice == "0":
            print("\n你决定待在原地...")
            self.director.event_manager.increment_event_count()
            return
        
        # 解析选择
        try:
            idx = int(choice)
            selected = next((m for m in menu if m[0] == idx), None)
            if selected:
                _, loc_id, loc_name = selected
                self.player_location = loc_name
                print(f"\n你来到了 {loc_name}...")
        except:
            print("\n无效选择，待在原地...")
            return
        
        # 6. 处理自由事件
        result = self.director.process_turn(self.player_location)
        self.handle_event_result(result)
    
    def handle_event_result(self, result: EventResult):
        """处理事件结果"""
        self.current_event_result = result
        
        # 显示事件
        display_event_result(result)
        
        # 检查游戏结束
        if result.game_over:
            self.running = False
            return
        
        # 处理选项
        if result.choices and result.choices.get("options"):
            self.handle_player_choice(result)
        
        # 应用结果
        if result.outcomes:
            self.director.apply_outcomes(result.outcomes)
        
        # 检查下一个事件
        if result.next_event:
            # 链式触发下一个事件
            next_event_data = self.director.event_manager.fixed_events.get("fixed_events", {}).get(result.next_event)
            if next_event_data:
                next_result = self.director._process_fixed_event({"id": result.next_event, **next_event_data})
                self.handle_event_result(next_result)
    
    def handle_player_choice(self, result: EventResult):
        """处理玩家选择"""
        options = result.choices.get("options", [])
        
        while True:
            choice = input("\n输入选项 (A/B/C/D/Q): ").strip().upper()
            
            if choice == "Q":
                display_world_state()
                display_choices(result.choices)
                continue
            
            if choice == "D":
                # 自由输入
                player_input = input("\n你说: ").strip()
                if not player_input:
                    continue
                
                # 找到主要角色
                main_char = None
                for line in result.dialogue:
                    if line.get("speaker") != "narrator":
                        main_char = line.get("speaker")
                        break
                
                if main_char:
                    response = call_character_api(main_char, player_input)
                    print(f"\n【{main_char}】")
                    print(f"  「{response.get('text_cn', '...')}」")
                    print(f"  [{response.get('emotion', 'neutral')}]")
                break
            
            if choice in ["A", "B", "C"]:
                opt = next((o for o in options if o.get("id") == choice), None)
                if opt:
                    print(f"\n你选择了: {opt.get('text_cn')}")
                    
                    # 使用预生成回应（如果有）
                    # TODO: 从result中获取预生成回应
                    
                    if opt.get("leads_to_badend"):
                        print("\n⚠️ 这个选择可能导向危险的结局...")
                    break
            
            print("无效输入，请重试")


# ============================================================================
# 入口
# ============================================================================

def main():
    """主入口"""
    game = GameLoopV2()
    game.run()


if __name__ == "__main__":
    main()
