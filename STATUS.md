# 项目状态追踪

> 最后更新：2025-12-21

---

## 更新日志

### 2025-12-21 - JSON 解析公共模块整合

**修复文件**: `api/character_actor.py`, `api/utils.py`

1. **移除本地 clean_json_response()**: 删除了简单版实现
2. **导入公共模块**: 添加 `from .utils import parse_json_with_diagnostics`
3. **修改 generate_dialogue_for_beat()**: 使用 `parse_json_with_diagnostics()` 替代 `json.loads(clean_json_response(...))`
4. **修改 generate_choice_responses()**: 同上
5. **改进错误处理**: 分离 JSONDecodeError 和其他异常，使用回退逻辑
6. **修复 +号数字问题**: 在 `clean_json_response()` 中添加正则处理 `"stress": +5` → `"stress": 5`

**现在 director_planner.py 和 character_actor.py 使用相同的 JSON 解析逻辑**

**utils.py 的 clean_json_response() 现在处理 5 种问题**：
1. markdown 代码块
2. JSON 对象提取
3. 中文引号和标点
4. 正数前的 + 号（JSON 不允许）
5. 尾部逗号

### 2025-12-20 - JSON 解析错误修复

**修复文件**: `api/director_planner.py`, `api/utils.py`

1. **增加 max_tokens**: 从 2048 → 4096，防止响应被截断
2. **创建公共模块 api/utils.py**:
   - `clean_json_response()`: 正则提取JSON、处理中文引号、移除尾部逗号
   - `fix_truncated_json()`: 自动补全被截断的 JSON 括号
   - `parse_json_with_diagnostics()`: 三次尝试解析（原始→清理→修复）
3. **重构 director_planner.py**: 使用公共模块

---

## 一、模块完成度

### 核心模块

| 模块 | 文件 | 状态 | 说明 |
|------|------|:----:|------|
| 导演规划层 | `api/director_planner.py` | ✅ | 生成ScenePlan，包含多个Beat |
| 角色演出层 | `api/character_actor.py` | ✅ | 根据Beat生成对话 |
| API模块导出 | `api/__init__.py` | ✅ | 导出核心类 |
| v3游戏循环 | `game_loop_v3.py` | ✅ | 两层导演架构主循环 |
| 规划层Prompt | `prompts/director_planner_prompt.txt` | ✅ | 规划层prompt模板 |
| 演出层Prompt | `prompts/character_actor_prompt.txt` | ✅ | 演出层prompt模板 |

### 现有模块

| 模块 | 文件 | 状态 | 说明 |
|------|------|:----:|------|
| 配置文件 | `config.py` | ✅ | API Key、模型配置 |
| v1游戏循环 | `game_loop.py` | ✅ | 单层导演架构 |
| v2游戏循环 | `game_loop_v2.py` | ✅ | 事件驱动架构 |
| 导演API v2 | `director_api_v2.py` | ✅ | 事件系统整合 |
| 角色API测试 | `test_api.py` | ✅ | 角色API测试脚本 |
| 中控API测试 | `test_controller_api.py` | ✅ | 中控API测试脚本 |
| 导演API测试 | `test_director_api.py` | ✅ | 导演API测试脚本 |
| 第一天体验 | `day1_experience.py` | ✅ | 第一天完整流程 |
| 第一天体验v2 | `day1_experience_v2.py` | ✅ | 第一天完整流程v2 |

### 待开发模块

| 模块 | 优先级 | 状态 | 说明 |
|------|:------:|:----:|------|
| 调查阶段逻辑 | 高 | 🚧 | 搜证、询问、线索收集 |
| 审判系统逻辑 | 高 | 🚧 | 投票、辩论、处刑 |
| 状态机 | 中 | 🚧 | free_time → event → investigation → trial |
| 事件验证器 | 中 | ❌ | 检查导演输出合法性 |
| 周目系统 | 低 | ❌ | 工具继承、多周目存档 |
| Unity对接 | 低 | ❌ | JSON接口导出 |

