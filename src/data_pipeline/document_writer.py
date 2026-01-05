"""
データベース書き込みモジュール

このモジュールは、ドキュメントとチャンクをOracle Databaseに保存します。
"""
from dataclasses import dataclass
from typing import List, Any
import logging
import oracledb
from .exceptions import DocumentWriteError


@dataclass
class SavedDocument:
    """
    保存されたドキュメントのメタデータ

    Attributes:
        document_id: 生成されたドキュメントID（bytes）
        filename: ファイル名
        content_type: コンテンツタイプ
    """
    document_id: bytes
    filename: str
    content_type: str


@dataclass
class SavedChunks:
    """
    保存されたチャンクの統計情報

    Attributes:
        document_id: ドキュメントID（bytes）
        chunk_count: 保存されたチャンク数
    """
    document_id: bytes
    chunk_count: int


class DocumentWriter:
    """
    ドキュメントとチャンクをデータベースに書き込むクラス

    設計:
    - NOT Singleton: 異なるDB接続で複数インスタンス可能
    - Dependency Injection: DB接続を外部から注入
    - Transaction management: 呼び出し側がcommitを制御

    Example:
        >>> import oracledb
        >>> connection = oracledb.connect(**db_params)
        >>> writer = DocumentWriter(connection)
        >>> doc = writer.save_document('test.pdf', 'folder', 'pdf', 1024, 500)
        >>> chunks_result = writer.save_chunks(doc.document_id, chunks, embeddings)
    """

    def __init__(self, connection: Any):
        """
        DocumentWriterを初期化

        Args:
            connection: oracledb接続オブジェクト

        Raises:
            ValueError: 接続がNoneの場合
        """
        if connection is None:
            raise ValueError("connection is required")

        self.connection = connection
        self.logger = logging.getLogger(__name__)

    def save_document(
        self,
        filename: str,
        filtering: str,
        content_type: str,
        file_size: int,
        text_length: int
    ) -> SavedDocument:
        """
        source_documentsテーブルにドキュメント情報を保存

        Args:
            filename: ファイル名
            filtering: ソースの種類（フォルダ名など）
            content_type: ファイルタイプ（pdf, txt, csvなど）
            file_size: ファイルサイズ（バイト単位）
            text_length: テキストの文字数

        Returns:
            SavedDocument: 保存されたドキュメントのメタデータ

        Raises:
            DocumentWriteError: 保存に失敗した場合
        """
        try:
            # Validate required parameters
            if not filename:
                raise DocumentWriteError("filename cannot be empty")
            if not content_type:
                raise DocumentWriteError("content_type cannot be empty")

            sql_insert = """
                INSERT INTO source_documents (
                    filename,
                    filtering,
                    content_type,
                    file_size,
                    text_length,
                    registered_date
                ) VALUES (
                    :filename,
                    :filtering,
                    :content_type,
                    :file_size,
                    :text_length,
                    CAST(systimestamp AT TIME ZONE 'Asia/Tokyo' AS timestamp)
                )
                RETURNING document_id INTO :document_id
            """

            # Create output variable for RETURNING clause
            document_id_var = self.connection.cursor().var(oracledb.DB_TYPE_RAW)

            with self.connection.cursor() as cursor:
                cursor.execute(
                    sql_insert,
                    filename=filename,
                    filtering=filtering,
                    content_type=content_type,
                    file_size=file_size,
                    text_length=text_length,
                    document_id=document_id_var
                )
                self.connection.commit()
                document_id = document_id_var.getvalue()[0]

                self.logger.info(
                    f"Saved document: {filename} (ID: {document_id.hex() if document_id else 'N/A'})"
                )

                return SavedDocument(
                    document_id=document_id,
                    filename=filename,
                    content_type=content_type
                )

        except DocumentWriteError:
            raise
        except Exception as e:
            raise DocumentWriteError(
                f"Failed to save document '{filename}': {str(e)}"
            ) from e

    def save_chunks(
        self,
        document_id: bytes,
        chunks: List[str],
        embeddings: List[str]
    ) -> SavedChunks:
        """
        chunksテーブルにチャンクとベクトルを一括保存

        Args:
            document_id: ドキュメントID
            chunks: チャンクテキストのリスト
            embeddings: ベクトルのリスト（文字列形式）

        Returns:
            SavedChunks: 保存統計情報

        Raises:
            DocumentWriteError: 保存に失敗した場合
        """
        try:
            # Validate input
            if len(chunks) != len(embeddings):
                raise DocumentWriteError(
                    f"chunks and embeddings must have the same length "
                    f"(got {len(chunks)} chunks and {len(embeddings)} embeddings)"
                )

            # Handle empty lists
            if not chunks:
                self.logger.info("No chunks to save (empty list)")
                return SavedChunks(
                    document_id=document_id,
                    chunk_count=0
                )

            sql_insert = """
                INSERT INTO chunks (
                    document_id,
                    chunk_text,
                    embedding,
                    registered_date
                ) VALUES (
                    :document_id,
                    :chunk_text,
                    TO_VECTOR(:embedding),
                    CAST(systimestamp AT TIME ZONE 'Asia/Tokyo' AS timestamp)
                )
            """

            with self.connection.cursor() as cursor:
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    cursor.execute(
                        sql_insert,
                        document_id=document_id,
                        chunk_text=chunk,
                        embedding=embedding
                    )
                    self.logger.debug(f"Saved chunk {i+1}/{len(chunks)}")

                self.connection.commit()

                self.logger.info(
                    f"Saved {len(chunks)} chunks for document "
                    f"ID: {document_id.hex() if document_id else 'N/A'}"
                )

                return SavedChunks(
                    document_id=document_id,
                    chunk_count=len(chunks)
                )

        except DocumentWriteError:
            raise
        except Exception as e:
            doc_id_str = document_id.hex() if document_id else 'N/A'
            raise DocumentWriteError(
                f"Failed to save chunks for document {doc_id_str}: {str(e)}"
            ) from e
