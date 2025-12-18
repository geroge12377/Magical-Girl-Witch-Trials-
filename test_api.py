# test_api.py - 角色API测试脚本
import anthropic
import json
import yaml
from pathlib import Path
from config import get_api_key, MODEL, MAX_TOKENS
ANTHROPIC_API_KEY = get_api_key("character")

def load_yaml(filepath):
    """加载YAML文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_json(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_template(filepath):
    """加载模板文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def build_character_prompt(character_id, player_input):
    """构建角色API的prompt"""
    
    # 加载角色数据
    char_path = Path(f"characters/{character_id}")
    core = load_yaml(char_path / "core.yaml")
    personality = load_yaml(char_path / "personality.yaml")
    speech = load_yaml(char_path / "speech.yaml")
    
    # 加载世界状态
    world_path = Path("world_state")
    character_states = load_json(world_path / "character_states.json")
    current_day = load_json(world_path / "current_day.json")
    
    # 获取当前角色状态
    state = character_states.get(character_id, {})
    
    # 构建prompt
    prompt = f"""【身份】
你是{core['name']['zh']}（{character_id}），游戏「魔法少女的魔女审判」中的角色。

【核心性格】
{personality['versions']['simple']}

【说话方式】
第一人称：{speech['first_person']}
口癖：{', '.join(speech['verbal_tics'][:3])}
{speech['tone_by_emotion'].get('nervous', '')}

【当前状态】
- 压力值：{state.get('stress', 50)}/100
- 疯狂值：{state.get('madness', 10)}/100
- 当前情绪：{state.get('emotion', 'calm')}
- 所在位置：{state.get('location', '未知')}
- 当前行为：{state.get('action', '无')}
- 当前时间：第{current_day.get('day', 1)}天 {current_day.get('time', '10:00')}

【玩家输入】
{player_input}

【任务】
根据玩家输入生成你的回复，并判断情绪和数值变化。

【对话规则】
1. 严格按照你的性格和说话方式回复
2. 考虑当前情绪、压力值对语气的影响
3. 使用{speech['first_person']}作为第一人称
4. 适当使用口癖

【输出要求】
严格按照JSON格式输出，不要有任何其他内容：
{{
  "text_cn": "中文回复（50-200字）",
  "text_jp": "日语回复",
  "emotion": "情绪标签（只能用：happy/sad/angry/scared/nervous/calm/surprised/conflicted）",
  "internal_thought": "内心独白（玩家不可见）",
  "status_changes": {{
    "stress": 变化值整数,
    "affection": 变化值整数,
    "madness": 变化值整数,
    "reason": "变化原因"
  }},
  "new_memory": "新记忆（如果有）"
}}"""
    
    return prompt

def call_character_api(character_id, player_input):
    """调用角色API"""
    
    # 构建prompt
    prompt = build_character_prompt(character_id, player_input)
    
    print("=" * 50)
    print("【发送的Prompt】")
    print("=" * 50)
    print(prompt)
    print("=" * 50)
    
    # 调用API
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # 获取返回内容
    result_text = response.content[0].text
    
    print("\n【API原始返回】")
    print("=" * 50)
    print(result_text)
    print("=" * 50)
    
    # 尝试解析JSON
    try:
        clean_text = result_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        clean_text = clean_text.replace(': +', ': ')  # 去掉+号
        
        result = json.loads(clean_text)
        print("\n【解析成功】")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    except json.JSONDecodeError as e:
        print(f"\n【JSON解析失败】: {e}")
        return None

def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("魔法少女的魔女审判 - 角色API测试")
    print("=" * 50)
    
    # 测试参数
    character_id = "aima"
    player_input = "你还好吗？看起来有点心事。"
    
    print(f"\n测试角色: {character_id}")
    print(f"玩家输入: {player_input}")
    print()
    
    # 调用API
    result = call_character_api(character_id, player_input)
    
    if result:
        print("\n" + "=" * 50)
        print("【测试结果】")
        print("=" * 50)
        print(f"角色回复(中): {result.get('text_cn', 'N/A')}")
        print(f"角色回复(日): {result.get('text_jp', 'N/A')}")
        print(f"情绪变化: {result.get('emotion', 'N/A')}")
        print(f"数值变化: {result.get('status_changes', {})}")
        print("=" * 50)

if __name__ == "__main__":
    main()
