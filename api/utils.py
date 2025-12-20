# ============================================================================
# API 公共工具模块 (Utils)
# ============================================================================
# 职责：
# 1. 提供 JSON 解析和清理的公共函数
# 2. 处理 API 返回的各种 JSON 格式问题
# 3. 供 director_planner.py 和 character_actor.py 共同使用
# ============================================================================

import json
import re
from typing import Optional


def clean_json_response(text: str) -> str:
    """
    清理 API 返回的 JSON，处理各种常见问题

    处理内容：
    1. 移除 markdown 代码块 (```json ... ```)
    2. 用正则提取 JSON 对象（处理前后可能有的额外文字）
    3. 处理中文引号和标点
    4. 处理尾部逗号（JSON 不允许）
    """
    text = text.strip()

    # 1. 移除 markdown 代码块
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()

    # 2. 用正则提取 JSON 对象（处理前后可能有的额外文字）
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        text = json_match.group()

    # 3. 处理中文引号和标点
    text = text.replace('"', '"').replace('"', '"')  # 中文双引号
    text = text.replace(''', "'").replace(''', "'")  # 中文单引号
    text = text.replace('：', ':')  # 中文冒号

    # 4. 处理尾部逗号（JSON 不允许）
    # 处理 ,] 和 ,} 的情况
    text = re.sub(r',(\s*[\]\}])', r'\1', text)

    return text


def fix_truncated_json(text: str) -> str:
    """
    修复被截断的 JSON，尝试补全缺失的括号

    当 API 响应因 max_tokens 限制被截断时，JSON 可能不完整。
    此函数尝试检测并补全缺失的括号。
    """
    # 计算括号平衡
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')

    # 如果不平衡，尝试修复
    if open_braces != close_braces or open_brackets != close_brackets:
        print(f"[utils] 检测到 JSON 截断: {{ 有 {open_braces} 个, }} 有 {close_braces} 个, [ 有 {open_brackets} 个, ] 有 {close_brackets} 个")

        # 检查是否在字符串中间被截断（寻找未闭合的引号）
        text = text.rstrip()

        # 如果在字符串中截断，先尝试闭合字符串
        if text.count('"') % 2 != 0:
            text += '"'

        # 补全缺失的括号
        missing_brackets = open_brackets - close_brackets
        missing_braces = open_braces - close_braces

        # 按照 JSON 结构，通常是先闭合 ]，再闭合 }
        if missing_brackets > 0:
            text += ']' * missing_brackets
        if missing_braces > 0:
            text += '}' * missing_braces

        print(f"[utils] 已尝试补全 JSON 括号")

    return text


def parse_json_with_diagnostics(
    raw_text: str,
    context_name: str = "JSON",
    caller_name: str = "API"
) -> dict:
    """
    带诊断信息的 JSON 解析，三次尝试

    尝试顺序：
    1. 直接解析原始文本
    2. 清理后解析（clean_json_response）
    3. 修复截断后解析（fix_truncated_json）

    Args:
        raw_text: API 返回的原始文本
        context_name: 上下文名称，用于错误日志（如 "场景规划"、"对话生成"）
        caller_name: 调用者名称，用于日志前缀（如 "DirectorPlanner"、"CharacterActor"）

    Returns:
        解析后的字典

    Raises:
        json.JSONDecodeError: 如果所有尝试都失败
    """
    # 第一次尝试：直接解析
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass  # 继续尝试

    # 第二次尝试：清理后解析
    cleaned_text = clean_json_response(raw_text)
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        pass  # 继续尝试

    # 第三次尝试：修复截断后解析
    fixed_text = fix_truncated_json(cleaned_text)
    try:
        return json.loads(fixed_text)
    except json.JSONDecodeError as e:
        # 所有尝试都失败，打印详细诊断信息
        print(f"\n[{caller_name}] ❌ {context_name} 解析失败")
        print(f"[{caller_name}] 错误类型: {e.msg}")
        print(f"[{caller_name}] 错误位置: 第 {e.lineno} 行, 第 {e.colno} 列 (字符位置 {e.pos})")

        # 显示错误位置附近的文本
        text = fixed_text
        start = max(0, e.pos - 50)
        end = min(len(text), e.pos + 50)
        context_text = text[start:end]

        # 标记错误位置
        error_marker_pos = e.pos - start
        print(f"[{caller_name}] 错误附近内容:")
        print(f"  ...{context_text}...")
        print(f"  {' ' * (error_marker_pos + 3)}^ 错误在这里")

        # 打印原始响应的前500个字符
        print(f"\n[{caller_name}] 原始响应前500字符:")
        print(raw_text[:500])
        if len(raw_text) > 500:
            print(f"... (共 {len(raw_text)} 字符)")

        raise
