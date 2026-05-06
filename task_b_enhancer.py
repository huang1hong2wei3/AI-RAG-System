import requests
import time
import json
from functools import lru_cache
from typing import List,Dict
import os




#==========1.查询重写========
def rewrite_query(original_query: str) ->str:
    url="https://api.deepseek.com/chat/completions"
    headers={
        "Authorization":f"Bearer {__import__('os').getenv('DEEPSEEK_API_KEY','')}",
         "Content-Type": "application/json"
    }
    prompt=f"""你是查询重写助手.请将用户的口语化问题改为更专业,更完整的表述,以便在知识库查询
要求:
1.保持原意
2.使用正式,完整的句子
3.不要回答问题,只输出改写后的问题
用户问题:{original_query}
改写后:"""
    payload={
        "model":"deepseek-chat",
        "messages":[{"role":"user","content":prompt}],
        "temperature": 0.3
    }
    try:
        response=requests.post(url,headers=headers,json=payload,timeout=10)
        response.raise_for_status()
        rewritten=response.json()["choices"][0]["message"]["content"].strip()
        print(f"原始问题: {original_query}")
        print(f"改写后的问题: {rewritten}")
        return rewritten
    except Exception as e:
        print(f"重写失败: {e}")
        return original_query
#==========2.检索缓存========
@lru_cache(maxsize=100)
def cached_hybrid_search(query: str, limit: int = 3) -> str:
    url="http://localhost:8000/chat"
    payload={"message":query}
    try:
        response=requests.post(url,json=payload,timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return json.dumps({"error":str(e)})
def clear_case():
    cached_hybrid_search.cache_clear()
    print("缓存已清除")
def benchmark_search():
    test_query="天网计划谁主导?"
    print("\n" + "=" * 50)
    print("⚡ 性能测试：缓存效果对比")
    print("=" * 50)
    # 第一次请求（无缓存）
    print("\n📝 第一次请求（无缓存）...")
    start = time.time()
    cached_hybrid_search(test_query)
    elapsed_1 = time.time() - start
    print(f"⏱️ 耗时：{elapsed_1:.2f} 秒")

    # 第二次请求（命中缓存）
    print("\n📝 第二次请求（命中缓存）...")
    start = time.time()
    cached_hybrid_search(test_query)
    elapsed_2 = time.time() - start
    print(f"⏱️ 耗时：{elapsed_2:.2f} 秒")

    if elapsed_1 > 0:
        speedup = elapsed_1 / elapsed_2
        print(f"\n🚀 性能提升：{speedup:.1f}x")
    return elapsed_1, elapsed_2


def test_streaming():
    """测试流式输出功能"""
    print("\n" + "=" * 50)
    print("🌊 流式输出测试")
    print("=" * 50)

    url = "http://localhost:8000/chat/stream"
    payload = {"message": "用一句话介绍天网计划"}

    print("\n🤖 AI 正在逐字输出：")
    print("-" * 50)
    try:
        with requests.post(url, json=payload, stream=True, timeout=30) as response:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data = line_str[6:]
                        if data == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get('content', '')
                            print(content, end='', flush=True)
                        except:
                            continue
        print("\n" + "-" * 50)
        print("✅ 流式输出完成")
    except Exception as e:
        print(f"\n❌ 流式输出失败：{e}")

    # ================ 5. 综合测试入口 ================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 任务 B：智能检索增强管道")
    print("=" * 50)

        # 测试 1：查询重写
    print("\n📝 测试 1：查询重写")
    print("-" * 50)
    original = "天网谁搞的？"
    rewritten = rewrite_query(original)

        # 测试 2：缓存性能
    print("\n📝 测试 2：缓存性能")
    print("-" * 50)
    benchmark_search()

        # 测试 3：流式输出
    print("\n📝 测试 3：流式输出")
    print("-" * 50)
    test_streaming()

    print("\n" + "=" * 50)
    print("✅ 任务 B 所有测试完成！")
    print("=" * 50)



























