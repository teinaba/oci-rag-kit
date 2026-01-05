"""
Unit tests for EmbeddingGenerator class

This module contains comprehensive tests for the EmbeddingGenerator class,
which generates embeddings using OCI Generative AI Service.

TDD（テスト駆動開発）アプローチで実装
目標カバレッジ: 90-95%
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.data_pipeline.embedding_generator import EmbeddingGenerator, Embedding
from src.data_pipeline.exceptions import EmbeddingError


class TestEmbeddingGeneratorInit:
    """コンストラクタの検証"""

    def test_default_initialization(self):
        """デフォルト値で初期化できることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-compartment',
                'endpoint': 'https://test.endpoint.com',
                'embed_model': 'cohere.embed-v4.0'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            assert generator.model_id == 'cohere.embed-v4.0'
            assert generator.compartment_id == 'test-compartment'
            assert generator.service_endpoint == 'https://test.endpoint.com'
            assert generator.logger is not None
            assert generator._embedder is None  # Lazy initialization

    def test_custom_model_initialization(self):
        """カスタムモデルIDで初期化できることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-compartment',
                'endpoint': 'https://test.endpoint.com',
                'embed_model': 'cohere.embed-v4.0'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator(model_id='custom.embed-model')

            assert generator.model_id == 'custom.embed-model'

    def test_config_loader_integration(self):
        """ConfigLoaderが正しく使用されることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config_class:
            mock_instance = Mock()
            mock_config_class.return_value = mock_instance
            mock_instance.get_genai_config.return_value = {
                'compartment_id': 'comp-id',
                'endpoint': 'https://endpoint.com',
                'embed_model': 'model-v1'
            }
            mock_instance.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            # ConfigLoader methods called
            mock_instance.get_genai_config.assert_called_once()
            mock_instance.get_genai_client.assert_called_once()


class TestEmbedQuery:
    """embed_queryメソッドのテスト"""

    def test_embed_query_returns_embedding_object(self):
        """embed_queryがEmbeddingオブジェクトを返すことを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            # Mock the embedder
            mock_embedder = Mock()
            mock_embedder.embed_query.return_value = [0.1, 0.2, 0.3]
            generator._embedder = mock_embedder

            result = generator.embed_query("test text")

            assert isinstance(result, Embedding)
            assert result.vector_str == "[0.1, 0.2, 0.3]"
            assert result.dimension == 3
            assert result.model_id == 'test-model'

    def test_embed_query_calls_embedder(self):
        """embed_queryが内部embedderを呼び出すことを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            # Mock the embedder
            mock_embedder = Mock()
            mock_embedder.embed_query.return_value = [0.5, 0.6]
            generator._embedder = mock_embedder

            result = generator.embed_query("sample text")

            mock_embedder.embed_query.assert_called_once_with("sample text")
            assert result.vector_str == "[0.5, 0.6]"

    def test_embed_query_empty_text_raises_error(self):
        """空のテキストでEmbeddingErrorが発生することを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            with pytest.raises(EmbeddingError, match="Input text cannot be empty"):
                generator.embed_query("")

    def test_embed_query_non_string_input_raises_error(self):
        """文字列以外の入力でEmbeddingErrorが発生することを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            with pytest.raises(EmbeddingError, match="Input must be str"):
                generator.embed_query(123)  # type: ignore

    def test_embed_query_none_input_raises_error(self):
        """None入力でEmbeddingErrorが発生することを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            with pytest.raises(EmbeddingError, match="Input must be str"):
                generator.embed_query(None)  # type: ignore

    def test_embed_query_vector_format_validation(self):
        """ベクトルが正しい文字列形式に変換されることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            # Mock the embedder
            mock_embedder = Mock()
            test_vector = [0.123, 0.456, 0.789]
            mock_embedder.embed_query.return_value = test_vector
            generator._embedder = mock_embedder

            result = generator.embed_query("test")

            # Vector should be string representation
            assert result.vector_str == str(test_vector)
            assert result.vector_str.startswith("[")
            assert result.vector_str.endswith("]")


class TestLazyInitialization:
    """遅延初期化の検証"""

    def test_embedder_not_initialized_on_construction(self):
        """コンストラクタでembedderが初期化されないことを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            assert generator._embedder is None

    @patch('src.data_pipeline.embedding_generator.OCIGenAIEmbeddings')
    def test_embedder_initialized_on_first_access(self, mock_embeddings_class):
        """初回アクセス時にembedderが初期化されることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_client = Mock()
            mock_config.return_value.get_genai_client.return_value = mock_client

            mock_embeddings_class.return_value = Mock()

            generator = EmbeddingGenerator()

            # Access via property
            embedder = generator.embedder

            assert embedder is not None
            assert generator._embedder is embedder  # Cached
            mock_embeddings_class.assert_called_once()

    @patch('src.data_pipeline.embedding_generator.OCIGenAIEmbeddings')
    def test_embedder_reused_on_subsequent_calls(self, mock_embeddings_class):
        """2回目以降のアクセスでembedderが再利用されることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            mock_embeddings_class.return_value = Mock()

            generator = EmbeddingGenerator()

            embedder1 = generator.embedder
            embedder2 = generator.embedder

            assert embedder1 is embedder2  # Same instance
            assert mock_embeddings_class.call_count == 1  # Only called once


class TestErrorHandling:
    """エラーハンドリングのテスト"""

    def test_api_error_wrapped_in_embedding_error(self):
        """APIエラーがEmbeddingErrorでラップされることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            # Mock the embedder to raise an exception
            mock_embedder = Mock()
            original_error = Exception("API connection failed")
            mock_embedder.embed_query.side_effect = original_error
            generator._embedder = mock_embedder

            with pytest.raises(EmbeddingError) as exc_info:
                generator.embed_query("test text")

            # Exception chain preserved
            assert exc_info.value.__cause__ is original_error

    def test_error_message_includes_text_preview(self):
        """エラーメッセージにテキストプレビューが含まれることを確認"""
        with patch('src.data_pipeline.embedding_generator.ConfigLoader') as mock_config:
            mock_config.return_value.get_genai_config.return_value = {
                'compartment_id': 'test-comp',
                'endpoint': 'https://test.com',
                'embed_model': 'test-model'
            }
            mock_config.return_value.get_genai_client.return_value = Mock()

            generator = EmbeddingGenerator()

            # Mock the embedder to raise an exception
            mock_embedder = Mock()
            mock_embedder.embed_query.side_effect = Exception("Test error")
            generator._embedder = mock_embedder

            with pytest.raises(EmbeddingError, match="Failed to generate embedding"):
                generator.embed_query("sample text for testing")


class TestEmbeddingDataclass:
    """Embeddingデータクラスのテスト"""

    def test_embedding_creation(self):
        """Embeddingが正しく作成されることを確認"""
        embedding = Embedding(
            vector_str="[0.1, 0.2, 0.3]",
            dimension=3,
            model_id="test-model"
        )

        assert embedding.vector_str == "[0.1, 0.2, 0.3]"
        assert embedding.dimension == 3
        assert embedding.model_id == "test-model"

    def test_embedding_attributes(self):
        """Embedding属性が正しくアクセスできることを確認"""
        embedding = Embedding(
            vector_str="[1.0, 2.0]",
            dimension=2,
            model_id="model-v1"
        )

        assert hasattr(embedding, 'vector_str')
        assert hasattr(embedding, 'dimension')
        assert hasattr(embedding, 'model_id')
