"""
DocumentLoaderクラスのユニットテスト

TDD（テスト駆動開発）アプローチで実装
目標カバレッジ: 90-95%
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.data_pipeline.document_loader import DocumentLoader, DocumentMetadata
from src.data_pipeline.exceptions import DocumentLoaderError


class TestDocumentLoaderInit:
    """コンストラクタの検証"""

    def test_stores_configuration_parameters(self):
        """設定パラメータが正しく保存されることを確認"""
        oci_config = {'region': 'us-chicago-1', 'user': 'test-user'}
        bucket_name = 'test-bucket'
        namespace = 'test-namespace'

        loader = DocumentLoader(
            oci_config=oci_config,
            bucket_name=bucket_name,
            namespace=namespace
        )

        assert loader.oci_config == oci_config
        assert loader.bucket_name == bucket_name
        assert loader.namespace == namespace

    def test_oci_client_lazy_initialization(self):
        """OCIクライアントが遅延初期化されることを確認"""
        oci_config = {'region': 'us-chicago-1'}
        loader = DocumentLoader(oci_config, 'test-bucket', 'test-namespace')

        # 初期化直後はクライアントがNone
        assert loader._client is None

    def test_raises_error_on_invalid_config(self):
        """無効な設定でエラーが発生することを確認"""
        with pytest.raises(ValueError, match="oci_config"):
            DocumentLoader(None, 'bucket', 'namespace')

        with pytest.raises(ValueError, match="bucket_name"):
            DocumentLoader({'region': 'us-chicago-1'}, '', 'namespace')


class TestListFiles:
    """ファイル一覧取得のテスト"""

    @patch('oci.object_storage.ObjectStorageClient')
    def test_list_files_success(self, mock_client_class):
        """ファイル一覧が正常に取得できることを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # モックのレスポンス作成
        mock_obj1 = Mock()
        mock_obj1.name = 'documents/file1.pdf'
        mock_obj2 = Mock()
        mock_obj2.name = 'documents/file2.txt'

        mock_response = Mock()
        mock_response.data.objects = [mock_obj1, mock_obj2]
        mock_client.list_objects.return_value = mock_response

        # テスト実行
        loader = DocumentLoader({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')
        files = loader.list_files()

        # 検証
        assert len(files) == 2
        assert 'documents/file1.pdf' in files
        assert 'documents/file2.txt' in files
        mock_client.list_objects.assert_called_once()

    @patch('oci.object_storage.ObjectStorageClient')
    def test_list_files_empty_bucket(self, mock_client_class):
        """空のバケットを処理できることを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.data.objects = []
        mock_client.list_objects.return_value = mock_response

        loader = DocumentLoader({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')
        files = loader.list_files()

        assert files == []

    @patch('oci.object_storage.ObjectStorageClient')
    def test_list_files_excludes_directories(self, mock_client_class):
        """ディレクトリ（名前が"/"で終わるオブジェクト）が除外されることを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # モックのレスポンス作成（ファイルとディレクトリを含む）
        mock_file1 = Mock()
        mock_file1.name = 'documents/file1.pdf'
        mock_dir1 = Mock()
        mock_dir1.name = 'documents/'  # ディレクトリ
        mock_file2 = Mock()
        mock_file2.name = 'manual/guide.txt'
        mock_dir2 = Mock()
        mock_dir2.name = 'manual/subfolder/'  # ディレクトリ

        mock_response = Mock()
        mock_response.data.objects = [mock_file1, mock_dir1, mock_file2, mock_dir2]
        mock_client.list_objects.return_value = mock_response

        # テスト実行
        loader = DocumentLoader({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')
        files = loader.list_files()

        # 検証: ファイルのみが含まれ、ディレクトリは除外される
        assert len(files) == 2
        assert 'documents/file1.pdf' in files
        assert 'manual/guide.txt' in files
        assert 'documents/' not in files  # ディレクトリは除外
        assert 'manual/subfolder/' not in files  # ディレクトリは除外

    @patch('oci.object_storage.ObjectStorageClient')
    def test_list_files_api_error(self, mock_client_class):
        """OCI APIエラーを適切にハンドリングすることを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.list_objects.side_effect = Exception("API Error")

        loader = DocumentLoader({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')

        with pytest.raises(DocumentLoaderError, match="Failed to list files"):
            loader.list_files()


class TestDownloadFile:
    """ファイルダウンロードのテスト"""

    @patch('oci.object_storage.ObjectStorageClient')
    def test_download_file_success(self, mock_client_class):
        """ファイルが正常にダウンロードできることを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # モックのレスポンス
        mock_response = Mock()
        mock_response.data.content = b'test content'
        mock_response.headers = {
            'Content-Type': 'application/pdf',
            'Content-Length': '12'
        }
        mock_client.get_object.return_value = mock_response

        loader = DocumentLoader({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')
        metadata = loader.download_file('documents/test.pdf')

        # 検証
        assert isinstance(metadata, DocumentMetadata)
        assert metadata.filename == 'test.pdf'
        assert metadata.full_path == 'documents/test.pdf'
        assert metadata.content == b'test content'
        assert metadata.content_type == 'application/pdf'
        assert metadata.file_size == 12

    @patch('oci.object_storage.ObjectStorageClient')
    def test_download_file_root_directory(self, mock_client_class):
        """ルートディレクトリのファイルを処理できることを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.data.content = b'test'
        mock_response.headers = {'Content-Type': 'text/plain', 'Content-Length': '4'}
        mock_client.get_object.return_value = mock_response

        loader = DocumentLoader({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')
        metadata = loader.download_file('file.txt')

        assert metadata.filename == 'file.txt'
        assert metadata.full_path == 'file.txt'

    @patch('oci.object_storage.ObjectStorageClient')
    def test_download_file_not_found(self, mock_client_class):
        """存在しないファイルでFileNotFoundErrorが発生することを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get_object.side_effect = Exception("404 Not Found")

        loader = DocumentLoader({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')

        with pytest.raises(DocumentLoaderError, match="Failed to download file"):
            loader.download_file('nonexistent.pdf')


class TestParseFilePath:
    """ファイルパス解析のテスト"""

    @pytest.mark.parametrize("full_path,expected_filename", [
        ("documents/report.pdf", "report.pdf"),
        ("folder/subfolder/file.txt", "file.txt"),
        ("file.csv", "file.csv"),
        ("a/b/c/d/e.pdf", "e.pdf"),
    ])
    def test_parse_file_path(self, full_path, expected_filename):
        """様々なパスから正しくファイル名を抽出できることを確認"""
        filename = DocumentLoader.parse_file_path(full_path)
        assert filename == expected_filename

    def test_parse_file_path_empty(self):
        """空のパスでエラーが発生することを確認"""
        with pytest.raises(ValueError, match="File path cannot be empty"):
            DocumentLoader.parse_file_path("")
