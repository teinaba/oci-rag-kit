"""
DataPipelineオーケストレータクラスのユニットテスト

このモジュールは、データ取り込みパイプライン全体を統括する
DataPipelineクラスの包括的なテストを含みます。

TDD（テスト駆動開発）アプローチで実装
目標カバレッジ: 90-95%
"""
import pytest
from unittest.mock import Mock, MagicMock, call
from src.data_pipeline.data_pipeline import (
    DataPipeline,
    PipelineResult,
    ProcessedDocument
)
from src.data_pipeline.exceptions import (
    DocumentLoaderError,
    TextExtractionError,
    ChunkingError,
    EmbeddingError,
    DocumentWriteError
)


class TestDataPipelineInit:
    """コンストラクタの検証"""

    def test_initialization_with_all_components(self):
        """全コンポーネントで初期化できることを確認"""
        loader = Mock()
        extractor = Mock()
        chunker = Mock()
        embedding_gen = Mock()
        writer = Mock()

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=writer
        )

        assert pipeline.loader is loader
        assert pipeline.extractor is extractor
        assert pipeline.chunker is chunker
        assert pipeline.embedding_gen is embedding_gen
        assert pipeline.writer is writer
        assert pipeline.progress_callback is None
        assert pipeline.logger is not None

    def test_initialization_with_progress_callback(self):
        """プログレスコールバック付きで初期化できることを確認"""
        callback = Mock()
        pipeline = DataPipeline(
            loader=Mock(),
            extractor=Mock(),
            chunker=Mock(),
            embedding_gen=Mock(),
            writer=Mock(),
            progress_callback=callback
        )

        assert pipeline.progress_callback is callback

    def test_initialization_validates_required_components(self):
        """必須コンポーネントの検証"""
        with pytest.raises(ValueError, match="loader is required"):
            DataPipeline(
                loader=None,
                extractor=Mock(),
                chunker=Mock(),
                embedding_gen=Mock(),
                writer=Mock()
            )

        with pytest.raises(ValueError, match="extractor is required"):
            DataPipeline(
                loader=Mock(),
                extractor=None,
                chunker=Mock(),
                embedding_gen=Mock(),
                writer=Mock()
            )

        with pytest.raises(ValueError, match="chunker is required"):
            DataPipeline(
                loader=Mock(),
                extractor=Mock(),
                chunker=None,
                embedding_gen=Mock(),
                writer=Mock()
            )

        with pytest.raises(ValueError, match="embedding_gen is required"):
            DataPipeline(
                loader=Mock(),
                extractor=Mock(),
                chunker=Mock(),
                embedding_gen=None,
                writer=Mock()
            )

        with pytest.raises(ValueError, match="writer is required"):
            DataPipeline(
                loader=Mock(),
                extractor=Mock(),
                chunker=Mock(),
                embedding_gen=Mock(),
                writer=None
            )


