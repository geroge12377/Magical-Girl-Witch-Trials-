# Claude Code 任务：测试问题修复 v10

## 问题来源

2025-12-24 测试日志发现以下问题：

| 问题 | 严重度 | 示例 |
|------|:------:|------|
| 场景内容为空 | 🔴 高 | Beat 只有标题，无实际内容 |
| NPC 不移动 | 🔴 高 | 从上午到夜晚位置完全不变 |
| 幻觉角色名 | 🔴 高 | 出现"美咲""亚美""千夏"等不存在角色 |
| 地点描写不匹配 | 🟡 中 | 选走廊，内容写"图书馆深处" |
| 固定事件太短 | 🟡 中 | 午餐/晚餐只有2句描述 |

---

## 一、问题1：场景内容为空

### 1.1 问题描述

```
[开] Beat 1: OPENING
   午后阳光下的庭院，安安独自站在角落静静观察这个陌生环境
   张力: [##--------] 2/10

--------------------------------------------------

[按Enter继续...]  ← 没有任何内容就结束了
```

CharacterActor 生成的对话为空，但没有检测和重试。

### 1.2 修复方案

**修改文件**: `api/character_actor.py`

```python
class CharacterActor:
    
    def generate_scene_dialogue(self, scene_plan: ScenePlan) -> Tuple[List[DialogueOutput], ...]:
        """生成场景对话，带空内容检测和重试"""
        
        max_retries = 2
        
        for attempt in range(max_retries + 1):
            outputs = self._generate_dialogue_internal(scene_plan)
            
            # 验证内容不为空
            empty_beats = self._check_empty_beats(outputs)
            
            if not empty_beats:
                return outputs
                
            if attempt < max_retries:
                print(f"⚠️ 检测到 {len(empty_beats)} 个空 Beat，重试中... ({attempt+1}/{max_retries})")
                # 可以只重新生成空的 Beat
                outputs = self._regenerate_empty_beats(outputs, empty_beats, scene_plan)
            else:
                print(f"⚠️ 重试后仍有空 Beat，使用回退内容填充")
                outputs = self._fill_empty_beats_with_fallback(outputs, empty_beats, scene_plan)
                
        return outputs
        
    def _check_empty_beats(self, outputs: List[DialogueOutput]) -> List[str]:
        """检查哪些 Beat 内容为空"""
        empty = []
        for output in outputs:
            # 检查对话列表是否为空或只有空字符串
            has_content = any(
                line.text_cn and line.text_cn.strip() 
                for line in output.dialogue
            )
            if not has_content:
                empty.append(output.beat_id)
        return empty
        
    def _fill_empty_beats_with_fallback(
        self, 
        outputs: List[DialogueOutput], 
        empty_beats: List[str],
        scene_plan: ScenePlan
    ) -> List[DialogueOutput]:
        """用回退内容填充空 Beat"""
        
        for output in outputs:
            if output.beat_id in empty_beats:
                # 找到对应的 Beat 信息
                beat_info = next(
                    (b for b in scene_plan.beats if b.beat_id == output.beat_id), 
                    None
                )
                
                if beat_info:
                    # 生成回退内容
                    fallback_text = self._generate_fallback_narration(beat_info)
                    output.dialogue = [
                        DialogueLine(
                            speaker="narrator",
                            text_cn=fallback_text,
                            text_jp="",
                            emotion="neutral"
                        )
                    ]
        return outputs
        
    def _generate_fallback_narration(self, beat: Beat) -> str:
        """根据 Beat 信息生成回退叙述"""
        
        templates = {
            "opening": "你来到了这里。{description}",
            "development": "{description} 气氛变得微妙起来。",
            "tension": "空气中弥漫着一丝紧张。{description}",
            "climax": "{description} 这一刻似乎格外漫长。",
            "resolution": "时间静静流逝。{description}"
        }
        
        template = templates.get(beat.beat_type, "{description}")
        return template.format(description=beat.description[:50])
```

### 1.3 验收标准

- [ ] 空 Beat 被检测并触发重试
- [ ] 重试失败后使用回退内容
- [ ] 回退内容至少包含 Beat 描述
- [ ] 不再出现完全空白的场景

