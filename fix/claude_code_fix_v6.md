# Claude Code 任务：预选回应提前生成优化 v6

## 问题描述

当前流程在玩家到达选择点时才生成预选回应，导致等待时间：

```
当前流程：
[DirectorPlanner] → [CharacterActor: 生成对话] → 显示 Beat... → 
到达选择点 → [等待: generate_choice_responses()] → 显示选项
                          ↑
                     这里有延迟！
```

## 优化目标

将预选回应的生成提前到场景开始时，与对话一起生成：

```
优化后：
[DirectorPlanner] → [CharacterActor: 生成对话 + 预选回应] → 
显示 Beat... → 到达选择点 → 显示选项（零延迟）
```

---

## 任务 1：修改 `api/character_actor.py`

### 1.1 修改 `generate_scene_dialogue()` 方法

在生成对话的同时，也生成预选回应：

```python
def generate_scene_dialogue(self, scene_plan: ScenePlan) -> Tuple[List[DialogueOutput], Optional[Dict[str, ChoiceResponse]]]:
    """
    生成整个场景的对话和预选回应
    
    Returns:
        Tuple[List[DialogueOutput], Optional[Dict[str, ChoiceResponse]]]
        - 对话列表
        - 预选回应字典（如果场景有选择点）
    """
    # 1. 生成对话（现有逻辑）
    dialogue_outputs = self._generate_all_beats_dialogue(scene_plan)
    
    # 2. 如果有选择点，同时生成预选回应
    choice_responses = None
    if scene_plan.player_choice_point:
        choice_point = scene_plan.player_choice_point
        characters = self._get_choice_responders(scene_plan)
        choice_responses = self.generate_choice_responses(choice_point, characters)
    
    return dialogue_outputs, choice_responses
```

### 1.2 或者：合并到单次 API 调用

更优的方案是在同一个 prompt 中同时生成对话和预选回应：

```python
def generate_scene_with_choices(self, scene_plan: ScenePlan) -> Dict:
    """
    单次 API 调用生成整个场景的对话和预选回应
    """
    prompt = self._build_scene_with_choices_prompt(scene_plan)
    
    response = self._call_api(prompt)
    
    result = self._parse_scene_with_choices(response)
    
    return {
        "dialogue_outputs": result["beats"],
        "choice_responses": result.get("choices", None)
    }

def _build_scene_with_choices_prompt(self, scene_plan: ScenePlan) -> str:
    """构建包含对话和选项的完整 prompt"""
    prompt = self._build_scene_prompt(scene_plan)
    
    # 如果有选择点，添加选项生成要求
    if scene_plan.player_choice_point:
        choice_point = scene_plan.player_choice_point
        prompt += f"""

---
【玩家选择点】
在 Beat {choice_point.get('after_beat', 'final')} 之后，玩家需要做出选择。

选项：
A. {choice_point['options']['A']['text']} ({choice_point['options']['A']['tone']})
B. {choice_point['options']['B']['text']} ({choice_point['options']['B']['tone']})
C. {choice_point['options']['C']['text']} ({choice_point['options']['C']['tone']})

请为每个选项生成角色回应，格式：
"choices": {{
    "A": {{
        "dialogue": [{{...}}],
        "effects": {{...}}
    }},
    "B": {{...}},
    "C": {{...}}
}}
"""
    
    return prompt
```

---

## 任务 2：修改 `game_loop_v3.py`

### 2.1 修改 `_run_free_scene()` 方法

```python
def _run_free_scene(self, location: str):
    """执行自由探索场景"""
    print("\n[导演] 正在规划场景...")
    
    # 1. 规划场景
    scene_plan = self.planner.plan_scene(location)
    display_scene_plan(scene_plan)
    
    # 2. 生成对话和预选回应（一次性）
    print("\n[角色] 正在演出...")
    dialogue_outputs, choice_responses = self.actor.generate_scene_dialogue(scene_plan)
    
    # 3. 显示场景（无需等待）
    for i, beat in enumerate(scene_plan.beats):
        display_beat_info(beat, i)
        if i < len(dialogue_outputs):
            display_dialogue(dialogue_outputs[i], self.show_jp_text)
        
        # 到达选择点
        if scene_plan.player_choice_point:
            after_beat = scene_plan.player_choice_point.get("after_beat", len(scene_plan.beats))
            if i + 1 == after_beat:
                # 直接使用预生成的回应，无需等待
                self._handle_player_choice_with_pregenerated(
                    scene_plan.player_choice_point,
                    choice_responses  # 已经生成好了
                )
        
        input("\n[按Enter继续...]")
    
    # 4. 应用效果
    self._apply_scene_effects(dialogue_outputs, scene_plan)

def _handle_player_choice_with_pregenerated(
    self, 
    choice_point: Dict, 
    pregenerated_responses: Dict[str, ChoiceResponse]
):
    """使用预生成的回应处理玩家选择"""
    display_choices(choice_point)
    
    # 玩家输入
    choice = input("\n输入选项 (A/B/C/D/Q): ").strip().upper()
    
    if choice == 'Q':
        self._display_status()
        return self._handle_player_choice_with_pregenerated(choice_point, pregenerated_responses)
    
    if choice == 'D':
        # 自由输入需要实时生成
        free_input = input("请输入你想说的话: ")
        response = self.actor.generate_free_response(free_input, ...)
        self._display_and_apply_response(response)
    elif choice in pregenerated_responses:
        # 使用预生成回应（零延迟）
        response = pregenerated_responses[choice]
        self._display_and_apply_response(response)
    else:
        print("无效选项，请重新选择")
        return self._handle_player_choice_with_pregenerated(choice_point, pregenerated_responses)
```

