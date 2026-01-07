"""
RAG処理パッケージ

Oracle Database 26aiのベクトル検索、日本語リランキング、LLM生成、
RAGAS評価までの一連のRAG処理を提供します。
"""

from .vector_searcher import VectorSearcher, SearchResult
from .exceptions import (
    RAGError,
    VectorSearchError,
    RerankError,
    AnswerGenerationError,
    RateLimitError,
    EvaluationError,
    ExcelHandlerError
)

__all__ = [
    # Classes
    'VectorSearcher',
    'SearchResult',
    # Exceptions
    'RAGError',
    'VectorSearchError',
    'RerankError',
    'AnswerGenerationError',
    'RateLimitError',
    'EvaluationError',
    'ExcelHandlerError',
]
