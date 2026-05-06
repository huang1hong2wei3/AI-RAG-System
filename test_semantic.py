import os
# 设置国内镜像，加速模型下载
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from sentence_transformers import SentenceTransformer
import numpy as np

print("1. 正在加载 AI 语义模型 (第一次运行需要下载，请稍等)...")
# 这是一个支持中文的多语言模型
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# 模拟你数据库里的内容
documents = [
    "本项目的管理员密码是 Admin@888",
    "PythonProject1 的核心目标是构建一个 RAG 系统",
    "该项目使用 FastAPI 作为后端框架"
]

# 你的搜索词（注意：这里没有“密码”两个字！）
query = "怎么登入系统？"

print("2. 正在将文字转化为数学向量...")
# 把所有句子变成向量（一串数字）
doc_vectors = model.encode(documents)
query_vector = model.encode([query])[0]

print("3. 计算语义相似度...")
# 计算搜索词和每句话的距离（余弦相似度）
similarities = np.dot(doc_vectors, query_vector) / (np.linalg.norm(doc_vectors, axis=1) * np.linalg.norm(query_vector))

# 找出最像的那一句
best_match_idx = np.argmax(similarities)

print("\n🎉 结果展示：")
print(f"用户搜索：'{query}'")
print(f"AI 找到的内容：'{documents[best_match_idx]}'")
print(f"匹配得分：{similarities[best_match_idx]:.4f}")