---

## 任务 3：更新返回类型

### 3.1 修改 `generate_scene_dialogue()` 的返回类型

```python
from typing import Tuple, Optional

def generate_scene_dialogue(
    self, 
    scene_plan: ScenePlan
) -> Tuple[List[DialogueOutput], Optional[Dict[str, ChoiceResponse]]]:
    """
    生成整个场景的对话和预选回应
    
    Args:
        scene_plan: 场景规划
    
    Returns:
        Tuple containing:
        - List[DialogueOutput]: 各 Beat 的对话
        - Optional[Dict[str, ChoiceResponse]]: 预选回应（A/B/C），如果没有选择点则为 None
    """
```

### 3.2 更新调用方

所有调用 `generate_scene_dialogue()` 的地方需要适配新的返回类型：

```python
# 旧代码
dialogue_outputs = self.actor.generate_scene_dialogue(scene_plan)

# 新代码
dialogue_outputs, choice_responses = self.actor.generate_scene_dialogue(scene_plan)
```

---

## 任务 4：优化日志输出

添加日志显示生成进度：

```python
def generate_scene_dialogue(self, scene_plan: ScenePlan):
    print(f"  [CharacterActor] 正在生成 {len(scene_plan.beats)} 个 Beat 的对话...")
    
    # 生成对话
    dialogue_outputs = self._generate_all_beats_dialogue(scene_plan)
    print(f"  [CharacterActor] 对话生成完成")
    
    # 生成预选回应
    choice_responses = None
    if scene_plan.player_choice_point:
        print(f"  [CharacterActor] 正在生成预选回应...")
        choice_responses = self._generate_choice_responses(...)
        print(f"  [CharacterActor] 预选回应生成完成")
    
    return dialogue_outputs, choice_responses
```

---

## 更新项目文档

### STATUS.md 更新

```markdown
### 2025-12-22 - 预选回应提前生成优化 v6 ⭐ 最新

**修改文件**: `api/character_actor.py`, `game_loop_v3.py`

**问题**: 玩家到达选择点时才生成预选回应，导致等待时间

**优化内容**:

1. **character_actor.py**:
   - `generate_scene_dialogue()` 返回类型改为 `Tuple[List[DialogueOutput], Optional[Dict[str, ChoiceResponse]]]`
   - 在生成对话的同时，提前生成预选回应

2. **game_loop_v3.py**:
   - `_run_free_scene()`: 一次性获取对话和预选回应
   - `_handle_player_choice_with_pregenerated()`: 使用预生成回应，零延迟显示

**API 调用流程优化**:
```
旧: Planner(1次) → Actor对话(1次) → [等待] → Actor选项(1次)
新: Planner(1次) → Actor对话+选项(1次或2次并行)
```

**验收标准**:
- ✅ 玩家到达选择点时无需等待
- ✅ 选项回应立即显示
- ✅ 自由输入(D选项)仍支持实时生成

---
```

---

## 验收标准

1. ✅ 场景开始时同时生成对话和预选回应
2. ✅ 玩家到达选择点时，选项回应零延迟显示
3. ✅ 自由输入（D选项）仍然支持实时生成
4. ✅ API 调用次数减少或保持不变

---

## 文件修改清单

| 文件 | 操作 |
|------|------|
| `api/character_actor.py` | 修改 `generate_scene_dialogue()` 返回类型和逻辑 |
| `game_loop_v3.py` | 修改 `_run_free_scene()`，新增 `_handle_player_choice_with_pregenerated()` |
| `STATUS.md` | 添加 v6 更新日志 |

---

## 可选优化：合并为单次 API 调用

如果希望进一步减少 API 调用，可以将对话和选项合并到同一个 prompt 中：

```python
# 单次 API 调用生成所有内容
def generate_complete_scene(self, scene_plan: ScenePlan) -> Dict:
    """
    单次 API 调用生成：
    - 所有 Beat 的对话
    - 所有选项的预生成回应
    """
    prompt = self._build_complete_scene_prompt(scene_plan)
    response = self._call_api(prompt)
    return self._parse_complete_scene(response)
```

这样 API 调用从 `Planner + Actor + Choice = 3次` 减少到 `Planner + Actor(含Choice) = 2次`。