---

## 二、问题2：NPC 不移动

### 2.1 问题描述

```
上午：图书室5人、庭院4人、牢房区1人、走廊1人、食堂2人
     ↓ 经过4个时段
夜晚：图书室5人、庭院4人、牢房区1人、走廊1人、食堂2人
     完全一样！
```

NPC 只在固定事件 `trigger_npc_scatter` 时移动一次，之后再也不动。

### 2.2 修复方案

**修改文件**: `game_loop_v3.py`

```python
import random

class GameLoopV3:
    
    def __init__(self):
        # ...
        self.npc_move_chance = 0.3  # 每个时段 30% 概率移动
        
    def advance_time(self):
        """推进时间，并触发 NPC 移动"""
        
        # 原有时间推进逻辑
        old_period = self._get_current_period()
        # ... 时间推进 ...
        new_period = self._get_current_period()
        
        # 时段变化时，触发 NPC 移动
        if old_period != new_period:
            self._maybe_move_npcs()
            
    def _maybe_move_npcs(self):
        """随机移动部分 NPC"""
        
        character_states = self._load_character_states()
        locations = ["食堂", "牢房区", "图书室", "庭院", "走廊"]
        
        moved_count = 0
        
        for char_id, state in character_states.items():
            if char_id == "aima":  # 玩家不自动移动
                continue
                
            # 概率移动
            if random.random() < self.npc_move_chance:
                old_location = state.get("location", "牢房区")
                
                # 选择新位置（排除当前位置）
                available = [loc for loc in locations if loc != old_location]
                new_location = random.choice(available)
                
                # 更新位置
                state["location"] = new_location
                moved_count += 1
                
        if moved_count > 0:
            self._save_character_states(character_states)
            print(f"[系统] {moved_count} 名角色移动了位置")
            
    def _move_npc_with_preference(self, char_id: str, current_location: str) -> str:
        """根据角色偏好移动（可选的高级版本）"""
        
        # 角色位置偏好（可以从 characters/{id}/core.yaml 读取）
        preferences = {
            "hannah": ["走廊", "牢房区"],      # 喜欢安静的地方
            "sherry": ["食堂", "庭院"],        # 喜欢热闹
            "anan": ["图书室", "牢房区"],      # 安静独处
            "noah": ["图书室", "庭院"],        # 画画
            "hiro": ["走廊", "庭院"],          # 巡逻
            "margo": ["图书室", "牢房区"],     # 研究
            "reia": ["食堂", "庭院"],          # 社交
            # ... 其他角色
        }
        
        preferred = preferences.get(char_id, ["食堂", "庭院", "走廊"])
        
        # 70% 去偏好地点，30% 随机
        if random.random() < 0.7:
            available = [loc for loc in preferred if loc != current_location]
            if available:
                return random.choice(available)
                
        # 随机
        all_locations = ["食堂", "牢房区", "图书室", "庭院", "走廊"]
        available = [loc for loc in all_locations if loc != current_location]
        return random.choice(available)
```

### 2.3 可选：角色位置偏好配置

**新增文件**: `worlds/witch_trial/npc_behavior.yaml`

```yaml
# NPC 行为配置

movement:
  base_chance: 0.3        # 基础移动概率
  period_modifiers:
    morning: 0.4          # 早上活跃
    noon: 0.2             # 午餐时少移动
    afternoon: 0.35
    evening: 0.3
    night: 0.1            # 夜晚很少移动

location_preferences:
  hannah:
    preferred: [走廊, 牢房区]
    avoid: [食堂]         # 不喜欢人多的地方
    
  sherry:
    preferred: [食堂, 庭院, 图书室]
    roaming: true         # 喜欢到处跑
    
  anan:
    preferred: [图书室, 牢房区]
    avoid: [食堂, 庭院]   # 不喜欢人多
    
  noah:
    preferred: [图书室, 庭院]
    stay_chance: 0.6      # 60% 概率待在原地（专注画画）
    
  hiro:
    preferred: [走廊, 庭院]
    roaming: true         # 巡逻
    
  margo:
    preferred: [图书室, 牢房区]
    
  reia:
    preferred: [食堂, 庭院]
    social: true          # 喜欢跟人在一起
    
  coco:
    preferred: [庭院, 走廊]
    avoid: [食堂]
    
  meruru:
    preferred: [图书室, 牢房区]
    follow_crowd: false   # 不跟人群
    
  arisa:
    preferred: [庭院, 走廊]
    avoid: [图书室]       # 不耐烦待在安静的地方
    
  nanoka:
    preferred: [食堂, 牢房区]
    stay_chance: 0.5      # 存在感低，常待原地
    
  miria:
    preferred: [食堂, 图书室]
```

