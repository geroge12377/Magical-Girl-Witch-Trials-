"""
游戏主循环 - 整合中控API、导演API、角色API
"""

import anthropic
import json
import yaml
import time
from pathlib import Path
from config import get_api_key, MODEL, MAX_TOKENS, ENABLE_CACHE, OUTPUT_DIR


# ============================================
# 工具函数
# ============================================

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_yaml(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_yaml_safe(filepath, default=None):
    """安全加载YAML，文件不存在返回default"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return default


# ============================================
# 时间推进系统
# ============================================

def advance_time(minutes=10):
    """推进游戏时间，返回是否触发特殊事件"""
    current_day = load_json("world_state/current_day.json")
    
    # 解析当前时间
    hour, minute = map(int, current_day["time"].split(":"))
    
    # 推进时间
    minute += minutes
    while minute >= 60:
        minute -= 60
        hour += 1
    
    # 更新时间字符串
    new_time = f"{hour:02d}:{minute:02d}"
    current_day["time"] = new_time
    
    # 判断时间段和阶段
    special_event = None
    
    if hour >= 22:
        # 就寝时间，进入下一天
        current_day["day"] += 1
        current_day["time"] = "08:00"
        current_day["period"] = "morning"
        current_day["phase"] = "free_time"
        special_event = "new_day"
        print(f"\n🌙 夜深了...进入第{current_day['day']}天")
    elif hour >= 19:
        current_day["period"] = "night"
        current_day["phase"] = "free_time"
    elif hour >= 18 and hour < 19:
        if current_day["phase"] != "meal_time":
            current_day["period"] = "evening"
            current_day["phase"] = "meal_time"
            special_event = "dinner"
            print("\n🍽️ 晚餐时间到了，所有人前往食堂...")
    elif hour >= 13:
        current_day["period"] = "afternoon"
        current_day["phase"] = "free_time"
    elif hour >= 12 and hour < 13:
        if current_day["phase"] != "meal_time":
            current_day["period"] = "noon"
            current_day["phase"] = "meal_time"
            special_event = "lunch"
            print("\n🍽️ 午餐时间到了，所有人前往食堂...")
    else:
        current_day["period"] = "morning"
        current_day["phase"] = "free_time"
    
    # 更新下一个事件
    if hour < 12:
        current_day["next_event"] = {"type": "meal_time", "time": "12:00", "description": "午餐时间"}
    elif hour < 18:
        current_day["next_event"] = {"type": "meal_time", "time": "18:00", "description": "晚餐时间"}
    elif hour < 22:
        current_day["next_event"] = {"type": "sleep", "time": "22:00", "description": "就寝时间"}
    
    save_json("world_state/current_day.json", current_day)
    
    return special_event


def get_time_display():
    """获取时间显示字符串"""
    current_day = load_json("world_state/current_day.json")
    period_names = {
        "morning": "上午",
        "noon": "中午",
        "afternoon": "下午",
        "evening": "傍晚",
        "night": "夜晚"
    }
    period_cn = period_names.get(current_day["period"], current_day["period"])
    return f"第{current_day['day']}天 {current_day['time']} ({period_cn})"


# 默认角色数据（没有角色文件时使用）
DEFAULT_CHARACTER = {
    "core": {
        "name": {"zh": "未知角色", "ja": "不明キャラ"}
    },
    "personality": {
        "versions": {"simple": "性格不明"}
    },
    "speech": {
        "first_person": "私",
        "verbal_tics": ["...", "那个", "嗯"],
        "tone_by_emotion": {"nervous": "语气紧张"}
    }
}

def get_character_data(character_id):
    """获取角色数据，没有文件时用默认值"""
    char_path = Path(f"characters/{character_id}")
    
    core = load_yaml_safe(char_path / "core.yaml")
    personality = load_yaml_safe(char_path / "personality.yaml")
    speech = load_yaml_safe(char_path / "speech.yaml")
    
    if core is None:
        # 使用默认数据，但名字用character_id
        return {
            "core": {"name": {"zh": character_id, "ja": character_id}},
            "personality": DEFAULT_CHARACTER["personality"],
            "speech": DEFAULT_CHARACTER["speech"]
        }
    
    return {"core": core, "personality": personality, "speech": speech}

def clean_json_response(text):
    """清理API返回的JSON"""
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.replace(': +', ': ')
    return text.strip()


# ============================================
# 中控API - 调度13人位置
# ============================================

def call_controller_api():
    """调用中控API，更新13人位置和行为"""
    print("\n🎮 调用中控API...")
    
    current_day = load_json("world_state/current_day.json")
    character_states = load_json("world_state/character_states.json")
    
    # 构建prompt
    chars_info = []
    for char_id, state in character_states.items():
        chars_info.append(f"- {char_id}: 位置={state['location']}, 情绪={state['emotion']}, 压力={state['stress']}")
    
    prompt = f"""你是中控AI，负责调度13名魔法少女的位置和行为。

【当前时间】第{current_day['day']}天 {current_day['time']}

【可用位置】庭院、食堂、图书室、走廊、牢房区

【当前13人状态】
{chr(10).join(chars_info)}

【任务】规划下一个10分钟的位置和行为。

【输出格式】严格JSON，不要markdown：
{{
  "world_state": {{
    "aima": {{"location": "位置", "action": "行为", "purpose": "目的", "can_interact": true}},
    // ...13人完整
  }},
  "dynamic_events": [
    {{"trigger_time": 5, "event": "事件", "condition": "条件"}}
  ]
}}

必须包含：aima, hiro, melulu, hanna, noah, leya, koyuki, seira, maki, rena, yuki, tsubasa, mira"""

    # 调用API
    client = anthropic.Anthropic(api_key=get_api_key("controller"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    
    result = json.loads(clean_json_response(response.content[0].text))
    
    # 更新character_states.json
    for char_id, new_data in result["world_state"].items():
        if char_id in character_states:
            character_states[char_id]["location"] = new_data["location"]
            character_states[char_id]["action"] = new_data["action"]
            character_states[char_id]["can_interact"] = new_data["can_interact"]
    
    save_json("world_state/character_states.json", character_states)
    
    print("✅ 中控API完成，位置已更新")
    return result


# ============================================
# 导演API - 生成对话和选项
# ============================================

def call_director_api(character_id):
    """调用导演API，生成对话剧本、选项、以及ABC的预生成回应"""
    print(f"\n🎬 调用导演API (角色: {character_id})...")
    
    # 加载数据
    current_day = load_json("world_state/current_day.json")
    character_states = load_json("world_state/character_states.json")
    char_state = character_states[character_id]
    
    # 使用安全加载
    char_data = get_character_data(character_id)
    core = char_data["core"]
    personality = char_data["personality"]
    speech = char_data["speech"]
    
    prompt = f"""你是导演AI，生成场景对话、选项、以及每个选项的角色回应。

【角色】{core['name']['zh']} ({core['name']['ja']})
性格: {personality['versions']['simple']}
说话方式: 第一人称{speech['first_person']}，口癖{', '.join(speech['verbal_tics'][:3])}

【场景】{char_state['location']}，第{current_day['day']}天 {current_day['time']}
角色状态: 压力{char_state['stress']}，情绪{char_state['emotion']}
当前行为: {char_state['action']}

【任务】
1. 生成角色注意到玩家后的对话(3-5句)
2. 生成3个选项(A正面、B中性、C是Bad End)
3. 预生成每个选项的角色回应(2-3句)和状态变化

【输出格式】严格JSON：
{{
  "dialogue": [
    {{"speaker": "{character_id}", "text_cn": "中文", "text_jp": "日文", "emotion": "情绪"}}
  ],
  "choice_point": {{
    "prompt_cn": "你要怎么回应？",
    "options": [
      {{
        "id": "A",
        "text_cn": "正面选项",
        "leads_to_badend": false,
        "response": {{
          "dialogue": [
            {{"speaker": "{character_id}", "text_cn": "中文", "text_jp": "日文", "emotion": "情绪"}}
          ],
          "status_changes": {{"stress": -5, "affection": 3, "madness": 0}},
          "relationship_hint": "关系提示"
        }}
      }},
      {{
        "id": "B",
        "text_cn": "中性选项",
        "leads_to_badend": false,
        "response": {{
          "dialogue": [
            {{"speaker": "{character_id}", "text_cn": "中文", "text_jp": "日文", "emotion": "情绪"}}
          ],
          "status_changes": {{"stress": 0, "affection": 1, "madness": 0}},
          "relationship_hint": "关系提示"
        }}
      }},
      {{
        "id": "C",
        "text_cn": "危险选项(伤害角色)",
        "leads_to_badend": true,
        "response": {{
          "dialogue": [
            {{"speaker": "{character_id}", "text_cn": "中文", "text_jp": "日文", "emotion": "负面情绪"}}
          ],
          "status_changes": {{"stress": 15, "affection": -10, "madness": 5}},
          "relationship_hint": "负面关系提示",
          "badend_triggered": true
        }}
      }}
    ]
  }},
  "recommended_bgm": "音乐名"
}}"""

    client = anthropic.Anthropic(api_key=get_api_key("director"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )
    
    result = json.loads(clean_json_response(response.content[0].text))
    print("✅ 导演API完成（含ABC预生成回应）")
    return result


# ============================================
# 导演API - 生成选项后续对话
# ============================================

def display_pregenerated_response(option, character_id):
    """显示预生成的选项回应，并更新角色状态"""
    response = option.get("response", {})
    
    print("\n" + "=" * 50)
    print("📖 角色回应")
    print("=" * 50)
    
    # 显示对话
    for line in response.get("dialogue", []):
        speaker = line.get("speaker", character_id)
        emotion = line.get("emotion", "neutral")
        print(f"\n{speaker} [{emotion}]:")
        print(f"  {line['text_cn']}")
        if line.get("text_jp"):
            print(f"  {line['text_jp']}")
    
    # 显示状态变化
    changes = response.get("status_changes", {})
    if changes:
        print("\n📊 状态变化:")
        if changes.get("stress", 0) != 0:
            sign = "+" if changes["stress"] > 0 else ""
            print(f"  压力: {sign}{changes['stress']}")
        if changes.get("affection", 0) != 0:
            sign = "+" if changes["affection"] > 0 else ""
            print(f"  好感: {sign}{changes['affection']}")
        if changes.get("madness", 0) != 0:
            sign = "+" if changes["madness"] > 0 else ""
            print(f"  疯狂: {sign}{changes['madness']}")
    
    if response.get("relationship_hint"):
        print(f"\n💭 {response['relationship_hint']}")
    
    if response.get("badend_triggered"):
        print("\n" + "=" * 50)
        print("⚠️ BAD END 路线已触发！")
        print("=" * 50)
    
    # 更新角色状态
    if changes:
        character_states = load_json("world_state/character_states.json")
        if character_id in character_states:
            char_state = character_states[character_id]
            char_state["stress"] = max(0, min(100, char_state["stress"] + changes.get("stress", 0)))
            char_state["madness"] = max(0, min(100, char_state["madness"] + changes.get("madness", 0)))
            # 更新情绪
            if response.get("dialogue"):
                char_state["emotion"] = response["dialogue"][-1].get("emotion", char_state["emotion"])
            save_json("world_state/character_states.json", character_states)


# ============================================
# 角色API - 自由对话回复
# ============================================

def call_character_api(character_id, player_input):
    """调用角色API，生成自由对话回复"""
    print(f"\n💬 调用角色API (角色: {character_id})...")
    
    # 加载数据
    current_day = load_json("world_state/current_day.json")
    character_states = load_json("world_state/character_states.json")
    char_state = character_states[character_id]
    
    # 使用安全加载
    char_data = get_character_data(character_id)
    core = char_data["core"]
    personality = char_data["personality"]
    speech = char_data["speech"]
    
    prompt = f"""【身份】你是{core['name']['zh']}（{character_id}）

【性格】{personality['versions']['simple']}

【说话方式】第一人称：{speech['first_person']}，口癖：{', '.join(speech['verbal_tics'][:3])}

【当前状态】压力{char_state['stress']}/100，疯狂值{char_state['madness']}/100，情绪{char_state['emotion']}

【玩家输入】{player_input}

【输出格式】严格JSON：
{{
  "text_cn": "中文回复(50-200字)",
  "text_jp": "日语回复",
  "emotion": "情绪(happy/sad/angry/scared/nervous/calm/surprised/conflicted)",
  "internal_thought": "内心独白",
  "status_changes": {{
    "stress": 变化值,
    "affection": 变化值,
    "madness": 变化值,
    "reason": "原因"
  }},
  "new_memory": "新记忆"
}}"""

    client = anthropic.Anthropic(api_key=get_api_key("character"))
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    
    result = json.loads(clean_json_response(response.content[0].text))
    
    # 更新角色状态
    if "status_changes" in result:
        changes = result["status_changes"]
        char_state["stress"] = max(0, min(100, char_state["stress"] + changes.get("stress", 0)))
        char_state["madness"] = max(0, min(100, char_state["madness"] + changes.get("madness", 0)))
        char_state["emotion"] = result.get("emotion", char_state["emotion"])
        save_json("world_state/character_states.json", character_states)
    
    print("✅ 角色API完成，状态已更新")
    return result


# ============================================
# 显示函数
# ============================================

def display_world_state():
    """显示当前世界状态"""
    current_day = load_json("world_state/current_day.json")
    character_states = load_json("world_state/character_states.json")
    
    print("\n" + "=" * 50)
    print(f"📅 {get_time_display()} - {current_day['phase']}")
    print("=" * 50)
    
    # 按位置分组
    locations = {}
    for char_id, state in character_states.items():
        loc = state["location"]
        if loc not in locations:
            locations[loc] = []
        locations[loc].append((char_id, state))
    
    for loc, chars in locations.items():
        print(f"\n📍 {loc} ({len(chars)}人)")
        for char_id, state in chars:
            mark = "✓" if state["can_interact"] else "✗"
            print(f"  {mark} {char_id}: {state['action']} [{state['emotion']}]")


def display_dialogue(result):
    """显示对话剧本"""
    print("\n" + "=" * 50)
    print("📖 对话")
    print("=" * 50)
    
    for line in result["dialogue"]:
        print(f"\n{line['speaker']} [{line['emotion']}]:")
        print(f"  {line['text_cn']}")


def display_choices(result):
    """显示选项"""
    print("\n" + "=" * 50)
    print(f"❓ {result['choice_point']['prompt_cn']}")
    print("=" * 50)
    
    for opt in result["choice_point"]["options"]:
        mark = " ⚠️" if opt["leads_to_badend"] else ""
        print(f"\n{opt['id']}. {opt['text_cn']}{mark}")
    
    print("\nD. [自由输入]")


def display_response(result):
    """显示角色回复"""
    print("\n" + "=" * 50)
    print("💬 角色回复")
    print("=" * 50)
    print(f"\n{result['text_cn']}")
    print(f"\n[情绪: {result['emotion']}]")
    if result.get("status_changes"):
        sc = result["status_changes"]
        print(f"[状态变化: stress{sc.get('stress',0):+d}, affection{sc.get('affection',0):+d}]")


# ============================================
# 主循环
# ============================================

def game_loop():
    """游戏主循环，返回特殊事件"""
    
    # 1. 中控API - 更新位置
    controller_result = call_controller_api()
    display_world_state()
    
    # 显示动态事件
    if controller_result.get("dynamic_events"):
        print("\n⚡ 即将发生的事件:")
        for evt in controller_result["dynamic_events"]:
            print(f"  +{evt['trigger_time']}分钟: {evt['event']}")
    
    # 2. 玩家选择位置
    print("\n" + "=" * 50)
    print("🚶 你要去哪里？")
    print("=" * 50)
    print("1. 庭院")
    print("2. 食堂")
    print("3. 图书室")
    print("4. 走廊")
    print("5. 牢房区")
    print("0. 退出")
    
    location_map = {"1": "庭院", "2": "食堂", "3": "图书室", "4": "走廊", "5": "牢房区"}
    
    choice = input("\n输入数字: ").strip()
    if choice == "0":
        print("\n👋 游戏结束")
        return None
    
    target_location = location_map.get(choice, "庭院")
    print(f"\n你来到了 {target_location}")
    
    # 3. 找到该位置的可互动角色
    character_states = load_json("world_state/character_states.json")
    available_chars = [
        (char_id, state) for char_id, state in character_states.items()
        if state["location"] == target_location and state["can_interact"]
    ]
    
    if not available_chars:
        print("这里没有可以交谈的人。")
        return
    
    print(f"\n👥 这里有: {', '.join([c[0] for c in available_chars])}")
    
    # 选择角色
    target_char = available_chars[0][0]  # 默认第一个
    if len(available_chars) > 1:
        print("\n你想和谁交谈？")
        for i, (char_id, state) in enumerate(available_chars, 1):
            print(f"{i}. {char_id} - {state['action']}")
        char_choice = input("输入数字: ").strip()
        idx = int(char_choice) - 1 if char_choice.isdigit() else 0
        target_char = available_chars[min(idx, len(available_chars)-1)][0]
    
    print(f"\n你走向 {target_char}...")
    
    # 4. 导演API - 生成对话和选项
    director_result = call_director_api(target_char)
    display_dialogue(director_result)
    display_choices(director_result)
    
    # 5. 玩家选择
    player_choice = input("\n输入选项 (A/B/C/D): ").strip().upper()
    
    if player_choice == "D":
        # 自由输入 - 调用角色API（需要等待）
        player_input = input("你说: ")
        character_result = call_character_api(target_char, player_input)
        display_response(character_result)
    elif player_choice in ["A", "B", "C"]:
        # 预设选项 - 使用预生成回应（零延迟）
        opt = next((o for o in director_result["choice_point"]["options"] if o["id"] == player_choice), None)
        if opt:
            print(f"\n你选择了: {opt['text_cn']}")
            # 直接显示预生成的回应
            display_pregenerated_response(opt, target_char)
    
    # 6. 时间推进
    special_event = advance_time(10)
    
    # 7. 显示最终状态
    display_world_state()
    
    print("\n" + "=" * 60)
    print(f"✅ 一轮游戏循环完成 | 当前: {get_time_display()}")
    print("=" * 60)
    
    return special_event


def main():
    """主游戏入口，支持多轮循环"""
    print("=" * 60)
    print("🎮 魔法少女的魔女审判 - 游戏主循环测试")
    print("=" * 60)
    
    while True:
        special_event = game_loop()
        
        # 处理特殊事件
        if special_event == "new_day":
            print("\n" + "=" * 60)
            current_day = load_json("world_state/current_day.json")
            print(f"☀️ 第{current_day['day']}天开始了")
            print("=" * 60)
        
        # 询问是否继续
        cont = input("\n继续下一轮？(y/n): ").strip().lower()
        if cont != 'y':
            print("\n👋 游戏结束，感谢游玩！")
            break


if __name__ == "__main__":
    main()