**图例**：✅ 已完成 | 🚧 开发中 | ❌ 未开始

---

## 二、API接口速查

### config.py

```python
# 配置常量
API_KEYS: Dict[str, str]           # API密钥字典
MODEL: str                         # 模型名称
MAX_TOKENS: int                    # 最大token数
CACHE_TTL: int                     # 缓存TTL（秒）
ENABLE_CACHE: bool                 # 是否启用缓存
PROJECT_ROOT: Path                 # 项目根目录
OUTPUT_DIR: Path                   # 输出目录

# 函数
def get_api_key(service_type: str) -> str
    """获取指定服务的API Key"""
```

---

### api/director_planner.py

```python
@dataclass
class Beat:
    """场景中的一个戏剧节拍"""
    beat_id: str                   # Beat唯一ID
    beat_type: str                 # opening/development/tension/climax/resolution
    description: str               # Beat描述
    characters: List[str]          # 参与角色
    speaker_order: List[str]       # 说话顺序
    emotion_targets: Dict[str, str] # 各角色情绪目标
    tension_level: int             # 张力等级 1-10
    dialogue_count: int            # 建议对话行数
    direction_notes: str           # 导演指示

@dataclass
class ScenePlan:
    """场景规划"""
    scene_id: str                  # 场景ID
    scene_name: str                # 场景名称
    location: str                  # 地点
    time_estimate_minutes: int     # 预计时长（分钟）
    total_beats: int               # Beat总数
    beats: List[Beat]              # Beat列表
    overall_arc: str               # 整体情感弧线
    key_moments: List[str]         # 关键时刻
    player_choice_point: Optional[Dict]  # 玩家选择点
    outcomes: Dict[str, Any]       # 可能的结果
    recommended_bgm: str           # 推荐BGM

class DirectorPlanner:
    """导演规划层"""

    def __init__(self, project_root: Path = None)
        """初始化，加载prompt模板"""

    def load_game_context(self) -> Dict
        """加载游戏上下文（current_day, character_states）"""

    def load_character_data(self, char_id: str) -> Dict
        """加载角色完整数据（core, personality, speech）"""

    def get_characters_at_location(self, location: str) -> List[str]
        """获取指定地点的角色列表"""

    def plan_scene(
        self,
        location: str,
        scene_type: str = "free",
        fixed_event_data: Optional[Dict] = None,
        player_location: str = None
    ) -> ScenePlan
        """生成场景规划（核心方法）"""
```

---

### api/character_actor.py

```python
@dataclass
class DialogueLine:
    """单行对话"""
    speaker: str                   # 角色ID或"narrator"
    text_cn: str                   # 中文对话
    emotion: str                   # 情绪
    action: Optional[str] = None   # 伴随动作

@dataclass
class DialogueOutput:
    """对话输出"""
    beat_id: str                   # Beat ID
    dialogue: List[DialogueLine]   # 对话列表
    effects: Dict[str, Any]        # 状态变化效果

@dataclass
class ChoiceResponse:
    """选项回应"""
    choice_id: str                 # 选项ID (A/B/C)
    dialogue: List[DialogueLine]   # 回应对话
    effects: Dict[str, Any]        # 效果

class CharacterActor:
    """角色演出层"""

    def __init__(self, project_root: Path = None)
        """初始化，加载prompt模板"""

    def load_character_data(self, char_id: str) -> Dict
        """加载角色数据（带缓存）"""

    def load_character_state(self, char_id: str) -> Dict
        """加载角色当前状态"""

    def generate_dialogue_for_beat(self, beat: Beat) -> DialogueOutput
        """根据Beat生成对话（核心方法）"""

    def generate_choice_responses(
        self,
        choice_point: Dict,
        characters: List[str]
    ) -> Dict[str, ChoiceResponse]
        """预生成玩家选项的回应"""

    def generate_scene_dialogue(self, scene_plan: ScenePlan) -> List[DialogueOutput]
        """生成整个场景的对话"""
```