### 2.4 验收标准

- [ ] 每个时段变化时触发 NPC 移动检查
- [ ] 约 30% 的 NPC 会移动
- [ ] 移动后位置正确保存到 `character_states.json`
- [ ] 显示移动提示信息
- [ ] 可选：角色偏好影响移动目的地

---

## 三、问题3：幻觉角色名

### 3.1 问题描述

```
[hiro] 美咲总是试图调节气氛...亚美那种直接的态度...千夏表面上看起来无害...
       ↑ 这些角色根本不存在！
```

AI 生成了不存在的角色名，严重破坏沉浸感。

### 3.2 修复方案

**修改文件**: `api/character_actor.py`

```python
class CharacterActor:
    
    # 角色名白名单
    VALID_CHARACTERS = {
        # ID: (中文名, 日文名, 别名)
        "aima": ("艾玛", "エマ", ["桜羽艾玛"]),
        "hiro": ("希罗", "ヒロ", ["寻", "二階堂希罗"]),
        "anan": ("安安", "アンアン", ["夏目安安"]),
        "noah": ("诺亚", "ノア", ["城ヶ崎诺亚"]),
        "reia": ("蕾雅", "レイア", ["蓮見蕾雅"]),
        "miria": ("米莉亚", "ミリア", ["佐伯米莉亚"]),
        "margo": ("玛尔戈", "マーゴ", ["玛格", "宝生玛尔戈"]),
        "nanoka": ("菜乃香", "ナノカ", ["黒部菜乃香"]),
        "arisa": ("爱丽莎", "アリサ", ["紫藤爱丽莎"]),
        "sherry": ("雪莉", "シェリー", ["橘雪莉"]),
        "hannah": ("汉娜", "ハンナ", ["遠野汉娜"]),
        "coco": ("可可", "ココ", ["沢渡可可"]),
        "meruru": ("梅露露", "メルル", ["冰上梅露露"]),
        "yuki": ("月代雪", "ユキ", ["典狱长"]),
    }
    
    # 所有有效名字的集合（用于快速查找）
    VALID_NAMES = set()
    for char_id, (cn, jp, aliases) in VALID_CHARACTERS.items():
        VALID_NAMES.add(cn)
        VALID_NAMES.add(jp)
        VALID_NAMES.update(aliases)
    
    def _validate_character_names(self, text: str) -> Tuple[bool, List[str]]:
        """检查文本中是否有无效角色名"""
        
        # 常见的幻觉角色名模式
        suspicious_patterns = [
            r'[美咲|亚美|千夏|真由|沙织|花子|樱|雪菜|彩香|美月|优子|理�的|惠|麻衣]',
            r'[ミサキ|アミ|チナツ|マユ|サオリ|ハナコ|サクラ|ユキナ|アヤカ|ミヅキ|ユウコ|メグミ|マイ]',
        ]
        
        import re
        invalid_names = []
        
        for pattern in suspicious_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match not in self.VALID_NAMES:
                    invalid_names.append(match)
                    
        return len(invalid_names) == 0, invalid_names
        
    def _fix_invalid_names(self, text: str, context_characters: List[str]) -> str:
        """替换无效角色名为上下文中的有效角色"""
        
        # 获取上下文角色的名字
        valid_replacements = []
        for char_id in context_characters:
            if char_id in self.VALID_CHARACTERS:
                cn_name = self.VALID_CHARACTERS[char_id][0]
                valid_replacements.append(cn_name)
                
        if not valid_replacements:
            valid_replacements = ["某人", "那个人", "她"]
            
        # 替换无效名字
        import re
        
        def replace_invalid(match):
            # 随机选一个有效名字或用代词
            import random
            return random.choice(valid_replacements + ["她", "那个人"])
            
        # 替换可疑名字
        suspicious_pattern = r'(美咲|亚美|千夏|真由|沙织|花子|雪菜|彩香|美月|优子|惠|麻衣)'
        text = re.sub(suspicious_pattern, replace_invalid, text)
        
        return text
        
    def generate_scene_dialogue(self, scene_plan: ScenePlan) -> ...:
        """生成对话时进行角色名验证"""
        
        outputs = self._generate_dialogue_internal(scene_plan)
        
        # 获取场景中的角色
        scene_characters = list(set(
            char for beat in scene_plan.beats for char in beat.characters
        ))
        
        # 验证和修复每个对话
        for output in outputs:
            for line in output.dialogue:
                # 检查说话者
                if line.speaker not in ["narrator", "player"] + list(self.VALID_CHARACTERS.keys()):
                    print(f"⚠️ 无效说话者: {line.speaker}")
                    line.speaker = "narrator"
                    
                # 检查对话内容
                is_valid, invalid_names = self._validate_character_names(line.text_cn)
                if not is_valid:
                    print(f"⚠️ 检测到幻觉角色名: {invalid_names}")
                    line.text_cn = self._fix_invalid_names(line.text_cn, scene_characters)
                    
        return outputs
```

