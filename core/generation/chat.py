"""
对话服务 - AI 对话接口
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Generator

from .prompt_builder import PromptBuilder


class ChatService:
    """对话服务"""

    def __init__(
        self, config: Dict[str, Any], prompt_builder: Optional[PromptBuilder] = None
    ):
        """
        初始化对话服务

        Args:
            config: 配置字典
            prompt_builder: 提示词构建器
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.prompt_builder = prompt_builder or PromptBuilder(
            max_context_tokens=config.get("max_doc_context_length", 4000)
        )

        # 初始化 AI 客户端
        self._init_client()

        # 对话历史
        self.history: List[Dict[str, str]] = []
        self.max_history = config.get("max_history", 10)

    def _init_client(self):
        """初始化 AI 客户端"""
        openai_config = self.config.get("ai", {}).get("openai", {})

        self.api_key = openai_config.get("api_key", "")
        self.model = openai_config.get("model", "gpt-3.5-turbo")
        self.base_url = openai_config.get("base_url", "https://api.openai.com/v1")

        if self.api_key:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                self.logger.info(f"AI 客户端初始化成功，模型: {self.model}")
            except ImportError:
                self.logger.error("OpenAI 包未安装")
                self.client = None
        else:
            self.logger.warning("API Key 未配置")
            self.client = None

    def chat(
        self,
        message: str,
        context_docs: Optional[List[str]] = None,
        use_context: bool = True,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        发送对话请求

        Args:
            message: 用户消息
            context_docs: 上下文文档
            use_context: 是否使用上下文

        Returns:
            (成功与否, 回复内容, 附加信息)
        """
        if not self.client:
            return False, "AI 服务未配置", {}

        try:
            # 构建上下文
            context = ""
            if use_context and context_docs:
                context = self.prompt_builder.build_context(context_docs)

            # 构建消息
            messages = self.prompt_builder.build_chat_prompt(
                message, self.history[-self.max_history :], context
            )

            # 调用 API
            chat_config = self.config.get("ai", {}).get("chat", {})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=chat_config.get("temperature", 0.7),
                max_tokens=chat_config.get("max_tokens", 2000),
            )

            if response.choices:
                content = response.choices[0].message.content

                # 更新历史
                self.history.append({"role": "user", "content": message})
                self.history.append({"role": "assistant", "content": content})

                info = {
                    "usage": {
                        "total_tokens": response.usage.total_tokens
                        if response.usage
                        else 0
                    },
                    "context_used": bool(context_docs),
                    "model": self.model,
                }

                return True, content, info

            return False, "无响应内容", {}

        except Exception as e:
            self.logger.error(f"对话请求失败: {e}")
            return False, str(e), {}

    def stream_chat(
        self, message: str, context_docs: Optional[List[str]] = None
    ) -> Generator[str, None, None]:
        """
        流式对话

        Args:
            message: 用户消息
            context_docs: 上下文文档

        Yields:
            文本片段
        """
        if not self.client:
            yield "AI 服务未配置"
            return

        try:
            context = ""
            if context_docs:
                context = self.prompt_builder.build_context(context_docs)

            messages = self.prompt_builder.build_chat_prompt(
                message, self.history[-self.max_history :], context
            )

            chat_config = self.config.get("ai", {}).get("chat", {})

            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=chat_config.get("temperature", 0.7),
                max_tokens=chat_config.get("max_tokens", 2000),
                stream=True,
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield content

            # 更新历史
            if full_response:
                self.history.append({"role": "user", "content": message})
                self.history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            self.logger.error(f"流式对话失败: {e}")
            yield f"错误: {e}"

    def clear_history(self):
        """清空对话历史"""
        self.history = []

    def validate(self) -> bool:
        """验证配置是否有效"""
        return self.client is not None
