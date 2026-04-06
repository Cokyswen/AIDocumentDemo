# 项目介绍 - 桌面文档问答应用

## 项目描述

一个基于 RAG（检索增强生成）技术的桌面文档问答应用，支持对本地文档进行向量化存储、智能检索和 AI 对话问答。

## 工作内容

● 基于 PySide6 搭建桌面界面，实现用户交互与文档管理，提升开发效率与系统可维护性。

● 采用 ChromaDB 设计向量存储层，结合 sentence-transformers 多语言嵌入模型实现文档向量化，采用本地文件方式实现持久化存储，提升信息检索效率与系统扩展性。

● 实现多种检索策略（向量检索、BM25 关键词检索、混合搜索、重排序、查询扩展），支持 10+ 种检索方式对比，显著提升检索准确性。

● 设计并实现 RAG 评估模块（Hit@K、Precision@K、Recall@K、F1@K、MRR、NDCG），量化评估检索效果，优化系统性能。

● 实现引用溯源功能，AI 回复时显示参考文档来源、相关性分数与内容预览，增强回答可信度。

● 优化中文分词与多语言嵌入模型支持，采用 jieba 分词与 paraphrase-multilingual-MiniLM-L12-v2 模型，显著提升中文检索效果。

## 技术栈

- **GUI**: PySide6
- **向量数据库**: ChromaDB
- **嵌入模型**: sentence-transformers
- **BM25**: rank-bm25
- **LLM**: OpenAI API (GLM-4-Flash)
- **文档解析**: PyPDF2, pymupdf, python-docx