"""
查询扩展模块 - 通过同义词和语义扩展提高召回率
"""

import logging
import re
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)

# 常见中文同义词词典
SYNONYM_DICT: Dict[str, List[str]] = {
    # 种植相关
    "种植": ["栽种", "播种", "栽培", "种花", "种菜", "种树"],
    "种花": ["种植", "养花", "栽花"],
    "种菜": ["种植", "种菜", "种田"],
    "花草": ["植物", "花卉", "绿植"],
    "植物": ["花草", "绿植", "植被"],
    # 计算机相关
    "电脑": ["计算机", "笔记本", "PC"],
    "计算机": ["电脑", "笔记本", "PC"],
    "手机": ["移动电话", "智能手机", "移动设备"],
    "服务器": ["服务机", "主机", "server"],
    "数据库": ["资料库", "DB", "数据仓库"],
    "软件": ["程序", "应用", "应用程序", "app"],
    "硬件": ["硬件设备", "设备", "配件"],
    # 网络相关
    "网络": ["互联网", "因特网", "网路", "网络连接"],
    "网站": ["站点", " webpage"],
    "博客": ["blog", "博文", "日志"],
    "服务器": ["server", "服务端", "后端"],
    # 数据相关
    "数据": ["信息", "资料", "数据信息"],
    "存储": ["储存", "存储器", "保存"],
    "文件": ["文档", "档案", "file"],
    # AI相关
    "人工智能": ["AI", "机器智能", "智能"],
    "机器学习": ["ML", "机器学习算法", "机器学习技术"],
    "深度学习": ["DL", "深度神经网络", "deep learning"],
    # 文档相关
    "文档": ["文件", "文档资料", "doc"],
    "查询": ["搜索", "检索", "查找", "search"],
    "用户": ["使用者", "客户", "user"],
    "系统": ["体系", "系统软件", "system"],
    # 安装配置
    "安装": ["部署", "搭建", "配置", "setup", "install"],
    "配置": ["设置", "config", "setup"],
    "编译": ["构建", "build", "编译"],
    "运行": ["启动", "执行", "run", "execute"],
    # 编程相关
    "代码": ["程序", "源码", "源代码", "code"],
    "函数": ["方法", "函数方法", "function"],
    "驱动": ["驱动程序", "driver", "驱动程式"],
    "内核": ["kernel", "核心"],
}

# 语义相关词扩展 - 更广泛的关联词
SEMANTIC_RELATED: Dict[str, List[str]] = {
    "种植": [
        "郁金香",
        "向日葵",
        "种子",
        "种球",
        "花盆",
        "土壤",
        "浇水",
        "发芽",
        "春化",
        "五度球",
        "自然球",
    ],
    "植物": ["种植", "养护", "浇水", "施肥", "土壤", "阳光", "生长", "发芽", "开花"],
    "Linux": ["内核", "Ubuntu", "CentOS", "Manjaro", "Shell", "命令", "终端"],
    "makefile": ["编译", "Makefile", "make", "gcc", "构建", "目标", "依赖", "自动化"],
    "内核驱动": [
        "Linux",
        "字符设备",
        "块设备",
        "设备号",
        "file_operations",
        "驱动开发",
    ],
    "数据库": ["MySQL", "SQL", "增删改查", "表", "字段", "索引", "查询优化"],
    "博客": ["文章", "写作", "Markdown", "Hexo", "博客搭建", "技术分享"],
    "NanoHTTPD": ["HTTP", "服务器", "Java", "Web", "HTTP服务器", "轻量级服务器"],
    "Streamlit": ["Python", "Web应用", "数据可视化", "仪表盘", "前端"],
    "Manjaro": ["Linux", "Arch", "安装", "系统配置", "桌面环境"],
}


