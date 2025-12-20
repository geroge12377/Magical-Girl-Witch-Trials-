# config.py - 项目配置文件
# 支持多个API Key和缓存机制

from pathlib import Path

# ============================================
# API配置 - 填入你的API Key
# ============================================
API_KEYS = {
    "",   # 角色API用
    "",    # 导演API用
    "controller": ""   # 中控API用
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
    """获取指定服务的API Key"""
    return API_KEYS.get(service_type, API_KEYS["director"])
