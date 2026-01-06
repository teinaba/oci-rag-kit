"""
Unit tests for TextExtractor class

This module contains comprehensive tests for the TextExtractor class,
which extracts text from PDF, TXT, and CSV files with encoding detection.
"""
import pytest
from unittest.mock import Mock, patch
from src.data_pipeline.text_extractor import TextExtractor, ExtractedText
from src.data_pipeline.exceptions import TextExtractionError


class TestTextExtractorInit:
    """コンストラクタの検証"""

    def test_initialization(self):
        """初期化できることを確認"""
        extractor = TextExtractor()
        assert extractor is not None
        assert extractor.logger is not None


class TestExtract:
    """ディスパッチロジックのテスト"""

    def test_extract_routes_to_pdf_extractor(self):
        """PDFファイルがPDF抽出器にルーティングされることを確認"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_pdf') as mock_pdf:
            mock_pdf.return_value = ExtractedText(
                content="PDF content",
                filename="test.pdf",
                content_type="pdf"
            )

            result = extractor.extract(b"pdf content", "pdf", "test.pdf")

            mock_pdf.assert_called_once_with(b"pdf content", "test.pdf")
            assert result.content == "PDF content"

    def test_extract_routes_to_text_extractor_for_txt(self):
        """TXTファイルがテキスト抽出器にルーティングされることを確認"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_text') as mock_text:
            mock_text.return_value = ExtractedText(
                content="Text content",
                filename="test.txt",
                content_type="txt",
                encoding="utf-8"
            )

            result = extractor.extract(b"text content", "txt", "test.txt")

            mock_text.assert_called_once_with(b"text content", "test.txt", "txt")

    def test_extract_routes_to_text_extractor_for_csv(self):
        """CSVファイルがテキスト抽出器にルーティングされることを確認"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_text') as mock_text:
            mock_text.return_value = ExtractedText(
                content="CSV content",
                filename="data.csv",
                content_type="csv",
                encoding="utf-8"
            )

            result = extractor.extract(b"csv content", "csv", "data.csv")

            mock_text.assert_called_once_with(b"csv content", "data.csv", "csv")

    def test_extract_unsupported_format_raises_error(self):
        """未サポート形式でTextExtractionErrorが発生することを確認"""
        extractor = TextExtractor()

        with pytest.raises(TextExtractionError, match="Unsupported file type: docx"):
            extractor.extract(b"content", "docx", "test.docx")


class TestExtractPDF:
    """PDF抽出のテスト"""

    @patch('src.data_pipeline.text_extractor.PyMuPDFLoader')
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_extract_pdf_success(self, mock_unlink, mock_exists, mock_temp, mock_loader_class):
        """PDF抽出が成功することを確認"""
        # モックの設定
        mock_temp_file = Mock()
        mock_temp_file.name = '/tmp/test.pdf'
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        # os.path.existsがTrueを返すようにモック
        mock_exists.return_value = True

        mock_doc1 = Mock()
        mock_doc1.page_content = "Page 1 content\n"
        mock_doc2 = Mock()
        mock_doc2.page_content = "Page 2 content"

        mock_loader = Mock()
        mock_loader.load.return_value = [mock_doc1, mock_doc2]
        mock_loader_class.return_value = mock_loader

        # テスト実行
        extractor = TextExtractor()
        result = extractor._extract_pdf(b"pdf binary", "test.pdf")

        # 検証
        assert result.content == "Page 1 content\nPage 2 content"
        assert result.filename == "test.pdf"
        assert result.content_type == "pdf"
        assert result.char_count == 29
        mock_unlink.assert_called_once_with('/tmp/test.pdf')

    @patch('src.data_pipeline.text_extractor.PyMuPDFLoader')
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.path.exists')
    @patch('os.unlink')
    def test_extract_pdf_cleanup_on_error(self, mock_unlink, mock_exists, mock_temp, mock_loader_class):
        """エラー時も一時ファイルがクリーンアップされることを確認"""
        mock_temp_file = Mock()
        mock_temp_file.name = '/tmp/test.pdf'
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        # os.path.existsがTrueを返すようにモック
        mock_exists.return_value = True

        mock_loader_class.side_effect = Exception("PDF load error")

        extractor = TextExtractor()

        with pytest.raises(TextExtractionError):
            extractor._extract_pdf(b"pdf binary", "test.pdf")

        # 一時ファイルがクリーンアップされたことを確認
        mock_unlink.assert_called_once_with('/tmp/test.pdf')

    @patch('src.data_pipeline.text_extractor.PyMuPDFLoader')
    @patch('tempfile.NamedTemporaryFile')
    def test_extract_pdf_empty_document(self, mock_temp, mock_loader_class):
        """空のPDFが処理できることを確認"""
        mock_temp_file = Mock()
        mock_temp_file.name = '/tmp/test.pdf'
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        mock_loader = Mock()
        mock_loader.load.return_value = []
        mock_loader_class.return_value = mock_loader

        extractor = TextExtractor()
        result = extractor._extract_pdf(b"pdf binary", "empty.pdf")

        assert result.content == ""
        assert result.char_count == 0


class TestExtractText:
    """TXT/CSVエンコーディング検出のテスト"""

    def test_extract_text_utf8_success(self):
        """UTF-8テキストが正しく抽出されることを確認"""
        extractor = TextExtractor()
        content = "こんにちは世界".encode('utf-8')

        result = extractor._extract_text(content, "test.txt", "txt")

        assert result.content == "こんにちは世界"
        assert result.filename == "test.txt"
        assert result.content_type == "txt"
        assert result.encoding == "utf-8"
        assert result.char_count == 7

    def test_extract_text_shift_jis_fallback(self):
        """Shift-JISフォールバックが動作することを確認"""
        extractor = TextExtractor()
        content = "こんにちは世界".encode('shift_jis')

        result = extractor._extract_text(content, "test.txt", "txt")

        assert result.content == "こんにちは世界"
        assert result.encoding == "shift_jis"

    def test_extract_text_csv_type(self):
        """CSV形式も処理できることを確認"""
        extractor = TextExtractor()
        content = "name,age\nAlice,30".encode('utf-8')

        result = extractor._extract_text(content, "data.csv", "csv")

        assert result.content == "name,age\nAlice,30"
        assert result.content_type == "csv"
        assert result.encoding == "utf-8"

    def test_extract_text_both_encodings_fail(self):
        """両エンコーディングで失敗時にエラーが発生することを確認"""
        extractor = TextExtractor()
        # 無効なバイト列
        content = b'\xff\xfe\xfd\xfc'

        with pytest.raises(TextExtractionError, match="not UTF-8 or Shift-JIS"):
            extractor._extract_text(content, "invalid.txt", "txt")

    def test_extract_text_empty_content(self):
        """空のコンテンツが処理できることを確認"""
        extractor = TextExtractor()
        content = b""

        result = extractor._extract_text(content, "empty.txt", "txt")

        assert result.content == ""
        assert result.char_count == 0


class TestErrorHandling:
    """エラーハンドリングのテスト"""

    def test_extract_preserves_exception_chain(self):
        """例外チェーンが保持されることを確認"""
        extractor = TextExtractor()

        with patch.object(extractor, '_extract_pdf') as mock_pdf:
            original_error = ValueError("Original error")
            mock_pdf.side_effect = original_error

            with pytest.raises(TextExtractionError) as exc_info:
                extractor.extract(b"content", "pdf", "test.pdf")

            # 元の例外が保持されていることを確認
            assert exc_info.value.__cause__ is original_error

    def test_extract_error_message_includes_filename(self):
        """エラーメッセージにファイル名が含まれることを確認"""
        extractor = TextExtractor()

        with patch.object(extractor, '_extract_text') as mock_text:
            mock_text.side_effect = Exception("Decode error")

            with pytest.raises(TextExtractionError, match="test_file.txt"):
                extractor.extract(b"content", "txt", "test_file.txt")


class TestMimeTypeSupport:
    """MIMEタイプサポートのテスト"""

    def test_extract_with_mime_type_application_pdf(self):
        """MIMEタイプ 'application/pdf' が正しく処理されることを確認"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_pdf') as mock_pdf:
            mock_pdf.return_value = ExtractedText(
                content="PDF content",
                filename="test.pdf",
                content_type="pdf"
            )

            result = extractor.extract(b"pdf content", "application/pdf", "test.pdf")

            mock_pdf.assert_called_once_with(b"pdf content", "test.pdf")
            assert result.content == "PDF content"

    def test_extract_with_mime_type_text_plain(self):
        """MIMEタイプ 'text/plain' が正しく処理されることを確認"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_text') as mock_text:
            mock_text.return_value = ExtractedText(
                content="Text content",
                filename="test.txt",
                content_type="txt",
                encoding="utf-8"
            )

            result = extractor.extract(b"text content", "text/plain", "test.txt")

            mock_text.assert_called_once_with(b"text content", "test.txt", "txt")
            assert result.content == "Text content"

    def test_extract_with_mime_type_text_csv(self):
        """MIMEタイプ 'text/csv' が正しく処理されることを確認"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_text') as mock_text:
            mock_text.return_value = ExtractedText(
                content="CSV content",
                filename="test.csv",
                content_type="csv",
                encoding="utf-8"
            )

            result = extractor.extract(b"csv content", "text/csv", "test.csv")

            mock_text.assert_called_once_with(b"csv content", "test.csv", "csv")
            assert result.content == "CSV content"

    def test_extract_with_mime_type_application_csv(self):
        """MIMEタイプ 'application/csv' が正しく処理されることを確認"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_text') as mock_text:
            mock_text.return_value = ExtractedText(
                content="CSV content",
                filename="data.csv",
                content_type="csv",
                encoding="utf-8"
            )

            result = extractor.extract(b"csv content", "application/csv", "data.csv")

            mock_text.assert_called_once_with(b"csv content", "data.csv", "csv")
            assert result.content == "CSV content"

    def test_extract_with_extension_still_works(self):
        """従来の拡張子ベースの呼び出しも引き続き動作することを確認（後方互換性）"""
        extractor = TextExtractor()
        with patch.object(extractor, '_extract_pdf') as mock_pdf:
            mock_pdf.return_value = ExtractedText(
                content="PDF content",
                filename="test.pdf",
                content_type="pdf"
            )

            # 拡張子形式で呼び出し
            result = extractor.extract(b"pdf content", "pdf", "test.pdf")

            mock_pdf.assert_called_once()
            assert result.content == "PDF content"

    def test_extract_with_unsupported_mime_type(self):
        """未サポートのMIMEタイプでエラーが発生することを確認"""
        extractor = TextExtractor()

        with pytest.raises(TextExtractionError, match="Unsupported file type: application/xyz"):
            extractor.extract(b"unknown content", "application/xyz", "test.xyz")
