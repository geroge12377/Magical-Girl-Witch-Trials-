# ============================================================================
# 故事规划层 (Story Planner)
# ============================================================================
# 职责：
# 1. 生成三天大纲（chapter_outline）
# 2. 获取每天的事件列表
# 3. 检查杀人准备状态
# 4. 判断结局类型
# ============================================================================

import anthropic
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import sys

# 添加父目录到路径以导入config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_api_key, MODEL

# 导入公共工具函数
from .utils import parse_json_with_diagnostics


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class DayOutline:
    """单日大纲"""
    day: int
    theme: str  # 当天主题
    key_events: List[str]  # 关键事件列表
    tension_arc: str  # 张力曲线描述
    potential_murder: bool  # 是否可能发生杀人
    notes: str  # 导演备注


@dataclass
class ChapterOutline:
    """章节大纲（三天）"""
    chapter: int
    title: str
    days: List[DayOutline]
    overall_theme: str
    ending_flags: Dict[str, bool]  # 可能触发的结局标记


# ============================================================================
# 结局类型
# ============================================================================

class EndingType:
    """结局类型常量"""
    BAD_END = "bad_end"          # 审判错误（投票处死无辜者）
    NORMAL_END = "normal_end"    # 杀人 + 审判正确
    GOOD_END = "good_end"        # 无人死亡
    TRUE_END = "true_end"        # 全员好感 ≥ 70 + library_secret_found


# ============================================================================
# 工具函数
# ============================================================================

def load_json(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath: str, data: dict):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================================
# 故事规划层
# ============================================================================

