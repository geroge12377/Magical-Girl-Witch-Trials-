# test_director_api.py - 导演API测试脚本
# 支持Prompt Caching和心跳机制

import anthropic
import json
import yaml
import time
import threading
from pathlib import Path
from datetime import datetime
from config import (
    get_api_key, MODEL, MAX_TOKENS,
    CACHE_TTL, HEARTBEAT_INTERVAL,
    ENABLE_CACHE, ENABLE_HEARTBEAT,
    OUTPUT_DIR
)

def load_yaml(filepath):
    """加载YAML文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_json(filepath):
    """加载JSON文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_character_data(character_id):
    """加载角色完整数据（从多个yaml合并）"""
    char_path = Path(f"characters/{character_id}")
    
    core = load_yaml(char_path / "core.yaml")
    personality = load_yaml(char_path / "personality.yaml")
    speech = load_yaml(char_path / "speech.yaml")
    
    return {
        "core": core,
        "personality": personality,
        "speech": speech
    }

def build_system_prompt(char_data):
    """构建系统prompt（可缓存部分）"""
    core = char_data["core"]
    personality = char_data["personality"]
    speech = char_data["speech"]
    
    system_prompt = f"""你是导演AI，负责为视觉小说游戏「魔法少女的魔女审判」生成场景对话和玩家选项。

【角色档案 - {core['name']['zh']}】
姓名: {core['name']['zh']} ({core['name']['ja']})
年龄: {core['age']}岁
囚人番号: {core['prisoner_number']}

【性格特征】
{personality['versions']['simple']}

【说话方式】
第一人称: {speech['first_person']}
口癖: {', '.join(speech['verbal_tics'][:4])}
语气特点: {speech['tone_by_emotion']['nervous']}

【示例台词】
开心时: {speech['example_lines']['happy']['zh']}
紧张时: {speech['example_lines']['nervous']['zh']}

【输出格式要求】
严格按照以下JSON格式输出，不要包含markdown代码块标记：

{{
  "dialogue": [
    {{"speaker": "aima", "text_cn": "中文对话", "text_jp": "日文对话", "emotion": "情绪"}}
  ],
  "choice_point": {{
    "prompt_cn": "你要怎么回应？",
    "options": [
      {{"id": "A", "text_cn": "选项A", "leads_to_badend": false}},
      {{"id": "B", "text_cn": "选项B", "leads_to_badend": false}},
      {{"id": "C", "text_cn": "选项C（危险选项）", "leads_to_badend": true}}
    ]
  }},
  "foreshadowing_planted": [],
  "recommended_bgm": "音乐名称"
}}

【创作要求】
1. 对话要符合角色性格，使用{speech['first_person']}作为第一人称
2. 适当使用角色的口癖
3. 情绪标签只能用: happy/sad/angry/scared/nervous/calm/surprised/conflicted
4. 选项要有性格差异，C选项应该是会冒犯角色或不当行为
5. 对话3-5句"""

    return system_prompt

def build_user_prompt(scene_info, character_state):
    """构建用户prompt（场景特定部分）"""
    user_prompt = f"""【当前场景】
地点: {scene_info['location']}
时间: 第{scene_info['day']}天 {scene_info['time']}
氛围: {scene_info.get('atmosphere', '平静')}

【角色当前状态】
压力值: {character_state['stress']}/100
疯狂值: {character_state['madness']}/100
情绪: {character_state['emotion']}
当前行为: {character_state['action']}

【任务】
玩家在{scene_info['location']}遇到了角色。请生成：
1. 角色注意到玩家后的3-5句对话
2. 玩家的3个回应选项（A/B正常，C导向Bad End）
3. 推荐的背景音乐

请立即输出JSON。"""

    return user_prompt

