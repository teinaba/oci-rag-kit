"""
テキスト抽出モジュール

このモジュールは、PDF、TXT、CSVファイルからテキストを抽出する機能を提供します。
エンコーディングの自動検出（UTF-8 → Shift-JIS フォールバック）をサポートしています。
"""
from dataclasses import dataclass
from typing import Optional
import tempfile
import os
import logging
from langchain_community.document_loaders import PyMuPDFLoader
from .exceptions import TextExtractionError


@dataclass
class ExtractedText:
    """
    抽出されたテキストのメタデータ

    Attributes:
        content: 抽出されたテキスト内容
        filename: ファイル名
        content_type: ファイルタイプ ('pdf', 'txt', 'csv')
        encoding: 検出されたエンコーディング（TXT/CSVのみ、オプション）
        char_count: 文字数（オプション）
    """
    content: str
    filename: str
    content_type: str
    encoding: Optional[str] = None
    char_count: Optional[int] = None


class TextExtractor:
    """
    バイナリコンテンツからテキストを抽出するクラス

    サポート形式:
    - PDF: PyMuPDFLoaderを使用してテキストを抽出
    - TXT: UTF-8 → Shift-JIS フォールバックでデコード
    - CSV: TXTと同様のエンコーディング検出

    Example:
        >>> extractor = TextExtractor()
        >>> with open('document.pdf', 'rb') as f:
        ...     content = f.read()
        >>> result = extractor.extract(content, 'pdf', 'document.pdf')
        >>> print(result.content)
    """

    def __init__(self):
        """
        TextExtractorを初期化します

        ロガーを設定し、テキスト抽出の準備を行います。
        """
        self.logger = logging.getLogger(__name__)

    def extract(
        self,
        content: bytes,
        content_type: str,
        filename: str
    ) -> ExtractedText:
        """
        ファイル形式に応じてテキスト抽出を実行します

        Args:
            content: バイナリコンテンツ
            content_type: ファイルタイプ ('pdf', 'txt', 'csv')
            filename: ファイル名（エラーメッセージ用）

        Returns:
            ExtractedText: 抽出されたテキストとメタデータ

        Raises:
            TextExtractionError: 抽出に失敗した場合、または未サポート形式の場合
        """
        try:
            if content_type == 'pdf':
                return self._extract_pdf(content, filename)
            elif content_type in ('txt', 'csv'):
                return self._extract_text(content, filename, content_type)
            else:
                raise TextExtractionError(
                    f"Unsupported file type: {content_type}"
                )
        except TextExtractionError:
            raise
        except Exception as e:
            raise TextExtractionError(
                f"Failed to extract text from '{filename}': {str(e)}"
            ) from e

    def _extract_pdf(self, pdf_content: bytes, filename: str) -> ExtractedText:
        """
        PDFコンテンツからテキストを抽出します

        一時ファイルを作成してPyMuPDFLoaderで処理します。
        処理後は一時ファイルを必ずクリーンアップします。

        Args:
            pdf_content: PDFのバイナリデータ
            filename: ファイル名

        Returns:
            ExtractedText: 抽出されたテキスト

        Raises:
            TextExtractionError: PDF抽出に失敗した場合
        """
        temp_file_path = None
        try:
            # 一時ファイル作成
            with tempfile.NamedTemporaryFile(
                suffix='.pdf',
                delete=False
            ) as temp_file:
                temp_file.write(pdf_content)
                temp_file.flush()
                temp_file_path = temp_file.name

            # PyMuPDFLoaderで読み込み
            loader = PyMuPDFLoader(temp_file_path)
            documents = loader.load()

            # 全ページのテキストを結合
            text = ""
            for doc in documents:
                text += doc.page_content

            return ExtractedText(
                content=text,
                filename=filename,
                content_type='pdf',
                char_count=len(text)
            )

        except Exception as e:
            raise TextExtractionError(
                f"Failed to extract PDF '{filename}': {str(e)}"
            ) from e

        finally:
            # 一時ファイルのクリーンアップ
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to delete temp file {temp_file_path}: {e}"
                    )

    def _extract_text(
        self,
        text_content: bytes,
        filename: str,
        content_type: str
    ) -> ExtractedText:
        """
        TXT/CSVコンテンツからテキストを抽出します

        エンコーディング検出（UTF-8 → Shift-JIS フォールバック）を実行します。

        Args:
            text_content: テキストのバイナリデータ
            filename: ファイル名
            content_type: 'txt' または 'csv'

        Returns:
            ExtractedText: 抽出されたテキスト

        Raises:
            TextExtractionError: デコードに失敗した場合
        """
        # UTF-8を試す
        try:
            text = text_content.decode('utf-8')
            encoding = 'utf-8'
        except UnicodeDecodeError:
            # Shift-JISへのフォールバック
            try:
                text = text_content.decode('shift_jis')
                encoding = 'shift_jis'
            except UnicodeDecodeError as e:
                raise TextExtractionError(
                    f"Failed to decode '{filename}': "
                    f"not UTF-8 or Shift-JIS"
                ) from e

        return ExtractedText(
            content=text,
            filename=filename,
            content_type=content_type,
            encoding=encoding,
            char_count=len(text)
        )