class StoryPlanner:
    """故事规划层 - 管理章节大纲和结局判定"""

    def __init__(self, project_root: Path = None):
        self.client = anthropic.Anthropic(api_key=get_api_key("director"))
        self.project_root = project_root or Path(__file__).parent.parent
        self._outline_cache: Optional[ChapterOutline] = None

    def _get_outline_path(self) -> Path:
        """获取大纲文件路径"""
        return self.project_root / "world_state" / "chapter_outline.json"

    def _get_murder_prep_path(self) -> Path:
        """获取杀人准备文件路径"""
        return self.project_root / "world_state" / "murder_prep.json"

    def load_outline(self) -> Optional[Dict]:
        """加载现有大纲"""
        path = self._get_outline_path()
        if path.exists():
            return load_json(path)
        return None

    def save_outline(self, outline: Dict):
        """保存大纲"""
        save_json(self._get_outline_path(), outline)

    def generate_three_day_outline(self) -> Dict:
        """
        生成三天大纲

        Returns:
            包含三天事件规划的字典
        """
        # 加载当前状态
        current_day = load_json(self.project_root / "world_state" / "current_day.json")
        character_states = load_json(self.project_root / "world_state" / "character_states.json")

        # 分析角色状态
        high_stress_chars = [
            char_id for char_id, state in character_states.items()
            if state.get("stress", 0) >= 70
        ]
        high_madness_chars = [
            char_id for char_id, state in character_states.items()
            if state.get("madness", 0) >= 50
        ]

        prompt = self._build_outline_prompt(current_day, high_stress_chars, high_madness_chars)

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )

            raw_text = response.content[0].text
            result = parse_json_with_diagnostics(raw_text, "三天大纲", "StoryPlanner")

            # 保存大纲
            self.save_outline(result)
            return result

        except Exception as e:
            print(f"[StoryPlanner] 生成大纲失败: {type(e).__name__}: {e}")
            return self._create_fallback_outline(current_day["day"])

    def _build_outline_prompt(self, current_day: Dict, high_stress: List[str], high_madness: List[str]) -> str:
        """构建大纲生成 prompt"""
        return f"""你是《魔法少女的魔女审判》的故事规划师。请为接下来的三天规划大纲。

【当前状态】
当前日期: 第{current_day.get('day', 1)}天
当前阶段: {current_day.get('phase', 'free_time')}
已触发事件: {current_day.get('event_count', 0)}次
已设置标记: {list(current_day.get('flags', {}).keys())}

【危险角色】
高压力角色（≥70）: {', '.join(high_stress) if high_stress else '无'}
高疯狂角色（≥50）: {', '.join(high_madness) if high_madness else '无'}

【规划要求】
1. 每天规划3-5个关键事件
2. 第一天：建立关系，埋下伏笔
3. 第二天：矛盾升级，可能发生杀人（如果有高疯狂角色）
4. 第三天：真相揭示，走向结局
5. 张力曲线要逐步升高

【输出格式】严格JSON：
{{
  "chapter": 1,
  "title": "章节标题",
  "overall_theme": "整体主题描述",
  "days": [
    {{
      "day": 1,
      "theme": "当天主题",
      "key_events": ["事件1描述", "事件2描述", "..."],
      "tension_arc": "低→中 (张力变化)",
      "potential_murder": false,
      "notes": "导演备注"
    }},
    {{
      "day": 2,
      "theme": "...",
      "key_events": [...],
      "tension_arc": "中→高",
      "potential_murder": true/false,
      "notes": "..."
    }},
    {{
      "day": 3,
      "theme": "...",
      "key_events": [...],
      "tension_arc": "高→结局",
      "potential_murder": false,
      "notes": "..."
    }}
  ],
  "ending_flags": {{
    "murder_occurred": false,
    "correct_judgment": null,
    "library_secret_found": false
  }}
}}

请直接输出JSON。"""

    def _create_fallback_outline(self, start_day: int) -> Dict:
        """创建回退大纲"""
        return {
            "chapter": 1,
            "title": "孤岛的第一章",
            "overall_theme": "互相试探与信任建立",
            "days": [
                {
                    "day": start_day,
                    "theme": "初次相遇",
                    "key_events": ["自我介绍", "探索环境", "建立初步关系"],
                    "tension_arc": "低→中",
                    "potential_murder": False,
                    "notes": "让玩家熟悉角色"
                },
                {
                    "day": start_day + 1,
                    "theme": "矛盾浮现",
                    "key_events": ["发现线索", "角色冲突", "秘密暴露"],
                    "tension_arc": "中→高",
                    "potential_murder": True,
                    "notes": "制造紧张氛围"
                },
                {
                    "day": start_day + 2,
                    "theme": "真相与选择",
                    "key_events": ["真相揭露", "最终对峙", "结局分歧"],
                    "tension_arc": "高→结局",
                    "potential_murder": False,
                    "notes": "走向结局"
                }
            ],
            "ending_flags": {
                "murder_occurred": False,
                "correct_judgment": None,
                "library_secret_found": False
            }
        }

    def get_day_events(self, day: int) -> List[str]:
        """
        获取指定日期的事件列表

        Args:
            day: 日期（1, 2, 3...）

        Returns:
            事件描述列表
        """
        outline = self.load_outline()
        if not outline:
            outline = self.generate_three_day_outline()

        days = outline.get("days", [])
        for day_data in days:
            if day_data.get("day") == day:
                return day_data.get("key_events", [])

        return ["自由探索"]

    def check_murder_prep(self) -> Optional[Dict]:
        """
        检查是否有角色准备杀人

        Returns:
            如果有准备杀人的角色，返回准备信息；否则返回 None
        """
        path = self._get_murder_prep_path()
        if not path.exists():
            return None

        prep = load_json(path)
        if prep.get("active", False):
            return prep
        return None

    def update_murder_prep(self, char_id: str, target_id: str, motivation: str, progress: int):
        """
        更新杀人准备状态

        Args:
            char_id: 准备杀人的角色ID
            target_id: 目标角色ID
            motivation: 动机
            progress: 准备进度（0-100）
        """
        prep = {
            "active": progress > 0,
            "killer_id": char_id,
            "target_id": target_id,
            "motivation": motivation,
            "progress": progress,
            "can_execute": progress >= 100
        }
        save_json(self._get_murder_prep_path(), prep)

    def check_ending(self) -> str:
        """
        检查当前状态应该触发哪种结局

        Returns:
            结局类型字符串
        """
        current_day = load_json(self.project_root / "world_state" / "current_day.json")
        character_states = load_json(self.project_root / "world_state" / "character_states.json")
        flags = current_day.get("flags", {})

        # 检查是否发生过杀人
        murder_occurred = flags.get("murder_occurred", False)

        # 检查审判结果
        correct_judgment = flags.get("correct_judgment", None)

        # 检查是否发现图书馆秘密
        library_secret = flags.get("library_secret_found", False)

        # 检查全员好感度
        all_high_affection = all(
            state.get("affection", 50) >= 70
            for state in character_states.values()
            if state.get("status") == "alive"
        )

        # 判定结局
        # True End: 全员好感 ≥ 70 + 发现图书馆秘密
        if all_high_affection and library_secret and not murder_occurred:
            return EndingType.TRUE_END

        # Good End: 无人死亡
        if not murder_occurred:
            return EndingType.GOOD_END

        # 有杀人发生
        if murder_occurred:
            # Bad End: 审判错误
            if correct_judgment is False:
                return EndingType.BAD_END
            # Normal End: 审判正确
            if correct_judgment is True:
                return EndingType.NORMAL_END

        # 默认返回 Normal End
        return EndingType.NORMAL_END

    def get_ending_description(self, ending_type: str) -> Dict[str, str]:
        """
        获取结局描述

        Args:
            ending_type: 结局类型

        Returns:
            包含标题和描述的字典
        """
        endings = {
            EndingType.BAD_END: {
                "title": "Bad End - 错误的审判",
                "description": "无辜者被处刑，真正的凶手逍遥法外...",
                "color": "red"
            },
            EndingType.NORMAL_END: {
                "title": "Normal End - 正义的代价",
                "description": "凶手被绳之以法，但生命已无法挽回...",
                "color": "yellow"
            },
            EndingType.GOOD_END: {
                "title": "Good End - 全员生还",
                "description": "所有人都活了下来，但秘密仍未揭开...",
                "color": "green"
            },
            EndingType.TRUE_END: {
                "title": "True End - 真相大白",
                "description": "全员生还，图书馆的秘密也被揭开了...",
                "color": "gold"
            }
        }
        return endings.get(ending_type, endings[EndingType.NORMAL_END])


# ============================================================================
# 测试
# ============================================================================

def test_story_planner():
    """测试故事规划层"""
    print("=" * 60)
    print("📖 故事规划层测试")
    print("=" * 60)

    planner = StoryPlanner()

    # 测试生成大纲
    print("\n📋 生成三天大纲...")
    outline = planner.generate_three_day_outline()

    print(f"\n【章节】{outline.get('title', '未命名')}")
    print(f"主题: {outline.get('overall_theme', '')}")

    for day_data in outline.get("days", []):
        print(f"\n--- 第{day_data.get('day')}天: {day_data.get('theme')} ---")
        print(f"张力: {day_data.get('tension_arc')}")
        print(f"可能杀人: {day_data.get('potential_murder')}")
        print("事件:")
        for event in day_data.get("key_events", []):
            print(f"  - {event}")

    # 测试结局判定
    print("\n\n📍 测试结局判定...")
    ending = planner.check_ending()
    ending_info = planner.get_ending_description(ending)
    print(f"当前结局: {ending_info['title']}")
    print(f"描述: {ending_info['description']}")

    print("\n✅ 测试完成")


if __name__ == "__main__":
    test_story_planner()
