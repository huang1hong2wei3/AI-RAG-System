import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

import sqlite3
import uuid
import importlib
import logging
from logging.handlers import TimedRotatingFileHandler
import pkgutil
from typing import Optional, List, Dict, Any
import time
import json
import re
from fastapi.responses import StreamingResponse
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ================ 定义工具 (Tools) ================

# 1. 告诉 AI 有哪些工具可用（JSON 格式描述）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "城市名，例如：北京"}
                },
                "required": ["location"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "执行复杂的数学计算",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，例如：25 * 4 + 10"}
                },
                "required": ["expression"],
            },
        }
    }
]


# 2. 定义工具的实际执行逻辑（AI 发出指令后，由你的 Python 代码执行）
def execute_tool(name: str, arguments: dict) -> str:
    if name == "get_weather":
        location = arguments.get("location", "未知地点")
        # 模拟调用天气 API
        return f" {location} 今天是晴天，气温 25°C，适合出行！"

    elif name == "calculator":
        expression = arguments.get("expression", "")
        try:
            # 安全执行数学计算
            result = eval(expression)
            return f" 计算结果：{expression} = {result}"
        except Exception as e:
            return f"❌ 计算错误：{e}"

    return "❌ 找不到该工具"


# ================ 配置 ================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
DB_PATH = "chat_history.db"

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 1. 文件日志：按天切割，最多保留 7 天，防止硬盘爆满
file_handler = TimedRotatingFileHandler(
    "app.log",
    when="D",           # D 代表按天切割 (Days)
    interval=1,         # 每 1 天切割一次
    backupCount=7,      # 最多保留 7 个历史文件，旧的自动删除
    encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter('%(asctime)s-%(name)s-%(levelname)s-%(message)s'))
logger.addHandler(file_handler)

# 2. 控制台日志：方便你看即时输出
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s-%(levelname)s-%(message)s'))
logger.addHandler(console_handler)

# ================ 🔴 核心防崩溃机制：安全加载 AI 模型 ================
VECTOR_AVAILABLE = False
try:
    # 尝试导入向量检索相关库
    import numpy as np
    import faiss
    from sentence_transformers import SentenceTransformer

    # 尝试加载模型
    EMBEDDING_MODEL = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    RERANKER_MODEL = SentenceTransformer('cross-encoder/ms-marco-MiniLM-L-6-v2')

    VECTOR_AVAILABLE = True
    logger.info("✅ 向量检索和重排序模型加载成功")
except Exception as e:
    # 如果 Windows 拦截了库，捕获错误，设置标志位，但不退出程序
    logger.warning(f"⚠️ 模型加载失败（{str(e)}），系统将自动降级为关键词检索模式。")
    logger.warning("⚠️ 降级模式下，AI 将使用关键词匹配，虽然笨一点，但完全可用！")
    VECTOR_AVAILABLE = False
    EMBEDDING_MODEL = None
    RERANKER_MODEL = None
    np = None
    faiss = None

# ================ FastAPI 应用 ================
app = FastAPI()


@app.middleware("http")
async def log_request(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {process_time:.3f}s")
    return response


request_count = 0


# ================ 数据库操作 ================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS conversations
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       session_id
                       TEXT
                       NOT
                       NULL,
                       role
                       TEXT
                       NOT
                       NULL,
                       content
                       TEXT
                       NOT
                       NULL,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS documents
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       content
                       TEXT
                       NOT
                       NULL,
                       vector
                       BLOB,
                       metadata
                       TEXT,
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   """)
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS cache
                   (
                       key TEXT PRIMARY KEY,
                       value TEXT,
                       expires_at TIMESTAMP
                   )
                   """)

    conn.commit()
    conn.close()


def save_message(session_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()


def get_history(session_id: str, limit: int = 10) -> List[Dict[str, str]]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]


