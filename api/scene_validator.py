"""
场景验证器 - 确保输出符合约束
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from .world_loader import WorldLoader, get_world_loader


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    errors: List[str]
    warnings: List[str]


class SceneValidator:
    """场景验证器 - 确保输出符合当天约束"""

    def __init__(self, world_loader: WorldLoader = None, project_root: Path = None):
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = project_root

        if world_loader is None:
            self.world = get_world_loader(project_root=project_root)
        else:
            self.world = world_loader

    def validate(self, scene_plan: Any, day: int) -> ValidationResult:
        """验证场景是否符合当天约束"""
        errors = []
        warnings = []

        arc = self.world.get_arc_for_day(day)
        tone = self.world.load_tone_for_arc(arc)

        # 获取约束
        tension_range = tone.get('张力范围', [1, 10])
        min_t, max_t = tension_range[0], tension_range[1]
        forbidden = tone.get('禁止内容', [])
        dialogue_density = tone.get('对话密度', 'normal')

        # 1. 张力检查
        if hasattr(scene_plan, 'beats'):
            for beat in scene_plan.beats:
                if hasattr(beat, 'tension_level'):
                    if beat.tension_level > max_t:
                        errors.append(f"Beat {beat.beat_id} 张力 {beat.tension_level} 超出上限 {max_t}")
                    if beat.tension_level < min_t:
                        warnings.append(f"Beat {beat.beat_id} 张力 {beat.tension_level} 低于下限 {min_t}")

        # 2. 禁止内容检查
        scene_text = self._extract_all_text(scene_plan)
        for keyword in forbidden:
            if keyword in scene_text:
                errors.append(f"检测到禁止内容：「{keyword}」")

        # 3. 角色行为检查（起阶段不能崩溃）
        if arc == "起":
            if hasattr(scene_plan, 'beats'):
                for beat in scene_plan.beats:
                    if hasattr(beat, 'emotion_targets'):
                        for char, emotion in beat.emotion_targets.items():
                            if emotion in ["崩溃", "失控", "魔女化", "绝望", "暴怒"]:
                                errors.append(f"起阶段不允许角色「{char}」处于「{emotion}」状态")

        # 4. 对话密度检查
        expected_density = dialogue_density
        if hasattr(scene_plan, 'beats'):
            total_dialogue = sum(
                getattr(beat, 'dialogue_count', 0)
                for beat in scene_plan.beats
            )
            if expected_density == "sparse" and total_dialogue > 8:
                warnings.append(f"对话过多（{total_dialogue}行），「起」阶段建议减少对话")
            elif expected_density == "dense" and total_dialogue < 5:
                warnings.append(f"对话过少（{total_dialogue}行），「合」阶段建议增加对话")

        # 5. 场景长度检查
        if hasattr(scene_plan, 'overall_arc'):
            arc_length = len(scene_plan.overall_arc)
            if arc_length < 50:
                warnings.append("场景描述过短，建议丰富overall_arc")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _extract_all_text(self, scene_plan: Any) -> str:
        """从场景计划中提取所有文本"""
        texts = []

        if hasattr(scene_plan, 'scene_name'):
            texts.append(scene_plan.scene_name)
        if hasattr(scene_plan, 'overall_arc'):
            texts.append(scene_plan.overall_arc)
        if hasattr(scene_plan, 'key_moments'):
            texts.extend(scene_plan.key_moments)

        if hasattr(scene_plan, 'beats'):
            for beat in scene_plan.beats:
                if hasattr(beat, 'description'):
                    texts.append(beat.description)
                if hasattr(beat, 'direction_notes'):
                    texts.append(beat.direction_notes)

        return ' '.join(texts)

    def auto_fix(self, scene_plan: Any, day: int) -> Any:
        """自动修正不符合约束的内容"""
        arc = self.world.get_arc_for_day(day)
        tone = self.world.load_tone_for_arc(arc)
        tension_range = tone.get('张力范围', [1, 10])
        min_t, max_t = tension_range[0], tension_range[1]

        # 修正张力
        if hasattr(scene_plan, 'beats'):
            for beat in scene_plan.beats:
                if hasattr(beat, 'tension_level'):
                    original = beat.tension_level
                    beat.tension_level = max(min_t, min(max_t, beat.tension_level))
                    if original != beat.tension_level:
                        print(f"[SceneValidator] 张力修正：{original} → {beat.tension_level}")

        # 修正情绪（起阶段降级）
        if arc == "起":
            emotion_downgrade = {
                "崩溃": "不安",
                "失控": "紧张",
                "绝望": "担忧",
                "暴怒": "不满",
                "魔女化": "异常"
            }
            if hasattr(scene_plan, 'beats'):
                for beat in scene_plan.beats:
                    if hasattr(beat, 'emotion_targets'):
                        for char, emotion in list(beat.emotion_targets.items()):
                            if emotion in emotion_downgrade:
                                new_emotion = emotion_downgrade[emotion]
                                beat.emotion_targets[char] = new_emotion
                                print(f"[SceneValidator] 情绪修正：{char} {emotion} → {new_emotion}")

        return scene_plan

    def validate_dialogue_output(self, dialogue_output: Any, scene_type: str, day: int) -> ValidationResult:
        """验证对话输出"""
        errors = []
        warnings = []

        # 获取长度要求
        length_req = self.world.get_scene_length_requirements(scene_type)
        min_chars = length_req.get('min_chars', 350)

        # 计算总字数
        total_chars = 0
        if hasattr(dialogue_output, 'dialogue'):
            for line in dialogue_output.dialogue:
                if hasattr(line, 'text_cn'):
                    total_chars += len(line.text_cn)

        if total_chars < min_chars:
            warnings.append(f"场景内容过短（{total_chars}字 < {min_chars}字），建议补充")

        # 检查叙述比例
        narrator_count = 0
        total_count = 0
        if hasattr(dialogue_output, 'dialogue'):
            for line in dialogue_output.dialogue:
                total_count += 1
                if hasattr(line, 'speaker') and line.speaker == 'narrator':
                    narrator_count += 1

        if total_count > 0:
            narrator_ratio = narrator_count / total_count
            if narrator_ratio < 0.25:
                warnings.append(f"叙述比例过低（{narrator_ratio:.0%}），建议增加环境/动作描写")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def check_scene_storytelling(self, outputs: List[Any]) -> ValidationResult:
        """检查场景故事性（验收测试用）"""
        errors = []
        warnings = []

        # 1. 长度检查
        total_chars = 0
        for output in outputs:
            if hasattr(output, 'dialogue'):
                for line in output.dialogue:
                    if hasattr(line, 'text_cn'):
                        total_chars += len(line.text_cn)

        if total_chars < 400:
            errors.append(f"场景太短：{total_chars}字（要求≥400字）")

        # 2. 结构检查
        beat_types = []
        for output in outputs:
            if hasattr(output, 'beat_id'):
                beat_types.append(output.beat_id)

        if not any('opening' in b.lower() for b in beat_types):
            warnings.append("缺少开场（opening）Beat")
        if not any('development' in b.lower() or 'climax' in b.lower() for b in beat_types):
            warnings.append("缺少发展/高潮 Beat")

        # 3. 叙述比例检查
        narrator_lines = 0
        total_lines = 0
        for output in outputs:
            if hasattr(output, 'dialogue'):
                for line in output.dialogue:
                    total_lines += 1
                    if hasattr(line, 'speaker') and line.speaker == 'narrator':
                        narrator_lines += 1

        if total_lines > 0:
            narrator_ratio = narrator_lines / total_lines
            if narrator_ratio < 0.25:
                errors.append(f"叙述太少：{narrator_ratio:.0%}（要求≥25%）")

        # 4. 画面感检查
        all_text = ""
        for output in outputs:
            if hasattr(output, 'dialogue'):
                for line in output.dialogue:
                    if hasattr(line, 'text_cn'):
                        all_text += line.text_cn + " "

        scene_words = ["阳光", "灰尘", "脚步", "沉默", "窗", "声音", "目光", "肩膀",
                       "光线", "气息", "温度", "风", "影子", "走廊", "桌子", "椅子"]
        found = [w for w in scene_words if w in all_text]
        if len(found) < 2:
            warnings.append(f"缺乏画面感词汇，仅找到：{found}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
