# Claude Code 任务：修复 API 认证错误 v7

## 问题描述

运行时出现 API 认证错误：

```
[CharacterActor] API 调用失败: TypeError: "Could not resolve authentication method. 
Expected either api_key or auth_token to be set. Or for one of the `X-Api-Key` or 
`Authorization` headers to be explicitly omitted"
```

**原因**：`character_actor.py` 在调用 Anthropic API 时没有正确传入 `api_key`。

---

## 任务 1：检查并修复 `api/character_actor.py`

### 1.1 检查 API 客户端初始化

找到 API 调用的位置，确保正确传入 api_key：

```python
# 错误写法（可能的情况）
client = anthropic.Anthropic()  # 没有传 api_key

# 正确写法
from config import get_api_key, API_KEYS

class CharacterActor:
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.api_key = get_api_key("anthropic")  # 或 API_KEYS.get("anthropic")
        # ... 其他初始化 ...
    
    def _call_api(self, prompt: str, system_prompt: str = None) -> str:
        """调用 API"""
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.api_key)  # ← 关键：传入 api_key
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # 或从 config 读取
            max_tokens=4096,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
```

### 1.2 检查所有 API 调用位置

在 `character_actor.py` 中搜索以下关键词，确保都正确传入了 api_key：
- `anthropic.Anthropic(`
- `client.messages.create(`
- `requests.post(` (如果使用 requests)

### 1.3 常见错误模式

```python
# 错误 1：没有传 api_key
client = anthropic.Anthropic()

# 错误 2：api_key 变量名错误
client = anthropic.Anthropic(api_key=self.key)  # 应该是 self.api_key

# 错误 3：从环境变量读取但没设置
client = anthropic.Anthropic()  # 期望从 ANTHROPIC_API_KEY 环境变量读取

# 正确写法
client = anthropic.Anthropic(api_key=self.api_key)
```

---

## 任务 2：检查 `config.py` 配置

### 2.1 确认 API_KEYS 存在

```python
# config.py 应该有类似这样的配置
API_KEYS = {
    "anthropic": "sk-ant-api03-xxxxx",  # 你的 API key
    # 或者
    "default": "sk-ant-api03-xxxxx",
}

def get_api_key(service_type: str = "anthropic") -> str:
    """获取指定服务的 API Key"""
    return API_KEYS.get(service_type) or API_KEYS.get("default")
```

### 2.2 检查 API key 是否有效

```python
# 可以添加一个简单的验证
def get_api_key(service_type: str = "anthropic") -> str:
    key = API_KEYS.get(service_type) or API_KEYS.get("default")
    if not key:
        raise ValueError(f"API key not found for service: {service_type}")
    return key
```

---

## 任务 3：统一 API 调用方式

### 3.1 创建公共 API 调用方法（可选）

如果多个模块都需要调用 API，可以在 `api/utils.py` 中创建公共方法：

```python
# api/utils.py

import anthropic
from config import get_api_key, MODEL, MAX_TOKENS

def call_claude_api(
    prompt: str, 
    system_prompt: str = None,
    max_tokens: int = None
) -> str:
    """
    统一的 Claude API 调用方法
    
    Args:
        prompt: 用户提示
        system_prompt: 系统提示（可选）
        max_tokens: 最大 token 数（可选，默认使用 config 中的值）
    
    Returns:
        API 响应文本
    """
    api_key = get_api_key("anthropic")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens or MAX_TOKENS,
        system=system_prompt or "",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text
```

### 3.2 在 character_actor.py 中使用

```python
from .utils import call_claude_api

class CharacterActor:
    def _generate_dialogue(self, prompt: str) -> str:
        return call_claude_api(prompt, system_prompt=self.system_prompt)
```

---

## 任务 4：添加错误处理和日志

```python
def _call_api(self, prompt: str, system_prompt: str = None) -> str:
    """调用 API（带错误处理）"""
    try:
        if not self.api_key:
            raise ValueError("API key is not configured")
        
        client = anthropic.Anthropic(api_key=self.api_key)
        
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
        
    except anthropic.AuthenticationError as e:
        print(f"[CharacterActor] API 认证失败: {e}")
        raise
    except anthropic.APIError as e:
        print(f"[CharacterActor] API 调用错误: {e}")
        raise
    except Exception as e:
        print(f"[CharacterActor] 未知错误: {type(e).__name__}: {e}")
        raise
```

---

## 快速修复步骤

1. 打开 `api/character_actor.py`
2. 找到 `anthropic.Anthropic(` 的位置
3. 确保传入了 `api_key=self.api_key`
4. 确保 `__init__` 中有 `self.api_key = get_api_key("anthropic")`
5. 确保 `from config import get_api_key` 在文件顶部

---

## 验收标准

1. ✅ 运行 `python game_loop_v3.py` 不再出现认证错误
2. ✅ API 调用成功返回对话内容
3. ✅ 预选回应生成成功

---

## 文件修改清单

| 文件 | 操作 |
|------|------|
| `api/character_actor.py` | 修复 API key 传递 |
| `config.py` | 确认 API_KEYS 配置正确（如需要）|
| `api/utils.py` | 可选：添加公共 API 调用方法 |

---

## 任务完成后

### 1. 测试验证

```bash
python game_loop_v3.py
```

确认不再出现认证错误。

### 2. 更新 STATUS.md（如果是代码bug而非配置问题）

```markdown
### 2025-12-22 - API 认证错误修复 v7

**修改文件**: `api/character_actor.py`

**问题**: API 调用时未传入 api_key，导致认证失败

**修复**: 在 Anthropic client 初始化时正确传入 api_key
```

### 3. Git 提交

```bash
git add api/character_actor.py
git commit -m "fix: 修复 CharacterActor API 认证错误"
git push origin main
```
