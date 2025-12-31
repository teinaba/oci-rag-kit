"""
データパイプライン処理パッケージ

OCI Object Storageからのドキュメント取得、テキスト抽出、チャンク化、
埋め込み生成、データベース書き込みまでの一連の処理を提供します。
"""

from .document_loader import DocumentLoader, DocumentMetadata
from .exceptions import (
    DataPipelineError,
    DocumentLoaderError,
    TextExtractionError,
    ChunkingError,
    EmbeddingError,
    DocumentWriteError
)

__all__ = [
    # Classes
    'DocumentLoader',
    'DocumentMetadata',
    # Exceptions
    'DataPipelineError',
    'DocumentLoaderError',
    'TextExtractionError',
    'ChunkingError',
    'EmbeddingError',
    'DocumentWriteError',
]
