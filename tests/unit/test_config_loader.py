"""
config_loader.py のユニットテスト
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "notebooks"))

from config_loader import (
    ConfigLoader,
    load_config,
    get_db_connection_params,
    get_oci_config,
    get_genai_endpoint_from_region,
    get_genai_config,
    get_object_storage_config,
    get_app_config,
    get_genai_client,
    get_object_storage_client,
)


# =============================================================================
# 純粋関数のテスト（モック不要）
# =============================================================================

class TestGetGenaiEndpointFromRegion:
    """get_genai_endpoint_from_region() のテスト"""

    @pytest.mark.unit
    @pytest.mark.parametrize("region,expected", [
        ("us-chicago-1", "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"),
        ("ap-osaka-1", "https://inference.generativeai.ap-osaka-1.oci.oraclecloud.com"),
    ])
    def test_supported_regions(self, region, expected):
        """サポートされているリージョンのエンドポイント生成"""
        result = get_genai_endpoint_from_region(region)
        assert result == expected


# =============================================================================
# 環境変数ベースの関数のテスト
# =============================================================================

class TestGetAppConfig:
    """get_app_config() のテスト"""

    @pytest.mark.unit
    def test_default_values(self):
        """環境変数が設定されていない場合のデフォルト値"""
        with patch.dict(os.environ, {}, clear=True):
            config = get_app_config()
            assert config['chunk_size'] == 500
            assert config['chunk_overlap'] == 50
            assert config['top_k'] == 5

    @pytest.mark.unit
    def test_custom_values(self):
        """環境変数でカスタム値を設定した場合"""
        with patch.dict(os.environ, {
            'CHUNK_SIZE': '1000',
            'CHUNK_OVERLAP': '100',
            'TOP_K': '10'
        }, clear=True):
            config = get_app_config()
            assert config['chunk_size'] == 1000
            assert config['chunk_overlap'] == 100
            assert config['top_k'] == 10

    @pytest.mark.unit
    def test_partial_custom_values(self):
        """一部の環境変数のみ設定した場合"""
        with patch.dict(os.environ, {
            'CHUNK_SIZE': '750',
        }, clear=True):
            config = get_app_config()
            assert config['chunk_size'] == 750
            assert config['chunk_overlap'] == 50  # デフォルト
            assert config['top_k'] == 5  # デフォルト


class TestGetDbConnectionParams:
    """get_db_connection_params() のテスト"""

    @pytest.mark.unit
    def test_success_with_all_params(self):
        """全てのパラメータが設定されている場合"""
        with patch.dict(os.environ, {
            'DB_USERNAME': 'testuser',
            'DB_PASSWORD': 'testpass',
            'DB_DSN': 'testhost:1521/testdb'
        }, clear=True):
            result = get_db_connection_params()
            assert result['user'] == 'testuser'
            assert result['password'] == 'testpass'
            assert result['dsn'] == 'testhost:1521/testdb'

    @pytest.mark.unit
    def test_missing_username(self):
        """ユーザー名が欠けている場合"""
        with patch.dict(os.environ, {
            'DB_PASSWORD': 'testpass',
            'DB_DSN': 'testhost:1521/testdb'
        }, clear=True):
            with pytest.raises(ValueError, match="DB_USERNAME"):
                get_db_connection_params()

    @pytest.mark.unit
    def test_missing_password(self):
        """パスワードが欠けている場合"""
        with patch.dict(os.environ, {
            'DB_USERNAME': 'testuser',
            'DB_DSN': 'testhost:1521/testdb'
        }, clear=True):
            with pytest.raises(ValueError, match="DB_PASSWORD"):
                get_db_connection_params()

    @pytest.mark.unit
    def test_missing_dsn(self):
        """DSNが欠けている場合"""
        with patch.dict(os.environ, {
            'DB_USERNAME': 'testuser',
            'DB_PASSWORD': 'testpass'
        }, clear=True):
            with pytest.raises(ValueError, match="DB_DSN"):
                get_db_connection_params()

    @pytest.mark.unit
    def test_missing_all_params(self):
        """全てのパラメータが欠けている場合"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                get_db_connection_params()
            error_message = str(exc_info.value)
            assert "DB_USERNAME" in error_message
            assert "DB_PASSWORD" in error_message
            assert "DB_DSN" in error_message


