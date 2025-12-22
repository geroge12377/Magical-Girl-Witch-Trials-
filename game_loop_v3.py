# ============================================================================
# 游戏主循环 v3 - 三层导演架构 + 完整三天流程
# ============================================================================
# 架构：故事规划层 + 导演规划层 + 角色演出层
# 流程：大纲生成 → 时段循环 → 导演规划 → 角色演出 → 结局判定
# ============================================================================

import json
import yaml
import random
from pathlib import Path
from typing import Dict, List, Optional, Any

# 导入API模块
from api import DirectorPlanner, CharacterActor, ScenePlan, Beat, DialogueOutput
from api import StoryPlanner, EndingType
from api.fixed_event_manager import FixedEventManager
from config import get_api_key, MODEL, OUTPUT_DIR


# ============================================================================
# 常量
# ============================================================================

# 时段顺序
PERIODS = ["dawn", "morning", "noon", "afternoon", "evening", "night"]

# 时段中文名
PERIOD_NAMES = {
    "dawn": "黎明",
    "morning": "上午",
    "noon": "正午",
    "afternoon": "下午",
    "evening": "傍晚",
    "night": "夜晚"
}

# 阶段中文名
PHASE_NAMES = {
    "free_time": "自由时间",
    "investigation": "调查阶段",
    "trial": "审判阶段",
    "ending": "结局"
}


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
    print("   魔法少女的魔女审判 - AI对话系统 v3")
    print("   三层导演架构: StoryPlanner + DirectorPlanner + Actor")
    print("=" * 60)

def display_time(project_root: Path):
    """显示当前时间"""
    current_day = load_json(project_root / "world_state" / "current_day.json")
    period = current_day.get("period", "dawn")
    phase = current_day.get("phase", "free_time")

    period_cn = PERIOD_NAMES.get(period, period)
    phase_cn = PHASE_NAMES.get(phase, phase)

    print(f"\n[第{current_day['day']}天 - {period_cn}] ({phase_cn})")
    print(f"   事件计数: {current_day.get('event_count', 0)}")

