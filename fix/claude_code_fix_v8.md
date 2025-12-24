# Claude Code 任务：支持多个 API Key 配置 v8

## 目标

修改 `config.py`，支持从 `config_local.py` 读取多个 API Key，分散 rate limit。

---

## 任务 1：修改 `config.py`

将现有的单 Key 读取改为支持多 Key：

```python
# config.py - 项目配置文件
# 支持多个API Key和缓存机制

import os
from pathlib import Path

# ============================================
# API配置
# 优先级: 1. 环境变量 2. config_local.py 3. 报错
# ============================================

# 尝试从 config_local.py 读取（本地开发用，不上传到git）
_LOCAL_API_KEY = ""
_LOCAL_KEYS = {}

try:
    from config_local import ANTHROPIC_API_KEY as _LOCAL_API_KEY
except ImportError:
    pass

try:
    from config_local import ANTHROPIC_API_KEY_CHARACTER
    _LOCAL_KEYS["character"] = ANTHROPIC_API_KEY_CHARACTER
except ImportError:
    pass

try:
    from config_local import ANTHROPIC_API_KEY_DIRECTOR
    _LOCAL_KEYS["director"] = ANTHROPIC_API_KEY_DIRECTOR
except ImportError:
    pass

try:
    from config_local import ANTHROPIC_API_KEY_CONTROLLER
    _LOCAL_KEYS["controller"] = ANTHROPIC_API_KEY_CONTROLLER
except ImportError:
    pass

# 从环境变量读取，或使用本地配置
_DEFAULT_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "") or _LOCAL_API_KEY

API_KEYS = {
    "character": os.environ.get("ANTHROPIC_API_KEY_CHARACTER") or _LOCAL_KEYS.get("character") or _DEFAULT_API_KEY,
    "director": os.environ.get("ANTHROPIC_API_KEY_DIRECTOR") or _LOCAL_KEYS.get("director") or _DEFAULT_API_KEY,
    "controller": os.environ.get("ANTHROPIC_API_KEY_CONTROLLER") or _LOCAL_KEYS.get("controller") or _DEFAULT_API_KEY,
}

# 模型配置
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024

# ============================================
# 缓存设置
# ============================================
CACHE_TTL = 3600          # 1小时缓存
HEARTBEAT_INTERVAL = 3000  # 50分钟心跳（秒）
ENABLE_CACHE = True
ENABLE_HEARTBEAT = False   # 测试时关闭

# ============================================
# 路径配置
# ============================================
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "test_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================
# 兼容旧版
# ============================================
ANTHROPIC_API_KEY = API_KEYS.get("character", "")

def get_api_key(service_type="director"):
    """
    获取指定服务的API Key
    
    优先级:
    1. 环境变量 ANTHROPIC_API_KEY_<SERVICE>
    2. config_local.py 中的 ANTHROPIC_API_KEY_<SERVICE>
    3. 环境变量 ANTHROPIC_API_KEY
    4. config_local.py 中的 ANTHROPIC_API_KEY
    5. 抛出错误
    """
    key = API_KEYS.get(service_type) or API_KEYS.get("director") or _DEFAULT_API_KEY
    
    if not key:
        raise ValueError(
            f"\n{'='*60}\n"
            f"[错误] 未找到 API Key\n"
            f"{'='*60}\n"
            f"请通过以下方式之一设置 API Key:\n\n"
            f"方式1: 设置环境变量\n"
            f"  Windows: set ANTHROPIC_API_KEY=sk-ant-api03-xxx\n"
            f"  Linux/Mac: export ANTHROPIC_API_KEY=sk-ant-api03-xxx\n\n"
            f"方式2: 创建 config_local.py 文件\n"
            f"  在项目根目录创建 config_local.py，内容:\n"
            f"  ANTHROPIC_API_KEY = 'sk-ant-api03-xxx'\n\n"
            f"方式3: 多个 API Key（可选）\n"
            f"  ANTHROPIC_API_KEY_CHARACTER = 'sk-ant-api03-key1'\n"
            f"  ANTHROPIC_API_KEY_DIRECTOR = 'sk-ant-api03-key2'\n"
            f"  ANTHROPIC_API_KEY_CONTROLLER = 'sk-ant-api03-key3'\n"
            f"{'='*60}"
        )
    
    return key
```

