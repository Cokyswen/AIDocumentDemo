"""
文档管理器 - 整合文档处理流程
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from core.indexing import DocumentProcessor, Chunk
from core.retrieval import VectorStore, RetrievalResult
from utils.text_processor import estimate_tokens


class DocumentManager:
    """文档管理器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化文档管理器

        Args:
            config: 配置字典
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # 获取配置
        processing_config = config.get("document", {}).get("processing", {})
        chunk_size = processing_config.get("chunk_size", 600)
        overlap = processing_config.get("chunk_overlap", 150)

        # 初始化处理器
        self.processor = DocumentProcessor(chunk_size, overlap)

        # 支持的文件类型
        self.supported_extensions = config.get("document", {}).get(
            "supported_extensions", [".txt", ".md", ".pdf", ".docx"]
        )

    def is_supported(self, file_path: Path) -> bool:
        """检查是否支持该文件"""
        return file_path.suffix.lower() in self.supported_extensions

    def validate_document(self, file_path: Path) -> Dict[str, Any]:
        """
        验证文档

        Args:
            file_path: 文件路径

        Returns:
            {"valid": bool, "reason": str, "file_info": dict}
        """
        if not file_path.exists():
            return {"valid": False, "reason": "文件不存在", "file_info": {}}

        if not self.is_supported(file_path):
            return {"valid": False, "reason": "不支持的文件格式", "file_info": {}}

        try:
            stat = file_path.stat()
            file_size_mb = stat.st_size / (1024 * 1024)
            max_size = (
                self.config.get("document", {})
                .get("processing", {})
                .get("max_file_size_mb", 10)
            )

            if file_size_mb > max_size:
                return {
                    "valid": False,
                    "reason": f"文件过大（{file_size_mb:.1f}MB > {max_size}MB）",
                    "file_info": {},
                }

            file_info = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_size": stat.st_size,
                "extension": file_path.suffix.lower(),
                "modified_time": stat.st_mtime,
            }

            return {"valid": True, "reason": "", "file_info": file_info}

        except Exception as e:
            return {"valid": False, "reason": str(e), "file_info": {}}

    def process(
        self, file_path: Path
    ) -> Tuple[bool, List[Dict[str, Any]], Dict[str, Any]]:
        """
        处理文档

        Args:
            file_path: 文件路径

        Returns:
            (成功与否, 块列表, 文件信息)
        """
        if not file_path.exists():
            return False, [], {"error": "文件不存在"}

        if not self.is_supported(file_path):
            return False, [], {"error": "不支持的文件格式"}

        try:
            # 处理文件
            chunks = self.processor.process_file(file_path)

            if not chunks:
                return False, [], {"error": "文档内容为空"}

            # 转换为字典
            chunk_dicts = []
            for chunk in chunks:
                chunk_dicts.append(
                    {
                        "content": chunk.content,
                        "token_count": chunk.token_count,
                        "char_count": chunk.char_count,
                        "metadata": {
                            **chunk.metadata,
                            "source": file_path.name,
                            "file_path": str(file_path),
                            "chunk_index": chunk.chunk_index,
                        },
                    }
                )

            file_info = {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "file_size": file_path.stat().st_size,
                "extension": file_path.suffix,
                "chunk_count": len(chunks),
            }

            return True, chunk_dicts, file_info

        except Exception as e:
            self.logger.error(f"文档处理失败: {e}")
            return False, [], {"error": str(e)}

    def process_batch(self, file_paths: List[Path]) -> Dict[str, Any]:
        """
        批量处理文档

        Args:
            file_paths: 文件路径列表

        Returns:
            处理结果统计
        """
        results = {
            "total": len(file_paths),
            "success": 0,
            "failed": 0,
            "total_chunks": 0,
            "errors": [],
        }

        for path in file_paths:
            success, chunks, info = self.process(path)
            if success:
                results["success"] += 1
                results["total_chunks"] += len(chunks)
            else:
                results["failed"] += 1
                results["errors"].append(
                    {"file": str(path), "reason": info.get("error", "未知错误")}
                )

        return results


def create_document_manager(config: Dict[str, Any]) -> DocumentManager:
    """创建文档管理器"""
    return DocumentManager(config)
