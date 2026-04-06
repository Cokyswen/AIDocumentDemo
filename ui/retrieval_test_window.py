"""
检索对比测试界面 - 用于对比不同检索方式的效果
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QGroupBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QSpinBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.indexing.vector_database import create_vector_database
from core.retrieval import (
    VectorStore,
    HybridSearch,
    BM25Retriever,
    RetrievalResult,
    rerank_results,
    QueryExpander,
    RGADEvaluator,
    TestCase,
    create_default_evaluator,
)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def format_result(r: RetrievalResult) -> dict:
    """格式化检索结果"""
    return {
        "content": r.content[:200] + "..." if len(r.content) > 200 else r.content,
        "source": r.metadata.get("source", "unknown"),
        "score": round(r.score, 4),
        "full_content": r.content,
    }


class RetrievalWorker(QThread):
    """检索工作线程"""

    finished = Signal(dict)
    error = Signal(str)
    expanded_queries = Signal(list)

    def __init__(
        self,
        vector_store: VectorStore,
        query: str,
        methods: Dict[str, bool],
        top_k: int = 5,
        use_expansion: bool = False,
    ):
        super().__init__()
        self.vector_store = vector_store
        self.query = query
        self.methods = methods
        self.top_k = top_k
        self.use_expansion = use_expansion
        self.expander = QueryExpander(max_expansion_terms=5) if use_expansion else None

    def _search_with_expansion(self, search_func, **kwargs) -> List[RetrievalResult]:
        """使用查询扩展进行搜索"""
        if not self.use_expansion or not self.expander:
            return search_func(**kwargs)

        expanded = self.expander.expand_with_queries(self.query)
        self.expanded_queries.emit(expanded)

        all_results = {}
        for q in expanded:
            kwargs_copy = kwargs.copy()
            kwargs_copy["query"] = q
            results = search_func(**kwargs_copy)
            for r in results:
                if r.content not in all_results:
                    all_results[r.content] = r
                elif r.score > all_results[r.content].score:
                    all_results[r.content].score = r.score

        return list(all_results.values())

    def run(self):
        try:
            results = {}

            # 先获取扩展查询
            expanded_queries_list = [self.query]
            if self.use_expansion and self.expander:
                expanded_queries_list = self.expander.expand_with_queries(self.query)
                self.expanded_queries.emit(expanded_queries_list)

            # 1. 向量搜索
            if self.methods.get("vector"):
                results_list = self._search_with_expansion(
                    lambda query, n_results: self.vector_store.search(
                        query, n_results=n_results
                    ),
                    query=self.query,
                    n_results=self.top_k * 2,
                )
                results["vector"] = [format_result(r) for r in results_list]

            # 2. 向量搜索 + 查询扩展
            if self.methods.get("vector_expanded"):
                all_results = {}
                for q in expanded_queries_list:
                    vector_results = self.vector_store.search(
                        q, n_results=self.top_k * 2
                    )
                    for r in vector_results:
                        if r.content not in all_results:
                            all_results[r.content] = r
                        elif r.score > all_results[r.content].score:
                            all_results[r.content].score = r.score
                sorted_results = sorted(
                    all_results.values(), key=lambda x: x.score, reverse=True
                )
                results["vector_expanded"] = [
                    format_result(r) for r in sorted_results[: self.top_k * 2]
                ]

            # 3. 关键词搜索 (BM25)
            if self.methods.get("bm25"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        bm25_results = bm25.search(self.query, top_k=self.top_k * 2)
                        results["bm25"] = [
                            {
                                "content": r.content[:200] + "..."
                                if len(r.content) > 200
                                else r.content,
                                "source": r.metadata.get("source", "unknown"),
                                "score": round(r.score, 4),
                                "full_content": r.content,
                            }
                            for r in bm25_results
                        ]
                except Exception as e:
                    results["bm25"] = [{"error": str(e)}]

            # 4. 关键词搜索 + 查询扩展
            if self.methods.get("bm25_expanded"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        all_bm25_results = {}
                        for q in expanded_queries_list:
                            bm25_results = bm25.search(q, top_k=self.top_k * 2)
                            for r in bm25_results:
                                if r.content not in all_bm25_results:
                                    all_bm25_results[r.content] = r
                                elif r.score > all_bm25_results[r.content].score:
                                    all_bm25_results[r.content].score = r.score
                        sorted_results = sorted(
                            all_bm25_results.values(),
                            key=lambda x: x.score,
                            reverse=True,
                        )
                        results["bm25_expanded"] = [
                            {
                                "content": r.content[:200] + "..."
                                if len(r.content) > 200
                                else r.content,
                                "source": r.metadata.get("source", "unknown"),
                                "score": round(r.score, 4),
                                "full_content": r.content,
                            }
                            for r in sorted_results[: self.top_k * 2]
                        ]
                except Exception as e:
                    results["bm25_expanded"] = [{"error": str(e)}]

            # 5. 混合搜索 (RRF)
            if self.methods.get("hybrid_rrf"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.7,
                            keyword_weight=0.3,
                            fusion_method="rrf",
                        )
                        hybrid_results = hybrid.search(self.query, top_k=self.top_k * 2)
                        results["hybrid_rrf"] = [
                            format_result(r) for r in hybrid_results
                        ]
                except Exception as e:
                    results["hybrid_rrf"] = [{"error": str(e)}]

            # 6. 混合搜索 (RRF) + 查询扩展
            if self.methods.get("hybrid_rrf_expanded"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.7,
                            keyword_weight=0.3,
                            fusion_method="rrf",
                        )
                        all_hybrid_results = {}
                        for q in expanded_queries_list:
                            hybrid_results = hybrid.search(q, top_k=self.top_k * 2)
                            for r in hybrid_results:
                                if r.content not in all_hybrid_results:
                                    all_hybrid_results[r.content] = r
                                elif r.score > all_hybrid_results[r.content].score:
                                    all_hybrid_results[r.content].score = r.score
                        sorted_results = sorted(
                            all_hybrid_results.values(),
                            key=lambda x: x.score,
                            reverse=True,
                        )
                        results["hybrid_rrf_expanded"] = [
                            format_result(r) for r in sorted_results[: self.top_k * 2]
                        ]
                except Exception as e:
                    results["hybrid_rrf_expanded"] = [{"error": str(e)}]

            # 7. 混合搜索 (加权求和)
            if self.methods.get("hybrid_weighted"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.5,
                            keyword_weight=0.5,
                            fusion_method="weighted_sum",
                        )
                        hybrid_results = hybrid.search(self.query, top_k=self.top_k * 2)
                        results["hybrid_weighted"] = [
                            format_result(r) for r in hybrid_results
                        ]
                except Exception as e:
                    results["hybrid_weighted"] = [{"error": str(e)}]

            # 8. 混合搜索 (加权) + 查询扩展
            if self.methods.get("hybrid_weighted_expanded"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.5,
                            keyword_weight=0.5,
                            fusion_method="weighted_sum",
                        )
                        all_hybrid_results = {}
                        for q in expanded_queries_list:
                            hybrid_results = hybrid.search(q, top_k=self.top_k * 2)
                            for r in hybrid_results:
                                if r.content not in all_hybrid_results:
                                    all_hybrid_results[r.content] = r
                                elif r.score > all_hybrid_results[r.content].score:
                                    all_hybrid_results[r.content].score = r.score
                        sorted_results = sorted(
                            all_hybrid_results.values(),
                            key=lambda x: x.score,
                            reverse=True,
                        )
                        results["hybrid_weighted_expanded"] = [
                            format_result(r) for r in sorted_results[: self.top_k * 2]
                        ]
                except Exception as e:
                    results["hybrid_weighted_expanded"] = [{"error": str(e)}]

            # 9. 向量搜索 + 分数重排序
            if self.methods.get("vector_rerank_score"):
                try:
                    vector_results = self.vector_store.search(
                        self.query, n_results=self.top_k * 2
                    )
                    reranked = rerank_results(
                        self.query, vector_results, self.top_k, method="score"
                    )
                    results["vector_rerank_score"] = [
                        format_result(r) for r in reranked
                    ]
                except Exception as e:
                    results["vector_rerank_score"] = [{"error": str(e)}]

            # 10. 向量搜索 + 多样性重排序
            if self.methods.get("vector_rerank_diversity"):
                try:
                    vector_results = self.vector_store.search(
                        self.query, n_results=self.top_k * 2
                    )
                    reranked = rerank_results(
                        self.query, vector_results, self.top_k, method="diversity"
                    )
                    results["vector_rerank_diversity"] = [
                        format_result(r) for r in reranked
                    ]
                except Exception as e:
                    results["vector_rerank_diversity"] = [{"error": str(e)}]

            # 11. 混合搜索(RRF) + 分数重排序
            if self.methods.get("hybrid_rrf_rerank_score"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.7,
                            keyword_weight=0.3,
                            fusion_method="rrf",
                        )
                        hybrid_results = hybrid.search(self.query, top_k=self.top_k * 2)
                        reranked = rerank_results(
                            self.query, hybrid_results, self.top_k, method="score"
                        )
                        results["hybrid_rrf_rerank_score"] = [
                            format_result(r) for r in reranked
                        ]
                except Exception as e:
                    results["hybrid_rrf_rerank_score"] = [{"error": str(e)}]

            # 12. 混合搜索(RRF) + 多样性重排序
            if self.methods.get("hybrid_rrf_rerank_diversity"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.7,
                            keyword_weight=0.3,
                            fusion_method="rrf",
                        )
                        hybrid_results = hybrid.search(self.query, top_k=self.top_k * 2)
                        reranked = rerank_results(
                            self.query, hybrid_results, self.top_k, method="diversity"
                        )
                        results["hybrid_rrf_rerank_diversity"] = [
                            format_result(r) for r in reranked
                        ]
                except Exception as e:
                    results["hybrid_rrf_rerank_diversity"] = [{"error": str(e)}]

            # 13. 混合搜索(加权) + 分数重排序
            if self.methods.get("hybrid_weighted_rerank_score"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.5,
                            keyword_weight=0.5,
                            fusion_method="weighted_sum",
                        )
                        hybrid_results = hybrid.search(self.query, top_k=self.top_k * 2)
                        reranked = rerank_results(
                            self.query, hybrid_results, self.top_k, method="score"
                        )
                        results["hybrid_weighted_rerank_score"] = [
                            format_result(r) for r in reranked
                        ]
                except Exception as e:
                    results["hybrid_weighted_rerank_score"] = [{"error": str(e)}]

            # 14. 混合搜索(加权) + 多样性重排序
            if self.methods.get("hybrid_weighted_rerank_diversity"):
                try:
                    all_docs = self.vector_store.collection.get(
                        include=["documents", "metadatas"]
                    )
                    if all_docs.get("documents"):
                        bm25 = BM25Retriever(
                            all_docs["documents"], all_docs.get("metadatas", [])
                        )
                        hybrid = HybridSearch(
                            vector_store=self.vector_store,
                            bm25_retriever=bm25,
                            vector_weight=0.5,
                            keyword_weight=0.5,
                            fusion_method="weighted_sum",
                        )
                        hybrid_results = hybrid.search(self.query, top_k=self.top_k * 2)
                        reranked = rerank_results(
                            self.query, hybrid_results, self.top_k, method="diversity"
                        )
                        results["hybrid_weighted_rerank_diversity"] = [
                            format_result(r) for r in reranked
                        ]
                except Exception as e:
                    results["hybrid_weighted_rerank_diversity"] = [{"error": str(e)}]

            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class EvaluationWorker(QThread):
    """评估工作线程"""

    finished = Signal(dict, dict)
    progress = Signal(str, int, int)
    error = Signal(str)

    def __init__(
        self,
        vector_store: VectorStore,
        test_cases: List[TestCase],
        methods: Dict[str, bool],
        k: int = 5,
        use_expansion: bool = False,
    ):
        super().__init__()
        self.vector_store = vector_store
        self.test_cases = test_cases
        self.methods = methods
        self.k = k
        self.use_expansion = use_expansion
        self.expander = QueryExpander(max_expansion_terms=5) if use_expansion else None

    def _retrieve(self, query: str, top_k: int, method: str) -> tuple:
        """执行检索，返回(来源列表, 分数列表)"""
        all_docs = self.vector_store.collection.get(include=["documents", "metadatas"])
        sources = []

        if method == "vector":
            results = self.vector_store.search(query, n_results=top_k)
            sources = [r.metadata.get("source", "unknown") for r in results]

        elif method == "bm25":
            if all_docs.get("documents"):
                bm25 = BM25Retriever(
                    all_docs["documents"], all_docs.get("metadatas", [])
                )
                results = bm25.search(query, top_k=top_k)
                sources = [r.metadata.get("source", "unknown") for r in results]

        elif method == "hybrid_rrf":
            if all_docs.get("documents"):
                bm25 = BM25Retriever(
                    all_docs["documents"], all_docs.get("metadatas", [])
                )
                hybrid = HybridSearch(
                    vector_store=self.vector_store,
                    bm25_retriever=bm25,
                    vector_weight=0.7,
                    keyword_weight=0.3,
                    fusion_method="rrf",
                )
                results = hybrid.search(query, top_k=top_k)
                sources = [r.metadata.get("source", "unknown") for r in results]

        elif method == "hybrid_weighted":
            if all_docs.get("documents"):
                bm25 = BM25Retriever(
                    all_docs["documents"], all_docs.get("metadatas", [])
                )
                hybrid = HybridSearch(
                    vector_store=self.vector_store,
                    bm25_retriever=bm25,
                    vector_weight=0.5,
                    keyword_weight=0.5,
                    fusion_method="weighted_sum",
                )
                results = hybrid.search(query, top_k=top_k)
                sources = [r.metadata.get("source", "unknown") for r in results]

        elif method == "vector_expanded" and self.expander:
            expanded = self.expander.expand_with_queries(query)
            all_sources = {}
            for q in expanded:
                results = self.vector_store.search(q, n_results=top_k)
                for r in results:
                    source = r.metadata.get("source", "unknown")
                    if source not in all_sources:
                        all_sources[source] = r.score
                    else:
                        all_sources[source] = max(all_sources[source], r.score)
            sources = sorted(
                all_sources.keys(), key=lambda s: all_sources[s], reverse=True
            )[:top_k]

        elif method == "hybrid_rrf_expanded" and self.expander:
            expanded = self.expander.expand_with_queries(query)
            if all_docs.get("documents"):
                bm25 = BM25Retriever(
                    all_docs["documents"], all_docs.get("metadatas", [])
                )
                hybrid = HybridSearch(
                    vector_store=self.vector_store,
                    bm25_retriever=bm25,
                    vector_weight=0.7,
                    keyword_weight=0.3,
                    fusion_method="rrf",
                )
                all_sources = {}
                for q in expanded:
                    results = hybrid.search(q, top_k=top_k)
                    for r in results:
                        source = r.metadata.get("source", "unknown")
                        if source not in all_sources:
                            all_sources[source] = r.score
                        else:
                            all_sources[source] = max(all_sources[source], r.score)
                sources = sorted(
                    all_sources.keys(), key=lambda s: all_sources[s], reverse=True
                )[:top_k]

        else:
            results = self.vector_store.search(query, n_results=top_k)
            sources = [r.metadata.get("source", "unknown") for r in results]

        return sources, []

    def run(self):
        try:
            evaluator = RGADEvaluator(k=self.k)
            evaluator.load_test_cases(self.test_cases)

            results_by_method = {}
            all_results = {}

            enabled_methods = [m for m, enabled in self.methods.items() if enabled]
            total = len(self.test_cases) * len(enabled_methods)
            current = 0

            for method in enabled_methods:
                results_by_method[method] = []

                for i, test_case in enumerate(self.test_cases):
                    current += 1
                    self.progress.emit(f"评估 {method}...", current, total)

                    try:
                        sources, scores = self._retrieve(
                            test_case.query, self.k, method
                        )
                        eval_result = evaluator.evaluate_retrieval(
                            test_case.query, sources, test_case.relevant_sources
                        )
                        eval_result.method = method
                        results_by_method[method].append(eval_result)
                    except Exception as e:
                        logger.error(f"评估 {method}/{test_case.query} 时出错: {e}")

            avg_metrics_by_method = {}
            for method, results in results_by_method.items():
                avg_metrics_by_method[method] = evaluator.calculate_average_metrics(
                    results
                )

            self.finished.emit(results_by_method, avg_metrics_by_method)

        except Exception as e:
            self.error.emit(str(e))


class RetrievalTestWindow(QMainWindow):
    """检索对比测试窗口"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.vector_store = None

        self.init_ui()
        self.init_data()

    def init_ui(self):
        self.setWindowTitle("检索方式对比测试")
        self.setMinimumSize(1400, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 查询区域
        query_group = QGroupBox("查询设置")
        query_layout = QVBoxLayout()

        query_input_layout = QHBoxLayout()
        self.query_edit = QTextEdit()
        self.query_edit.setPlaceholderText("输入你的查询问题...")
        self.query_edit.setMaximumHeight(80)

        self.search_btn = QPushButton("🔍 开始检索")
        self.search_btn.setMinimumWidth(120)
        self.search_btn.clicked.connect(self.do_search)

        query_input_layout.addWidget(self.query_edit)
        query_input_layout.addWidget(self.search_btn)
        query_layout.addLayout(query_input_layout)

        # 检索方法选择 - 第一行
        basic_layout = QHBoxLayout()
        basic_layout.addWidget(QLabel("基础检索:"))
        basic_layout.setSpacing(10)

        self.cb_vector = QCheckBox("向量搜索")
        self.cb_vector.setChecked(True)
        basic_layout.addWidget(self.cb_vector)

        self.cb_bm25 = QCheckBox("BM25")
        self.cb_bm25.setChecked(True)
        basic_layout.addWidget(self.cb_bm25)

        self.cb_hybrid_rrf = QCheckBox("混合(RRF)")
        self.cb_hybrid_rrf.setChecked(True)
        basic_layout.addWidget(self.cb_hybrid_rrf)

        self.cb_hybrid_weighted = QCheckBox("混合(加权)")
        self.cb_hybrid_weighted.setChecked(True)
        basic_layout.addWidget(self.cb_hybrid_weighted)

        basic_layout.addStretch()

        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 20)
        self.top_k_spin.setValue(5)
        basic_layout.addWidget(QLabel("返回数量:"))
        basic_layout.addWidget(self.top_k_spin)

        query_layout.addLayout(basic_layout)

        # 查询扩展选项
        expansion_layout = QHBoxLayout()
        expansion_layout.addWidget(QLabel("查询优化:"))

        self.cb_use_expansion = QCheckBox("启用查询扩展")
        self.cb_use_expansion.setToolTip("使用同义词和语义相关词扩展查询，提高召回率")
        expansion_layout.addWidget(self.cb_use_expansion)

        self.expanded_queries_label = QLabel("扩展查询: (将在检索后显示)")
        self.expanded_queries_label.setStyleSheet("color: #666; font-style: italic;")
        expansion_layout.addWidget(self.expanded_queries_label)

        expansion_layout.addStretch()
        query_layout.addLayout(expansion_layout)

        # 检索方法选择 - 第二行（查询扩展后的检索）
        expanded_layout = QHBoxLayout()
        expanded_layout.addWidget(QLabel("+查询扩展:"))
        expanded_layout.setSpacing(10)

        self.cb_vector_expanded = QCheckBox("向量+扩展")
        expanded_layout.addWidget(self.cb_vector_expanded)

        self.cb_bm25_expanded = QCheckBox("BM25+扩展")
        expanded_layout.addWidget(self.cb_bm25_expanded)

        self.cb_hybrid_rrf_expanded = QCheckBox("混合(RRF)+扩展")
        expanded_layout.addWidget(self.cb_hybrid_rrf_expanded)

        self.cb_hybrid_weighted_expanded = QCheckBox("混合(加权)+扩展")
        expanded_layout.addWidget(self.cb_hybrid_weighted_expanded)

        expanded_layout.addStretch()
        query_layout.addLayout(expanded_layout)

        # 检索方法选择 - 第三行（重排序）
        rerank_layout = QHBoxLayout()
        rerank_layout.addWidget(QLabel("重排序:"))
        rerank_layout.setSpacing(10)

        self.cb_vector_rerank_score = QCheckBox("向量+分数重排")
        rerank_layout.addWidget(self.cb_vector_rerank_score)

        self.cb_vector_rerank_diversity = QCheckBox("向量+多样性重排")
        rerank_layout.addWidget(self.cb_vector_rerank_diversity)

        self.cb_hybrid_rrf_rerank_score = QCheckBox("混合(RRF)+分数重排")
        rerank_layout.addWidget(self.cb_hybrid_rrf_rerank_score)

        self.cb_hybrid_rrf_rerank_diversity = QCheckBox("混合(RRF)+多样性重排")
        rerank_layout.addWidget(self.cb_hybrid_rrf_rerank_diversity)

        self.cb_hybrid_weighted_rerank_score = QCheckBox("混合(加权)+分数重排")
        rerank_layout.addWidget(self.cb_hybrid_weighted_rerank_score)

        self.cb_hybrid_weighted_rerank_diversity = QCheckBox("混合(加权)+多样性重排")
        rerank_layout.addWidget(self.cb_hybrid_weighted_rerank_diversity)

        rerank_layout.addStretch()
        query_layout.addLayout(rerank_layout)

        query_group.setLayout(query_layout)
        layout.addWidget(query_group)

        # 统计信息
        self.stats_label = QLabel("请输入查询并点击检索")
        self.stats_label.setStyleSheet(
            "padding: 5px; background: #f0f0f0; border-radius: 4px;"
        )
        layout.addWidget(self.stats_label)

        # 结果区域 - 使用标签页
        self.tab_widget = QTabWidget()

        # 创建各检索方式的标签页
        self.result_tabs = {}
        method_configs = [
            ("vector", "🔍 向量搜索"),
            ("vector_expanded", "🔍 向量+扩展"),
            ("bm25", "📝 BM25"),
            ("bm25_expanded", "📝 BM25+扩展"),
            ("hybrid_rrf", "🔀 混合(RRF)"),
            ("hybrid_rrf_expanded", "🔀 混合(RRF)+扩展"),
            ("hybrid_weighted", "⚖️ 混合(加权)"),
            ("hybrid_weighted_expanded", "⚖️ 混合(加权)+扩展"),
            ("vector_rerank_score", "📊 向量+分数重排"),
            ("vector_rerank_diversity", "🎯 向量+多样性重排"),
            ("hybrid_rrf_rerank_score", "📊 混合(RRF)+分数重排"),
            ("hybrid_rrf_rerank_diversity", "🎯 混合(RRF)+多样性重排"),
            ("hybrid_weighted_rerank_score", "📊 混合(加权)+分数重排"),
            ("hybrid_weighted_rerank_diversity", "🎯 混合(加权)+多样性重排"),
        ]

        for method_id, method_name in method_configs:
            tab = self.create_result_tab(method_id)
            self.result_tabs[method_id] = tab
            self.tab_widget.addTab(tab, method_name)

        # 添加评估标签页
        eval_tab = self.create_evaluation_tab()
        self.tab_widget.addTab(eval_tab, "📊 RAG评估")

        layout.addWidget(self.tab_widget)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.setStatusWidget(self.status_label)

        # 初始化评估器
        self.evaluator = create_default_evaluator()
        self.eval_worker = None

    def create_result_tab(self, method_id: str) -> QWidget:
        """创建结果标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 表格
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["排名", "来源", "分数", "内容预览"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.itemClicked.connect(lambda item: self.show_detail(item, method_id))
        layout.addWidget(table)

        # 详细信息
        detail_group = QGroupBox("详细信息")
        detail_layout = QVBoxLayout()
        self.detail_texts = getattr(self, "detail_texts", {})
        self.detail_texts[method_id] = QTextEdit()
        self.detail_texts[method_id].setReadOnly(True)
        self.detail_texts[method_id].setMaximumHeight(150)
        detail_layout.addWidget(self.detail_texts[method_id])
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        return widget

    def get_table(self, method_id: str) -> QTableWidget:
        """获取指定方法的表格"""
        tab = self.result_tabs.get(method_id)
        if tab:
            return tab.findChild(QTableWidget)
        return None

    def init_data(self):
        """初始化数据"""
        try:
            config = ConfigManager().config
            self.vector_store = create_vector_database(config)

            count = self.vector_store.count()
            self.stats_label.setText(f"向量数据库已加载，共 {count} 个文档块")

        except Exception as e:
            self.stats_label.setText(f"数据加载失败: {e}")
            logger.error(f"数据加载失败: {e}")

    def get_selected_methods(self) -> Dict[str, bool]:
        """获取选择的检索方式"""
        return {
            "vector": self.cb_vector.isChecked(),
            "vector_expanded": self.cb_vector_expanded.isChecked(),
            "bm25": self.cb_bm25.isChecked(),
            "bm25_expanded": self.cb_bm25_expanded.isChecked(),
            "hybrid_rrf": self.cb_hybrid_rrf.isChecked(),
            "hybrid_rrf_expanded": self.cb_hybrid_rrf_expanded.isChecked(),
            "hybrid_weighted": self.cb_hybrid_weighted.isChecked(),
            "hybrid_weighted_expanded": self.cb_hybrid_weighted_expanded.isChecked(),
            "vector_rerank_score": self.cb_vector_rerank_score.isChecked(),
            "vector_rerank_diversity": self.cb_vector_rerank_diversity.isChecked(),
            "hybrid_rrf_rerank_score": self.cb_hybrid_rrf_rerank_score.isChecked(),
            "hybrid_rrf_rerank_diversity": self.cb_hybrid_rrf_rerank_diversity.isChecked(),
            "hybrid_weighted_rerank_score": self.cb_hybrid_weighted_rerank_score.isChecked(),
            "hybrid_weighted_rerank_diversity": self.cb_hybrid_weighted_rerank_diversity.isChecked(),
        }

    def do_search(self):
        """执行检索"""
        query = self.query_edit.toPlainText().strip()
        if not query:
            self.query_edit.setFocus()
            return

        if not self.vector_store:
            self.stats_label.setText("向量数据库未初始化")
            return

        self.search_btn.setEnabled(False)
        self.search_btn.setText("检索中...")
        self.status_label.setText(f"正在检索: {query[:50]}...")

        methods = self.get_selected_methods()
        if not any(methods.values()):
            self.stats_label.setText("请至少选择一种检索方式")
            self.search_btn.setEnabled(True)
            self.search_btn.setText("🔍 开始检索")
            return

        use_expansion = self.cb_use_expansion.isChecked()

        # 如果有任何扩展方法被选中，自动启用查询扩展
        expanded_methods = [
            "vector_expanded",
            "bm25_expanded",
            "hybrid_rrf_expanded",
            "hybrid_weighted_expanded",
        ]
        if any(methods.get(m) for m in expanded_methods):
            use_expansion = True

        self.worker = RetrievalWorker(
            self.vector_store, query, methods, self.top_k_spin.value(), use_expansion
        )
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_search_error)
        self.worker.expanded_queries.connect(self.on_expanded_queries)
        self.worker.start()

    def on_expanded_queries(self, expanded: List[str]):
        """显示扩展后的查询"""
        if expanded and len(expanded) > 1:
            queries_str = " | ".join(f'"{q}"' for q in expanded)
            self.expanded_queries_label.setText(f"扩展查询: {queries_str}")
            self.expanded_queries_label.setStyleSheet(
                "color: #008000; font-weight: bold;"
            )
        else:
            self.expanded_queries_label.setText("扩展查询: 无扩展")

    def on_search_finished(self, results: Dict[str, Any]):
        """检索完成"""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("🔍 开始检索")

        total_results = sum(len(r) for r in results.values() if isinstance(r, list))
        self.stats_label.setText(f"检索完成，共返回 {total_results} 个结果")
        self.status_label.setText("检索完成")

        self.results_data = results

        # 更新各标签页
        for method_id, method_results in results.items():
            self.update_result_tab(method_id, method_results)

        # 切换到第一个有结果的标签页
        priority_order = [
            "hybrid_rrf_rerank_diversity",
            "hybrid_weighted_rerank_diversity",
            "hybrid_rrf_rerank_score",
            "hybrid_weighted_rerank_score",
            "vector_rerank_diversity",
            "vector_rerank_score",
            "hybrid_rrf",
            "hybrid_weighted",
            "bm25",
            "vector",
        ]
        for method_id in priority_order:
            if method_id in results and results[method_id]:
                self.tab_widget.setCurrentWidget(self.result_tabs[method_id])
                break

    def on_search_error(self, error: str):
        """检索错误"""
        self.search_btn.setEnabled(True)
        self.search_btn.setText("🔍 开始检索")
        self.stats_label.setText(f"检索失败: {error}")
        self.status_label.setText("检索失败")

    def update_result_tab(self, method_id: str, results: List[Dict]):
        """更新结果标签页"""
        table = self.get_table(method_id)
        if not table:
            return

        table.setRowCount(0)

        if not results:
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem("-"))
            table.setItem(0, 1, QTableWidgetItem("-"))
            table.setItem(0, 2, QTableWidgetItem("-"))
            table.setItem(0, 3, QTableWidgetItem("无结果"))
            return

        for i, result in enumerate(results):
            table.insertRow(i)

            if "error" in result:
                table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                table.setItem(i, 1, QTableWidgetItem("错误"))
                table.setItem(i, 2, QTableWidgetItem("-"))
                table.setItem(i, 3, QTableWidgetItem(result["error"]))
                continue

            # 排名
            rank_item = QTableWidgetItem(str(i + 1))
            rank_item.setData(Qt.UserRole, i)
            table.setItem(i, 0, rank_item)

            # 来源
            table.setItem(i, 1, QTableWidgetItem(result.get("source", "unknown")))

            # 分数 - 使用颜色区分
            score_item = QTableWidgetItem(f"{result.get('score', 0):.4f}")
            score = result.get("score", 0)
            if score >= 0.8:
                score_item.setBackground(QColor(144, 238, 144))  # 浅绿
            elif score >= 0.5:
                score_item.setBackground(QColor(255, 255, 144))  # 浅黄
            elif score > 0:
                score_item.setBackground(QColor(255, 200, 144))  # 浅橙
            table.setItem(i, 2, score_item)

            # 内容预览
            table.setItem(i, 3, QTableWidgetItem(result.get("content", "")))

        table.resizeColumnsToContents()
        table.setColumnWidth(3, 400)

    def show_detail(self, item: QTableWidgetItem, method_id: str):
        """显示详细信息"""
        if not hasattr(self, "results_data"):
            return

        results = self.results_data.get(method_id, [])
        row = item.row()

        if row < len(results):
            result = results[row]
            detail = self.detail_texts.get(method_id)
            if detail and "full_content" in result:
                detail.setPlainText(f"【完整内容】\n{result['full_content']}")

    def setStatusWidget(self, widget: QWidget):
        """设置状态栏"""
        self.statusBar().addPermanentWidget(widget)

    def create_evaluation_tab(self) -> QWidget:
        """创建评估标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 评估设置
        settings_layout = QHBoxLayout()

        # 评估K值
        settings_layout.addWidget(QLabel("评估K值:"))
        self.eval_k_spin = QSpinBox()
        self.eval_k_spin.setRange(1, 20)
        self.eval_k_spin.setValue(5)
        self.eval_k_spin.setToolTip("检索返回的文档数量")
        settings_layout.addWidget(self.eval_k_spin)

        # 评估方法选择
        settings_layout.addWidget(QLabel("评估方法:"))
        self.eval_methods = {}
        eval_method_names = [
            ("vector", "向量搜索"),
            ("vector_expanded", "向量+扩展"),
            ("bm25", "BM25"),
            ("hybrid_rrf", "混合(RRF)"),
            ("hybrid_weighted", "混合(加权)"),
        ]
        for method_id, method_name in eval_method_names:
            cb = QCheckBox(method_name)
            cb.setChecked(True)
            self.eval_methods[method_id] = cb
            settings_layout.addWidget(cb)

        settings_layout.addStretch()

        # 评估按钮
        self.eval_btn = QPushButton("🚀 开始评估")
        self.eval_btn.clicked.connect(self.do_evaluation)
        settings_layout.addWidget(self.eval_btn)

        layout.addLayout(settings_layout)

        # 测试用例信息
        self.eval_info_label = QLabel("测试用例数量: 0")
        self.eval_info_label.setStyleSheet(
            "padding: 5px; background: #f0f0f0; border-radius: 4px;"
        )
        layout.addWidget(self.eval_info_label)

        # 评估结果表格
        self.eval_results_table = QTableWidget()
        self.eval_results_table.setColumnCount(7)
        self.eval_results_table.setHorizontalHeaderLabels(
            ["方法", "Hit@K", "Precision@K", "Recall@K", "F1@K", "MRR@K", "NDCG@K"]
        )
        self.eval_results_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.eval_results_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.eval_results_table.setAlternatingRowColors(True)
        layout.addWidget(self.eval_results_table)

        # 详细结果
        detail_group = QGroupBox("各查询详细结果")
        detail_layout = QVBoxLayout()
        self.eval_detail_text = QTextEdit()
        self.eval_detail_text.setReadOnly(True)
        self.eval_detail_text.setMaximumHeight(200)
        detail_layout.addWidget(self.eval_detail_text)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        # 更新测试用例信息
        self._update_eval_info()

        return widget

    def _update_eval_info(self):
        """更新评估信息"""
        if hasattr(self, "evaluator") and self.evaluator:
            cases = self.evaluator.test_cases
            self.eval_info_label.setText(
                f"测试用例数量: {len(cases)} | "
                f"分类: {', '.join(set(c.category for c in cases if c.category)) or '全部'}"
            )

    def do_evaluation(self):
        """执行评估"""
        if not self.vector_store:
            self.eval_detail_text.setPlainText("向量数据库未初始化")
            return

        if not self.evaluator or not self.evaluator.test_cases:
            self.eval_detail_text.setPlainText("没有测试用例")
            return

        self.eval_btn.setEnabled(False)
        self.eval_btn.setText("评估中...")

        methods = {
            method_id: cb.isChecked() for method_id, cb in self.eval_methods.items()
        }
        if not any(methods.values()):
            self.eval_detail_text.setPlainText("请至少选择一种评估方法")
            self.eval_btn.setEnabled(True)
            self.eval_btn.setText("🚀 开始评估")
            return

        self.eval_worker = EvaluationWorker(
            self.vector_store,
            self.evaluator.test_cases,
            methods,
            self.eval_k_spin.value(),
            False,
        )
        self.eval_worker.finished.connect(self.on_evaluation_finished)
        self.eval_worker.progress.connect(self.on_evaluation_progress)
        self.eval_worker.error.connect(self.on_evaluation_error)
        self.eval_worker.start()

    def on_evaluation_progress(self, message: str, current: int, total: int):
        """评估进度更新"""
        self.eval_detail_text.setPlainText(f"{message} ({current}/{total})")

    def on_evaluation_finished(self, results_by_method: Dict, avg_metrics: Dict):
        """评估完成"""
        self.eval_btn.setEnabled(True)
        self.eval_btn.setText("🚀 开始评估")

        # 更新结果表格
        self.eval_results_table.setRowCount(0)

        method_display_names = {
            "vector": "向量搜索",
            "vector_expanded": "向量+扩展",
            "bm25": "BM25",
            "hybrid_rrf": "混合(RRF)",
            "hybrid_weighted": "混合(加权)",
        }

        for method_id, metrics in sorted(
            avg_metrics.items(), key=lambda x: x[1].get("F1@K", 0), reverse=True
        ):
            row = self.eval_results_table.rowCount()
            self.eval_results_table.insertRow(row)

            # 方法名
            name_item = QTableWidgetItem(method_display_names.get(method_id, method_id))
            self.eval_results_table.setItem(row, 0, name_item)

            # 各指标
            for col, key in enumerate(
                ["Hit@K", "Precision@K", "Recall@K", "F1@K", "MRR@K", "NDCG@K"], 1
            ):
                value = metrics.get(key, 0)
                item = QTableWidgetItem(f"{value:.4f}")

                # 高亮最佳结果
                if key == "F1@K" and value == max(
                    m.get(key, 0) for m in avg_metrics.values()
                ):
                    item.setBackground(QColor(144, 238, 144))
                elif value >= 0.8:
                    item.setBackground(QColor(200, 255, 200))
                elif value >= 0.5:
                    item.setBackground(QColor(255, 255, 200))

                self.eval_results_table.setItem(row, col, item)

        # 生成详细报告
        report = self.evaluator.generate_report(results_by_method)
        self.eval_detail_text.setPlainText(report)

    def on_evaluation_error(self, error: str):
        """评估错误"""
        self.eval_btn.setEnabled(True)
        self.eval_btn.setText("🚀 开始评估")
        self.eval_detail_text.setPlainText(f"评估出错: {error}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = RetrievalTestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
