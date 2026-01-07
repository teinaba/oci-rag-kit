"""
RAG処理パッケージ

Oracle Database 26aiのベクトル検索、日本語リランキング、LLM生成、
RAGAS評価までの一連のRAG処理を提供します。
"""

from .vector_searcher import VectorSearcher, SearchResult
from .rag_pipeline import RAGPipeline, RAGResult, BatchResult
from .excel_handler import ExcelHandler
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
    'RAGPipeline',
    'RAGResult',
    'BatchResult',
    'ExcelHandler',
    # Exceptions
    'RAGError',
    'VectorSearchError',
    'RerankError',
    'AnswerGenerationError',
    'RateLimitError',
    'EvaluationError',
    'ExcelHandlerError',
]
