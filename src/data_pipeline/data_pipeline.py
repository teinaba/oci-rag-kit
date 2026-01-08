"""
データパイプライン オーケストレータ

このモジュールは、Object Storageからデータベースストレージまでの
ドキュメント処理において、すべてのデータパイプラインコンポーネントを調整します。
"""
from dataclasses import dataclass
from typing import List, Optional, Callable, Any
import logging
import time
from .document_loader import DocumentLoader
from .text_extractor import TextExtractor
from .text_chunker import TextChunker
from .embedding_generator import EmbeddingGenerator
from .document_writer import DocumentWriter
from .exceptions import (
    DocumentLoaderError,
    TextExtractionError,
    ChunkingError,
    EmbeddingError,
    DocumentWriteError,
    DataPipelineError
)


@dataclass
class ProcessedDocument:
    """
    単一ドキュメントの処理結果

    Attributes:
        filename: ドキュメントのファイル名
        status: 処理ステータス ('success' | 'failed' | 'skipped')
        document_id: 生成されたドキュメントID（bytes）、またはNone
        chunks_saved: 保存されたチャンク数
        error: 失敗時のエラーメッセージ、成功時はNone
    """
    filename: str
    status: str
    document_id: Optional[bytes]
    chunks_saved: int
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """
    パイプライン全体の実行結果

    Attributes:
        total_files: 処理されたファイルの総数
        successful: 正常に処理されたファイル数
        failed: 失敗したファイル数
        skipped: スキップされたファイル数
        total_chunks: 全ファイルで生成された総チャンク数
        processed_docs: 個別のドキュメント結果のリスト
        elapsed_time: 総処理時間（秒）
    """
    total_files: int
    successful: int
    failed: int
    skipped: int
    total_chunks: int
    processed_docs: List[ProcessedDocument]
    elapsed_time: float