class TestGetGenaiConfig:
    """get_genai_config() のテスト"""

    @pytest.mark.unit
    def test_success_with_required_params(self):
        """必須パラメータのみ設定されている場合（デフォルト値使用）"""
        with patch.dict(os.environ, {
            'OCI_COMPARTMENT_ID': 'ocid1.compartment.oc1..test',
            'OCI_REGION': 'us-chicago-1'
        }, clear=True):
            result = get_genai_config()
            assert result['compartment_id'] == 'ocid1.compartment.oc1..test'
            assert result['endpoint'] == 'https://inference.generativeai.us-chicago-1.oci.oraclecloud.com'
            assert result['embed_model'] == 'cohere.embed-v4.0'  # デフォルト
            assert result['llm_model'] == 'cohere.command-a-03-2025'  # デフォルト

    @pytest.mark.unit
    def test_success_with_custom_models(self):
        """カスタムモデルを指定した場合"""
        with patch.dict(os.environ, {
            'OCI_COMPARTMENT_ID': 'ocid1.compartment.oc1..test',
            'OCI_REGION': 'ap-osaka-1',
            'OCI_EMBED_MODEL': 'custom.embed.model',
            'OCI_LLM_MODEL': 'custom.llm.model'
        }, clear=True):
            result = get_genai_config()
            assert result['compartment_id'] == 'ocid1.compartment.oc1..test'
            assert result['endpoint'] == 'https://inference.generativeai.ap-osaka-1.oci.oraclecloud.com'
            assert result['embed_model'] == 'custom.embed.model'
            assert result['llm_model'] == 'custom.llm.model'

    @pytest.mark.unit
    def test_missing_compartment_id(self):
        """Compartment IDが欠けている場合"""
        with patch.dict(os.environ, {
            'OCI_REGION': 'us-chicago-1'
        }, clear=True):
            with pytest.raises(ValueError, match="OCI_COMPARTMENT_ID"):
                get_genai_config()

    @pytest.mark.unit
    def test_missing_region(self):
        """リージョンが欠けている場合"""
        with patch.dict(os.environ, {
            'OCI_COMPARTMENT_ID': 'ocid1.compartment.oc1..test'
        }, clear=True):
            with pytest.raises(ValueError, match="OCI_REGION"):
                get_genai_config()


class TestGetObjectStorageConfig:
    """get_object_storage_config() のテスト"""

    @pytest.mark.unit
    def test_default_values(self):
        """環境変数が設定されていない場合"""
        with patch.dict(os.environ, {}, clear=True):
            result = get_object_storage_config()
            assert result['bucket_name'] == ''
            assert result['namespace'] == ''

    @pytest.mark.unit
    def test_custom_values(self):
        """カスタム値が設定されている場合"""
        with patch.dict(os.environ, {
            'OCI_BUCKET_NAME': 'test-bucket',
            'OCI_NAMESPACE': 'test-namespace'
        }, clear=True):
            result = get_object_storage_config()
            assert result['bucket_name'] == 'test-bucket'
            assert result['namespace'] == 'test-namespace'


# =============================================================================
# ファイルシステム操作のテスト
# =============================================================================

class TestLoadConfig:
    """load_config() のテスト"""

    @pytest.mark.unit
    def test_env_file_in_current_directory(self, tmp_path, monkeypatch):
        """カレントディレクトリに.envがある場合"""
        ConfigLoader._reset()  # Singletonの状態をリセット
        # 既存のインスタンスも強制的にリセット
        import config_loader
        config_loader._default_config_loader = ConfigLoader()

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\n")

        monkeypatch.chdir(tmp_path)

        with patch('config_loader.load_dotenv') as mock_load_dotenv:
            with patch('builtins.print'):
                load_config()
                mock_load_dotenv.assert_called_once()
                called_path = mock_load_dotenv.call_args[0][0]
                assert called_path.name == ".env"

    @pytest.mark.unit
    def test_env_file_in_parent_directory(self, tmp_path, monkeypatch):
        """親ディレクトリに.envがある場合"""
        ConfigLoader._reset()  # Singletonの状態をリセット
        # 既存のインスタンスも強制的にリセット
        import config_loader
        config_loader._default_config_loader = ConfigLoader()

        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=test_value\n")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        monkeypatch.chdir(subdir)

        with patch('config_loader.load_dotenv') as mock_load_dotenv:
            with patch('builtins.print'):
                load_config()
                mock_load_dotenv.assert_called_once()
                called_path = mock_load_dotenv.call_args[0][0]
                assert called_path.name == ".env"

    @pytest.mark.unit
    def test_env_file_not_found(self, tmp_path, monkeypatch):
        """.envファイルが見つからない場合"""
        ConfigLoader._reset()  # Singletonの状態をリセット
        # 既存のインスタンスも強制的にリセット
        import config_loader
        config_loader._default_config_loader = ConfigLoader()

        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError, match=".envファイルが見つかりません"):
            load_config()


