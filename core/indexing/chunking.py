"""
文本分块处理器 - 基于 Token 的智能分块
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Chunk:
    """文本块"""

    content: str
    chunk_index: int
    token_count: int
    char_count: int
    metadata: Dict[str, Any]


class ChunkProcessor:
    """文本分块处理器"""

    def __init__(self, chunk_size: int = 600, overlap: int = 150):
        """
        初始化分块处理器

        Args:
            chunk_size: 目标块大小（Token数）
            overlap: 块之间的重叠大小（Token数）
        """
        self.logger = logging.getLogger(__name__)
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.effective_size = chunk_size - overlap

        # 初始化编码器
        self._encoder = self._init_encoder()

    def _init_encoder(self):
        """初始化 tiktoken 编码器"""
        try:
            import tiktoken

            return tiktoken.get_encoding("cl100k_base")
        except ImportError:
            self.logger.warning("tiktoken 未安装，使用字符估算")
            return None

    def count_tokens(self, text: str) -> int:
        """
        计算 Token 数量

        Args:
            text: 输入文本

        Returns:
            Token 数量
        """
        if self._encoder:
            return len(self._encoder.encode(text))
        else:
            chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 2 + other_chars / 4)

    def split_by_lines(self, text: str) -> List[str]:
        """按行分割文本"""
        return [line.strip() for line in text.splitlines() if line.strip()]

    def chunk_text(self, text: str, source: str = "") -> List[Chunk]:
        """
        将文本分割成块

        Args:
            text: 输入文本
            source: 文档来源

        Returns:
            Chunk 列表
        """
        if not text:
            return []

        # 预处理
        text = self._preprocess(text)

        # 短文本直接返回
        if self.count_tokens(text) <= self.chunk_size:
            return [
                Chunk(
                    content=text,
                    chunk_index=0,
                    token_count=self.count_tokens(text),
                    char_count=len(text),
                    metadata={"source": source},
                )
            ]

        return self._token_aware_chunk(text, source)

    def _preprocess(self, text: str) -> str:
        """文本预处理"""
        # 移除多余空白
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        # 移除不规范字符
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)

        return text

    def _token_aware_chunk(self, text: str, source: str) -> List[Chunk]:
        """基于 Token 的智能分块"""
        chunks = []
        current_text = ""
        current_tokens = 0
        chunk_index = 0

        lines = self.split_by_lines(text)

        for line in lines:
            line_clean = line.replace(" ", "")
            line_tokens = self.count_tokens(line_clean)

            # 长行处理
            if line_tokens > self.chunk_size:
                if current_text:
                    chunks.append(self._create_chunk(current_text, chunk_index, source))
                    chunk_index += 1
                    current_text = ""
                    current_tokens = 0

                # 分割长行
                sub_chunks = self._split_long_line(line_clean)
                for sub in sub_chunks:
                    chunks.append(self._create_chunk(sub, chunk_index, source))
                    chunk_index += 1
                continue

            # 尝试添加到当前块
            if current_tokens + line_tokens <= self.effective_size:
                current_text += line_clean + "\n"
                current_tokens += line_tokens + 1
            else:
                # 保存当前块
                if current_text.strip():
                    chunks.append(
                        self._create_chunk(current_text.strip(), chunk_index, source)
                    )
                    chunk_index += 1

                # 重置（带重叠）
                if self.overlap > 0 and len(current_text) > self.overlap:
                    overlap_text = current_text[-self.overlap * 2 :]
                    current_text = overlap_text + line_clean + "\n"
                    current_tokens = self.count_tokens(current_text) + line_tokens
                else:
                    current_text = line_clean + "\n"
                    current_tokens = line_tokens

        # 添加最后一个块
        if current_text.strip():
            chunks.append(self._create_chunk(current_text.strip(), chunk_index, source))

        return [c for c in chunks if c.token_count > 0]

    def _split_long_line(self, line: str) -> List[str]:
        """分割长行"""
        chunks = []
        total_tokens = self.count_tokens(line)

        if total_tokens <= self.chunk_size:
            return [line]

        # 按字符估算分割
        chars_per_token = len(line) / total_tokens
        chars_per_chunk = int(self.effective_size * chars_per_token)

        start = 0
        while start < len(line):
            end = min(start + chars_per_chunk, len(line))

            if end < len(line):
                # 尝试在标点处分割
                for punct in ["。", "！", "？", ".", "!", "?", "，", ",", "、"]:
                    pos = line.rfind(punct, start, end)
                    if pos > start:
                        end = pos + 1
                        break

            chunks.append(line[start:end].strip())
            start = end

        return [c for c in chunks if c]

    def _create_chunk(self, content: str, index: int, source: str) -> Chunk:
        """创建 Chunk 对象"""
        return Chunk(
            content=content,
            chunk_index=index,
            token_count=self.count_tokens(content),
            char_count=len(content),
            metadata={"source": source},
        )
