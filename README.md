# 魔法少女的魔女审判 - API测试项目

## 目录结构

```
test_project/
├── config.py                # API配置（需要填写API Key）
├── test_api.py              # 测试脚本
├── README.md                # 本文件
├── characters/
│   └── aima/
│       ├── core.yaml        # 角色核心信息
│       ├── personality.yaml # 性格档案
│       ├── speech.yaml      # 语言模式
│       └── relationships.yaml # 人际关系
└── world_state/
    ├── current_day.json     # 当前时间状态
    ├── character_states.json # 13人状态
    └── events_log.json      # 事件日志
```

## 使用方法

### 1. 安装依赖

```bash
pip install anthropic pyyaml
```

### 2. 配置API Key

编辑 `config.py`，将 `你的API_KEY_填在这里` 替换为你的Anthropic API Key：

```python
ANTHROPIC_API_KEY = "sk-ant-xxxxx"
```

### 3. 运行测试

```bash
python test_api.py
```

### 4. 预期输出

脚本会：
1. 加载艾玛的角色数据
2. 加载世界状态
3. 构建prompt发送给Claude API
4. 显示API返回的JSON结果

## 测试场景

默认测试场景：
- 角色：艾玛（aima）
- 位置：庭院
- 玩家输入："你还好吗？看起来有点心事。"

## 修改测试

编辑 `test_api.py` 中的 `main()` 函数：

```python
character_id = "aima"  # 可改为其他角色
player_input = "你还好吗？看起来有点心事。"  # 可改为其他输入
```

## 注意事项

- 需要有效的Anthropic API Key
- 默认使用 claude-sonnet-4-20250514 模型
- 每次调用会消耗API额度