# =============================================================================
# OCI クライアントのテスト（モック使用）
# =============================================================================

class TestGetOciConfig:
    """get_oci_config() のテスト"""

    @pytest.mark.unit
    def test_success_with_default_profile(self):
        """デフォルトプロファイルでの設定読み込み"""
        mock_config = {
            'user': 'ocid1.user.oc1..test',
            'region': 'us-chicago-1',
            'tenancy': 'ocid1.tenancy.oc1..test'
        }

        with patch.dict(os.environ, {}, clear=True):
            with patch('config_loader.Path.exists', return_value=True):
                with patch('oci.config.from_file', return_value=mock_config):
                    with patch('builtins.print'):
                        result = get_oci_config()
                        assert result['user'] == 'ocid1.user.oc1..test'
                        assert result['region'] == 'us-chicago-1'

    @pytest.mark.unit
    def test_success_with_custom_profile(self):
        """カスタムプロファイルでの設定読み込み"""
        mock_config = {
            'user': 'ocid1.user.oc1..test',
            'region': 'ap-osaka-1'
        }

        with patch.dict(os.environ, {'OCI_PROFILE': 'CUSTOM'}, clear=True):
            with patch('config_loader.Path.exists', return_value=True):
                with patch('oci.config.from_file', return_value=mock_config) as mock_from_file:
                    with patch('builtins.print'):
                        result = get_oci_config()
                        mock_from_file.assert_called_once()
                        # 位置引数として渡されているため、call_args[0][1]で確認
                        assert mock_from_file.call_args[0][1] == 'CUSTOM'

    @pytest.mark.unit
    def test_config_file_not_found(self):
        """設定ファイルが見つからない場合"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('config_loader.Path.exists', return_value=False):
                with pytest.raises(FileNotFoundError, match="OCI設定ファイルが見つかりません"):
                    get_oci_config()

    @pytest.mark.unit
    def test_config_file_invalid(self):
        """設定ファイルの読み込みに失敗した場合"""
        with patch.dict(os.environ, {}, clear=True):
            with patch('config_loader.Path.exists', return_value=True):
                with patch('oci.config.from_file', side_effect=Exception("Invalid config")):
                    with pytest.raises(ValueError, match="OCI設定の読み込みに失敗しました"):
                        get_oci_config()


class TestGetGenaiClient:
    """get_genai_client() のテスト"""

    @pytest.mark.unit
    def test_client_creation(self):
        """GenAIクライアントの作成"""
        mock_oci_config = {'region': 'us-chicago-1'}
        mock_genai_config = {
            'compartment_id': 'ocid1.compartment.oc1..test',
            'endpoint': 'https://inference.generativeai.us-chicago-1.oci.oraclecloud.com'
        }

        # _default_config_loaderのメソッドをモック
        with patch.object(ConfigLoader, 'get_oci_config', return_value=mock_oci_config):
            with patch.object(ConfigLoader, 'get_genai_config', return_value=mock_genai_config):
                with patch('oci.generative_ai_inference.GenerativeAiInferenceClient') as mock_client_class:
                    mock_client = MagicMock()
                    mock_client_class.return_value = mock_client

                    result = get_genai_client()

                    assert result == mock_client
                    mock_client_class.assert_called_once_with(
                        config=mock_oci_config,
                        service_endpoint=mock_genai_config['endpoint']
                    )


class TestGetObjectStorageClient:
    """get_object_storage_client() のテスト"""

    @pytest.mark.unit
    def test_client_creation(self):
        """Object Storageクライアントの作成"""
        mock_oci_config = {'region': 'us-chicago-1'}

        # _default_config_loaderのメソッドをモック
        with patch.object(ConfigLoader, 'get_oci_config', return_value=mock_oci_config):
            with patch('oci.object_storage.ObjectStorageClient') as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client

                result = get_object_storage_client()

                assert result == mock_client
                mock_client_class.assert_called_once_with(mock_oci_config)