---

### director_api_v2.py

```python
@dataclass
class GameContext:
    """游戏上下文"""
    day: int
    phase: str
    event_count: int
    flags: Dict[str, bool]
    player_location: str

@dataclass
class EventResult:
    """事件结果"""
    event_id: str
    event_type: str                # "fixed" | "free"
    dialogue: List[Dict]
    choices: Optional[Dict]
    outcomes: Dict[str, Dict]
    next_event: Optional[str]
    next_phase: Optional[str]
    flags_set: List[str]
    game_over: bool
    ending_type: Optional[str]

class ConditionEvaluator:
    """条件评估器"""

    def __init__(self, character_states, current_day, locations)
    def evaluate(self, condition: str) -> bool
        """评估条件字符串"""
    def check_trigger(self, trigger: Dict) -> bool
        """检查事件触发条件"""

class EventManager:
    """事件管理器"""

    def __init__(self)
    def reload_state(self)
    def get_pending_fixed_event(self) -> Optional[Dict]
    def check_branch(self, event_data: Dict) -> Optional[str]
    def select_free_event_template(self, player_location: str) -> Optional[Dict]
    def get_characters_at_location(self, location_name: str) -> List[str]
    def mark_event_triggered(self, event_id: str)
    def set_flag(self, flag_name: str, value: bool = True)
    def increment_event_count(self)
    def set_phase(self, phase: str)
    def next_day(self)

class DirectorAPIv2:
    """导演API v2"""

    def __init__(self)
    def process_turn(self, player_location: str) -> EventResult
        """处理一个回合"""
    def apply_outcomes(self, outcomes: Dict)
        """应用事件结果到角色状态"""
```

---

### game_loop.py

```python
# 工具函数
def load_json(filepath) -> dict
def save_json(filepath, data)
def load_yaml(filepath) -> dict
def load_yaml_safe(filepath, default=None) -> dict
def get_character_data(character_id) -> dict
def clean_json_response(text) -> str

# 时间系统
def advance_time(minutes=10) -> Optional[str]
    """推进游戏时间，返回特殊事件"""
def get_time_display() -> str
    """获取时间显示字符串"""

# API调用
def call_controller_api() -> dict
    """调用中控API，更新13人位置和行为"""
def call_director_api(character_id) -> dict
    """调用导演API，生成对话剧本和选项"""
def call_character_api(character_id, player_input) -> dict
    """调用角色API，生成自由对话回复"""

# 显示函数
def display_world_state()
def display_dialogue(result)
def display_choices(result)
def display_response(result)
def display_pregenerated_response(option, character_id)

# 主循环
def game_loop() -> Optional[str]
    """游戏主循环，返回特殊事件"""
def main()
    """主游戏入口"""
```

---

### game_loop_v2.py

```python
# 显示函数
def display_header()
def display_time()
def display_world_state()
def display_dialogue(dialogue: list)
def display_choices(choices: dict)
def display_event_result(result: EventResult)
def display_ending(ending_type: str)
def display_location_menu(locations: dict, current_phase: str)

# NPC更新
def call_controller_api()
    """调用中控API更新NPC位置"""

# 角色对话
def call_character_api(char_id: str, player_input: str) -> dict
    """调用角色API进行自由对话"""

class GameLoopV2:
    """游戏主循环 v2"""

    def __init__(self)
    def run(self)
        """运行游戏"""
    def game_turn(self)
        """一个游戏回合"""
    def handle_event_result(self, result: EventResult)
    def handle_player_choice(self, result: EventResult)
```

---

### game_loop_v3.py