### 3.3 Prompt 增强

**修改文件**: `prompts/character_actor_prompt.txt`

在 prompt 开头添加：

```
【重要：角色名白名单】

本游戏只有以下13名角色，绝对不要创造其他名字：

| ID | 中文名 | 日文名 |
|----|--------|--------|
| aima | 艾玛 | エマ |
| hiro | 希罗 | ヒロ |
| anan | 安安 | アンアン |
| noah | 诺亚 | ノア |
| reia | 蕾雅 | レイア |
| miria | 米莉亚 | ミリア |
| margo | 玛尔戈 | マーゴ |
| nanoka | 菜乃香 | ナノカ |
| arisa | 爱丽莎 | アリサ |
| sherry | 雪莉 | シェリー |
| hannah | 汉娜 | ハンナ |
| coco | 可可 | ココ |
| meruru | 梅露露 | メルル |

❌ 禁止：美咲、亚美、千夏、真由、沙织、花子等任何其他名字
❌ 禁止：创造新角色
✅ 只能：使用上表中的名字
✅ 如果要泛指他人：用「她」「那个人」「某人」「其他人」
```

### 3.4 验收标准

- [ ] Prompt 包含角色名白名单
- [ ] 对话生成后进行角色名验证
- [ ] 检测到幻觉名字时自动替换
- [ ] 无效说话者被修正为 narrator
- [ ] 不再出现"美咲""亚美"等幻觉名字

---

## 四、问题4：地点描写不匹配

### 4.1 问题描述

```
输入数字: 5  ← 选择走廊

[场景规划] 理性的囚笼
地点: 走廊  ← 地点正确

[hiro] ...在图书馆深处整理思绪...  ← 内容写的是图书馆！
```

DirectorPlanner 已经检测并警告，但 CharacterActor 生成的内容仍然不匹配。

### 4.2 修复方案

**修改文件**: `api/character_actor.py`