class QueryExpander:
    """查询扩展器"""

    def __init__(
        self,
        synonym_dict: Optional[Dict[str, List[str]]] = None,
        semantic_related: Optional[Dict[str, List[str]]] = None,
        max_expansion_terms: int = 5,
        use_synonym: bool = True,
        use_semantic: bool = True,
    ):
        """
        初始化查询扩展器

        Args:
            synonym_dict: 同义词词典
            semantic_related: 语义相关词词典
            max_expansion_terms: 最大扩展词数
            use_synonym: 是否使用同义词扩展
            use_semantic: 是否使用语义相关词扩展
        """
        self.synonym_dict = synonym_dict or SYNONYM_DICT
        self.semantic_related = semantic_related or SEMANTIC_RELATED
        self.max_expansion_terms = max_expansion_terms
        self.use_synonym = use_synonym
        self.use_semantic = use_semantic

    def expand(self, query: str) -> List[str]:
        """
        扩展查询，返回扩展后的查询列表

        Args:
            query: 原始查询

        Returns:
            扩展后的查询列表，包含原始查询
        """
        expanded = set()
        expanded.add(query)

        terms = self._tokenize(query)

        for term in terms:
            if self.use_synonym:
                synonyms = self._get_synonyms(term)
                expanded.update(synonyms)

            if self.use_semantic:
                related = self._get_semantic_related(term)
                expanded.update(related)

        expanded_list = list(expanded)
        if len(expanded_list) > self.max_expansion_terms + 1:
            expanded_list = [query] + list(expanded - {query})[
                : self.max_expansion_terms
            ]

        return expanded_list

    def expand_with_queries(self, query: str) -> List[str]:
        """
        生成扩展后的完整查询语句

        Args:
            query: 原始查询

        Returns:
            扩展后的查询列表，每个元素是一个完整查询
        """
        expanded_terms = set()
        terms = self._tokenize(query)

        for term in terms:
            if self.use_synonym:
                expanded_terms.update(self._get_synonyms(term))
            if self.use_semantic:
                expanded_terms.update(self._get_semantic_related(term))

        expanded_queries = [query]
        for term in expanded_terms:
            if term != query and len(term) >= 2:
                expanded_queries.append(term)

        if len(expanded_queries) > self.max_expansion_terms + 1:
            expanded_queries = expanded_queries[: self.max_expansion_terms + 1]

        return expanded_queries

    def _get_synonyms(self, term: str) -> List[str]:
        """获取同义词"""
        synonyms = []
        term_lower = term.lower()

        if term in self.synonym_dict:
            synonyms.extend(self.synonym_dict[term])

        if term_lower in self.synonym_dict:
            synonyms.extend(self.synonym_dict[term_lower])

        for key, values in self.synonym_dict.items():
            if term_lower in values or term in values:
                synonyms.append(key)
                synonyms.extend(values)

        return list(set(synonyms))

    def _get_semantic_related(self, term: str) -> List[str]:
        """获取语义相关词"""
        related = []
        term_lower = term.lower()

        for key, values in self.semantic_related.items():
            if term_lower in key.lower() or key.lower() in term_lower:
                related.extend(values)
            if term_lower in [v.lower() for v in values]:
                related.append(key)
                related.extend(values)

        return list(set(related))

    def _tokenize(self, text: str) -> List[str]:
        """分词 - 支持中英文"""
        english_words = re.findall(r"[a-zA-Z0-9_]+", text)

        chinese_text = re.sub(r"[a-zA-Z0-9_\s]", "", text)
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", chinese_text)

        chinese_words = re.findall(r"[\u4e00-\u9fff]{2,}", chinese_text)

        chinese_bigrams = []
        for i in range(len(chinese_chars) - 1):
            bigram = chinese_chars[i] + chinese_chars[i + 1]
            chinese_bigrams.append(bigram)

        return english_words + chinese_words + chinese_bigrams

    def add_synonym(self, term: str, synonyms: List[str]):
        """添加同义词"""
        if term in self.synonym_dict:
            existing = set(self.synonym_dict[term])
            existing.update(synonyms)
            self.synonym_dict[term] = list(existing)
        else:
            self.synonym_dict[term] = synonyms

    def add_semantic_related(self, term: str, related: List[str]):
        """添加语义相关词"""
        if term in self.semantic_related:
            existing = set(self.semantic_related[term])
            existing.update(related)
            self.semantic_related[term] = list(existing)
        else:
            self.semantic_related[term] = related


def expand_query(query: str, max_terms: int = 5) -> List[str]:
    """
    便捷函数：扩展查询

    Args:
        query: 原始查询
        max_terms: 最大扩展词数

    Returns:
        扩展后的查询列表
    """
    expander = QueryExpander(max_expansion_terms=max_terms)
    return expander.expand_with_queries(query)
