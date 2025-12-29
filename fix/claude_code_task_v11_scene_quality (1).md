# Claude Code 任务：场景生成质量完善 v11

## 问题来源

2025-12-24 测试发现以下待改进问题：

| 问题 | 严重度 | 示例 |
|------|:------:|------|
| Beat 1 (OPENING) 总是空 | 🔴 高 | 连续3次重试都空，最后用回退模板 |
| 地点名称不匹配 | 🟡 中 | 食堂场景说"厨房"、"晚餐后" |
| 时段描写不匹配 | 🟡 中 | 上午时段说"晚餐后的厨房" |
| 场景名与内容不一致 | 🟡 中 | 场景名"厨房的沉默时光"但地点是食堂 |

---

## 一、问题1：OPENING Beat 总是空

### 1.1 问题分析

```
测试日志：
  [CharacterActor] 对话生成完成 (响应长度: 3264 字符)
  ⚠️ 检测到 1 个空 Beat，重试中... (1/2)
  ...（连续3次都是空）
  ⚠️ 重试后仍有空 Beat，使用回退内容填充

最终显示：
  [开] Beat 1: OPENING
  --------------------------------------------------
  你来到了这里。午后阳光透过窗棂洒在图书室里...  ← 回退模板
```

**根本原因**：AI 认为 OPENING 只需要描述，不需要生成对话，所以 `dialogue` 数组为空。

### 1.2 修复方案

**修改文件**: `prompts/character_actor_prompt.txt`

在 prompt 中明确要求每个 Beat 类型必须输出什么：

```markdown
【重要：每个Beat必须有内容】

不管什么类型的Beat，都必须在 dialogue 数组中输出内容！

| Beat类型 | 必须包含 | 最少行数 |
|----------|----------|:--------:|
| OPENING | narrator 环境描写 | 2行 |
| DEVELOPMENT | 角色对话 + narrator动作 | 3行 |
| TENSION | 角色对话 + narrator动作 | 3行 |
| CLIMAX | 角色对话 + narrator动作 | 3行 |
| RESOLUTION | narrator收尾 或 角色对话 | 2行 |

❌ 错误示例（dialogue为空）：
{
  "beat_id": "beat_1",
  "dialogue": []  // 这是错的！
}

✅ 正确示例（OPENING也要有narrator内容）：
{
  "beat_id": "beat_1", 
  "dialogue": [
    {"speaker": "narrator", "text_cn": "午后的阳光透过高窗洒落，在图书室的地板上画出金色的光斑。", "emotion": "peaceful"},
    {"speaker": "narrator", "text_cn": "安安独自坐在角落的沙发上，手中的绘本已经翻到了最后几页。她的表情很平静，仿佛外面的世界与她无关。", "emotion": "peaceful"}
  ]
}

【OPENING 的正确写法】
OPENING 不是"不说话"，而是用 narrator 来描写环境和角色初始状态。
必须输出至少2行 narrator 内容，包括：
1. 环境描写（光线、声音、氛围）
2. 角色状态（在做什么、表情、姿态）
```

### 1.3 修改 CharacterActor 验证逻辑

**修改文件**: `api/character_actor.py`

```python
def _check_empty_beats(self, outputs: List[DialogueOutput]) -> List[str]:
    """检查哪些 Beat 内容为空或过短"""
    empty = []
    for output in outputs:
        # 检查对话列表是否为空
        if not output.dialogue:
            empty.append(output.beat_id)
            continue
            
        # 检查是否只有空字符串
        has_content = any(
            line.text_cn and line.text_cn.strip() and len(line.text_cn.strip()) > 10
            for line in output.dialogue
        )
        if not has_content:
            empty.append(output.beat_id)
            
    return empty
```

### 1.4 改进回退内容

**修改文件**: `api/character_actor.py`

```python
def _generate_fallback_narration(self, beat: Beat, location: str) -> List[DialogueLine]:
    """根据 Beat 信息生成更丰富的回退叙述"""
    
    # 环境描写模板
    location_descriptions = {
        "食堂": "食堂里弥漫着淡淡的饭菜香气，长桌上整齐地摆放着餐具。",
        "图书室": "图书室里很安静，阳光透过窗户洒在书架上，灰尘在光线中轻轻飘浮。",
        "庭院": "庭院里微风轻拂，午后的阳光温暖而柔和。",
        "走廊": "长长的走廊寂静无声，窗外的光线在地板上投下斑驳的影子。",
        "牢房区": "牢房区的空气有些沉闷，铁栏杆在昏暗的光线中泛着冷光。",
    }
    
    env_desc = location_descriptions.get(location, "这里很安静，空气中弥漫着微妙的紧张感。")
    
    # 根据 Beat 类型生成不同内容
    if beat.beat_type == "opening":
        lines = [
            DialogueLine(
                speaker="narrator",
                text_cn=env_desc,
                text_jp="",
                emotion="neutral"
            ),
            DialogueLine(
                speaker="narrator", 
                text_cn=beat.description,
                text_jp="",
                emotion="neutral"
            )
        ]
    elif beat.beat_type == "resolution":
        lines = [
            DialogueLine(
                speaker="narrator",
                text_cn=f"时间静静流逝。{beat.description}",
                text_jp="",
                emotion="neutral"
            )
        ]
    else:
        # development, tension, climax
        lines = [
            DialogueLine(
                speaker="narrator",
                text_cn=beat.description,
                text_jp="",
                emotion="neutral"
            )
        ]
        
        # 如果有角色，添加一句简单对话
        if beat.characters:
            char = beat.characters[0]
            lines.append(DialogueLine(
                speaker=char,
                text_cn="......",
                text_jp="......",
                emotion="neutral",
                action="沉默着"
            ))
            
    return lines
```

