"""
文本工具
"""

import re


def estimate_tokens(text: str) -> int:
    """
    估算 Token 数量

    Args:
        text: 输入文本

    Returns:
        Token 估算值
    """
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 2 + other_chars / 4)


def preprocess_text(text: str) -> str:
    """
    预处理文本

    Args:
        text: 原始文本

    Returns:
        处理后的文本
    """
    if not text:
        return ""

    # 移除多余空白
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    # 移除不规范字符
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

    # 标准化标点
    text = re.sub(r"[\u2018\u2019]", "'", text)
    text = re.sub(r"[\u201c\u201d]", '"', text)
    text = re.sub(r"[\u2013\u2014]", "-", text)

    return text


def split_sentences(text: str) -> list:
    """
    按句子分割（简单实现）

    Args:
        text: 输入文本

    Returns:
        句子列表
    """
    sentences = re.split(r"[.!?。！？]+", text)
    return [s.strip() for s in sentences if s.strip()]
