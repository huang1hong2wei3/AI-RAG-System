import requests
import time
import json


class RAGEvaluator:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.results = []

    def ask_ai(self, question: str) -> dict:
        """向 AI 提问并获取完整响应"""
        try:
            # 向正在运行的服务器发送请求
            response = requests.post(
                f"{self.base_url}/chat",
                json={"message": question},
                timeout=30
            )
            data = response.json()
            return {
                "reply": data.get("reply", ""),
                "status_code": response.status_code
            }
        except Exception as e:
            return {"reply": f"错误：{str(e)}", "status_code": 500}

    def run_evaluation(self, test_cases: list):
        """运行完整评估"""
        print("\n" + "=" * 60)
        print("🚀 RAG 系统评估报告")
        print("=" * 60)

        total_score = 0
        pass_count = 0

        for i, case in enumerate(test_cases, 1):
            print(f"\n📝 测试 {i}/{len(test_cases)}: {case['question']}")
            print("-" * 50)

            # 发送请求
            start_time = time.time()
            result = self.ask_ai(case['question'])
            elapsed = time.time() - start_time

            reply = result['reply']

            # 简单评分：检查回答中是否包含所有关键词
            matched = sum(1 for kw in case['expected_keywords'] if kw in reply)
            score = (matched / len(case['expected_keywords'])) * 100
            is_pass = score >= 80

            if is_pass:
                pass_count += 1
                status = "✅ 通过"
            else:
                status = "❌ 失败"

            total_score += score

            # 打印结果
            print(f"状态：{status} (得分：{score:.0f}/100)")
            print(f"耗时：{elapsed:.2f}秒")
            print(f"期望关键词：{case['expected_keywords']}")
            print(f"AI 回答：{reply[:100]}{'...' if len(reply) > 100 else ''}")

            self.results.append({
                "question": case['question'],
                "reply": reply,
                "score": score,
                "elapsed": elapsed
            })

        # 打印总结
        print("\n" + "=" * 60)
        print("📊 评估总结")
        print("=" * 60)
        print(f"总测试数：{len(test_cases)}")
        print(f"通过数：{pass_count}")
        print(f"通过率：{pass_count / len(test_cases) * 100:.1f}%")
        print(f"平均得分：{total_score / len(test_cases):.1f}/100")

        avg_score = total_score / len(test_cases)
        if avg_score >= 80:
            print("\n🏆 优秀！系统表现非常好！")
        elif avg_score >= 60:
            print("\n👍 良好。建议优化 Prompt 或检查数据。")
        else:
            print("\n⚠️ 需要改进。请检查数据库中是否有数据，或检索逻辑是否工作。")


# ================ 运行评估 ================
if __name__ == "__main__":
    # 定义测试用例
    test_cases = [
        {
            "question": "天网计划由谁主导？",
            "expected_keywords": ["黄鸿玮"],
            "category": "私有知识检索"
        },
        {
            "question": "管理员密码是多少？",
            "expected_keywords": ["Admin@888"],
            "category": "精确信息提取"
        },
        {
            "question": "项目使用什么技术框架？",
            "expected_keywords": ["FastAPI"],
            "category": "技术栈识别"
        }
    ]

    # 运行评估
    evaluator = RAGEvaluator()
    evaluator.run_evaluation(test_cases)