# ================ 文档处理（分块） ================
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """将长文本切分成小块"""
    paragraphs = re.split(r'\n+', text)
    chunks = []
    current_chunk = []
    current_length = 0
    for para in paragraphs:
        para_len = len(para)
        if current_length + para_len > chunk_size:
            chunks.append("".join(current_chunk))
            current_chunk = [current_chunk[-1]] if current_chunk else []
            current_length = len("".join(current_chunk))
        current_chunk.append(para + "\n")
        current_length += para_len
    if current_chunk:
        chunks.append("".join(current_chunk))
    return chunks


def add_document(content: str, metadata: Optional[Dict[str, Any]] = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 🔴 新增：查重逻辑（防止重复上传）
    cursor.execute("SELECT id FROM documents WHERE content = ? LIMIT 1", (content,))
    if cursor.fetchone():
        conn.close()
        logger.warning("⚠️ 文档内容已存在，跳过上传")
        return {"message": "内容已存在，无需重复添加"}
    chunks = chunk_text(content, chunk_size=500, overlap=50)

    for i, chunk_content in enumerate(chunks):
        chunk_meta = {**(metadata or {}), "chunk_index": i, "total_chunks": len(chunks)}
        vector_bytes = None

        # 如果向量功能可用，才计算向量
        if VECTOR_AVAILABLE:
            try:
                vec = EMBEDDING_MODEL.encode([chunk_content])[0].astype('float32')
                vector_bytes = vec.tobytes()
            except:
                pass

        cursor.execute(
            "INSERT INTO documents (content, vector, metadata) VALUES (?, ?, ?)",
            (chunk_content, vector_bytes, json.dumps(chunk_meta, ensure_ascii=False))
        )

    conn.commit()
    conn.close()
    logger.info(f"✅ 文档已切分为 {len(chunks)} 块")


# ================ 检索系统 ================
def hybrid_search(query: str, limit: int = 3) -> List[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, content, vector FROM documents")
        rows = cursor.fetchall()
        if not rows:
            return []

        doc_contents = [row[1] for row in rows]
        doc_ids = [row[0] for row in rows]

        final_indices = []
        seen = set()

        # 1. 向量检索 (仅当模型加载成功时执行)
        if VECTOR_AVAILABLE and np is not None and faiss is not None:
            try:
                valid_vectors = []
                valid_idx_map = []
                for idx, row in enumerate(rows):
                    if row[2]:
                        vec = np.frombuffer(row[2], dtype=np.float32)
                        if vec.size > 0:
                            valid_vectors.append(vec)
                            valid_idx_map.append(idx)

                if valid_vectors:
                    query_vector = EMBEDDING_MODEL.encode([query])[0].astype('float32')
                    index = faiss.IndexFlatIP(valid_vectors[0].shape[0])
                    index.add(np.array(valid_vectors))
                    _, top_k = index.search(np.array([query_vector]), min(limit * 3, len(valid_vectors)))
                    vec_indices = [valid_idx_map[i] for i in top_k[0]]

                    for idx in vec_indices:
                        if idx not in seen:
                            seen.add(idx)
                            final_indices.append(idx)
            except Exception as e:
                logger.error(f"向量检索异常: {e}")

        # 2. 关键词检索 (保底方案，永远可用)
        cursor.execute("SELECT id FROM documents WHERE content LIKE ? LIMIT ?",
                       (f"%{query}%", limit * 3))
        keyword_ids = [row[0] for row in cursor.fetchall()]
        keyword_indices = [doc_ids.index(kid) for kid in keyword_ids if kid in doc_ids]

        for idx in keyword_indices:
            if idx not in seen:
                seen.add(idx)
                final_indices.append(idx)
        # 3. 结果截取
        final_indices = final_indices[:limit]
        # 🔴 新增：重排序逻辑（Reranking）
        # 1. 先多取一些候选文档（比如 limit 的 3 倍），给重排序留出筛选空间
        candidate_limit = min(limit * 3, len(final_indices))
        candidate_indices = final_indices[:candidate_limit]

        if VECTOR_AVAILABLE and RERANKER_MODEL is not None and candidate_indices:
            try:
                # 2. 准备"问题 - 文档"对
                candidate_docs = [doc_contents[i] for i in candidate_indices]
                pairs = [(query, doc) for doc in candidate_docs]

                # 3. 让 Reranker 模型打分（分数越高越相关）
                scores = RERANKER_MODEL.predict(pairs)

                # 4. 按分数从高到低排序
                ranked = sorted(zip(candidate_indices, scores), key=lambda x: x[1], reverse=True)

                # 5. 取回 Top-limit 个最精准的文档索引
                final_indices = [idx for idx, score in ranked[:limit]]

                logger.info(f"✅ 重排序完成：从 {len(candidate_indices)} 个候选中精选了 {limit} 个")
            except Exception as e:
                logger.warning(f"⚠️ 重排序失败，使用原始排序: {e}")

        # 4. 清理文本
        def clean_text(text):
            text = re.sub(r'\n+', '\n', text)
            text = re.sub(r'^\n+|\n+$', '', text)
            text = re.sub(r' +', ' ', text)
            return text

        return [clean_text(doc_contents[i]) for i in final_indices if i < len(doc_contents)]

    except Exception as e:
        logger.error(f"检索失败: {e}")
        return []
    finally:
        conn.close()


# ================ Skill 加载 ================
import skills


def load_skills():
    skill_definitions = []
    skill_executors = {}
    for finder, name, ispkg in pkgutil.iter_modules(skills.__path__):
        module = importlib.import_module(f"skills.{name}")
        if hasattr(module, "get_skill_definition") and hasattr(module, "execute"):
            skill_definitions.append(module.get_skill_definition())
            skill_executors[name] = module.execute
    return skill_definitions, skill_executors


SKILL_DEFINITIONS, SKILL_EXECUTORS = load_skills()


# ================ 模型定义 ================
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class DocumentRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None


# ================ API 路由 ================
@app.get("/")
async def root():
    return {"message": "AI 服务已启动，请使用 POST 请求访问 /chat"}


@app.get("/health")
async def health():
    return {"status": "ok"}
# ================ 🔴 新增：监控指标接口 ================
START_TIME = time.time()

def count_documents() -> int:
    """辅助函数：统计数据库里有多少文档"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM documents")
        count = cursor.fetchone()[0]
        return count
    except:
        return 0
    finally:
        conn.close()

@app.get("/metrics")
async def get_metrics():
    """
    生产级监控接口：返回系统健康状态
    访问 http://localhost:8000/metrics 查看
    """
    uptime = time.time() - START_TIME
    return {
        "status": "healthy",
        "version": "1.0.0",
        "uptime_seconds": f"{uptime:.1f}",
        "vector_search_enabled": VECTOR_AVAILABLE,
        "documents_count": count_documents(),
        "message": "系统运行正常，随时待命！"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT value FROM cache WHERE key = ? AND expires_at > CURRENT_TIMESTAMP",
        (request.message,)
    )
    cached_row = cursor.fetchone()
    conn.close()

    if cached_row:
        logger.info("⚡ 命中缓存！直接返回，节省 API 费用！")
        return ChatResponse(reply=cached_row[0], session_id=request.session_id or str(uuid.uuid4()))
    # 1. 获取历史对话
    session_id = request.session_id or str(uuid.uuid4())
    history = get_history(session_id, limit=5)

    # 🔴 新增：先检索知识库（找回 RAG 功能）
    try:
        knowledge = hybrid_search(request.message, limit=2)
        context_text = "\n".join(knowledge) if knowledge else ""
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        context_text = ""

    # 2. 构建基础消息
    # 如果有检索到文档，就把它放进系统提示词里
    if context_text:
        system_prompt = f"""你是一个智能助手。请优先基于以下【参考信息】回答问题。
【参考信息】：
{context_text}
"""
    else:
        system_prompt = "你是一个智能助手。如果需要使用工具，请调用工具函数。"

    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": request.message}
    ]

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # --- 第一轮：询问 AI 是否需要使用工具 ---
        payload = {
            "model": MODEL,
            "messages": messages,
            "tools": TOOLS,  # 🔴 关键：把工具列表传给 AI
            "tool_choice": "auto"  # 🔴 关键：让 AI 自动决定是否使用
        }

        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        assistant_msg = response.json()["choices"][0]["message"]

        # --- 检查 AI 是否决定调用工具 ---
        if assistant_msg.get("tool_calls"):
            # 🟢 AI 决定调用工具！
            tool_calls = assistant_msg["tool_calls"]

            # 把 AI 的决定加到历史记录里
            messages.append(assistant_msg)

            # 🟢 执行工具！
            for tool_call in tool_calls:
                func_name = tool_call["function"]["name"]
                func_args = json.loads(tool_call["function"]["arguments"])

                # 调用刚才定义的 execute_tool 函数
                tool_response = execute_tool(func_name, func_args)

                # 把工具执行的结果告诉 AI
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": func_name,
                    "content": tool_response
                })

            # --- 第二轮：让 AI 根据工具的结果，生成最终回答 ---
            payload["messages"] = messages
            payload.pop("tools", None)  # 第二轮不需要再传工具定义了

            response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            final_reply = response.json()["choices"][0]["message"]["content"]
        else:
            # ⚪ AI 不需要工具，直接回答
            final_reply = assistant_msg["content"]

        # 🔴 步骤 2：把新回答存入缓存（设置 1 小时后过期）
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, datetime('now', '+1 hour'))",
            (request.message, final_reply)
        )
        conn.commit()
        conn.close()
        logger.info("💾 已缓存新回答。")



        # 3. 保存记录并返回
        save_message(session_id, "user", request.message)
        save_message(session_id, "assistant", final_reply)

        return ChatResponse(reply=final_reply, session_id=session_id)

    except Exception as e:
        logger.error(f"API 调用失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式输出接口：让 AI 逐字返回答案"""
    # 1. 检索知识库（逻辑同普通接口）
    try:
        knowledge = hybrid_search(request.message, limit=2)
        context_text = "\n".join(knowledge) if knowledge else ""
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        context_text = ""

    # 2. 构建提示词
    if context_text:
        system_content = f"""你是一个专业的 AI 助手。请严格遵守以下规则：
1. 【优先使用私有知识】：你必须优先使用以下【参考信息】中的内容来回答用户问题。
2. 【禁止瞎编】：如果【参考信息】中包含了答案，你必须基于这些信息回答。
3. 【明确说明】：如果【参考信息】不足以回答问题，请明确告诉用户"知识库中没有相关信息"。

【参考信息】：
{context_text}
"""
    else:
        system_content = "你是一个智能助手。"

    session_id = request.session_id or str(uuid.uuid4())
    save_message(session_id, "user", request.message)
    history = get_history(session_id, limit=5)
    messages = [{"role": "system", "content": system_content}] + history + [
        {"role": "user", "content": request.message}]

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    # 3. 关键区别：开启 stream=True
    payload = {"model": MODEL, "messages": messages, "stream": True}

    # 4. 定义生成器：逐块吐出数据
    async def generate():
        try:
            # 使用 stream=True 发送请求
            with requests.post(API_URL, headers=headers, json=payload, stream=True, timeout=60) as response:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            data = line_str[6:]
                            if data == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                content = chunk['choices'][0]['delta'].get('content', '')
                                if content:
                                    # 使用 SSE 格式返回
                                    yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.error(f"流式输出失败: {e}")

    # 5. 返回流式响应
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/knowledge")
async def add_knowledge(doc: DocumentRequest):
    add_document(doc.content, doc.metadata)
    return {"message": "知识添加成功", "content": doc.content}


@app.get("/knowledge")
async def list_knowledge():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, content, metadata, created_at FROM documents ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return {
        "total": len(rows),
        "documents": [{"id": r[0], "content": r[1], "metadata": json.loads(r[2]) if r[2] else None, "created_at": r[3]}
                      for r in rows]
    }


@app.delete("/knowledge/{doc_id}")
async def delete_knowledge(doc_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()
    return {"message": f"已删除 ID 为 {doc_id} 的知识"}


if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)