def display_world_state(project_root: Path):
    """显示世界状态"""
    character_states = load_json(project_root / "world_state" / "character_states.json")

    # 按地点分组
    loc_chars = {}
    for char_id, state in character_states.items():
        if state.get("status") != "alive":
            continue
        loc = state.get("location", "未知")
        if loc not in loc_chars:
            loc_chars[loc] = []
        loc_chars[loc].append((char_id, state))

    print("\n" + "-" * 40)
    print("当前位置分布")
    print("-" * 40)

    for loc, chars in sorted(loc_chars.items()):
        print(f"\n[{loc}] ({len(chars)}人)")
        for char_id, state in chars[:5]:
            stress = state.get("stress", 0)
            madness = state.get("madness", 0)
            emotion = state.get("emotion", "neutral")
            stress_bar = "*" * (stress // 20) + "-" * (5 - stress // 20)
            print(f"  {char_id:8} S:[{stress_bar}] M:{madness:2} {emotion:10}")
        if len(chars) > 5:
            print(f"  ...还有{len(chars)-5}人")

def display_scene_plan(scene_plan: ScenePlan):
    """显示场景规划"""
    print("\n" + "=" * 50)
    print(f"[场景规划] {scene_plan.scene_name}")
    print("=" * 50)
    print(f"地点: {scene_plan.location}")
    print(f"预计时长: {scene_plan.time_estimate_minutes}分钟")
    print(f"Beat数量: {scene_plan.total_beats}")
    print(f"推荐BGM: {scene_plan.recommended_bgm}")
    print(f"\n整体弧线: {scene_plan.overall_arc}")

    if scene_plan.key_moments:
        print(f"\n关键时刻:")
        for moment in scene_plan.key_moments:
            print(f"   - {moment}")

def display_beat_info(beat: Beat, beat_index: int):
    """显示Beat信息"""
    type_marks = {
        "opening": "[开]",
        "development": "[展]",
        "tension": "[张]",
        "climax": "[潮]",
        "resolution": "[收]"
    }
    mark = type_marks.get(beat.beat_type, "[?]")

    print(f"\n{mark} Beat {beat_index + 1}: {beat.beat_type.upper()}")
    desc = beat.description[:60] + "..." if len(beat.description) > 60 else beat.description
    print(f"   {desc}")
    tension_bar = "#" * beat.tension_level + "-" * (10 - beat.tension_level)
    print(f"   张力: [{tension_bar}] {beat.tension_level}/10")

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
            print(f"\n[{speaker}{emotion_mark}]{action_mark}")
            print(f"  {text_cn}")
            if show_jp and text_jp:
                print(f"  [TTS] {text_jp}")

def display_choices(choice_point: Dict):
    """显示选项"""
    if not choice_point:
        return

    print("\n" + "=" * 50)
    print(f"? {choice_point.get('prompt', '你要怎么做?')}")
    print("=" * 50)

    for opt in choice_point.get("options", []):
        opt_id = opt.get("id", "?")
        text = opt.get("text", "...")
        leads_to = opt.get("leads_to", "")
        hint = f" -> {leads_to}" if leads_to else ""
        print(f"\n  {opt_id}. {text}{hint}")

    print(f"\n  D. [自由输入]")
    print(f"  Q. [查看状态]")

def display_location_menu(locations: dict, current_phase: str):
    """显示地点选择菜单"""
    print("\n" + "-" * 40)
    print("你要去哪里?")
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

def display_ending(ending_type: str, ending_info: Dict):
    """显示结局"""
    print("\n" + "=" * 60)
    print("=" * 60)
    print(f"\n  {ending_info.get('title', ending_type)}")
    print(f"\n  {ending_info.get('description', '')}")
    print("\n" + "=" * 60)
    print("=" * 60)


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
        self.fixed_event_manager = FixedEventManager(self.project_root)  # 固定事件管理器
        self.locations = load_yaml(self.project_root / "world_state" / "locations.yaml")

        self.player_location = "牢房区"
        self.running = True
        self.current_scene_plan: Optional[ScenePlan] = None
        self.pregenerated_responses: Dict = {}
        self.show_jp_text = False  # 是否显示日文（调试用）

    def reset_game_state(self):
        """重置游戏状态（每次Demo启动时自动调用）"""
        print("[系统] 正在重置游戏状态...")

        # 重置 current_day.json
        initial_day_state = {
            "chapter": 1,
            "day": 1,
            "period": "dawn",
            "phase": "free_time",
            "event_count": 0,
            "daily_event_count": 0,
            "alive_count": 13,
            "dead_count": 0,
            "investigation_count": 0,
            "murderer_id": None,
            "victim_id": None,
            "crime_scene": None,
            "case_status": "no_case",
            "flags": {},
            "triggered_events": [],
            "next_event": None
        }
        save_json(self.project_root / "world_state" / "current_day.json", initial_day_state)

        # 重置 character_states.json
        character_states_path = self.project_root / "world_state" / "character_states.json"
        character_states = load_json(character_states_path)

        # 初始角色状态（基础stress/madness值）
        initial_stats = {
            "aima": {"stress": 10, "madness": 0, "emotion": "nervous"},
            "hiro": {"stress": 30, "madness": 5, "emotion": "defiant"},
            "anan": {"stress": 40, "madness": 0, "emotion": "terrified"},
            "noah": {"stress": 15, "madness": 3, "emotion": "withdrawn"},
            "reia": {"stress": 50, "madness": 2, "emotion": "anxious"},
            "miria": {"stress": 10, "madness": 0, "emotion": "calm"},
            "margo": {"stress": 5, "madness": 0, "emotion": "thoughtful"},
            "nanoka": {"stress": 20, "madness": 1, "emotion": "quiet"},
            "arisa": {"stress": 35, "madness": 5, "emotion": "irritated"},
            "sherry": {"stress": 25, "madness": 2, "emotion": "curious"},
            "hannah": {"stress": 5, "madness": 0, "emotion": "calm"},
            "coco": {"stress": 15, "madness": 3, "emotion": "mysterious"},
            "meruru": {"stress": 50, "madness": 0, "emotion": "apologetic"}
        }

        for char_id, state in character_states.items():
            if char_id in initial_stats:
                state["stress"] = initial_stats[char_id]["stress"]
                state["madness"] = initial_stats[char_id]["madness"]
                state["emotion"] = initial_stats[char_id]["emotion"]
            state["location"] = "牢房区"
            state["action"] = "刚刚醒来"
            state["alive"] = True
            state["status"] = "alive"
            state["can_interact"] = True
            state["is_murderer"] = False
            state["is_victim"] = False
            state["magic_revealed"] = False

        save_json(character_states_path, character_states)
        print("[系统] 游戏状态已重置完成")

    def run(self):
        """运行游戏"""
        display_header()

        # ★ 每次启动时自动重置状态
        self.reset_game_state()

        # 生成三天大纲
        print("\n[系统] 正在生成三天大纲...")
        self.story_planner.generate_three_day_outline()
        print("[系统] 大纲生成完成!")

        while self.running:
            try:
                self.game_turn()
            except KeyboardInterrupt:
                print("\n\n游戏中断，感谢游玩!")
                break
            except Exception as e:
                print(f"\n[错误] {e}")
                import traceback
                traceback.print_exc()

            if not self.running:
                break

            # 询问继续
            cont = input("\n继续? (y/n): ").strip().lower()
            if cont != 'y':
                print("\n游戏暂停，感谢游玩!")
                break

    def game_turn(self):
        """一个游戏回合"""

        # 0. 加载当前状态
        current_day_data = load_json(self.project_root / "world_state" / "current_day.json")
        print(f"[DEBUG] game_turn() 开始: day={current_day_data.get('day')}, period={current_day_data.get('period')}, event_count={current_day_data.get('event_count')}")

        # 检查是否已结束
        if current_day_data.get("phase") == "ending":
            self.running = False
            return

        # 1. 显示时间
        display_time(self.project_root)

        # 2. 显示世界状态
        display_world_state(self.project_root)

        # 3. 检查是否处于特殊阶段
        phase = current_day_data.get("phase", "free_time")
        if phase == "investigation":
            self.run_investigation()
            return
        elif phase == "trial":
            self.run_trial()
            return

        # === 新增：检查固定事件 ===
        fixed_event = self.fixed_event_manager.get_pending_fixed_event()
        if fixed_event:
            self._run_fixed_event(fixed_event)
            return

        # 4. 玩家选择地点
        menu = display_location_menu(self.locations, phase)

        choice = input("\n输入数字: ").strip()

        if choice == "0":
            print("\n你决定待在原地...")
            self._increment_event_count()
            self._check_and_advance()
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
                self._increment_event_count()
                self._check_and_advance()
                return
        except:
            print("\n无效选择，待在原地...")
            self._increment_event_count()
            self._check_and_advance()
            return

        # 5. 调用导演规划层
        print("\n[导演] 正在规划场景...")
        scene_plan = self.planner.plan_scene(
            location=self.player_location,
            scene_type="free"
        )
        self.current_scene_plan = scene_plan

        # 6. 显示场景规划
        display_scene_plan(scene_plan)

        # 7. 一次性生成所有 Beat 的对话和预选回应（v6优化：零延迟）
        print("\n[角色] 正在演出...")
        all_dialogues, pregenerated_responses = self.actor.generate_scene_dialogue(scene_plan)

        # ★ 保存预生成的回应（提前生成，无需在选择点等待）
        if pregenerated_responses:
            self.pregenerated_responses = pregenerated_responses

        # 8. 逐个显示 Beat
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
                    # ★ v6优化：使用提前生成的回应，零延迟
                    # 显示选项并处理玩家选择
                    self._handle_player_choice(scene_plan.player_choice_point, beat.characters)

            # 暂停让玩家阅读
            if i < len(scene_plan.beats) - 1:
                input("\n[按Enter继续...]")

        # 9. 场景结束
        print("\n" + "=" * 50)
        print("[场景结束]")
        print("=" * 50)

        # 应用场景结果
        self._apply_scene_outcomes(scene_plan)

        # 增加事件计数
        self._increment_event_count()

        # 10. 检查结局和推进时间
        self._check_and_advance()

    def _check_and_advance(self):
        """检查结局条件并推进时间"""
        current_day_data = load_json(self.project_root / "world_state" / "current_day.json")

        # 检测结局（仅在第3天晚上检测）
        day = current_day_data.get("day", 1)
        period = current_day_data.get("period", "dawn")

        if day >= 3 and period == "night":
            ending = self.story_planner.check_ending()
            if ending:
                self.handle_ending(ending)
                return

        # 检测杀人预备（每天 night 检测）
        if period == "night":
            murder = self.story_planner.check_murder_prep()
            if murder and murder.get("active") and murder.get("can_execute"):
                self.handle_murder_event(murder)
                return
            else:
                # 检查是否有高madness角色可能杀人
                self._check_madness_murder()

        # 推进时间
        self.advance_time()

    def advance_time(self):
        """推进时间：时段->时段，night后进入下一天"""
        day_path = self.project_root / "world_state" / "current_day.json"
        current_day = load_json(day_path)

        period = current_day.get("period", "dawn")
        print(f"[DEBUG] advance_time() 调用前: period={period}")

        try:
            idx = PERIODS.index(period)
        except ValueError:
            idx = 0

        if idx < len(PERIODS) - 1:
            # 推进到下一时段
            next_period = PERIODS[idx + 1]
            current_day["period"] = next_period
            print(f"\n[时间流逝] -> {PERIOD_NAMES.get(next_period, next_period)}")
        else:
            # night结束，进入下一天
            current_day["day"] = current_day.get("day", 1) + 1
            current_day["period"] = "dawn"
            current_day["daily_event_count"] = 0
            print(f"\n[新的一天] 第{current_day['day']}天开始了...")

            # 检查是否超过3天
            if current_day["day"] > 3:
                # 游戏应该在第3天结束前触发结局
                ending = self.story_planner.check_ending()
                self.handle_ending(ending)
                return

        # ★ 关键：确保保存到文件
        save_json(day_path, current_day)
        print(f"[DEBUG] advance_time() 调用后: period={current_day.get('period')}")

    def _check_madness_murder(self):
        """检查是否有角色madness过高触发杀人"""
        states_path = self.project_root / "world_state" / "character_states.json"
        states = load_json(states_path)

        # 找madness最高的角色
        highest_madness = 0
        killer_id = None
        for char_id, state in states.items():
            if state.get("status") != "alive":
                continue
            madness = state.get("madness", 0)
            if madness > highest_madness:
                highest_madness = madness
                killer_id = char_id

        # 如果有人madness >= 70，可能触发杀人
        if highest_madness >= 70 and killer_id:
            # 更新murder_prep状态
            self.story_planner.update_murder_prep(
                char_id=killer_id,
                target_id=self._select_victim(killer_id, states),
                motivation="madness_threshold",
                progress=100
            )
            print(f"\n[警告] {killer_id} 的疯狂值达到危险水平...")

    def _select_victim(self, killer_id: str, states: Dict) -> str:
        """选择受害者（基于关系或随机）"""
        alive_chars = [
            cid for cid, state in states.items()
            if state.get("status") == "alive" and cid != killer_id
        ]
        if alive_chars:
            return random.choice(alive_chars)
        return None

    def handle_ending(self, ending_type: str):
        """处理结局"""
        print("\n" + "=" * 60)
        print("[结局触发]")
        print("=" * 60)

        ending_info = self.story_planner.get_ending_description(ending_type)
        display_ending(ending_type, ending_info)

        # 更新状态
        day_path = self.project_root / "world_state" / "current_day.json"
        current_day = load_json(day_path)
        current_day["phase"] = "ending"
        current_day["ending_type"] = ending_type
        save_json(day_path, current_day)

        self.running = False

    def handle_murder_event(self, murder_prep: dict):
        """处理杀人事件 -> 调查 -> 审判"""
        print("\n" + "=" * 60)
        print("[杀人事件发生]")
        print("=" * 60)

        killer_id = murder_prep.get("killer_id")
        target_id = murder_prep.get("target_id")

        print(f"\n  这一夜，有什么不对劲...")
        print(f"  走廊里传来异样的脚步声，然后是...尖叫。")
        print(f"  接着，一切归于寂静。")
        input("\n[按Enter继续...]")

        # 更新状态
        states_path = self.project_root / "world_state" / "character_states.json"
        states = load_json(states_path)
        if target_id and target_id in states:
            states[target_id]["status"] = "dead"
            save_json(states_path, states)

        # 更新current_day
        day_path = self.project_root / "world_state" / "current_day.json"
        current_day = load_json(day_path)
        current_day["murderer_id"] = killer_id
        current_day["victim_id"] = target_id
        current_day["flags"]["murder_occurred"] = True
        current_day["phase"] = "investigation"
        current_day["investigation_count"] = 5  # 5次调查机会
        save_json(day_path, current_day)

        print(f"\n  [早晨] 发现了尸体...")
        print(f"  {target_id} 已经死亡。")
        print(f"\n  典狱长: 发现了尸体! 现在开始进入调查时间。")
        input("\n[按Enter进入调查阶段...]")

    def run_investigation(self):
        """调查阶段（框架）"""
        day_path = self.project_root / "world_state" / "current_day.json"
        current_day = load_json(day_path)

        inv_count = current_day.get("investigation_count", 0)

        print("\n" + "=" * 50)
        print(f"[调查阶段] 剩余调查次数: {inv_count}")
        print("=" * 50)

        if inv_count <= 0:
            print("\n调查时间结束，准备进入审判...")
            current_day["phase"] = "trial"
            save_json(day_path, current_day)
            input("\n[按Enter进入审判阶段...]")
            return

        print("\n可执行的调查行动:")
        print("  1. 搜查现场")
        print("  2. 询问角色")
        print("  3. 查看证据")
        print("  0. 结束调查，进入审判")

        choice = input("\n选择行动: ").strip()

        if choice == "0":
            current_day["phase"] = "trial"
            save_json(day_path, current_day)
            print("\n准备进入审判...")
            return
        elif choice in ["1", "2", "3"]:
            current_day["investigation_count"] = inv_count - 1
            save_json(day_path, current_day)

            # 简化的调查反馈
            if choice == "1":
                print("\n  你搜查了现场，发现了一些可疑的痕迹...")
            elif choice == "2":
                print("\n  你询问了其他人，收集了一些证言...")
            elif choice == "3":
                print("\n  你查看了已收集的证据...")
        else:
            print("\n无效选择")

    def run_trial(self):
        """审判阶段（框架）"""
        day_path = self.project_root / "world_state" / "current_day.json"
        current_day = load_json(day_path)

        print("\n" + "=" * 60)
        print("[魔女审判]")
        print("=" * 60)

        print("\n  典狱长: 魔女审判现在开始。")
        print("  你们有有限的时间讨论，找出凶手。")
        print("  讨论结束后，将进行投票。得票最多者将被处刑。")

        # 获取存活角色列表
        states_path = self.project_root / "world_state" / "character_states.json"
        states = load_json(states_path)
        alive_chars = [cid for cid, state in states.items() if state.get("status") == "alive"]

        print("\n存活角色:")
        for i, char_id in enumerate(alive_chars, 1):
            print(f"  {i}. {char_id}")

        print("\n请投票选择你认为的凶手:")
        vote = input("输入编号: ").strip()

        try:
            vote_idx = int(vote) - 1
            if 0 <= vote_idx < len(alive_chars):
                voted_id = alive_chars[vote_idx]
                murderer_id = current_day.get("murderer_id")

                print(f"\n  投票结果: {voted_id}")

                if voted_id == murderer_id:
                    # 正确审判
                    print(f"\n  {voted_id}: ...是我做的。我无法控制自己...")
                    print("  处刑开始。一条生命就这样消逝了。")
                    current_day["flags"]["correct_judgment"] = True
                    self.handle_ending(EndingType.NORMAL_END)
                else:
                    # 错误审判
                    print(f"\n  {voted_id}: 不...不是我...我什么都没做...!")
                    print("  处刑执行了。一个无辜的生命消逝了。")
                    print("  而真正的凶手...还藏在你们之中。")
                    current_day["flags"]["correct_judgment"] = False
                    self.handle_ending(EndingType.BAD_END)

                save_json(day_path, current_day)
            else:
                print("\n无效选择")
        except:
            print("\n无效输入")

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
                    print(f"\n[{main_char}] 正在思考...")
                    print(f"\n[{main_char}]")
                    print(f"  ......」")
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
                            print(f"\n[{line.speaker}] [{line.emotion}]")
                            print(f"  {line.text_cn}")

                        # 应用效果
                        self._apply_choice_effects(response.effects)

                        if opt.get("leads_to") == "负面" or opt.get("leads_to") == "危险":
                            print("\n[警告] 这个选择可能导向危险的结局...")
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

            for key, value in effects.items():
                if isinstance(value, dict):
                    if key in states:
                        for stat, change in value.items():
                            if stat in ["stress", "madness"]:
                                current = states[key].get(stat, 0)
                                states[key][stat] = max(0, min(100, current + change))
                else:
                    pass

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

            stress_changes = outcomes.get("stress_changes", {})
            for char_id, change in stress_changes.items():
                if char_id in states:
                    current = states[char_id].get("stress", 50)
                    states[char_id]["stress"] = max(0, min(100, current + change))

            save_json(states_path, states)

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
            current_day["daily_event_count"] = current_day.get("daily_event_count", 0) + 1
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
                if state.get("status") != "alive":
                    continue
                if random.random() < 0.3:
                    state["location"] = random.choice(locations_list)
                state["action"] = random.choice(actions)
                state["can_interact"] = True

            save_json(states_path, states)
        except Exception as e:
            print(f"[警告] 更新NPC位置失败: {e}")

    def scatter_npcs(self):
        """将NPC分散到各个地点"""
        try:
            states_path = self.project_root / "world_state" / "character_states.json"
            states = load_json(states_path)

            # 可用地点
            locations = ["食堂", "牢房区", "图书室", "庭院", "走廊"]
            actions = ["四处张望", "静静站着", "来回踱步", "若有所思", "环顾四周"]

            # 为每个角色随机分配地点
            for char_id, state in states.items():
                if state.get("status") == "alive":
                    state["location"] = random.choice(locations)
                    state["action"] = random.choice(actions)
                    state["can_interact"] = True

            save_json(states_path, states)
            print("\n[系统] NPC已分散到各个地点")
        except Exception as e:
            print(f"[警告] 分散NPC失败: {e}")

    # ============================================================================
    # 固定事件相关方法
    # ============================================================================

    def display_fixed_event(self, event_data: Dict):
        """显示固定事件"""
        event_name = event_data.get("name", "未知事件")
        scene = event_data.get("scene", {})
        script = event_data.get("script", [])

        print("\n" + "=" * 60)
        print(f"[固定事件] {event_name}")
        print("=" * 60)

        if scene.get("description"):
            print(f"\n{scene['description']}")

        # 显示脚本对话
        for line in script:
            speaker = line.get("speaker", "narrator")
            text = line.get("text_cn", line.get("text", "..."))

            if speaker == "narrator":
                print(f"\n  {text}")
            elif speaker == "warden":
                print(f"\n[典狱长]")
                print(f"  {text}")
            else:
                print(f"\n[{speaker}]")
                print(f"  {text}")

        input("\n[按Enter继续...]")

    def _run_fixed_event(self, event_data: Dict):
        """执行固定事件"""
        event_id = event_data.get("_event_id", "unknown")

        # 显示事件
        self.display_fixed_event(event_data)

        # 应用结果
        self.fixed_event_manager.apply_event_outcomes(event_data)

        # 标记为已触发
        self.fixed_event_manager.mark_event_triggered(event_id)

        # 增加事件计数
        self._increment_event_count()

        # 处理转换
        transitions = self.fixed_event_manager.handle_event_transitions(event_data)

        # 检查是否需要分散NPC
        if transitions.get("trigger_npc_scatter"):
            self.scatter_npcs()

        # 检查游戏结束
        if transitions.get("game_over"):
            ending_type = transitions.get("ending_type", "normal_end")
            self.handle_ending(ending_type)
            return

        # 检查分支
        branch = event_data.get("branch")
        if branch:
            self._handle_event_branch(branch)
            return

        # 检查是否有后续事件（next_event）
        if transitions.get("next_event"):
            # 有后续事件，不推进时间，让下一回合触发
            return

        # 检查是否改变了时段
        if transitions.get("next_period"):
            # 时段已在 handle_event_transitions 中更新
            print(f"\n[时间流逝] -> {PERIOD_NAMES.get(transitions['next_period'], transitions['next_period'])}")
            return

        # 检查是否进入下一天
        if transitions.get("next_day"):
            # next_day 已在 handle_event_transitions 中处理
            print(f"\n[新的一天开始了...]")
            return

        # 检查是否改变了阶段
        if transitions.get("next_phase"):
            # 阶段改变，不推进时间
            print(f"\n[阶段变更] -> {PHASE_NAMES.get(transitions['next_phase'], transitions['next_phase'])}")
            return

        # 普通事件：检查并推进时间
        self._check_and_advance()

    def _handle_event_branch(self, branches: List[Dict]):
        """处理事件分支"""
        state = load_json(self.project_root / "world_state" / "current_day.json")
        flags = state.get("flags", {})

        for branch in branches:
            condition = branch.get("condition", "default")
            next_event = branch.get("next_event")

            if condition == "default":
                # 默认分支
                if next_event:
                    state["next_event"] = next_event
                    save_json(self.project_root / "world_state" / "current_day.json", state)
                break

            # 评估条件
            if self.fixed_event_manager._evaluate_condition(condition, flags):
                if next_event:
                    state["next_event"] = next_event
                    save_json(self.project_root / "world_state" / "current_day.json", state)
                break


# ============================================================================
# 入口
# ============================================================================

def main():
    """主入口"""
    print("\n正在启动游戏...")

    game = GameLoopV3()
    game.run()


if __name__ == "__main__":
    main()