### 1.5 验收标准

- [ ] OPENING Beat 不再为空
- [ ] OPENING 包含至少2行 narrator 内容
- [ ] 回退内容包含环境描写
- [ ] 不再出现只有模板的 Beat

---

## 二、问题2：地点和时段不匹配

### 2.1 问题分析

```
测试日志：
  输入数字: 1  ← 选择食堂
  [场景规划] 厨房的沉默时光  ← 说"厨房"不是"食堂"
  整体弧线: ...晚餐后的厨房...  ← 当时是上午！

问题：
1. DirectorPlanner 生成时不知道当前时段
2. 场景名称、描述中出现错误地点/时间词
```

### 2.2 修复方案 - 传递时段信息

**修改文件**: `api/director_planner.py`

```python
def plan_scene(
    self,
    location: str,
    scene_type: str = "free",
    fixed_event_data: Optional[Dict] = None,
    player_location: str = None
) -> ScenePlan:
    """生成场景规划"""
    
    # 获取当前时段
    current_day = self._load_current_day()
    period = current_day.get("period", "morning")
    day = current_day.get("day", 1)
    
    # 时段中文映射
    period_cn = {
        "dawn": "黎明",
        "morning": "上午", 
        "noon": "正午",
        "afternoon": "下午",
        "evening": "傍晚",
        "night": "夜晚"
    }
    
    # 构建 prompt 时传入时段信息
    prompt = self._build_prompt(
        location=location,
        period=period,
        period_cn=period_cn.get(period, "白天"),
        day=day,
        ...
    )
```

### 2.3 修改 Prompt 模板

**修改文件**: `prompts/director_planner_prompt.txt`

```markdown
【重要：时间和地点一致性】

当前状态：
- 地点：{location}（必须使用这个地点名，不能用别名）
- 时段：{period_cn}（{period}）
- 第 {day} 天

❌ 禁止：
- 使用其他地点名（如：食堂不能写成"厨房"、"餐厅"）
- 使用错误时段（如：上午不能写"晚餐后"、"夜晚"）
- 场景名包含错误地点

✅ 正确：
- 场景名必须包含正确地点："{location}的xxx"
- 描述必须符合当前时段：
  - 黎明/上午：晨光、朝阳、早餐后
  - 正午：午后阳光、午餐时间
  - 下午：午后、下午茶时间
  - 傍晚：夕阳、晚霞、晚餐前
  - 夜晚：月光、灯光、就寝前

地点正确名称对照：
| 正确 ✅ | 错误 ❌ |
|---------|---------|
| 食堂 | 厨房、餐厅、饭堂 |
| 图书室 | 图书馆、阅览室 |
| 牢房区 | 牢房、监狱、囚室 |
| 走廊 | 长廊、过道、通道 |
| 庭院 | 花园、院子、天井 |
```

### 2.4 增强地点验证

**修改文件**: `api/director_planner.py`

```python
def _validate_and_fix_scene_plan(self, scene_plan: Dict, location: str, period: str) -> Dict:
    """验证并修正场景规划"""
    
    # 地点别名映射
    location_aliases = {
        "厨房": "食堂", "餐厅": "食堂", "饭堂": "食堂",
        "图书馆": "图书室", "阅览室": "图书室",
        "牢房": "牢房区", "监狱": "牢房区", "囚室": "牢房区",
        "长廊": "走廊", "过道": "走廊", "通道": "走廊",
        "花园": "庭院", "院子": "庭院", "天井": "庭院",
    }
    
    # 时段关键词
    period_keywords = {
        "dawn": ["黎明", "晨曦", "破晓"],
        "morning": ["上午", "早晨", "晨光", "朝阳"],
        "noon": ["正午", "中午", "午后"],
        "afternoon": ["下午", "午后"],
        "evening": ["傍晚", "黄昏", "夕阳", "晚霞"],
        "night": ["夜晚", "月光", "夜色", "灯光"]
    }
    
    # 错误时段关键词
    wrong_period_keywords = {
        "morning": ["晚餐", "夜晚", "月光", "晚上"],
        "noon": ["早餐", "黎明", "夜晚"],
        "afternoon": ["早餐", "黎明", "晚餐后"],
        "evening": ["早餐", "午餐", "黎明"],
        "night": ["早餐", "午餐", "阳光"]
    }
    
    # 1. 修正场景名称中的地点
    scene_name = scene_plan.get("scene_name", "")
    for wrong, correct in location_aliases.items():
        if wrong in scene_name and correct == location:
            scene_name = scene_name.replace(wrong, correct)
    scene_plan["scene_name"] = scene_name
    
    # 2. 检查场景名是否包含正确地点
    if location not in scene_name:
        scene_plan["scene_name"] = f"{location}的{scene_name}"
        
    # 3. 检查描述中的时段错误
    overall_arc = scene_plan.get("overall_arc", "")
    wrong_keywords = wrong_period_keywords.get(period, [])
    for keyword in wrong_keywords:
        if keyword in overall_arc:
            print(f"⚠️ 时段描写不匹配: 当前是{period}，但出现了「{keyword}」")
            # 可以选择替换或警告
            
    return scene_plan
```

