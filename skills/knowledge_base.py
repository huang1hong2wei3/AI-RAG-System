import json
from typing import Dict, Any

# Skill 名称（必须唯一）
SKILL_NAME = "query_knowledge_base"

# Skill 描述（LLM 根据这个决定何时调用）
SKILL_DESCRIPTION = "从知识库中检索与用户问题相关的信息。当用户询问事实、概念、流程或需要从私有知识中查找内容时使用此工具。"

# 参数定义（告诉 LLM 需要传什么参数）
SKILL_PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "搜索关键词或短语，用于在知识库中查找相关内容。例如：'Python 编程'、'公司请假流程'"
        }
    },
    "required": ["query"]  # 必填参数
}


def get_skill_definition() -> Dict[str, Any]:
    """返回 Skill 的定义（发给 LLM 看）"""
    return {
        "name": SKILL_NAME,
        "description": SKILL_DESCRIPTION,
        "parameters": SKILL_PARAMETERS
    }


def execute(query: str) -> str:
    """执行检索逻辑（本地调用）"""
    # 导入 main.py 中的检索函数
    from main import search_documents

    # 调用检索函数
    results = search_documents(query, limit=3)

    if not results:
        return "知识库中未找到相关信息。"

    # 格式化结果
    formatted_results = "\n".join([f"- {doc}" for doc in results])
    return f"找到以下相关信息：\n{formatted_results}"