```python
class CharacterActor:
    
    # 地点关键词映射
    LOCATION_KEYWORDS = {
        "食堂": ["食堂", "餐桌", "饭菜", "餐具", "厨房", "用餐"],
        "牢房区": ["牢房", "铁栏", "牢门", "囚室", "床铺", "狭小"],
        "图书室": ["图书室", "书架", "书本", "阅读", "书页", "书籍"],
        "庭院": ["庭院", "阳光", "花草", "树木", "天空", "户外", "草地"],
        "走廊": ["走廊", "长廊", "通道", "脚步声", "回响", "窗户"],
    }
    
    # 地点排斥词（提到这些词说明地点错了）
    LOCATION_CONFLICTS = {
        "食堂": ["图书", "书架", "牢房", "铁栏", "庭院", "花草"],
        "牢房区": ["图书", "餐桌", "庭院", "阳光"],
        "图书室": ["餐桌", "饭菜", "铁栏", "牢房", "庭院"],
        "庭院": ["图书", "书架", "餐桌", "牢房", "走廊里"],
        "走廊": ["图书室", "书架", "餐桌", "牢房里", "庭院里"],
    }
    
    def _validate_location_consistency(self, text: str, target_location: str) -> Tuple[bool, List[str]]:
        """检查文本是否与目标地点一致"""
        
        conflicts = self.LOCATION_CONFLICTS.get(target_location, [])
        found_conflicts = []
        
        for conflict_word in conflicts:
            if conflict_word in text:
                found_conflicts.append(conflict_word)
                
        return len(found_conflicts) == 0, found_conflicts
        
    def _fix_location_references(self, text: str, wrong_location: str, correct_location: str) -> str:
        """替换错误的地点引用"""
        
        # 地点替换映射
        replacements = {
            "图书馆": {"食堂": "食堂", "牢房区": "牢房", "庭院": "庭院", "走廊": "走廊"},
            "图书室": {"食堂": "食堂", "牢房区": "牢房", "庭院": "庭院", "走廊": "走廊"},
            "书架": {"食堂": "餐桌", "牢房区": "墙壁", "庭院": "长椅", "走廊": "窗户"},
        }
        
        for wrong_word, location_map in replacements.items():
            if wrong_word in text and correct_location in location_map:
                text = text.replace(wrong_word, location_map[correct_location])
                
        return text
        
    def _build_story_prompt(self, scene_plan: ScenePlan) -> str:
        """构建 prompt，强调地点"""
        
        location = scene_plan.location
        location_keywords = self.LOCATION_KEYWORDS.get(location, [])
        
        prompt = f"""
# 场景演出任务

【重要：地点一致性】
当前地点是「{location}」，所有描写必须与此地点相关。

✅ 应该出现的元素：{', '.join(location_keywords)}
❌ 不应该出现：{', '.join(self.LOCATION_CONFLICTS.get(location, []))}

例如：
- 如果在「走廊」，不要写"图书馆深处"
- 如果在「食堂」，不要写"书架旁边"

## 场景信息
- 地点：{location}（必须一致！）
...
"""
        return prompt
```

### 4.3 验收标准

- [ ] Prompt 强调地点一致性
- [ ] 生成后检查地点冲突词
- [ ] 检测到冲突时自动替换或警告
- [ ] 走廊场景不再出现"图书馆"

---

## 五、问题5：固定事件太短

### 5.1 问题描述

```
[固定事件] 第一天午餐

  午餐时间到了，所有人聚集在食堂...

  简陋的饭菜被端上桌，气氛依然沉重。

[按Enter继续...]  ← 就这？2句话？
```

固定事件脚本太简陋，与AI生成的丰富场景形成巨大反差。

### 5.2 修复方案

**修改文件**: `events/fixed_events.yaml`