```python
# 显示函数
def display_header()
def display_time(project_root: Path)
def display_world_state(project_root: Path)
def display_scene_plan(scene_plan: ScenePlan)
def display_beat_info(beat: Beat, beat_index: int)
def display_dialogue(dialogue_output: DialogueOutput)
def display_choices(choice_point: Dict)
def display_location_menu(locations: dict, current_phase: str)

class GameLoopV3:
    """游戏主循环 v3 - 两层导演架构"""

    def __init__(self)
        """初始化 DirectorPlanner 和 CharacterActor"""

    def run(self)
        """运行游戏"""

    def game_turn(self)
        """一个游戏回合：规划 → 演出 → 选择"""

    def _handle_player_choice(self, choice_point: Dict, characters: List[str])
        """处理玩家选择"""

    def _apply_dialogue_effects(self, dialogue_output: DialogueOutput)
        """应用对话效果"""

    def _apply_choice_effects(self, effects: Dict)
        """应用选项效果"""

    def _apply_scene_outcomes(self, scene_plan: ScenePlan)
        """应用场景结果"""

    def _increment_event_count(self)
        """增加事件计数"""
```

---

### test_api.py

```python
def build_character_prompt(character_id, player_input) -> str
    """构建角色API的prompt"""

def call_character_api(character_id, player_input) -> dict
    """调用角色API"""

def main()
    """测试入口"""
```

---

### test_controller_api.py

```python
def build_controller_prompt(current_day, character_states) -> str
    """构建中控API的prompt"""

def main()
    """测试入口"""
```

---

### test_director_api.py

```python
def load_character_data(character_id) -> dict
    """加载角色完整数据"""

def build_system_prompt(char_data) -> str
    """构建系统prompt（可缓存部分）"""

def build_user_prompt(scene_info, character_state) -> str
    """构建用户prompt（场景特定部分）"""

class DirectorAPITester:
    """导演API测试器"""

    def __init__(self)
    def call_api(self, system_prompt, user_prompt, use_cache=True) -> str
    def send_heartbeat(self, system_prompt)
    def start_heartbeat(self, system_prompt)
    def stop_heartbeat(self)
    def parse_response(self, response_text) -> dict
    def display_result(self, result)
    def display_cache_stats(self)

def main()
    """测试入口"""
```

---

## 三、数据流向图