class DirectorAPITester:
    """导演API测试器"""
    
    def __init__(self):
        self.api_key = get_api_key("director")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.heartbeat_active = False
        self.heartbeat_thread = None
        self.cache_stats = {
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "input_tokens": 0
        }
    
    def call_api(self, system_prompt, user_prompt, use_cache=True):
        """调用API（支持缓存）"""
        try:
            if use_cache and ENABLE_CACHE:
                # 使用prompt caching
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ],
                    messages=[{"role": "user", "content": user_prompt}]
                )
            else:
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
            
            # 更新缓存统计
            usage = response.usage
            if hasattr(usage, 'cache_creation_input_tokens'):
                self.cache_stats['cache_creation_input_tokens'] = usage.cache_creation_input_tokens or 0
            if hasattr(usage, 'cache_read_input_tokens'):
                self.cache_stats['cache_read_input_tokens'] = usage.cache_read_input_tokens or 0
            self.cache_stats['input_tokens'] = usage.input_tokens
            
            return response.content[0].text
        
        except Exception as e:
            print(f"❌ API调用失败: {e}")
            return None
    
    def send_heartbeat(self, system_prompt):
        """发送心跳包"""
        try:
            print(f"💓 发送心跳包 ({datetime.now().strftime('%H:%M:%S')})")
            self.client.messages.create(
                model=MODEL,
                max_tokens=10,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }],
                messages=[{"role": "user", "content": "ping"}]
            )
            print("✅ 心跳包发送成功")
        except Exception as e:
            print(f"⚠️ 心跳包失败: {e}")
    
    def start_heartbeat(self, system_prompt):
        """启动心跳线程"""
        if not ENABLE_HEARTBEAT:
            return
        
        def heartbeat_loop():
            while self.heartbeat_active:
                time.sleep(HEARTBEAT_INTERVAL)
                if self.heartbeat_active:
                    self.send_heartbeat(system_prompt)
        
        self.heartbeat_active = True
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        print(f"💓 心跳线程已启动（间隔: {HEARTBEAT_INTERVAL}秒）")
    
    def stop_heartbeat(self):
        """停止心跳"""
        self.heartbeat_active = False
        print("💓 心跳线程已停止")
    
    def parse_response(self, response_text):
        """解析响应"""
        try:
            clean = response_text.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            if clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            clean = clean.replace(': +', ': ')  # 去掉+号
            
            return json.loads(clean)
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return None
    
    def display_result(self, result):
        """美化显示结果"""
        print("\n" + "="*60)
        print("【生成的对话剧本】")
        print("="*60)
        
        for i, line in enumerate(result['dialogue'], 1):
            print(f"\n{i}. {line['speaker']} [{line['emotion']}]")
            print(f"   中: {line['text_cn']}")
            print(f"   日: {line['text_jp']}")
        
        print("\n" + "="*60)
        print("【玩家选项】")
        print("="*60)
        print(f"\n{result['choice_point']['prompt_cn']}")
        
        for opt in result['choice_point']['options']:
            mark = " ⚠️[BAD END]" if opt['leads_to_badend'] else ""
            print(f"\n{opt['id']}. {opt['text_cn']}{mark}")
        
        print(f"\n🎵 推荐BGM: {result['recommended_bgm']}")
        print("="*60)
    
    def display_cache_stats(self):
        """显示缓存统计"""
        print("\n【缓存统计】")
        print(f"缓存创建token: {self.cache_stats['cache_creation_input_tokens']}")
        print(f"缓存读取token: {self.cache_stats['cache_read_input_tokens']}")
        print(f"输入token: {self.cache_stats['input_tokens']}")
        
        if self.cache_stats['cache_read_input_tokens'] > 0:
            saved = self.cache_stats['cache_read_input_tokens']
            print(f"💰 节省token: {saved}")

def main():
    """主函数"""
    print("="*60)
    print("导演API测试 - 支持Prompt Caching")
    print("="*60)
    
    # 1. 加载数据
    print("\n📚 加载数据...")
    char_data = load_character_data("aima")
    character_states = load_json("world_state/character_states.json")
    current_day = load_json("world_state/current_day.json")
    
    aima_state = character_states["aima"]
    scene_info = {
        "location": "庭院",
        "day": current_day["day"],
        "time": current_day["time"],
        "atmosphere": current_day.get("atmosphere", "平静")
    }
    
    print(f"   场景: {scene_info['location']} - 第{scene_info['day']}天 {scene_info['time']}")
    print(f"   角色: {char_data['core']['name']['zh']} (stress:{aima_state['stress']}, emotion:{aima_state['emotion']})")
    
    # 2. 构建prompts
    print("\n🔧 构建prompts...")
    system_prompt = build_system_prompt(char_data)
    user_prompt = build_user_prompt(scene_info, aima_state)
    
    print("\n【System Prompt预览】")
    print(system_prompt[:500] + "...")
    
    print("\n【User Prompt】")
    print(user_prompt)
    
    # 3. 调用API
    tester = DirectorAPITester()
    
    if ENABLE_HEARTBEAT:
        tester.start_heartbeat(system_prompt)
    
    print("\n🚀 调用导演API...")
    response = tester.call_api(system_prompt, user_prompt, use_cache=ENABLE_CACHE)
    
    if not response:
        print("❌ API调用失败")
        return
    
    print("\n【API原始返回】")
    print(response)
    
    # 4. 解析结果
    result = tester.parse_response(response)
    
    if result:
        print("\n✅ 解析成功")
        tester.display_result(result)
        tester.display_cache_stats()
        
        # 保存结果
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_DIR / "director_result.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 结果已保存到: {OUTPUT_DIR / 'director_result.json'}")
    
    tester.stop_heartbeat()
    print("\n✅ 测试完成！")

if __name__ == "__main__":
    main()
