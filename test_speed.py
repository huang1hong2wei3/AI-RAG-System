import requests
import time

print("🚀 开始性能压测...")
url = "http://localhost:8000/chat"
times = []

# 模拟 5 次提问
for i in range(5):
    start = time.time()
    res = requests.post(url, json={'message': '怎么登入系统？'}).json()
    end = time.time()
    cost = end - start
    times.append(cost)
    print(f"第 {i+1} 次请求耗时: {cost:.3f} 秒")

print(f"\n📊 平均响应速度: {sum(times)/len(times):.3f} 秒")
