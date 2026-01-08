"""
DocumentWriterクラスのユニットテスト

このモジュールは、ドキュメントとチャンクをOracle Databaseに
保存するDocumentWriterクラスの包括的なテストを含みます。

TDD（テスト駆動開発）アプローチで実装
目標カバレッジ: 90-95%
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from src.data_pipeline.document_writer import (
    DocumentWriter,
    SavedDocument,
    SavedChunks
)
from src.data_pipeline.exceptions import DocumentWriteError


class TestDocumentWriterInit:
    """コンストラクタの検証"""

    def test_initialization_with_connection(self):
        """DB接続を渡して初期化できることを確認"""
        mock_connection = Mock()

        writer = DocumentWriter(mock_connection)

        assert writer.connection is mock_connection
        assert writer.logger is not None

    def test_initialization_validates_connection(self):
        """接続がNoneの場合にValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="connection is required"):
            DocumentWriter(None)  # type: ignore


class TestSaveDocument:
    """save_documentメソッドのテスト"""

    def test_save_document_success(self):
        """ドキュメント保存が成功することを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # var()呼び出しをモック
        mock_var = Mock()
        mock_var.getvalue.return_value = [b'test-document-id-bytes']
        mock_connection.cursor.return_value.var.return_value = mock_var

        writer = DocumentWriter(mock_connection)

        result = writer.save_document(
            filename='test.pdf',
            filtering='test-folder',
            content_type='pdf',
            file_size=1024,
            text_length=500
        )

        assert isinstance(result, SavedDocument)
        assert result.document_id == b'test-document-id-bytes'
        assert result.filename == 'test.pdf'
        assert result.content_type == 'pdf'

        # 検証 cursor.execute was called
        mock_cursor.execute.assert_called_once()

        # 検証 commit was called
        mock_connection.commit.assert_called_once()

    def test_save_document_executes_correct_sql(self):
        """正しいSQL文が実行されることを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        mock_var = Mock()
        mock_var.getvalue.return_value = [b'doc-id']
        mock_connection.cursor.return_value.var.return_value = mock_var

        writer = DocumentWriter(mock_connection)

        writer.save_document(
            filename='doc.txt',
            filtering='folder1',
            content_type='txt',
            file_size=2048,
            text_length=1000
        )

        # SQLに期待される要素が含まれていることを確認
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]

        assert 'INSERT INTO source_documents' in sql
        assert 'filename' in sql
        assert 'filtering' in sql
        assert 'RETURNING document_id INTO' in sql

    def test_save_document_passes_correct_parameters(self):
        """正しいパラメータが渡されることを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        mock_var = Mock()
        mock_var.getvalue.return_value = [b'doc-id']
        mock_connection.cursor.return_value.var.return_value = mock_var

        writer = DocumentWriter(mock_connection)

        writer.save_document(
            filename='test.csv',
            filtering='data',
            content_type='csv',
            file_size=512,
            text_length=250
        )

        # 検証 parameters passed to execute
        call_kwargs = mock_cursor.execute.call_args[1]
        assert call_kwargs['filename'] == 'test.csv'
        assert call_kwargs['filtering'] == 'data'
        assert call_kwargs['content_type'] == 'csv'
        assert call_kwargs['file_size'] == 512
        assert call_kwargs['text_length'] == 250

    def test_save_document_database_error_raises_exception(self):
        """DB エラーが発生した場合に DocumentWriteError が発生することを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # モック database error
        import oracledb
        db_error = oracledb.DatabaseError("ORA-00001: unique constraint violated")
        mock_cursor.execute.side_effect = db_error

        writer = DocumentWriter(mock_connection)

        with pytest.raises(DocumentWriteError) as exc_info:
            writer.save_document(
                filename='test.pdf',
                filtering='folder',
                content_type='pdf',
                file_size=1024,
                text_length=500
            )

        # 検証 exception chain
        assert exc_info.value.__cause__ is db_error

    def test_save_document_validates_required_parameters(self):
        """必須パラメータの検証"""
        mock_connection = Mock()
        writer = DocumentWriter(mock_connection)

        # 空のファイル名
        with pytest.raises(DocumentWriteError, match="filename cannot be empty"):
            writer.save_document(
                filename='',
                filtering='folder',
                content_type='pdf',
                file_size=1024,
                text_length=500
            )

        # 空のcontent_type
        with pytest.raises(DocumentWriteError, match="content_type cannot be empty"):
            writer.save_document(
                filename='test.pdf',
                filtering='folder',
                content_type='',
                file_size=1024,
                text_length=500
            )


