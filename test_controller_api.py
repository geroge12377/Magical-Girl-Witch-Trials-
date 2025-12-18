"""
中控API测试 - 管理13人位置和行为，生成动态事件
"""

import anthropic
import json
from pathlib import Path
from config import get_api_key, MODEL, MAX_TOKENS, ENABLE_CACHE, OUTPUT_DIR


def load_json(file_path):
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def clean_json_response(text):
    """清理API返回的JSON文本"""
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.replace(': +', ': ')
    return text.strip()


def build_controller_prompt(current_day, character_states):
    """构建中控API的prompt"""
    
    # 格式化当前13人状态
    chars_info = []
    for char_id, state in character_states.items():
        chars_info.append(f"- {char_id}: 位置={state['location']}, 行为={state['action']}, 情绪={state['emotion']}, 压力={state['stress']}")
    
    chars_text = '\n'.join(chars_info)
    
    prompt = f"""你是中控AI，负责调度13名魔法少女的位置和行为。

【当前时间】
第{current_day['day']}天 {current_day['time']}
阶段: {current_day['phase']}

【可用位置】
庭院、食堂、图书室、走廊、牢房区

【当前13人状态】
{chars_text}

【任务】
规划下一个10分钟的位置和行为：
1. 为每个角色指定位置和行为
2. 行为需符合角色当前情绪和压力
3. 设计1-2个动态事件
4. 标注是否可互动(can_interact)

【输出格式】
严格JSON，不要markdown标记：

{{
  "world_state": {{
    "aima": {{
      "location": "庭院",
      "action": "独自坐在长椅上",
      "purpose": "躲避他人",
      "can_interact": true
    }},
    "hiro": {{ ... }},
    // ...13人完整
  }},
  "dynamic_events": [
    {{
      "trigger_time": 5,
      "event": "事件描述",
      "condition": "触发条件"
    }}
  ]
}}

必须包含全部13人：aima, hiro, melulu, hanna, noah, leya, koyuki, seira, maki, rena, yuki, tsubasa, mira"""

    return prompt


def main():
    print("=" * 60)
    print("中控API测试 - 13人位置调度")
    print("=" * 60)
    
    # 加载数据
    print("\n📚 加载数据...")
    current_day = load_json("world_state/current_day.json")
    character_states = load_json("world_state/character_states.json")
    
    print(f"   时间: 第{current_day['day']}天 {current_day['time']}")
    print(f"   角色数: {len(character_states)}")
    
    # 构建prompt
    prompt = build_controller_prompt(current_day, character_states)
    print(f"\n🔧 Prompt构建完成 ({len(prompt)}字符)")
    
    # 调用API
    print("\n🚀 调用中控API...")
    api_key = get_api_key("controller")
    client = anthropic.Anthropic(api_key=api_key)
    
    if ENABLE_CACHE:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=[{
                "type": "text",
                "text": "你是游戏中控AI，负责管理角色位置和动态事件。",
                "cache_control": {"type": "ephemeral"}
            }],
            messages=[{"role": "user", "content": prompt}]
        )
    else:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system="你是游戏中控AI，负责管理角色位置和动态事件。",
            messages=[{"role": "user", "content": prompt}]
        )
    
    result_text = response.content[0].text
    
    print("\n【API原始返回】")
    print(result_text[:500] + "..." if len(result_text) > 500 else result_text)
    
    # 解析
    clean_text = clean_json_response(result_text)
    try:
        result = json.loads(clean_text)
        print("\n✅ 解析成功")
        
        # 显示位置分布
        print("\n" + "=" * 60)
        print("📍 13人位置分布")
        print("=" * 60)
        
        locations = {}
        for char_id, data in result["world_state"].items():
            loc = data["location"]
            if loc not in locations:
                locations[loc] = []
            locations[loc].append((char_id, data))
        
        for loc, chars in locations.items():
            print(f"\n【{loc}】({len(chars)}人)")
            for char_id, data in chars:
                mark = "✓" if data["can_interact"] else "✗"
                print(f"  {mark} {char_id}: {data['action']}")
        
        # 显示动态事件
        if result.get("dynamic_events"):
            print("\n" + "=" * 60)
            print("⚡ 动态事件")
            print("=" * 60)
            for evt in result["dynamic_events"]:
                print(f"\n+{evt['trigger_time']}分钟: {evt['event']}")
                print(f"  条件: {evt['condition']}")
        
        # 保存
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_DIR / "controller_result.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 已保存: {OUTPUT_DIR / 'controller_result.json'}")
        
        # 缓存统计
        usage = response.usage
        print(f"\n【Token统计】")
        print(f"输入: {usage.input_tokens}")
        print(f"输出: {usage.output_tokens}")
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON解析失败: {e}")
    
    print("\n✅ 测试完成！")


if __name__ == "__main__":
    main()
