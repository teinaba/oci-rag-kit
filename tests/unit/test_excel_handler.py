"""
ExcelHandlerクラスのユニットテスト

TDD（テスト駆動開発）アプローチで実装
目標カバレッジ: 90-95%
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
import pandas as pd
from src.rag.excel_handler import ExcelHandler
from src.rag.exceptions import ExcelHandlerError


class TestExcelHandlerInit:
    """コンストラクタの検証"""

    def test_stores_configuration_parameters(self):
        """設定パラメータが正しく保存されることを確認"""
        oci_config = {'region': 'us-chicago-1', 'user': 'test-user'}
        bucket_name = 'test-bucket'
        namespace = 'test-namespace'

        handler = ExcelHandler(
            oci_config=oci_config,
            bucket_name=bucket_name,
            namespace=namespace
        )

        assert handler.oci_config == oci_config
        assert handler.bucket_name == bucket_name
        assert handler.namespace == namespace

    def test_oci_client_lazy_initialization(self):
        """OCIクライアントが遅延初期化されることを確認"""
        oci_config = {'region': 'us-chicago-1'}
        handler = ExcelHandler(oci_config, 'test-bucket', 'test-namespace')

        # 初期化直後はクライアントがNone
        assert handler._client is None

    def test_raises_error_on_invalid_config(self):
        """無効な設定でエラーが発生することを確認"""
        with pytest.raises(ValueError, match="oci_config"):
            ExcelHandler(None, 'bucket', 'namespace')

        with pytest.raises(ValueError, match="bucket_name"):
            ExcelHandler({'region': 'us-chicago-1'}, '', 'namespace')

        with pytest.raises(ValueError, match="namespace"):
            ExcelHandler({'region': 'us-chicago-1'}, 'bucket', '')


class TestLoadFAQ:
    """FAQ読み込み機能のテスト"""

    @patch('oci.object_storage.ObjectStorageClient')
    def test_load_faq_success(self, mock_client_class):
        """FAQファイルが正常に読み込めることを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # FAQデータの作成
        faq_data = {
            'id': [1, 2, 3],
            'question': ['質問1', '質問2', '質問3'],
            'ground_truth': ['回答1', '回答2', '回答3'],
            'filter': ['source1', 'source2', 'source3']
        }
        faq_df = pd.DataFrame(faq_data)

        # ExcelファイルをBytesIOで作成
        excel_buffer = BytesIO()
        faq_df.to_excel(excel_buffer, index=False, sheet_name='FAQ')
        excel_buffer.seek(0)

        # モックのレスポンス作成
        mock_response = Mock()
        mock_response.data.content = excel_buffer.getvalue()
        mock_client.get_object.return_value = mock_response

        # テスト実行
        handler = ExcelHandler({'region': 'us-chicago-1'}, 'faq-bucket', 'test-namespace')
        result_df = handler.load_faq('faq.xlsx', sheet_name='FAQ')

        # 検証
        assert len(result_df) == 3
        assert 'id' in result_df.columns
        assert 'question' in result_df.columns
        assert 'ground_truth' in result_df.columns
        assert 'filter' in result_df.columns
        assert result_df['question'].tolist() == ['質問1', '質問2', '質問3']
        mock_client.get_object.assert_called_once_with('test-namespace', 'faq-bucket', 'faq.xlsx')

    @patch('oci.object_storage.ObjectStorageClient')
    def test_load_faq_default_sheet_name(self, mock_client_class):
        """デフォルトのシート名（0番目）でFAQファイルが読み込めることを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # FAQデータの作成
        faq_data = {
            'id': [1],
            'question': ['質問1'],
            'ground_truth': ['回答1'],
            'filter': ['source1']
        }
        faq_df = pd.DataFrame(faq_data)

        # ExcelファイルをBytesIOで作成
        excel_buffer = BytesIO()
        faq_df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)

        # モックのレスポンス作成
        mock_response = Mock()
        mock_response.data.content = excel_buffer.getvalue()
        mock_client.get_object.return_value = mock_response

        # テスト実行（sheet_nameを省略）
        handler = ExcelHandler({'region': 'us-chicago-1'}, 'faq-bucket', 'test-namespace')
        result_df = handler.load_faq('faq.xlsx')

        # 検証
        assert len(result_df) == 1
        assert 'id' in result_df.columns

    @patch('oci.object_storage.ObjectStorageClient')
    def test_load_faq_file_not_found(self, mock_client_class):
        """ファイルが存在しない場合にエラーが発生することを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # ファイル未発見エラーをシミュレート
        mock_client.get_object.side_effect = Exception("Object not found")

        # テスト実行
        handler = ExcelHandler({'region': 'us-chicago-1'}, 'faq-bucket', 'test-namespace')

        with pytest.raises(ExcelHandlerError, match="FAQ file load failed"):
            handler.load_faq('nonexistent.xlsx')

    @patch('oci.object_storage.ObjectStorageClient')
    def test_load_faq_missing_required_columns(self, mock_client_class):
        """必須列が欠けている場合にエラーが発生することを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # 必須列が欠けているFAQデータ（'filter'列が無い）
        faq_data = {
            'id': [1],
            'question': ['質問1'],
            'ground_truth': ['回答1']
        }
        faq_df = pd.DataFrame(faq_data)

        # ExcelファイルをBytesIOで作成
        excel_buffer = BytesIO()
        faq_df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)

        # モックのレスポンス作成
        mock_response = Mock()
        mock_response.data.content = excel_buffer.getvalue()
        mock_client.get_object.return_value = mock_response

        # テスト実行
        handler = ExcelHandler({'region': 'us-chicago-1'}, 'faq-bucket', 'test-namespace')

        with pytest.raises(ExcelHandlerError, match="Missing required columns"):
            handler.load_faq('faq.xlsx')


class TestSaveResults:
    """結果保存機能のテスト"""

    @patch('oci.object_storage.ObjectStorageClient')
    def test_save_results_without_metadata(self, mock_client_class):
        """メタデータなしで結果を保存できることを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # 結果データの作成
        results_data = {
            'id': [1, 2],
            'question': ['質問1', '質問2'],
            'answer': ['回答1', '回答2'],
            'contexts': ['コンテキスト1', 'コンテキスト2']
        }
        results_df = pd.DataFrame(results_data)

        # テスト実行
        handler = ExcelHandler({'region': 'us-chicago-1'}, 'results-bucket', 'test-namespace')
        object_name = handler.save_results(results_df, 'results.xlsx')

        # 検証
        assert object_name == 'results.xlsx'
        mock_client.put_object.assert_called_once()

        # put_objectの呼び出し引数を検証
        call_args = mock_client.put_object.call_args
        assert call_args[1]['namespace_name'] == 'test-namespace'
        assert call_args[1]['bucket_name'] == 'results-bucket'
        assert call_args[1]['object_name'] == 'results.xlsx'
        assert isinstance(call_args[1]['put_object_body'], bytes)

    @patch('oci.object_storage.ObjectStorageClient')
    def test_save_results_with_metadata(self, mock_client_class):
        """メタデータありで結果を保存できることを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # 結果データの作成
        results_data = {
            'id': [1],
            'question': ['質問1'],
            'answer': ['回答1'],
            'contexts': ['コンテキスト1']
        }
        results_df = pd.DataFrame(results_data)

        # メタデータの作成
        metadata_data = {
            'パラメータ': ['TOP_K', 'CHAT_MODEL'],
            '設定値': [10, 'cohere.command-a-03-2025']
        }
        metadata_df = pd.DataFrame(metadata_data)

        # テスト実行
        handler = ExcelHandler({'region': 'us-chicago-1'}, 'results-bucket', 'test-namespace')
        object_name = handler.save_results(results_df, 'results_with_meta.xlsx', metadata_df=metadata_df)

        # 検証
        assert object_name == 'results_with_meta.xlsx'
        mock_client.put_object.assert_called_once()

        # put_objectの引数を検証
        call_args = mock_client.put_object.call_args
        assert call_args[1]['object_name'] == 'results_with_meta.xlsx'

    @patch('oci.object_storage.ObjectStorageClient')
    def test_save_results_upload_failure(self, mock_client_class):
        """アップロード失敗時にエラーが発生することを確認"""
        # モックの設定
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # アップロードエラーをシミュレート
        mock_client.put_object.side_effect = Exception("Upload failed")

        # 結果データの作成
        results_data = {
            'id': [1],
            'question': ['質問1'],
            'answer': ['回答1']
        }
        results_df = pd.DataFrame(results_data)

        # テスト実行
        handler = ExcelHandler({'region': 'us-chicago-1'}, 'results-bucket', 'test-namespace')

        with pytest.raises(ExcelHandlerError, match="Results save failed"):
            handler.save_results(results_df, 'failed.xlsx')


class TestClientProperty:
    """クライアントプロパティのテスト"""

    @patch('oci.object_storage.ObjectStorageClient')
    def test_client_lazy_initialization(self, mock_client_class):
        """クライアントが遅延初期化されることを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        handler = ExcelHandler({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')

        # clientプロパティにアクセスするとOCIクライアントが作成される
        client = handler.client

        assert client is mock_client
        mock_client_class.assert_called_once_with({'region': 'us-chicago-1'})

    @patch('oci.object_storage.ObjectStorageClient')
    def test_client_reuses_instance(self, mock_client_class):
        """クライアントが再利用されることを確認"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        handler = ExcelHandler({'region': 'us-chicago-1'}, 'test-bucket', 'test-namespace')

        # 複数回アクセスしても同じインスタンスが返される
        client1 = handler.client
        client2 = handler.client

        assert client1 is client2
        mock_client_class.assert_called_once()
