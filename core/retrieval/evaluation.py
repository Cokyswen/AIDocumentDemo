"""
RAG评估模块 - 评估检索和生成质量
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """评估结果"""

    query: str
    method: str

    # 检索指标
    hit_rate: float = 0.0  # 命中率
    precision: float = 0.0  # 精确率
    recall: float = 0.0  # 召回率
    f1: float = 0.0  # F1分数
    mrr: float = 0.0  # 平均倒数排名
    ndcg: float = 0.0  # NDCG

    # 额外信息
    num_retrieved: int = 0
    num_relevant: int = 0
    num_relevant_retrieved: int = 0
    retrieved_docs: List[str] = field(default_factory=list)
    relevant_docs: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "method": self.method,
            "Hit@K": round(self.hit_rate, 4),
            "Precision@K": round(self.precision, 4),
            "Recall@K": round(self.recall, 4),
            "F1@K": round(self.f1, 4),
            "MRR@K": round(self.mrr, 4),
            "NDCG@K": round(self.ndcg, 4),
        }


@dataclass
class TestCase:
    """测试用例"""

    query: str
    relevant_sources: List[str]  # 相关的文档来源
    relevant_keywords: List[str] = field(default_factory=list)  # 相关关键词
    ground_truth_answer: str = ""  # 标准答案（可选）
    category: str = ""  # 分类

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "relevant_sources": self.relevant_sources,
            "relevant_keywords": self.relevant_keywords,
            "ground_truth_answer": self.ground_truth_answer,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TestCase":
        return cls(**data)


class RGADEvaluator:
    """RAG评估器"""

    def __init__(self, k: int = 5):
        """
        初始化评估器

        Args:
            k: 评估时检索的文档数量
        """
        self.k = k
        self.test_cases: List[TestCase] = []
        self.evaluation_results: List[EvaluationResult] = []

    def load_test_cases(self, test_cases: List[TestCase]):
        """加载测试用例"""
        self.test_cases = test_cases
        logger.info(f"加载了 {len(test_cases)} 个测试用例")

    def load_test_cases_from_file(self, filepath: str):
        """从文件加载测试用例"""
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"测试用例文件不存在: {filepath}")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.test_cases = [TestCase.from_dict(tc) for tc in data]
        logger.info(f"从文件加载了 {len(self.test_cases)} 个测试用例")

    def save_test_cases(self, filepath: str):
        """保存测试用例到文件"""
        data = [tc.to_dict() for tc in self.test_cases]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"保存了 {len(self.test_cases)} 个测试用例到 {filepath}")

    def add_test_case(
        self,
        query: str,
        relevant_sources: List[str],
        relevant_keywords: List[str] = None,
        ground_truth_answer: str = "",
        category: str = "",
    ):
        """添加测试用例"""
        test_case = TestCase(
            query=query,
            relevant_sources=relevant_sources,
            relevant_keywords=relevant_keywords or [],
            ground_truth_answer=ground_truth_answer,
            category=category,
        )
        self.test_cases.append(test_case)

    def evaluate_retrieval(
        self, query: str, retrieved_sources: List[str], relevant_sources: List[str]
    ) -> EvaluationResult:
        """
        评估检索结果

        Args:
            query: 查询文本
            retrieved_sources: 检索到的文档来源列表
            retrieved_sources 中相关文档的数量
        """
        result = EvaluationResult(
            query=query,
            method="retrieval",
            retrieved_docs=retrieved_sources[: self.k],
            relevant_docs=relevant_sources,
        )

        retrieved_set = set(retrieved_sources[: self.k])
        relevant_set = set(relevant_sources)

        result.num_retrieved = len(retrieved_set)
        result.num_relevant = len(relevant_set)
        result.num_relevant_retrieved = len(retrieved_set & relevant_set)

        # Hit Rate
        result.hit_rate = 1.0 if result.num_relevant_retrieved > 0 else 0.0

        # Precision
        if result.num_retrieved > 0:
            result.precision = result.num_relevant_retrieved / result.num_retrieved

        # Recall
        if result.num_relevant > 0:
            result.recall = result.num_relevant_retrieved / result.num_relevant

        # F1
        if result.precision + result.recall > 0:
            result.f1 = (
                2
                * result.precision
                * result.recall
                / (result.precision + result.recall)
            )

        # MRR (Mean Reciprocal Rank)
        for i, source in enumerate(retrieved_sources[: self.k]):
            if source in relevant_set:
                result.mrr = 1.0 / (i + 1)
                break

        # NDCG
        result.ndcg = self._calculate_ndcg(
            retrieved_sources[: self.k], relevant_sources
        )

        return result

    def _calculate_ndcg(self, retrieved: List[str], relevant: List[str]) -> float:
        """计算 NDCG"""
        relevant_set = set(relevant)

        # DCG
        dcg = 0.0
        for i, doc in enumerate(retrieved):
            if doc in relevant_set:
                dcg += 1.0 / (i + 1)

        # IDCG (ideal DCG)
        idcg = sum(1.0 / (i + 1) for i in range(min(len(relevant), len(retrieved))))

        if idcg > 0:
            return dcg / idcg
        return 0.0

    def evaluate_retriever(
        self, retriever_func, methods: Dict[str, bool] = None
    ) -> Dict[str, List[EvaluationResult]]:
        """
        评估检索器在所有测试用例上的表现

        Args:
            retriever_func: 检索函数，接受 (query, top_k) 返回 (sources, scores)
            methods: 评估的方法列表

        Returns:
            每个方法的评估结果列表
        """
        if not self.test_cases:
            logger.warning("没有测试用例")
            return {}

        results_by_method = defaultdict(list)

        for test_case in self.test_cases:
            for method_name, enabled in (methods or {}).items():
                if not enabled:
                    continue

                try:
                    sources, scores = retriever_func(
                        test_case.query, self.k, method_name
                    )
                    eval_result = self.evaluate_retrieval(
                        test_case.query, sources, test_case.relevant_sources
                    )
                    eval_result.method = method_name
                    results_by_method[method_name].append(eval_result)
                except Exception as e:
                    logger.error(f"评估方法 {method_name} 时出错: {e}")

        return dict(results_by_method)

    def calculate_average_metrics(
        self, results: List[EvaluationResult]
    ) -> Dict[str, float]:
        """计算平均指标"""
        if not results:
            return {}

        metrics = {
            "Hit@K": 0.0,
            "Precision@K": 0.0,
            "Recall@K": 0.0,
            "F1@K": 0.0,
            "MRR@K": 0.0,
            "NDCG@K": 0.0,
        }

        for r in results:
            metrics["Hit@K"] += r.hit_rate
            metrics["Precision@K"] += r.precision
            metrics["Recall@K"] += r.recall
            metrics["F1@K"] += r.f1
            metrics["MRR@K"] += r.mrr
            metrics["NDCG@K"] += r.ndcg

        n = len(results)
        for key in metrics:
            metrics[key] /= n

        return metrics

    def generate_report(
        self, results_by_method: Dict[str, List[EvaluationResult]]
    ) -> str:
        """生成评估报告"""
        report_lines = ["=" * 60]
        report_lines.append("RAG 检索评估报告")
        report_lines.append("=" * 60)
        report_lines.append(f"测试用例数量: {len(self.test_cases)}")
        report_lines.append(f"评估 K 值: {self.k}")
        report_lines.append("")

        for method, results in results_by_method.items():
            avg_metrics = self.calculate_average_metrics(results)

            report_lines.append(f"方法: {method}")
            report_lines.append("-" * 40)
            report_lines.append(f"  Hit@K:     {avg_metrics['Hit@K']:.4f}")
            report_lines.append(f"  Precision@K: {avg_metrics['Precision@K']:.4f}")
            report_lines.append(f"  Recall@K:    {avg_metrics['Recall@K']:.4f}")
            report_lines.append(f"  F1@K:        {avg_metrics['F1@K']:.4f}")
            report_lines.append(f"  MRR@K:       {avg_metrics['MRR@K']:.4f}")
            report_lines.append(f"  NDCG@K:      {avg_metrics['NDCG@K']:.4f}")
            report_lines.append("")

        report_lines.append("=" * 60)
        return "\n".join(report_lines)


# 预定义的测试用例
DEFAULT_TEST_CASES = [
    TestCase(
        query="我种植过什么",
        relevant_sources=["2024-11-24-郁金香的种植记录.md", "2024-11-10-sunflower.md"],
        relevant_keywords=["种植", "郁金香", "向日葵", "种球", "种子"],
        category="种植",
    ),
    TestCase(
        query="makefile怎么写",
        relevant_sources=["2020-08-06-makefile-入门学习篇1.md"],
        relevant_keywords=["makefile", "make", "编译", "目标", "依赖"],
        category="技术",
    ),
    TestCase(
        query="NanoHTTPD服务器原理",
        relevant_sources=["2024-04-17-server原理分析.md"],
        relevant_keywords=["NanoHTTPD", "HTTP", "服务器", "启动"],
        category="技术",
    ),
    TestCase(
        query="Linux内核驱动开发",
        relevant_sources=["2023-07-29-编写一个简单的内核驱动.md"],
        relevant_keywords=["内核", "驱动", "Linux", "设备号", "字符设备"],
        category="技术",
    ),
    TestCase(
        query="Manjaro安装配置",
        relevant_sources=["2020-03-29-manjaro安装记录.md"],
        relevant_keywords=["Manjaro", "Linux", "安装", "分区"],
        category="技术",
    ),
]


def create_default_evaluator() -> RGADEvaluator:
    """创建带有默认测试用例的评估器"""
    evaluator = RGADEvaluator(k=5)
    evaluator.load_test_cases(DEFAULT_TEST_CASES)
    return evaluator
