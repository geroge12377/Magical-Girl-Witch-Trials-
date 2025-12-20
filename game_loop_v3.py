# ============================================================================
# 游戏主循环 v3 - 两层导演架构 + 故事规划系统
# ============================================================================
# 架构：故事规划层 + 导演规划层 + 角色演出层
# 流程：大纲检查 → 导演规划 → 角色演出 → 玩家选择 → 状态更新 → 结局判定
# ============================================================================

import json
import yaml
import random
from pathlib import Path
from typing import Dict, List, Optional, Any

# 导入API模块
from api import DirectorPlanner, CharacterActor, ScenePlan, Beat, DialogueOutput
from api import StoryPlanner, EndingType
from config import get_api_key, MODEL, OUTPUT_DIR


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


# ============================================================================
# 显示函数
# ============================================================================

def display_header():
    """显示游戏标题"""
    print("\n" + "=" * 60)
    print("   🌙 魔法少女的魔女审判 - AI对话系统 v3")
    print("   📐 两层导演架构: Planner + Actor")
    print("=" * 60)

def display_time(project_root: Path):
    """显示当前时间"""
    current_day = load_json(project_root / "world_state" / "current_day.json")
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

def display_world_state(project_root: Path):
    """显示世界状态"""
    character_states = load_json(project_root / "world_state" / "character_states.json")

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
        for char_id, state in chars[:5]:
            stress = state.get("stress", 0)
            emotion = state.get("emotion", "neutral")
            stress_bar = "█" * (stress // 20) + "░" * (5 - stress // 20)
            print(f"  {char_id:8} [{stress_bar}] {emotion:10}")
        if len(chars) > 5:
            print(f"  ...还有{len(chars)-5}人")

def display_scene_plan(scene_plan: ScenePlan):
    """显示场景规划"""
    print("\n" + "=" * 50)
    print(f"🎬 场景规划: {scene_plan.scene_name}")
    print("=" * 50)
    print(f"📍 地点: {scene_plan.location}")
    print(f"⏱️  预计时长: {scene_plan.time_estimate_minutes}分钟")
    print(f"📊 Beat数量: {scene_plan.total_beats}")
    print(f"🎵 推荐BGM: {scene_plan.recommended_bgm}")
    print(f"\n📈 整体弧线: {scene_plan.overall_arc}")

    if scene_plan.key_moments:
        print(f"\n⭐ 关键时刻:")
        for moment in scene_plan.key_moments:
            print(f"   • {moment}")

def display_beat_info(beat: Beat, beat_index: int):
    """显示Beat信息"""
    type_icons = {
        "opening": "🎬",
        "development": "📖",
        "tension": "⚡",
        "climax": "🔥",
        "resolution": "🌙"
    }
    icon = type_icons.get(beat.beat_type, "▶")

    print(f"\n{icon} Beat {beat_index + 1}: {beat.beat_type.upper()}")
    print(f"   {beat.description[:60]}...")
    print(f"   张力: {'▓' * beat.tension_level}{'░' * (10 - beat.tension_level)} {beat.tension_level}/10")

def display_dialogue(dialogue_output: DialogueOutput, show_jp: bool = False):
    """
    显示对话（双语支持）

    Args:
        dialogue_output: 对话输出
        show_jp: 是否同时显示日文（用于调试TTS）
    """
    print("\n" + "-" * 50)

    for line in dialogue_output.dialogue:
        speaker = line.speaker
        text_cn = line.text_cn
        text_jp = line.text_jp
        emotion = line.emotion
        action = line.action

        if speaker == "narrator":
            print(f"\n  {text_cn}")
            if show_jp and text_jp != text_cn:
                print(f"  [JP] {text_jp}")
        else:
            emotion_mark = f" [{emotion}]" if emotion else ""
            action_mark = f" *{action}*" if action else ""
            print(f"\n【{speaker}{emotion_mark}】{action_mark}")
            print(f"  「{text_cn}」")
            if show_jp and text_jp:
                print(f"  [TTS] 「{text_jp}」")

def display_choices(choice_point: Dict):
    """显示选项"""
    if not choice_point:
        return

    print("\n" + "=" * 50)
    print(f"❓ {choice_point.get('prompt', '你要怎么做？')}")
    print("=" * 50)

    for opt in choice_point.get("options", []):
        opt_id = opt.get("id", "?")
        text = opt.get("text", "...")
        leads_to = opt.get("leads_to", "")
        hint = f" → {leads_to}" if leads_to else ""
        print(f"\n  {opt_id}. {text}{hint}")

    print(f"\n  D. [自由输入]")
    print(f"  Q. [查看状态]")

def display_location_menu(locations: dict, current_phase: str):
    """显示地点选择菜单"""
    print("\n" + "-" * 40)
    print("🚶 你要去哪里？")
    print("-" * 40)

    locs = locations.get("locations", {})
    menu_items = []

    for i, (loc_id, loc_data) in enumerate(locs.items(), 1):
        name = loc_data.get("name_cn", loc_id)

        # 检查是否锁定
        if loc_data.get("locked", False):
            continue

        menu_items.append((i, loc_id, name))
        print(f"  {i}. {name}")

    print(f"\n  0. [跳过/待在原地]")

    return menu_items


# ============================================================================
# 游戏主循环 v3
# ============================================================================

class GameLoopV3:
    """游戏主循环 v3 - 三层架构（故事规划 + 导演规划 + 角色演出）"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.story_planner = StoryPlanner(self.project_root)  # 故事规划层
        self.planner = DirectorPlanner(self.project_root)      # 导演规划层
        self.actor = CharacterActor(self.project_root)         # 角色演出层
        self.locations = load_yaml(self.project_root / "world_state" / "locations.yaml")

        self.player_location = "牢房区"
        self.running = True
        self.current_scene_plan: Optional[ScenePlan] = None
        self.pregenerated_responses: Dict = {}
        self.show_jp_text = False  # 是否显示日文（调试用）

    def run(self):
        """运行游戏"""
        display_header()

        while self.running:
            try:
                self.game_turn()
            except KeyboardInterrupt:
                print("\n\n👋 游戏中断，感谢游玩！")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                import traceback
                traceback.print_exc()

            if not self.running:
                break

            # 询问继续
            cont = input("\n继续？(y/n): ").strip().lower()
            if cont != 'y':
                print("\n👋 游戏暂停，感谢游玩！")
                break

    def game_turn(self):
        """一个游戏回合"""

        # 1. 显示时间
        display_time(self.project_root)

        # 2. 显示世界状态
        display_world_state(self.project_root)

        # 3. 玩家选择地点
        current_day = load_json(self.project_root / "world_state" / "current_day.json")
        menu = display_location_menu(self.locations, current_day.get("phase", "free_time"))

        choice = input("\n输入数字: ").strip()

        if choice == "0":
            print("\n你决定待在原地...")
            self._increment_event_count()
            return

        # 解析选择
        try:
            idx = int(choice)
            selected = next((m for m in menu if m[0] == idx), None)
            if selected:
                _, loc_id, loc_name = selected
                self.player_location = loc_name
                print(f"\n你来到了 {loc_name}...")
            else:
                print("\n无效选择，待在原地...")
                return
        except:
            print("\n无效选择，待在原地...")
            return

        # 4. 调用导演规划层
        print("\n🎬 导演正在规划场景...")
        scene_plan = self.planner.plan_scene(
            location=self.player_location,
            scene_type="free"
        )
        self.current_scene_plan = scene_plan

        # 5. 显示场景规划
        display_scene_plan(scene_plan)

        # 6. 一次性生成所有 Beat 的对话
        print("\n💬 角色正在演出...")
        all_dialogues = self.actor.generate_scene_dialogue(scene_plan)

        # 7. 逐个显示 Beat
        for i, beat in enumerate(scene_plan.beats):
            display_beat_info(beat, i)

            # 显示对话（从预生成的列表中获取）
            if i < len(all_dialogues):
                dialogue_output = all_dialogues[i]
                display_dialogue(dialogue_output, self.show_jp_text)
                # 应用效果
                self._apply_dialogue_effects(dialogue_output)

            # 检查是否是玩家选择点
            if scene_plan.player_choice_point:
                if scene_plan.player_choice_point.get("after_beat") == beat.beat_id:
                    # 预生成选项回应
                    print("\n🔮 预生成选项回应...")
                    self.pregenerated_responses = self.actor.generate_choice_responses(
                        scene_plan.player_choice_point,
                        beat.characters
                    )

                    # 显示选项并处理玩家选择
                    self._handle_player_choice(scene_plan.player_choice_point, beat.characters)

            # 暂停让玩家阅读
            if i < len(scene_plan.beats) - 1:
                input("\n[按Enter继续...]")

        # 8. 场景结束
        print("\n" + "=" * 50)
        print("📖 场景结束")
        print("=" * 50)

        # 应用场景结果
        self._apply_scene_outcomes(scene_plan)

        # 增加事件计数
        self._increment_event_count()

    def _handle_player_choice(self, choice_point: Dict, characters: List[str]):
        """处理玩家选择"""
        display_choices(choice_point)

        while True:
            choice = input("\n输入选项 (A/B/C/D/Q): ").strip().upper()

            if choice == "Q":
                display_world_state(self.project_root)
                display_choices(choice_point)
                continue

            if choice == "D":
                # 自由输入
                player_input = input("\n你说: ").strip()
                if not player_input:
                    continue

                # 找主要角色
                main_char = characters[0] if characters else None
                if main_char:
                    print(f"\n💬 {main_char} 正在思考...")
                    # 可以调用角色API进行自由对话
                    print(f"\n【{main_char}】")
                    print(f"  「......」")
                break

            if choice in ["A", "B", "C"]:
                options = choice_point.get("options", [])
                opt = next((o for o in options if o.get("id") == choice), None)

                if opt:
                    print(f"\n你选择了: {opt.get('text')}")

                    # 显示预生成回应
                    if choice in self.pregenerated_responses:
                        response = self.pregenerated_responses[choice]
                        print("\n" + "-" * 40)
                        for line in response.dialogue:
                            print(f"\n【{line.speaker}】[{line.emotion}]")
                            print(f"  「{line.text_cn}」")

                        # 应用效果
                        self._apply_choice_effects(response.effects)

                        if opt.get("leads_to") == "负面" or opt.get("leads_to") == "危险":
                            print("\n⚠️ 这个选择可能导向危险的结局...")
                break

            print("无效输入，请重试")

    def _apply_dialogue_effects(self, dialogue_output: DialogueOutput):
        """应用对话效果"""
        if not dialogue_output.effects:
            return

        try:
            states_path = self.project_root / "world_state" / "character_states.json"
            states = load_json(states_path)

            for char_id, effects in dialogue_output.effects.items():
                if char_id in states:
                    if "stress" in effects:
                        current = states[char_id].get("stress", 50)
                        states[char_id]["stress"] = max(0, min(100, current + effects["stress"]))
                    if "emotion" in effects:
                        states[char_id]["emotion"] = effects["emotion"]
                    if "madness" in effects:
                        current = states[char_id].get("madness", 0)
                        states[char_id]["madness"] = max(0, min(100, current + effects["madness"]))

            save_json(states_path, states)
        except Exception as e:
            print(f"[警告] 应用对话效果失败: {e}")

    def _apply_choice_effects(self, effects: Dict):
        """应用选项效果"""
        if not effects:
            return

        try:
            states_path = self.project_root / "world_state" / "character_states.json"
            states = load_json(states_path)

            # effects可能是 {"stress": 5, "affection": -3} 格式
            # 或者 {"char_id": {"stress": 5}} 格式
            for key, value in effects.items():
                if isinstance(value, dict):
                    # 角色特定效果
                    if key in states:
                        for stat, change in value.items():
                            if stat in ["stress", "madness"]:
                                current = states[key].get(stat, 0)
                                states[key][stat] = max(0, min(100, current + change))
                else:
                    # 全局效果（应用到某个主要角色）
                    pass  # 需要知道主要角色

            save_json(states_path, states)
        except Exception as e:
            print(f"[警告] 应用选项效果失败: {e}")

    def _apply_scene_outcomes(self, scene_plan: ScenePlan):
        """应用场景结果"""
        outcomes = scene_plan.outcomes
        if not outcomes:
            return

        try:
            states_path = self.project_root / "world_state" / "character_states.json"
            states = load_json(states_path)

            # 应用压力变化
            stress_changes = outcomes.get("stress_changes", {})
            for char_id, change in stress_changes.items():
                if char_id in states:
                    current = states[char_id].get("stress", 50)
                    states[char_id]["stress"] = max(0, min(100, current + change))

            save_json(states_path, states)

            # 设置标记
            flags_to_set = outcomes.get("flags_to_set", [])
            if flags_to_set:
                day_path = self.project_root / "world_state" / "current_day.json"
                current_day = load_json(day_path)
                flags = current_day.get("flags", {})
                for flag in flags_to_set:
                    flags[flag] = True
                current_day["flags"] = flags
                save_json(day_path, current_day)

        except Exception as e:
            print(f"[警告] 应用场景结果失败: {e}")

    def _increment_event_count(self):
        """增加事件计数"""
        try:
            day_path = self.project_root / "world_state" / "current_day.json"
            current_day = load_json(day_path)
            current_day["event_count"] = current_day.get("event_count", 0) + 1
            save_json(day_path, current_day)
        except Exception as e:
            print(f"[警告] 更新事件计数失败: {e}")

    def _update_npc_locations(self):
        """更新NPC位置（简化版）"""
        try:
            states_path = self.project_root / "world_state" / "character_states.json"
            states = load_json(states_path)

            locations_list = ["食堂", "庭院", "走廊", "图书室", "牢房区"]
            actions = ["站着发呆", "四处张望", "低头沉思", "靠墙休息", "来回踱步"]

            for char_id, state in states.items():
                # 随机移动
                if random.random() < 0.3:  # 30%几率移动
                    state["location"] = random.choice(locations_list)
                state["action"] = random.choice(actions)
                state["can_interact"] = True

            save_json(states_path, states)
        except Exception as e:
            print(f"[警告] 更新NPC位置失败: {e}")


# ============================================================================
# 入口
# ============================================================================

def main():
    """主入口"""
    print("\n🎮 正在启动游戏...")

    game = GameLoopV3()
    game.run()


if __name__ == "__main__":
    main()