class TestSaveChunks:
    """save_chunksメソッドのテスト"""

    def test_save_chunks_success(self):
        """チャンク保存が成功することを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        writer = DocumentWriter(mock_connection)

        document_id = b'test-doc-id'
        chunks = ['chunk1', 'chunk2', 'chunk3']
        embeddings = ['[0.1, 0.2]', '[0.3, 0.4]', '[0.5, 0.6]']

        result = writer.save_chunks(document_id, chunks, embeddings)

        assert isinstance(result, SavedChunks)
        assert result.document_id == document_id
        assert result.chunk_count == 3

        # 検証 execute was called 3 times
        assert mock_cursor.execute.call_count == 3

        # 検証 commit was called
        mock_connection.commit.assert_called_once()

    def test_save_chunks_executes_correct_sql(self):
        """正しいSQL文が実行されることを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        writer = DocumentWriter(mock_connection)

        writer.save_chunks(
            b'doc-id',
            ['chunk1'],
            ['[0.1]']
        )

        # Check SQL contains expected elements
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]

        assert 'INSERT INTO chunks' in sql
        assert 'document_id' in sql
        assert 'chunk_text' in sql
        assert 'embedding' in sql
        assert 'TO_VECTOR' in sql

    def test_save_chunks_passes_correct_parameters(self):
        """正しいパラメータが各チャンクに渡されることを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        writer = DocumentWriter(mock_connection)

        document_id = b'test-id'
        chunks = ['chunk1', 'chunk2']
        embeddings = ['[0.1, 0.2]', '[0.3, 0.4]']

        writer.save_chunks(document_id, chunks, embeddings)

        # 検証 first call
        first_call_kwargs = mock_cursor.execute.call_args_list[0][1]
        assert first_call_kwargs['document_id'] == document_id
        assert first_call_kwargs['chunk_text'] == 'chunk1'
        assert first_call_kwargs['embedding'] == '[0.1, 0.2]'

        # 検証 second call
        second_call_kwargs = mock_cursor.execute.call_args_list[1][1]
        assert second_call_kwargs['chunk_text'] == 'chunk2'
        assert second_call_kwargs['embedding'] == '[0.3, 0.4]'

    def test_save_chunks_empty_lists_success(self):
        """空のリストで成功することを確認（0件保存）"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        writer = DocumentWriter(mock_connection)

        result = writer.save_chunks(b'doc-id', [], [])

        assert result.chunk_count == 0

        # No execute calls
        mock_cursor.execute.assert_not_called()

        # No commit for empty save
        mock_connection.commit.assert_not_called()

    def test_save_chunks_mismatched_lengths_raises_error(self):
        """chunks と embeddings の長さが異なる場合にエラー"""
        mock_connection = Mock()
        writer = DocumentWriter(mock_connection)

        with pytest.raises(DocumentWriteError, match="chunks and embeddings must have the same length"):
            writer.save_chunks(
                b'doc-id',
                ['chunk1', 'chunk2'],
                ['[0.1]']  # Only 1 embedding
            )

    def test_save_chunks_database_error_raises_exception(self):
        """DB エラーが発生した場合に DocumentWriteError が発生することを確認"""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # モック database error
        import oracledb
        db_error = oracledb.DatabaseError("ORA-02291: foreign key constraint violated")
        mock_cursor.execute.side_effect = db_error

        writer = DocumentWriter(mock_connection)

        with pytest.raises(DocumentWriteError) as exc_info:
            writer.save_chunks(b'invalid-doc-id', ['chunk1'], ['[0.1]'])

        # 検証 exception chain
        assert exc_info.value.__cause__ is db_error


class TestSavedDocumentDataclass:
    """SavedDocumentデータクラスのテスト"""

    def test_saved_document_creation(self):
        """SavedDocumentが正しく作成されることを確認"""
        doc = SavedDocument(
            document_id=b'test-id',
            filename='test.pdf',
            content_type='pdf'
        )

        assert doc.document_id == b'test-id'
        assert doc.filename == 'test.pdf'
        assert doc.content_type == 'pdf'


class TestSavedChunksDataclass:
    """SavedChunksデータクラスのテスト"""

    def test_saved_chunks_creation(self):
        """SavedChunksが正しく作成されることを確認"""
        chunks = SavedChunks(
            document_id=b'doc-id',
            chunk_count=5
        )

        assert chunks.document_id == b'doc-id'
        assert chunks.chunk_count == 5