class DataPipeline:
    """
    すべてのコンポーネントを調整するデータパイプライン オーケストレータ

    このクラスは、データ取り込みパイプライン全体を統括します：
    1. DocumentLoader - Object Storageからのダウンロード
    2. TextExtractor - PDF/TXT/CSVからテキスト抽出
    3. TextChunker - チャンクへの分割
    4. EmbeddingGenerator - 埋め込みベクトルの生成
    5. DocumentWriter - データベースへの保存

    設計:
    - NOT Singleton: 異なる設定で複数のパイプライン可能
    - Composition: 5つのコンポーネントクラスすべてを使用
    - Error Isolation: 1つのファイルが失敗しても処理を継続
    - Progress Tracking: 監視用のオプションのコールバック

    Example:
        >>> loader = DocumentLoader(oci_config, bucket, namespace)
        >>> extractor = TextExtractor()
        >>> chunker = TextChunker(chunk_size=500)
        >>> embedding_gen = EmbeddingGenerator()
        >>> writer = DocumentWriter(connection)
        >>>
        >>> pipeline = DataPipeline(
        ...     loader=loader,
        ...     extractor=extractor,
        ...     chunker=chunker,
        ...     embedding_gen=embedding_gen,
        ...     writer=writer
        ... )
        >>>
        >>> files = loader.list_files()
        >>> result = pipeline.process_all(files)
        >>> print(f"Processed: {result.successful}/{result.total_files}")
    """

    def __init__(
        self,
        loader: DocumentLoader,
        extractor: TextExtractor,
        chunker: TextChunker,
        embedding_gen: EmbeddingGenerator,
        writer: DocumentWriter,
        progress_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        DataPipelineオーケストレータを初期化

        Args:
            loader: DocumentLoaderインスタンス
            extractor: TextExtractorインスタンス
            chunker: TextChunkerインスタンス
            embedding_gen: EmbeddingGeneratorインスタンス
            writer: DocumentWriterインスタンス
            progress_callback: オプションのコールバック(filename, status)

        Raises:
            ValueError: 必須コンポーネントがNoneの場合
        """
        if loader is None:
            raise ValueError("loader is required")
        if extractor is None:
            raise ValueError("extractor is required")
        if chunker is None:
            raise ValueError("chunker is required")
        if embedding_gen is None:
            raise ValueError("embedding_gen is required")
        if writer is None:
            raise ValueError("writer is required")

        self.loader = loader
        self.extractor = extractor
        self.chunker = chunker
        self.embedding_gen = embedding_gen
        self.writer = writer
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)

    def process_single(self, file_path: str) -> ProcessedDocument:
        """
        パイプラインを通じて単一ドキュメントを処理

        Args:
            file_path: Object Storageのファイルパス

        Returns:
            ProcessedDocument: ステータスとメタデータを含む処理結果
        """
        try:
            # ステップ1: Object Storageからダウンロード
            self.logger.info(f"Processing: {file_path}")
            doc_metadata = self.loader.download_file(file_path)

            # ステップ2: テキスト抽出
            extracted = self.extractor.extract(
                content=doc_metadata.content,
                filename=doc_metadata.filename,
                content_type=doc_metadata.content_type
            )

            # ステップ3: テキストをチャンク化
            chunked = self.chunker.chunk(extracted.content)

            # 空のチャンクを処理
            if not chunked.chunks:
                self.logger.warning(f"No chunks created for {doc_metadata.filename}")
                result = ProcessedDocument(
                    filename=doc_metadata.filename,
                    status='skipped',
                    document_id=None,
                    chunks_saved=0,
                    error="No chunks created from text"
                )
                if self.progress_callback:
                    self.progress_callback(doc_metadata.filename, 'skipped')
                return result

            # ステップ4: 埋め込みベクトル生成
            embeddings = []
            for chunk in chunked.chunks:
                embedding = self.embedding_gen.embed_query(chunk)
                embeddings.append(embedding.vector_str)

            # ステップ5: データベースへの保存
            # 5a. ドキュメントメタデータを保存
            saved_doc = self.writer.save_document(
                filename=doc_metadata.filename,
                filtering=self._extract_filtering(doc_metadata.full_path),
                content_type=self._extract_content_type(doc_metadata.content_type),
                file_size=doc_metadata.file_size,
                text_length=len(extracted.content)
            )

            # 5b. チャンクと埋め込みベクトルを保存
            saved_chunks = self.writer.save_chunks(
                document_id=saved_doc.document_id,
                chunks=chunked.chunks,
                embeddings=embeddings
            )

            self.logger.info(
                f"Successfully processed {doc_metadata.filename}: "
                f"{saved_chunks.chunk_count} chunks"
            )

            result = ProcessedDocument(
                filename=doc_metadata.filename,
                status='success',
                document_id=saved_doc.document_id,
                chunks_saved=saved_chunks.chunk_count
            )

            if self.progress_callback:
                self.progress_callback(doc_metadata.filename, 'success')

            return result

        except TextExtractionError as e:
            # サポートされていないファイルタイプ - スキップ
            filename = file_path.split('/')[-1]
            self.logger.warning(f"Skipping {filename}: {str(e)}")
            result = ProcessedDocument(
                filename=filename,
                status='skipped',
                document_id=None,
                chunks_saved=0,
                error=str(e)
            )
            if self.progress_callback:
                self.progress_callback(filename, 'skipped')
            return result

        except (DocumentLoaderError, ChunkingError, EmbeddingError, DocumentWriteError) as e:
            # 既知のパイプラインエラー - 失敗としてマーク
            filename = file_path.split('/')[-1]
            self.logger.error(f"Failed to process {filename}: {str(e)}")
            result = ProcessedDocument(
                filename=filename,
                status='failed',
                document_id=None,
                chunks_saved=0,
                error=str(e)
            )
            if self.progress_callback:
                self.progress_callback(filename, 'failed')
            return result

        except Exception as e:
            # 予期しないエラー - 失敗としてマーク
            filename = file_path.split('/')[-1]
            self.logger.error(f"Unexpected error processing {filename}: {str(e)}")
            result = ProcessedDocument(
                filename=filename,
                status='failed',
                document_id=None,
                chunks_saved=0,
                error=f"Unexpected error: {str(e)}"
            )
            if self.progress_callback:
                self.progress_callback(filename, 'failed')
            return result

    def process_all(self, file_paths: List[str]) -> PipelineResult:
        """
        パイプラインを通じて複数ドキュメントを処理

        Args:
            file_paths: Object Storageのファイルパスのリスト

        Returns:
            PipelineResult: 全体的な処理統計と結果
        """
        start_time = time.time()

        processed_docs = []
        successful = 0
        failed = 0
        skipped = 0
        total_chunks = 0

        self.logger.info(f"Starting pipeline processing: {len(file_paths)} files")

        for file_path in file_paths:
            result = self.process_single(file_path)
            processed_docs.append(result)

            if result.status == 'success':
                successful += 1
                total_chunks += result.chunks_saved
            elif result.status == 'failed':
                failed += 1
            elif result.status == 'skipped':
                skipped += 1

        elapsed_time = time.time() - start_time

        self.logger.info(
            f"Pipeline complete: {successful} success, {failed} failed, "
            f"{skipped} skipped, {total_chunks} total chunks, "
            f"{elapsed_time:.2f}s elapsed"
        )

        return PipelineResult(
            total_files=len(file_paths),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_chunks=total_chunks,
            processed_docs=processed_docs,
            elapsed_time=elapsed_time
        )

    def _extract_filtering(self, full_path: str) -> str:
        """
        フルパスからフィルタリング（フォルダ名）を抽出

        Args:
            full_path: Object Storageのフルパス（例: 'folder/file.pdf'）

        Returns:
            フォルダ名、または空文字列
        """
        parts = full_path.split('/')
        if len(parts) > 1:
            return parts[0]
        return ''

    def _extract_content_type(self, mime_type: str) -> str:
        """
        MIMEタイプからシンプルなコンテンツタイプを抽出

        Args:
            mime_type: MIMEタイプ（例: 'application/pdf'）

        Returns:
            シンプルなタイプ（例: 'pdf'）
        """
        # 一般的なMIMEタイプをマッピング
        mime_map = {
            'application/pdf': 'pdf',
            'text/plain': 'txt',
            'text/csv': 'csv',
            'application/csv': 'csv'
        }

        return mime_map.get(mime_type, mime_type.split('/')[-1])