```yaml
day1_lunch:
  id: day1_lunch
  name: "第一天午餐"
  trigger:
    type: event_count
    count: 6
    period: "noon"
  priority: 90
  
  # 扩充脚本
  script:
    - speaker: narrator
      text: |
        午餐时间的铃声响起，回荡在走廊里。
        
        少女们陆续来到食堂，在长桌两侧坐下。
        简陋的餐盘被一一端上——米饭、味噌汤、几片腌菜。
        
        没有人说话。只有餐具轻轻碰撞的声音。
        
    - speaker: sherry
      text: "呜哇...这就是我们的午餐吗？好朴素啊..."
      emotion: disappointed
      
    - speaker: reia
      text: "至少还有东西吃，就别抱怨了。"
      emotion: calm
      
    - speaker: narrator
      text: |
        雪莉撅起嘴，但还是乖乖地拿起筷子。
        
        汉娜用优雅的姿势夹起一片腌菜，放入口中。
        她的表情没有变化，但你注意到她的筷子在微微颤抖。
        
    - speaker: hiro
      text: "......"
      emotion: defiant
      action: 一个人坐在角落，背对着所有人
      
    - speaker: narrator
      text: |
        希罗独自坐在长桌的尽头，和其他人保持着距离。
        她的背影看起来比早上更加僵硬。
        
        午餐时间就这样沉默地过去了。
        
  outcomes:
    all:
      stress: 2
      
  transitions:
    next_phase: free_time
    
# ─────────────────────────────────────────

day1_dinner:
  id: day1_dinner
  name: "第一天晚餐"
  trigger:
    type: event_count
    count: 9
    period: "evening"
  priority: 90
  
  script:
    - speaker: narrator
      text: |
        傍晚的铃声响起时，天边已经染上了橘红色。
        
        晚餐和午餐一样简朴——或许更简朴。
        但经过一天的紧张，没有人有心思抱怨。
        
    - speaker: miria
      text: "呼...总算能坐下来歇一歇了。"
      emotion: tired
      action: 重重地坐到椅子上
      
    - speaker: meruru
      text: "大、大家今天辛苦了..."
      emotion: nervous
      action: 小声地说，不敢看任何人的眼睛
      
    - speaker: narrator
      text: |
        梅露露的声音几乎被餐具的声音淹没。
        
        诺亚坐在窗边，望着渐暗的天空，筷子一直没有动。
        她的眼神似乎在追逐着什么远方的东西。
        
    - speaker: reia
      text: "诺亚，不吃点东西吗？"
      emotion: concerned
      
    - speaker: noah
      text: "...天空的颜色，很难画出来呢。"
      emotion: distant
      
    - speaker: narrator
      text: |
        蕾雅欲言又止，最终只是轻轻叹了口气。
        
        第一天即将结束。
        少女们的脸上写满了疲惫、不安，还有一丝——对明天的恐惧。
        
  outcomes:
    noah:
      stress: 3
    all:
      stress: 1
      
  transitions:
    next_phase: free_time
```

### 5.3 验收标准

- [ ] 午餐事件脚本至少10行
- [ ] 晚餐事件脚本至少10行
- [ ] 包含多角色互动
- [ ] 包含叙述描写（不只是对话）
- [ ] 与AI生成场景风格一致

---

## 六、实施顺序

```
优先级排序：
🔴 高优先级（影响可玩性）
🟡 中优先级（影响体验）
🟢 低优先级（锦上添花）
```

### Phase 1：紧急修复（1小时）

1. **幻觉角色名** 🔴
   - 在 Prompt 添加角色名白名单
   - 添加生成后验证

2. **空内容检测** 🔴
   - 添加 `_check_empty_beats()`
   - 添加回退内容生成

### Phase 2：核心修复（1小时）

3. **NPC 移动** 🔴
   - 在 `advance_time()` 添加移动逻辑
   - 30% 概率随机移动

4. **地点一致性** 🟡
   - Prompt 添加地点关键词
   - 添加冲突词检测

### Phase 3：内容完善（30分钟）

5. **固定事件扩充** 🟡
   - 重写 `day1_lunch` 脚本
   - 重写 `day1_dinner` 脚本

---

## 七、验收测试

```bash
# 测试脚本
python -c "
from api.character_actor import CharacterActor

actor = CharacterActor()

# 测试1: 幻觉角色名检测
test_text = '美咲总是试图调节气氛，亚美那种直接的态度'
is_valid, invalid = actor._validate_character_names(test_text)
assert not is_valid, '应该检测到幻觉名字'
print('✅ 幻觉角色名检测通过')

# 测试2: 地点一致性检测
test_text = '在图书馆深处整理思绪'
is_valid, conflicts = actor._validate_location_consistency(test_text, '走廊')
assert not is_valid, '应该检测到地点冲突'
print('✅ 地点一致性检测通过')

# 测试3: 角色名白名单
assert 'aima' in actor.VALID_CHARACTERS
assert '艾玛' in actor.VALID_NAMES
print('✅ 角色名白名单通过')

print('\\n全部测试通过!')
"
```

---

*任务版本：v10*
*创建日期：2024-12-24*
*修复问题：空内容、NPC不移动、幻觉角色名、地点不匹配、固定事件太短*
