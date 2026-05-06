import ast
import operator
from typing import Dict, Any

SKILL_NAME = "calculate"
SKILL_DESCRIPTION = "计算数学表达式，支持加减乘除和括号"
SKILL_PARAMETERS = {
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "数学表达式，例如 '3+5*2' 或 '(10-2)/4'"
        }
    },
    "required": ["expression"]
}

def get_skill_definition() -> Dict[str, Any]:
    return {
        "name": SKILL_NAME,
        "description": SKILL_DESCRIPTION,
        "parameters": SKILL_PARAMETERS
    }

def execute(expression: str) -> str:
    """安全地计算数学表达式"""
    # 只允许数字、运算符、括号、小数点
    allowed_chars = set("0123456789+-*/(). ")
    if not all(c in allowed_chars for c in expression):
        return "错误：表达式包含不允许的字符"
    try:
        # 使用 ast.literal_eval 配合 operator 更安全，但简单起见用 eval 并限制命名空间
        # 注意：生产环境建议用 safer 库，这里仅用于学习
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误：{str(e)}"
