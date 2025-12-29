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
# 注意: Claude 3.5 Sonnet 已升级为 Claude Sonnet 4
# 可用模型: claude-sonnet-4-20250514, claude-3-haiku-20240307
MODEL = "claude-sonnet-4-20250514"  # Claude Sonnet 4
MAX_TOKENS = 4096  # 增加token限制

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