class TestProcessSingle:
    """単一ファイル処理のテスト"""

    def test_process_single_success(self):
        """単一ファイルの正常処理を確認"""
        # モックをセットアップ
        loader = Mock()
        loader.download_file.return_value = Mock(
            filename='test.pdf',
            full_path='docs/test.pdf',
            content=b'pdf content',
            content_type='application/pdf',
            file_size=1024
        )

        extractor = Mock()
        extractor.extract.return_value = Mock(text='extracted text', text_length=100)

        chunker = Mock()
        chunker.chunk.return_value = Mock(
            chunks=['chunk1', 'chunk2', 'chunk3'],
            chunk_count=3
        )

        embedding_gen = Mock()
        embedding_gen.embed_query.side_effect = [
            Mock(vector_str='[0.1, 0.2]'),
            Mock(vector_str='[0.3, 0.4]'),
            Mock(vector_str='[0.5, 0.6]')
        ]

        writer = Mock()
        writer.save_document.return_value = Mock(
            document_id=b'doc-id-123',
            filename='test.pdf',
            content_type='pdf'
        )
        writer.save_chunks.return_value = Mock(
            document_id=b'doc-id-123',
            chunk_count=3
        )

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=writer
        )

        # 実行
        result = pipeline.process_single('docs/test.pdf')

        # 検証
        assert isinstance(result, ProcessedDocument)
        assert result.filename == 'test.pdf'
        assert result.status == 'success'
        assert result.document_id == b'doc-id-123'
        assert result.chunks_saved == 3
        assert result.error is None

        # 検証 component calls
        loader.download_file.assert_called_once_with('docs/test.pdf')
        extractor.extract.assert_called_once()
        chunker.chunk.assert_called_once()
        assert embedding_gen.embed_query.call_count == 3
        writer.save_document.assert_called_once()
        writer.save_chunks.assert_called_once()

    def test_process_single_with_progress_callback(self):
        """プログレスコールバックが呼ばれることを確認"""
        loader = Mock()
        loader.download_file.return_value = Mock(
            filename='test.txt',
            full_path='folder/test.txt',
            content=b'content',
            content_type='text/plain',
            file_size=100
        )
        extractor = Mock()
        extractor.extract.return_value = Mock(text='text', text_length=10)
        chunker = Mock()
        chunker.chunk.return_value = Mock(chunks=['chunk'], chunk_count=1)
        embedding_gen = Mock()
        embedding_gen.embed_query.return_value = Mock(vector_str='[0.1]')
        writer = Mock()
        writer.save_document.return_value = Mock(document_id=b'id')
        writer.save_chunks.return_value = Mock(chunk_count=1)

        callback = Mock()
        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=writer,
            progress_callback=callback
        )

        pipeline.process_single('test.txt')

        callback.assert_called_with('test.txt', 'success')

    def test_process_single_unsupported_file_type(self):
        """未対応ファイルタイプでスキップされることを確認"""
        loader = Mock()
        loader.download_file.return_value = Mock(
            filename='test.xyz',
            content=b'content',
            content_type='application/xyz',
            file_size=100
        )

        extractor = Mock()
        extractor.extract.side_effect = TextExtractionError("Unsupported file type")

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=Mock(),
            embedding_gen=Mock(),
            writer=Mock()
        )

        result = pipeline.process_single('test.xyz')

        assert result.status == 'skipped'
        assert result.chunks_saved == 0
        assert 'Unsupported file type' in result.error

    def test_process_single_loader_error(self):
        """ローダーエラーで失敗ステータスになることを確認"""
        loader = Mock()
        loader.download_file.side_effect = DocumentLoaderError("Download failed")

        pipeline = DataPipeline(
            loader=loader,
            extractor=Mock(),
            chunker=Mock(),
            embedding_gen=Mock(),
            writer=Mock()
        )

        result = pipeline.process_single('test.pdf')

        assert result.status == 'failed'
        assert 'Download failed' in result.error

    def test_process_single_embedding_error(self):
        """埋め込みエラーで失敗ステータスになることを確認"""
        loader = Mock()
        loader.download_file.return_value = Mock(
            filename='test.pdf',
            content=b'content',
            content_type='application/pdf',
            file_size=100
        )
        extractor = Mock()
        extractor.extract.return_value = Mock(text='text', text_length=10)
        chunker = Mock()
        chunker.chunk.return_value = Mock(chunks=['chunk'], chunk_count=1)
        embedding_gen = Mock()
        embedding_gen.embed_query.side_effect = EmbeddingError("API error")

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=Mock()
        )

        result = pipeline.process_single('test.pdf')

        assert result.status == 'failed'
        assert 'API error' in result.error

    def test_process_single_database_error(self):
        """DBエラーで失敗ステータスになることを確認"""
        loader = Mock()
        loader.download_file.return_value = Mock(
            filename='test.pdf',
            full_path='folder/test.pdf',
            content=b'content',
            content_type='application/pdf',
            file_size=100
        )
        extractor = Mock()
        extractor.extract.return_value = Mock(text='text', text_length=10)
        chunker = Mock()
        chunker.chunk.return_value = Mock(chunks=['chunk'], chunk_count=1)
        embedding_gen = Mock()
        embedding_gen.embed_query.return_value = Mock(vector_str='[0.1]')
        writer = Mock()
        writer.save_document.side_effect = DocumentWriteError("DB connection failed")

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=writer
        )

        result = pipeline.process_single('test.pdf')

        assert result.status == 'failed'
        assert 'DB connection failed' in result.error