### 2.5 验收标准

- [ ] 场景名称使用正确地点名（食堂不是厨房）
- [ ] 描述符合当前时段（上午不说"晚餐后"）
- [ ] Prompt 明确传递时段信息
- [ ] 自动修正错误地点别名

---

## 三、问题3：场景名重复/不够独特

### 3.1 问题分析

每次去同一地点，场景名可能很相似：
- "食堂的沉默时光"
- "食堂的静谧午后"
- "食堂的平静时刻"

### 3.2 修复方案 - 场景名去重

**修改文件**: `api/director_planner.py`

```python
def _get_used_scene_names(self) -> List[str]:
    """获取已使用的场景名"""
    history_path = self.project_root / "world_state" / "scene_history.json"
    if history_path.exists():
        history = load_json(history_path)
        return [s.get("scene_name", "") for s in history.get("scenes", [])]
    return []

def _ensure_unique_scene_name(self, scene_name: str, location: str) -> str:
    """确保场景名不重复"""
    used_names = self._get_used_scene_names()
    
    if scene_name not in used_names:
        return scene_name
        
    # 重复了，添加序号
    base_name = scene_name
    for i in range(2, 10):
        new_name = f"{base_name}（{i}）"
        if new_name not in used_names:
            return new_name
            
    # 还是重复，用时间戳
    import time
    return f"{location}_{int(time.time())}"
```

---

## 四、实施顺序

### Phase 1：修复 OPENING 空内容（优先级最高）

1. 修改 `prompts/character_actor_prompt.txt`
   - 添加每个Beat必须有内容的说明
   - 添加OPENING正确写法示例

2. 修改 `api/character_actor.py`
   - 改进 `_generate_fallback_narration()`
   - 添加地点感知的环境描写

### Phase 2：修复地点/时段不匹配

3. 修改 `api/director_planner.py`
   - `plan_scene()` 传递时段信息
   - 添加 `_validate_and_fix_scene_plan()`

4. 修改 `prompts/director_planner_prompt.txt`
   - 添加时段一致性要求
   - 添加地点正确名称对照表

### Phase 3：场景名去重

5. 修改 `api/director_planner.py`
   - 添加 `_get_used_scene_names()`
   - 添加 `_ensure_unique_scene_name()`

---

## 五、验收测试

```python
# 测试脚本
def test_v11_fixes():
    """测试 v11 修复"""
    
    # 测试1: OPENING 不为空
    print("测试1: OPENING Beat 内容")
    # 运行一个场景，检查 Beat 1 是否有内容
    
    # 测试2: 地点一致性
    print("测试2: 地点名称")
    # 选择食堂，检查场景名不包含"厨房"
    
    # 测试3: 时段一致性  
    print("测试3: 时段描写")
    # 上午时段，检查不出现"晚餐"、"夜晚"
    
    # 测试4: 场景名去重
    print("测试4: 场景名唯一性")
    # 连续去同一地点，检查场景名不重复
```

---

## 六、预期效果

**修复前：**
```
[开] Beat 1: OPENING
--------------------------------------------------
你来到了这里。午后阳光透过窗棂...  ← 回退模板，内容单薄

[场景规划] 厨房的沉默时光  ← 地点错误
整体弧线: 晚餐后的厨房...  ← 时段错误（当时是上午）
```

**修复后：**
```
[开] Beat 1: OPENING
--------------------------------------------------
[narrator]
  食堂里弥漫着淡淡的饭菜香气，午后的阳光透过窗户洒在长桌上。

[narrator]
  米莉亚独自站在水槽边，慢慢地洗着餐具。她的动作很轻柔，仿佛在享受这难得的宁静时光。

[场景规划] 食堂的午后时光  ← 地点正确
整体弧线: 午后的食堂里，两人在无声的劳动中...  ← 时段正确
```

---

*任务版本：v11*
*创建日期：2024-12-24*
*修复问题：OPENING空内容、地点/时段不匹配、场景名去重*
