"""
AI 工程师核心概念详解
目标：理解 RAG 系统的底层架构
"""

import sqlite3  # 导入 SQLite 数据库模块（Python 内置，无需安装）
import importlib  # 导入动态导入模块，用于运行时加载代码
import pkgutil  # 导入包工具，用于扫描目录下的模块
from typing import List, Dict, Any, Optional  # 导入类型注解，提高代码可读性
import json  # 导入 JSON 处理模块，用于字典和字符串转换

# ============================================================================
# 模块 1：数据库操作层（Data Layer）
# 为什么重要：RAG 的核心是"检索"，检索的前提是数据能被高效存储和查询
# ============================================================================

DB_PATH = "chat_history.db"  # 定义数据库文件路径常量，所有数据库操作都用这个路径


def init_db():
    """
    初始化数据库表结构
    工程师思考：
    - 为什么用 "IF NOT EXISTS"？→ 避免重复创建报错，支持多次启动
    - 为什么分两个表？→ 职责分离：conversations 存对话，documents 存知识
    """
    conn = sqlite3.connect(DB_PATH)  # 连接数据库文件，如果不存在会自动创建
    cursor = conn.cursor()  # 创建游标对象，用于执行 SQL 语句

    # 表 1：对话历史（用于多轮对话上下文）
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS conversations -- 创建表，如果不存在才创建
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,    -- 自增 ID，唯一标识，主键
                       session_id
                       TEXT
                       NOT
                       NULL,             -- 会话 ID，区分不同用户/对话，不能为空
                       role
                       TEXT
                       NOT
                       NULL,             -- 角色：user(用户) 或 assistant(AI)，不能为空
                       content
                       TEXT
                       NOT
                       NULL,             -- 对话内容，不能为空
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP -- 时间戳，默认当前时间，用于排序
                   )
                   """)  # 执行 SQL 语句创建 conversations 表

    # 表 2：知识库（RAG 的"检索源"）
    cursor.execute("""
                   CREATE TABLE IF NOT EXISTS documents -- 创建表，如果不存在才创建
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,    -- 自增 ID，唯一标识，主键
                       content
                       TEXT
                       NOT
                       NULL,             -- 文档正文（检索的核心），不能为空
                       metadata
                       TEXT,             -- 元数据（JSON 格式，存来源、标签等），可以为空
                       created_at
                       TIMESTAMP
                       DEFAULT
                       CURRENT_TIMESTAMP -- 时间戳，默认当前时间
                   )
                   """)  # 执行 SQL 语句创建 documents 表

    conn.commit()  # 提交事务，将更改保存到数据库
    conn.close()  # 关闭数据库连接，释放资源


def add_document(content: str, metadata: Optional[Dict[str, Any]] = None):
    """
    向知识库添加文档
    参数：
        content: 文档正文内容（字符串）
        metadata: 元数据（字典，可选，默认为 None）
    工程师思考：
    - 为什么 metadata 要 json.dumps()？→ SQLite 没有 JSON 类型，转字符串存储
    - 生产环境优化：应该用连接池，避免频繁 connect/close
    """
    conn = sqlite3.connect(DB_PATH)  # 连接数据库
    cursor = conn.cursor()  # 创建游标

    # 将 Python 字典转为 JSON 字符串（入库）
    # 如果 metadata 存在，用 json.dumps 转换；否则为 None
    # ensure_ascii=False 保证中文字符正常显示，不转义为 \uXXXX
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    cursor.execute(
        "INSERT INTO documents (content, metadata) VALUES (?, ?)",  # SQL 插入语句，? 是占位符
        (content, metadata_json)  # 替换 ? 的实际值，防止 SQL 注入
    )  # 执行插入操作
    conn.commit()  # 提交事务，保存插入的数据
    conn.close()  # 关闭数据库连接


def search_documents(query: str, limit: int = 3) -> List[str]:
    """
    从知识库检索文档（当前是关键词匹配）
    参数：
        query: 搜索关键词
        limit: 返回结果数量限制，默认 3 条
    返回：
        List[str]: 匹配的文档内容列表
    工程师思考：
    - LIKE '%{query}%' 是模糊匹配，性能差但简单
    - 生产环境：应该用向量检索（FAISS）或全文检索（Elasticsearch）
    - 返回 List[str] 而不是完整对象？→ 只返回内容，减少内存占用
    """
    conn = sqlite3.connect(DB_PATH)  # 连接数据库
    cursor = conn.cursor()  # 创建游标

    # LIKE '%Python%' 表示包含 "Python" 的所有记录
    # % 是通配符，表示任意字符
    # ORDER BY created_at DESC 按时间倒序排列（最新的在前）
    # LIMIT ? 限制返回结果数量
    cursor.execute(
        "SELECT content FROM documents WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
        (f"%{query}%", limit)  # 第一个 ? 替换为 %关键词%，第二个 ? 替换为 limit 值
    )

    rows = cursor.fetchall()  # 获取所有查询结果，返回元组列表
    conn.close()  # 关闭数据库连接

    # 列表推导式：提取每行的第 0 列（content 字段）
    # row[0] 是因为每行是一个元组，如 ('Python 是编程语言',)
    return [row[0] for row in rows]


# ============================================================================
# 模块 2：Skill 动态加载机制（Plugin System）
# 为什么重要：这是 AI Agent 的核心，让 LLM 能"调用工具"
# ============================================================================

def load_skills():
    """
    自动扫描 skills/ 目录，加载所有 Skill 模块
    返回：
        skill_definitions: Skill 描述列表（发给 LLM 看）
        skill_executors: Skill 执行函数字典（本地调用）
    工程师思考：
    - 为什么用 pkgutil.iter_modules()？→ 不需要硬编码文件名，自动发现新插件
    - 设计模式：插件化架构，类似 VSCode 扩展机制
    """
    import skills  # 导入 skills 包

    skill_definitions = []  # 存储 Skill 描述（发给 LLM 看）
    skill_executors = {}  # 存储 Skill 执行函数（本地调用）

    # 遍历 skills/ 目录下的所有模块
    # finder: 模块查找器
    # name: 模块名称（如 calculator）
    # ispkg: 是否是包
    for finder, name, ispkg in pkgutil.iter_modules(skills.__path__):
        # 动态导入模块，例如 skills.calculator
        module = importlib.import_module(f"skills.{name}")

        # 检查是否实现了 Skill 标准接口
        # hasattr 检查对象是否有指定属性
        if hasattr(module, "get_skill_definition") and hasattr(module, "execute"):
            skill_definitions.append(module.get_skill_definition())  # 添加 Skill 描述
            skill_executors[name] = module.execute  # 添加执行函数

    return skill_definitions, skill_executors  # 返回两个结果


# 全局加载一次，避免每次请求都重新加载
SKILL_DEFINITIONS, SKILL_EXECUTORS = load_skills()  # 解包赋值，获取 Skill 定义和执行器

"""
Skill 标准接口（以 calculator.py 为例）：
每个 Skill 必须实现两个函数：

