"""
提示词构建器 - 构建 AI 对话提示词
"""

import logging
from typing import List, Optional, Dict, Any


class PromptBuilder:
    """提示词构建器"""

    def __init__(self, max_context_tokens: int = 4000):
        """
        初始化提示词构建器

        Args:
            max_context_tokens: 最大上下文 Token 数
        """
        self.logger = logging.getLogger(__name__)
        self.max_context_tokens = max_context_tokens
        self._encoder = self._init_encoder()

    def _init_encoder(self):
        """初始化编码器"""
        try:
            import tiktoken

            return tiktoken.get_encoding("cl100k_base")
        except ImportError:
            return None

    def count_tokens(self, text: str) -> int:
        """计算 Token 数"""
        if self._encoder:
            return len(self._encoder.encode(text))
        chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        return int((len(text) - chinese) / 4 + chinese / 2)

    def build_context(self, docs: List[str]) -> str:
        """
        构建上下文提示

        Args:
            docs: 文档列表

        Returns:
            上下文文本
        """
        if not docs:
            return ""

        context_parts = []
        current_tokens = 0
        total_docs = len(docs)

        for i, doc in enumerate(docs):
            doc_tokens = self.count_tokens(doc)

            if current_tokens + doc_tokens > self.max_context_tokens:
                remaining = self.max_context_tokens - current_tokens
                if remaining > 50:
                    # 按比例截断
                    ratio = remaining / doc_tokens * 0.9
                    doc = doc[: int(len(doc) * ratio)] + "..."
                    doc_tokens = self.count_tokens(doc)
                else:
                    break

            context_parts.append(doc.strip())
            current_tokens += doc_tokens

        if not context_parts:
            return ""

        # 构建上下文文本
        context = "\n\n---\n\n".join(context_parts)

        # 添加超限提示
        if total_docs > len(context_parts):
            context += (
                f"\n\n[提示: 已省略 {total_docs - len(context_parts)} 个相关片段]"
            )

        return f"\n\n【参考文档】\n{context}\n\n"

    def build_system_prompt(
        self, role: str = "文档问答助手", context: Optional[str] = None
    ) -> str:
        """
        构建系统提示

        Args:
            role: AI 角色描述
            context: 上下文文档

        Returns:
            系统提示文本
        """
        prompt = f"你是一个专业的{role}。"

        if context:
            prompt += f"\n\n请根据以下参考文档回答用户问题。\n{context}"

        return prompt

    def build_chat_prompt(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        构建对话提示

        Args:
            user_message: 用户消息
            history: 对话历史
            context: 上下文文档

        Returns:
            消息列表
        """
        messages = []

        # 系统消息
        system_content = self.build_system_prompt(context=context)
        if system_content:
            messages.append({"role": "system", "content": system_content})

        # 历史消息
        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["user", "assistant"]:
                    messages.append({"role": role, "content": content})

        # 当前消息
        messages.append({"role": "user", "content": user_message})

        return messages
