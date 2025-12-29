#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Key 测试脚本
测试所有配置的 API Key 是否有效
"""

import anthropic
from config import API_KEYS, MODEL

def test_api_key(key, service_name):
    """测试单个 API Key"""
    print(f"\n{'='*60}")
    print(f"测试 {service_name} API Key")
    print(f"{'='*60}")

    if not key:
        print("❌ 未配置 API Key")
        return False

    # 显示 Key 的前10位和后4位
    masked_key = f"{key[:10]}...{key[-4:]}"
    print(f"Key: {masked_key}")
    print(f"模型: {MODEL}")

    try:
        client = anthropic.Anthropic(api_key=key)

        # 发送测试请求
        print("发送测试请求...")
        response = client.messages.create(
            model=MODEL,
            max_tokens=50,
            messages=[
                {"role": "user", "content": "请回复'测试成功'"}
            ]
        )

        result = response.content[0].text
        print(f"✅ API Key 有效！")
        print(f"响应: {result}")
        return True

    except anthropic.AuthenticationError as e:
        print(f"❌ 认证失败: API Key 无效")
        print(f"详细: {e}")
        return False

    except anthropic.PermissionDeniedError as e:
        print(f"❌ 权限拒绝: 可能是账户余额不足或模型访问受限")
        print(f"详细: {e}")
        return False

    except anthropic.RateLimitError as e:
        print(f"⚠️  速率限制: 请求过于频繁")
        print(f"详细: {e}")
        return False

    except Exception as e:
        print(f"❌ 未知错误: {type(e).__name__}")
        print(f"详细: {e}")
        return False

def main():
    print("="*60)
    print("  API Key 测试工具")
    print("="*60)

    results = {}

    for service, key in API_KEYS.items():
        results[service] = test_api_key(key, service.upper())

    # 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}")

    for service, success in results.items():
        status = "✅ 正常" if success else "❌ 失败"
        print(f"{service:12} : {status}")

    all_success = all(results.values())

    if all_success:
        print(f"\n✅ 所有 API Key 都正常工作！")
    else:
        print(f"\n⚠️  部分 API Key 有问题，请检查配置")
        print(f"\n建议:")
        print(f"1. 检查 API Key 是否正确复制（无多余空格）")
        print(f"2. 登录 https://console.anthropic.com/ 检查账户余额")
        print(f"3. 确认账户有权限使用模型: {MODEL}")
        print(f"4. 如果是新账户，可能需要等待激活")

if __name__ == "__main__":
    main()