---

## 任务 2：更新 `config_local.py.example`

```python
# config_local.py.example - 本地API配置模板
# 使用方法：复制此文件为 config_local.py，填入你的API Key
# 注意：config_local.py 不会上传到 git

# ============================================
# 方式1：单个 API Key（简单）
# ============================================
ANTHROPIC_API_KEY = "sk-ant-api03-你的API密钥"

# ============================================
# 方式2：多个 API Key（可选，分散 rate limit）
# ============================================
# 如果你有多个 API Key，可以分别配置：
# ANTHROPIC_API_KEY_CHARACTER = "sk-ant-api03-角色演出用key"
# ANTHROPIC_API_KEY_DIRECTOR = "sk-ant-api03-导演规划用key"
# ANTHROPIC_API_KEY_CONTROLLER = "sk-ant-api03-中控API用key"

# ============================================
# 说明
# ============================================
# - 如果只设置 ANTHROPIC_API_KEY，三个服务都会用这个 key
# - 如果设置了 ANTHROPIC_API_KEY_XXX，对应服务会优先使用专用 key
# - 优先级：专用 key > 通用 key
```

---

## 任务 3：创建用户的 `config_local.py`

用户需要手动创建此文件（或复制 example）：

```python
# config_local.py - 多个 API Key 配置

# 通用 key（备用）
ANTHROPIC_API_KEY = "sk-ant-api03-默认key"

# 专用 key（分散 rate limit）
ANTHROPIC_API_KEY_CHARACTER = "sk-ant-api03-key1"
ANTHROPIC_API_KEY_DIRECTOR = "sk-ant-api03-key2"
ANTHROPIC_API_KEY_CONTROLLER = "sk-ant-api03-key3"
```

---

## Key 使用对应

| 配置项 | 使用模块 | 说明 |
|--------|----------|------|
| `ANTHROPIC_API_KEY_CHARACTER` | `api/character_actor.py` | 角色演出层，生成对话 |
| `ANTHROPIC_API_KEY_DIRECTOR` | `api/director_planner.py` | 导演规划层，生成场景规划 |
| `ANTHROPIC_API_KEY_CONTROLLER` | 中控 API | NPC 位置更新（目前较少使用）|

---

## 验收标准

1. ✅ 单个 Key 配置仍然有效（向后兼容）
2. ✅ 多个 Key 配置生效，各服务使用对应 Key
3. ✅ 优先级正确：专用 Key > 通用 Key
4. ✅ 无 Key 时显示清晰错误信息

---

## 测试命令

```bash
# 测试配置是否生效
python -c "from config import API_KEYS; print('Character:', API_KEYS['character'][:25]); print('Director:', API_KEYS['director'][:25]); print('Controller:', API_KEYS['controller'][:25])"
```

---

## 文件修改清单

| 文件 | 操作 |
|------|------|
| `config.py` | 修改，支持多 Key 读取 |
| `config_local.py.example` | 更新，添加多 Key 示例 |

---

## 任务完成后

### 1. 更新 STATUS.md

```markdown
### 2025-12-22 - 多 API Key 支持 v8 ⭐ 最新

**修改文件**: `config.py`, `config_local.py.example`

**新增功能**: 支持从 config_local.py 读取多个 API Key

**配置方式**:
- 单 Key: 只设置 `ANTHROPIC_API_KEY`
- 多 Key: 分别设置 `ANTHROPIC_API_KEY_CHARACTER/DIRECTOR/CONTROLLER`

**优先级**: 专用 Key > 通用 Key > 环境变量
```

### 2. Git 提交

```bash
git add config.py config_local.py.example
git commit -m "feat: 支持多个 API Key 配置，分散 rate limit"
git push origin main
```
