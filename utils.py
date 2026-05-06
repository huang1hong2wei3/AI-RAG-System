import re


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """
    将长文本切分成小块
    :param text: 原始长文本
    :param chunk_size: 每块大约的字符数
    :param overlap: 相邻两块之间重复的字符数（防止关键信息被切断）
    :return: 切分后的文本列表
    """
    # 1. 先按段落切分（保留语义完整性）
    paragraphs = re.split(r'\n+', text)

    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para_len = len(para)

        # 如果加上这一段会超过限制，就先把之前的存起来
        if current_length + para_len > chunk_size:
            # 存入当前的块
            chunks.append("".join(current_chunk))
            # 保留最后一段作为重叠部分 (Overlap)，防止上下文断裂
            current_chunk = [current_chunk[-1]] if current_chunk else []
            current_length = len("".join(current_chunk))

        current_chunk.append(para + "\n")
        current_length += para_len

    # 2. 处理最后一段
    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks


# 测试代码
if __name__ == "__main__":
    long_text = "这是第一段。\n这是第二段。\n" * 20
    result = chunk_text(long_text, chunk_size=100, overlap=20)
    print(f"切分结果共 {len(result)} 块")
    print(result[0])  # 打印第一块看看效果
