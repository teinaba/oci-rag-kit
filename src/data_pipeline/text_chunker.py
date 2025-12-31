"""
テキスト分割モジュール

このモジュールは、抽出されたテキストを指定サイズのチャンクに分割し、
オーバーラップを考慮して処理します。日本語対応の区切り文字を使用します。
"""
from dataclasses import dataclass
from typing import List, Optional
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .exceptions import ChunkingError


@dataclass
class ChunkedText:
    """
    チャンク化されたテキストのメタデータ

    Attributes:
        chunks: チャンクのリスト（文字列）
        original_text_length: 元テキストの文字数
        chunk_count: チャンク数
        chunk_size: 使用されたチャンクサイズ
        chunk_overlap: 使用されたオーバーラップサイズ
        avg_chunk_length: 平均チャンク長（オプション）
    """
    chunks: List[str]
    original_text_length: int
    chunk_count: int
    chunk_size: int
    chunk_overlap: int
    avg_chunk_length: Optional[float] = None


class TextChunker:
    """
    テキストをチャンクに分割するクラス

    日本語対応のセパレータでRecursiveCharacterTextSplitterを使用します。

    設計:
    - NOT Singleton: 異なる設定で複数インスタンス可能
    - Lazy initialization: RecursiveCharacterTextSplitterは初回アクセス時に生成
    - Parameter validation: コンストラクタで検証

    Example:
        >>> chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        >>> result = chunker.chunk("長いテキスト...")
        >>> print(f"Chunks: {result.chunk_count}")
    """

    # Class constant - Japanese-aware separators
    DEFAULT_SEPARATORS = ["\n\n", "\n", "。", "、", " ", ""]

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[List[str]] = None
    ):
        """
        TextChunkerを初期化

        Args:
            chunk_size: チャンクサイズ（文字数）
            chunk_overlap: オーバーラップサイズ（文字数）
            separators: カスタムセパレータ（デフォルト: 日本語対応セパレータ）

        Raises:
            ValueError: パラメータが無効な場合
        """
        # Parameter validation
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be > 0, got {chunk_size}")
        if chunk_overlap < 0:
            raise ValueError(f"chunk_overlap must be >= 0, got {chunk_overlap}")
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators if separators is not None else self.DEFAULT_SEPARATORS
        self._splitter: Optional[RecursiveCharacterTextSplitter] = None
        self.logger = logging.getLogger(__name__)

    @property
    def splitter(self) -> RecursiveCharacterTextSplitter:
        """
        RecursiveCharacterTextSplitterを取得（遅延初期化）

        Returns:
            初期化済みのRecursiveCharacterTextSplitter
        """
        if self._splitter is None:
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.separators,
                length_function=len
            )
        return self._splitter

    def chunk(self, text: str) -> ChunkedText:
        """
        テキストをチャンクに分割

        Args:
            text: 分割対象のテキスト

        Returns:
            ChunkedText: チャンクとメタデータ

        Raises:
            ChunkingError: チャンク化に失敗した場合
        """
        try:
            # Input validation
            if not isinstance(text, str):
                raise ChunkingError(
                    f"Input must be str, got {type(text).__name__}"
                )

            # Handle empty text
            if not text:
                self.logger.warning("Empty text provided for chunking")
                return ChunkedText(
                    chunks=[],
                    original_text_length=0,
                    chunk_count=0,
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    avg_chunk_length=0.0
                )

            # Execute chunking
            chunks = self.splitter.split_text(text)

            # Calculate statistics
            avg_length = (
                sum(len(c) for c in chunks) / len(chunks) if chunks else 0.0
            )

            return ChunkedText(
                chunks=chunks,
                original_text_length=len(text),
                chunk_count=len(chunks),
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                avg_chunk_length=avg_length
            )

        except ChunkingError:
            raise
        except Exception as e:
            text_length = len(text) if isinstance(text, str) else "N/A"
            raise ChunkingError(
                f"Failed to chunk text (length={text_length}): {str(e)}"
            ) from e
