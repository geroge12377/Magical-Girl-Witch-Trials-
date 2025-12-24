"""
世界观加载器 - 按需加载世界观数据
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache


class WorldLoader:
    """世界观数据加载器"""

    def __init__(self, world_id: str = "witch_trial", project_root: Path = None):
        self.world_id = world_id
        if project_root is None:
            project_root = Path(__file__).parent.parent
        self.project_root = project_root
        self.world_path = project_root / "worlds" / world_id
        self._cache: Dict[str, Any] = {}

    def _load_yaml(self, filepath: Path) -> Dict:
        """加载YAML文件"""
        if not filepath.exists():
            print(f"[WorldLoader] 警告: 文件不存在 {filepath}")
            return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[WorldLoader] 加载YAML失败 {filepath}: {e}")
            return {}

    def load_manifest(self) -> Dict:
        """加载世界观元信息（始终加载）"""
        if 'manifest' not in self._cache:
            self._cache['manifest'] = self._load_yaml(self.world_path / "manifest.yaml")
        return self._cache['manifest']

    def load_core_rules(self) -> Dict:
        """加载核心规则"""
        if 'rules' not in self._cache:
            self._cache['rules'] = self._load_yaml(self.world_path / "core" / "rules.yaml")
        return self._cache['rules']

    def load_tone(self) -> Dict:
        """加载氛围指导（完整）"""
        if 'tone' not in self._cache:
            self._cache['tone'] = self._load_yaml(self.world_path / "core" / "tone.yaml")
        return self._cache['tone']

    def load_tone_for_arc(self, arc: str) -> Dict:
        """根据当前arc加载氛围指导"""
        tone = self.load_tone()
        scene_guidance = tone.get('scene_guidance', {})
        arc_tone = scene_guidance.get(arc, {})

        # 获取张力范围
        manifest = self.load_manifest()
        arc_info = manifest.get('arc', {}).get(arc, {})
        tension_range = arc_info.get('tension_range', [1, 10])

        # 合并信息
        result = {
            '主基调': arc_tone.get('主基调', ''),
            '氛围词': arc_tone.get('氛围词', []),
            '场景比例': arc_tone.get('场景比例', {}),
            '对话指导': arc_tone.get('对话指导', {}),
            '张力范围': tension_range,
            '静默比例': arc_info.get('silence_ratio', 0.3),
            '对话密度': arc_tone.get('对话指导', {}).get('density', 'normal')
        }

        # 禁止/允许内容
        if '禁止内容' in arc_tone:
            result['禁止内容'] = arc_tone['禁止内容']
        elif 'forbidden' in arc_info:
            result['禁止内容'] = arc_info['forbidden']

        if '允许内容' in arc_tone:
            result['允许内容'] = arc_tone['允许内容']
        elif 'allowed' in arc_info:
            result['允许内容'] = arc_info['allowed']

        return result

    def load_structure(self) -> Dict:
        """加载7天故事结构"""
        if 'structure' not in self._cache:
            self._cache['structure'] = self._load_yaml(
                self.world_path / "event_tree" / "structure.yaml"
            )
        return self._cache['structure']

    def load_scene_types(self) -> Dict:
        """加载场景类型定义"""
        if 'scene_types' not in self._cache:
            self._cache['scene_types'] = self._load_yaml(
                self.world_path / "event_tree" / "scene_types.yaml"
            )
        return self._cache['scene_types']

    def load_triggers(self) -> Dict:
        """加载触发条件库"""
        if 'triggers' not in self._cache:
            self._cache['triggers'] = self._load_yaml(
                self.world_path / "event_tree" / "triggers.yaml"
            )
        return self._cache['triggers']

    def load_character_arcs(self) -> Dict:
        """加载角色弧线"""
        if 'character_arcs' not in self._cache:
            self._cache['character_arcs'] = self._load_yaml(
                self.world_path / "event_tree" / "branches" / "character_arcs.yaml"
            )
        return self._cache['character_arcs']

    def load_endings(self) -> Dict:
        """加载结局分支"""
        if 'endings' not in self._cache:
            self._cache['endings'] = self._load_yaml(
                self.world_path / "event_tree" / "branches" / "endings.yaml"
            )
        return self._cache['endings']

    def load_location(self, location_id: str) -> Dict:
        """按需加载地点详情"""
        cache_key = f'location_{location_id}'
        if cache_key not in self._cache:
            location_path = self.world_path / "locations" / f"{location_id}.yaml"
            self._cache[cache_key] = self._load_yaml(location_path)
        return self._cache[cache_key]

    def get_arc_for_day(self, day: int) -> str:
        """获取指定日期所属的arc（起/承/转/合）"""
        manifest = self.load_manifest()
        arc_config = manifest.get('arc', {})

        for arc_name, arc_info in arc_config.items():
            days = arc_info.get('days', [])
            if day in days:
                return arc_name

        # 默认返回
        if day <= 2:
            return '起'
        elif day <= 4:
            return '承'
        elif day <= 6:
            return '转'
        else:
            return '合'

    def get_scene_constraints(self, day: int) -> Dict:
        """获取当天的场景生成约束"""
        arc = self.get_arc_for_day(day)
        tone = self.load_tone_for_arc(arc)
        structure = self.load_structure()
        scene_types = self.load_scene_types()

        # 获取当天结构
        day_key = f"day_{day}"
        day_structure = structure.get('days', {}).get(day_key, {})

        # 获取arc约束
        arc_constraints = scene_types.get('generation_rules', {}).get('arc_constraints', {}).get(arc, {})

        return {
            'arc': arc,
            'day': day,
            'theme': day_structure.get('theme', ''),
            'tension_template': day_structure.get('tension_template', 'peaceful_day'),
            'tension_range': tone.get('张力范围', [1, 10]),
            'allowed_moods': arc_constraints.get('allowed_moods', ['peaceful', 'relaxed']),
            'allowed_player_roles': arc_constraints.get('allowed_player_roles', ['spectator', 'passerby']),
            'info_value_weights': arc_constraints.get('info_value_weights', {'none': 0.7, 'hint': 0.3, 'clue': 0}),
            'forbidden': tone.get('禁止内容', []),
            'allowed': tone.get('允许内容', []),
            'scene_ratio': tone.get('场景比例', {}),
            'dialogue_density': tone.get('对话密度', 'normal'),
            'possible_scenes': day_structure.get('possible_scenes', {}),
            'hints_allowed': day_structure.get('hints_allowed', []),
            'events_unlocked': day_structure.get('events_unlocked', []),
        }

    def get_tension_curve(self, template: str) -> List[int]:
        """获取张力曲线模板"""
        tone = self.load_tone()
        templates = tone.get('tension_templates', {})
        template_data = templates.get(template, {})
        return template_data.get('curve', [3, 3, 3, 3, 3, 3])

    def get_scene_length_requirements(self, scene_type: str) -> Dict:
        """获取场景长度要求"""
        tone = self.load_tone()
        requirements = tone.get('scene_length_requirements', {})
        return requirements.get(scene_type, {
            'min_chars': 350,
            'suggested_chars': '400-600',
            'structure': '完整五段式'
        })

    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()


# 全局实例
_world_loader: Optional[WorldLoader] = None

def get_world_loader(world_id: str = "witch_trial", project_root: Path = None) -> WorldLoader:
    """获取世界观加载器单例"""
    global _world_loader
    if _world_loader is None or _world_loader.world_id != world_id:
        _world_loader = WorldLoader(world_id, project_root)
    return _world_loader