class TestProcessAll:
    """複数ファイル処理のテスト"""

    def test_process_all_multiple_files_success(self):
        """複数ファイルの正常処理を確認"""
        # モックをセットアップ for successful processing
        loader = Mock()
        loader.download_file.side_effect = [
            Mock(filename='file1.pdf', full_path='folder/file1.pdf', content=b'c1', content_type='application/pdf', file_size=100),
            Mock(filename='file2.txt', full_path='folder/file2.txt', content=b'c2', content_type='text/plain', file_size=200)
        ]

        extractor = Mock()
        extractor.extract.side_effect = [
            Mock(text='text1', text_length=50),
            Mock(text='text2', text_length=100)
        ]

        chunker = Mock()
        chunker.chunk.side_effect = [
            Mock(chunks=['c1', 'c2'], chunk_count=2),
            Mock(chunks=['c3'], chunk_count=1)
        ]

        embedding_gen = Mock()
        embedding_gen.embed_query.return_value = Mock(vector_str='[0.1]')

        writer = Mock()
        writer.save_document.side_effect = [
            Mock(document_id=b'id1'),
            Mock(document_id=b'id2')
        ]
        writer.save_chunks.side_effect = [
            Mock(chunk_count=2),
            Mock(chunk_count=1)
        ]

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=writer
        )

        # 実行
        result = pipeline.process_all(['path1.pdf', 'path2.txt'])

        # 検証
        assert isinstance(result, PipelineResult)
        assert result.total_files == 2
        assert result.successful == 2
        assert result.failed == 0
        assert result.skipped == 0
        assert result.total_chunks == 3
        assert len(result.processed_docs) == 2

    def test_process_all_mixed_success_failure(self):
        """成功と失敗が混在する場合を確認"""
        loader = Mock()
        loader.download_file.side_effect = [
            Mock(filename='good.pdf', full_path='folder/good.pdf', content=b'c1', content_type='application/pdf', file_size=100),
            DocumentLoaderError("Failed to download")
        ]

        extractor = Mock()
        extractor.extract.return_value = Mock(text='text', text_length=50)

        chunker = Mock()
        chunker.chunk.return_value = Mock(chunks=['c1'], chunk_count=1)

        embedding_gen = Mock()
        embedding_gen.embed_query.return_value = Mock(vector_str='[0.1]')

        writer = Mock()
        writer.save_document.return_value = Mock(document_id=b'id1')
        writer.save_chunks.return_value = Mock(chunk_count=1)

        pipeline = DataPipeline(
            loader=loader,
            extractor=extractor,
            chunker=chunker,
            embedding_gen=embedding_gen,
            writer=writer
        )

        result = pipeline.process_all(['good.pdf', 'bad.pdf'])

        assert result.total_files == 2
        assert result.successful == 1
        assert result.failed == 1
        assert result.skipped == 0
        assert result.total_chunks == 1

    def test_process_all_empty_file_list(self):
        """空のファイルリストを処理できることを確認"""
        pipeline = DataPipeline(
            loader=Mock(),
            extractor=Mock(),
            chunker=Mock(),
            embedding_gen=Mock(),
            writer=Mock()
        )

        result = pipeline.process_all([])

        assert result.total_files == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.total_chunks == 0
        assert len(result.processed_docs) == 0

    def test_process_all_tracks_elapsed_time(self):
        """処理時間が記録されることを確認"""
        pipeline = DataPipeline(
            loader=Mock(),
            extractor=Mock(),
            chunker=Mock(),
            embedding_gen=Mock(),
            writer=Mock()
        )

        result = pipeline.process_all([])

        assert result.elapsed_time >= 0
        assert isinstance(result.elapsed_time, float)


class TestProcessedDocumentDataclass:
    """ProcessedDocumentデータクラスのテスト"""

    def test_processed_document_creation(self):
        """ProcessedDocumentが正しく作成されることを確認"""
        doc = ProcessedDocument(
            filename='test.pdf',
            status='success',
            document_id=b'test-id',
            chunks_saved=5,
            error=None
        )

        assert doc.filename == 'test.pdf'
        assert doc.status == 'success'
        assert doc.document_id == b'test-id'
        assert doc.chunks_saved == 5
        assert doc.error is None


class TestPipelineResultDataclass:
    """PipelineResultデータクラスのテスト"""

    def test_pipeline_result_creation(self):
        """PipelineResultが正しく作成されることを確認"""
        doc1 = ProcessedDocument('f1.pdf', 'success', b'id1', 3)
        doc2 = ProcessedDocument('f2.txt', 'failed', None, 0, 'Error msg')

        result = PipelineResult(
            total_files=2,
            successful=1,
            failed=1,
            skipped=0,
            total_chunks=3,
            processed_docs=[doc1, doc2],
            elapsed_time=1.5
        )

        assert result.total_files == 2
        assert result.successful == 1
        assert result.failed == 1
        assert result.skipped == 0
        assert result.total_chunks == 3
        assert len(result.processed_docs) == 2
        assert result.elapsed_time == 1.5