1. get_skill_definition() → 返回 JSON 描述
   {
       "name": "calculate",
       "description": "计算数学表达式",
       "parameters": {
           "type": "object",
           "properties": {
               "expression": {"type": "string", "description": "数学表达式"}
           },
           "required": ["expression"]
       }
   }
   → 这个描述会发给 DeepSeek，LLM 根据它决定何时调用

2. execute(expression: str) → 实际执行逻辑
   → LLM 决定调用后，本地执行这个函数
"""


# ============================================================================
# 模块 3：对话逻辑（RAG 的核心流程）
# 为什么重要：这是 AI 回答问题的"大脑"
# ============================================================================

def build_rag_prompt(user_message: str, history: List[Dict]) -> List[Dict]:
    """
    构建 RAG 提示词（这是任务 5 的内容，先理解概念）
    参数：
        user_message: 用户输入的消息
        history: 历史对话记录
    返回：
        List[Dict]: 完整的消息列表，包含 system、history、user

    RAG 标准流程：
    1. 检索：search_documents(user_message) → 找到相关知识
    2. 增强：将知识拼接到 prompt 中
    3. 生成：发送给 LLM

    示例：
    用户问："Python 是什么？"

    检索到：["Python 是一种编程语言"]

    最终 prompt：
    [
        {"role": "system", "content": "你是 AI 助手。参考以下知识回答：\nPython 是一种编程语言"},
        {"role": "user", "content": "Python 是什么？"}
    ]
    """
    # 1. 检索知识库
    # 根据用户消息搜索相关文档，最多返回 2 条
    knowledge = search_documents(user_message, limit=2)

    # 2. 拼接上下文
    # 用换行符将多个文档连接成一个字符串
    context = "\n".join(knowledge)
    # 构建 system prompt，包含检索到的知识
    system_prompt = f"""你是 AI 助手。请基于以下知识回答问题：
{context}

如果知识不足，请说明。"""

    # 3. 构建消息列表
    # 先放 system 消息，再加历史记录
    messages = [{"role": "system", "content": system_prompt}] + history
    # 最后添加用户当前消息
    messages.append({"role": "user", "content": user_message})

    return messages  # 返回完整的消息列表


# ============================================================================
# 模块 4：FastAPI 路由设计（API Layer）
# 为什么重要：这是系统的"入口"
# ============================================================================

"""
路由设计原则：
1. RESTful 风格：GET 查询，POST 创建
2. 路径清晰：/chat, /history, /knowledge
3. 类型注解：ChatRequest, ChatResponse（Pydantic 验证）

关键路由：
- POST /chat      → 发送消息，接收回复（核心）
- GET  /history   → 查询历史对话
- POST /knowledge → 添加知识（任务 6）
- GET  /knowledge → 检索知识（任务 6）
"""

# ============================================================================
# 工程师自检清单（学完这些才算入门）
# ============================================================================

"""
□ 能解释 documents 表每个字段的作用
□ 理解为什么 metadata 要用 JSON 存储
□ 知道 search_documents 的 LIKE 查询有什么缺点
□ 理解 load_skills() 的插件化设计思想
□ 能画出 RAG 的三步流程（检索 → 增强 → 生成）
□ 知道 Skill 是如何被 LLM 调用的（工具调用机制）

进阶思考：
1. 如果知识库有 10 万条数据，LIKE 查询会怎样？→ 很慢，需要索引或向量检索
2. 如果两个 Skill 功能重复怎么办？→ LLM 会随机选一个，需要优化描述
3. 如何保证 search_documents 返回最相关的结果？→ 引入 BM25 或向量相似度
"""