### v3 两层导演架构数据流

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           game_loop_v3.py                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. 加载数据                                                            │
│     ├─ world_state/current_day.json      → 当前时间、阶段、标记        │
│     ├─ world_state/character_states.json → 13人状态                    │
│     └─ world_state/locations.yaml        → 地点信息                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. 玩家选择地点                                                        │
│     player_location = "食堂" / "庭院" / "图书室" / ...                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. 导演规划层 (DirectorPlanner)                                        │
│     ┌─────────────────────────────────────────────────────────────┐    │
│     │ 输入:                                                       │    │
│     │   - location: "食堂"                                        │    │
│     │   - context: {day, phase, flags, character_states}          │    │
│     │   - characters/*.yaml (角色数据)                            │    │
│     └─────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│     ┌─────────────────────────────────────────────────────────────┐    │
│     │ API调用: Claude API                                         │    │
│     │ Prompt: prompts/director_planner_prompt.txt                 │    │
│     └─────────────────────────────────────────────────────────────┘    │
│                              │                                          │
│                              ▼                                          │
│     ┌─────────────────────────────────────────────────────────────┐    │
│     │ 输出: ScenePlan                                             │    │
│     │   - scene_id, scene_name, location                          │    │
│     │   - beats: [Beat1, Beat2, Beat3, ...]                       │    │
│     │   - player_choice_point: {after_beat, options}              │    │
│     │   - outcomes, recommended_bgm                               │    │
│     └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. 角色演出层 (CharacterActor) - 逐Beat执行                            │
│     ┌─────────────────────────────────────────────────────────────┐    │
│     │ for beat in scene_plan.beats:                               │    │
│     │                                                             │    │
│     │   输入:                                                     │    │
│     │     - beat: {beat_id, characters, emotion_targets, ...}     │    │
│     │     - characters/*.yaml (角色数据)                          │    │
│     │     - character_states (当前状态)                           │    │
│     │                                                             │    │
│     │   API调用: Claude API                                       │    │
│     │   Prompt: prompts/character_actor_prompt.txt                │    │
│     │                                                             │    │
│     │   输出: DialogueOutput                                      │    │
│     │     - dialogue: [{speaker, text_cn, emotion, action}, ...]  │    │
│     │     - effects: {char_id: {stress, emotion}}                 │    │
│     └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. 玩家选择点                                                          │
│     ┌─────────────────────────────────────────────────────────────┐    │
│     │ if beat == player_choice_point.after_beat:                  │    │
│     │                                                             │    │
│     │   预生成回应: generate_choice_responses()                   │    │
│     │     → Dict[A/B/C, ChoiceResponse]                           │    │
│     │                                                             │    │
│     │   显示选项: A. 正面 / B. 中性 / C. 危险 / D. 自由输入       │    │
│     │                                                             │    │
│     │   玩家选择 → 显示预生成回应（零延迟）                       │    │
│     └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  6. 状态更新                                                            │
│     ├─ _apply_dialogue_effects()  → 更新 character_states.json         │
│     ├─ _apply_choice_effects()    → 更新 character_states.json         │
│     ├─ _apply_scene_outcomes()    → 更新 character_states.json, flags  │
│     └─ _increment_event_count()   → 更新 current_day.json              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │  下一回合    │
                            └──────────────┘
```

### 数据文件关系

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              数据文件                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  characters/                                                            │
│  ├── aima/                                                              │
│  │   ├── core.yaml          ← 基础信息 (name, age, prisoner_number)    │
│  │   ├── personality.yaml   ← 性格特质 (versions, traits, triggers)    │
│  │   ├── speech.yaml        ← 说话方式 (first_person, verbal_tics)     │
│  │   └── relationships.yaml ← 人际关系 (existing, potential)           │
│  ├── hiro/                                                              │
│  ├── ...                                                                │
│  └── (共14个角色)                                                       │
│                                                                         │
│  world_state/                                                           │
│  ├── current_day.json       ← 当前时间状态                              │
│  │   {day, time, phase, event_count, flags, triggered_events}           │
│  ├── character_states.json  ← 13人实时状态                              │
│  │   {char_id: {stress, madness, emotion, location, action, ...}}       │
│  ├── locations.yaml         ← 地点信息                                  │
│  ├── events_log.json        ← 事件日志                                  │
│  └── pending_events.json    ← 待处理事件                                │
│                                                                         │
│  events/                                                                │
│  ├── fixed_events.yaml      ← 固定事件定义                              │
│  └── free_event_templates.yaml ← 自由事件模板                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 四、版本对比

| 特性 | v1 (game_loop.py) | v2 (game_loop_v2.py) | v3 (game_loop_v3.py) |
|------|:-----------------:|:--------------------:|:--------------------:|
| 架构 | 单层导演 | 事件驱动 | 两层导演 |
| 场景规划 | 无 | 事件模板 | ScenePlan + Beat |
| 对话生成 | 单次API调用 | 单次API调用 | 分层API调用 |
| 张力控制 | 无 | 无 | 1-10等级 |
| 预生成回应 | ✅ | ✅ | ✅ |
| 固定事件 | 无 | ✅ | 兼容 |
| 自由事件 | 无 | ✅ | 兼容 |
| 可调试性 | 低 | 中 | 高 |

---

## 五、运行方式

```bash
# 进入项目目录
cd test_project

# 运行v1版本
python game_loop.py

# 运行v2版本
python game_loop_v2.py

# 运行v3版本（推荐）
python game_loop_v3.py

# 运行测试
python test_api.py             # 角色API测试
python test_controller_api.py  # 中控API测试
python test_director_api.py    # 导演API测试
```

---

*状态更新日期：2025-12-20*
