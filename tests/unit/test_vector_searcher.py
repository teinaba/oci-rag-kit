"""
VectorSearcherクラスのユニットテスト
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.rag.vector_searcher import VectorSearcher, SearchResult
from src.rag.exceptions import VectorSearchError


class TestVectorSearcherInit:
    """VectorSearcher.__init__()のテスト"""

    def test_stores_configuration_parameters(self):
        """設定パラメータが正しく保存されることを確認"""
        db_params = {'user': 'admin', 'password': 'pass', 'dsn': 'dsn'}
        genai_client = Mock()

        searcher = VectorSearcher(
            db_params=db_params,
            embedding_model='cohere.embed-v4.0',
            genai_client=genai_client,
            compartment_id='ocid1.compartment.test',
            service_endpoint='https://test.endpoint',
            top_k=5
        )

        assert searcher.db_params == db_params
        assert searcher.embedding_model == 'cohere.embed-v4.0'
        assert searcher.genai_client == genai_client
        assert searcher.compartment_id == 'ocid1.compartment.test'
        assert searcher.service_endpoint == 'https://test.endpoint'
        assert searcher.top_k == 5

    def test_raises_error_when_db_params_is_none(self):
        """db_paramsがNoneの場合にValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="db_params is required"):
            VectorSearcher(
                db_params=None,
                embedding_model='cohere.embed-v4.0',
                genai_client=Mock(),
                compartment_id='test',
                service_endpoint='https://test'
            )

    def test_raises_error_when_embedding_model_is_empty(self):
        """embedding_modelが空の場合にValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="embedding_model is required"):
            VectorSearcher(
                db_params={'user': 'admin'},
                embedding_model='',
                genai_client=Mock(),
                compartment_id='test',
                service_endpoint='https://test'
            )

    def test_raises_error_when_top_k_is_zero(self):
        """top_kが0の場合にValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="top_k must be > 0"):
            VectorSearcher(
                db_params={'user': 'admin'},
                embedding_model='cohere.embed-v4.0',
                genai_client=Mock(),
                compartment_id='test',
                service_endpoint='https://test',
                top_k=0
            )


class TestEmbedder:
    """embedderプロパティのテスト"""

    def test_embedder_not_initialized_on_construction(self):
        """コンストラクタでembedderが初期化されないことを確認"""
        searcher = VectorSearcher(
            db_params={'user': 'admin'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )
        assert searcher._embedder is None

    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_embedder_initialized_on_first_access(self, mock_embeddings_class):
        """初回アクセス時にembedderが初期化されることを確認"""
        mock_embeddings = Mock()
        mock_embeddings_class.return_value = mock_embeddings

        searcher = VectorSearcher(
            db_params={'user': 'admin'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='ocid1.compartment.test',
            service_endpoint='https://test.endpoint'
        )

        embedder = searcher.embedder

        mock_embeddings_class.assert_called_once_with(
            model_id='cohere.embed-v4.0',
            service_endpoint='https://test.endpoint',
            compartment_id='ocid1.compartment.test',
            auth_type="API_KEY",
            model_kwargs={"input_type": "search_query"}
        )
        assert embedder == mock_embeddings

    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_embedder_raises_error_on_initialization_failure(self, mock_embeddings_class):
        """embedder初期化失敗時にVectorSearchErrorが発生することを確認"""
        mock_embeddings_class.side_effect = Exception("API key error")

        searcher = VectorSearcher(
            db_params={'user': 'admin'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )

        with pytest.raises(VectorSearchError, match="Failed to initialize embedder"):
            _ = searcher.embedder


class TestEmbedQuery:
    """embed_query()メソッドのテスト"""

    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_embed_query_returns_embedding_vector(self, mock_embeddings_class):
        """クエリが正常に埋め込みベクトルに変換されることを確認"""
        mock_embeddings = Mock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_embeddings_class.return_value = mock_embeddings

        searcher = VectorSearcher(
            db_params={'user': 'admin'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )

        result = searcher.embed_query("テスト質問")

        assert result == [0.1, 0.2, 0.3]
        mock_embeddings.embed_query.assert_called_once_with("テスト質問")

    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_embed_query_raises_error_on_empty_query(self, mock_embeddings_class):
        """空のクエリでVectorSearchErrorが発生することを確認"""
        mock_embeddings_class.return_value = Mock()

        searcher = VectorSearcher(
            db_params={'user': 'admin'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )

        with pytest.raises(VectorSearchError, match="Query cannot be empty"):
            searcher.embed_query("")


class TestSearch:
    """search()メソッドのテスト"""

    @patch('oracledb.connect')
    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_search_without_filtering(self, mock_embeddings_class, mock_connect):
        """フィルタリングなしの検索が正常に動作することを確認"""
        # Embedderをモック
        mock_embeddings = Mock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_embeddings_class.return_value = mock_embeddings

        # DB mock
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        # CLOBデータをモック
        mock_clob = Mock()
        mock_clob.read.return_value = "チャンクテキスト1"

        mock_cursor.fetchall.return_value = [
            (1, 100, 'doc1.pdf', mock_clob, 0.15),
            (2, 100, 'doc1.pdf', 'チャンクテキスト2', 0.25),
        ]

        searcher = VectorSearcher(
            db_params={'user': 'admin', 'password': 'pass', 'dsn': 'dsn'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )

        results = searcher.search("テスト質問", top_k=2)

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].chunk_id == 1
        assert results[0].chunk_text == "チャンクテキスト1"
        assert results[0].distance == 0.15
        assert results[1].chunk_text == "チャンクテキスト2"

        # SQLにfilteringパラメータが含まれないことを確認
        call_args = mock_cursor.execute.call_args[0]
        bind_params = call_args[1]
        assert 'filtering' not in bind_params

    @patch('oracledb.connect')
    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_search_with_filtering(self, mock_embeddings_class, mock_connect):
        """フィルタリング指定時の検索が正常に動作することを確認"""
        # Embedderをモック
        mock_embeddings = Mock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_embeddings_class.return_value = mock_embeddings

        # DB mock
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        mock_cursor.fetchall.return_value = [
            (1, 100, 'manual.pdf', 'マニュアルの内容', 0.10),
        ]

        searcher = VectorSearcher(
            db_params={'user': 'admin', 'password': 'pass', 'dsn': 'dsn'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )

        results = searcher.search("テスト質問", top_k=5, filtering='manual')

        assert len(results) == 1
        assert results[0].filename == 'manual.pdf'

        # SQLにfilteringパラメータが含まれることを確認
        call_args = mock_cursor.execute.call_args[0]
        bind_params = call_args[1]
        assert bind_params['filtering'] == 'manual'

    @patch('oracledb.connect')
    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_search_returns_empty_list_when_no_results(self, mock_embeddings_class, mock_connect):
        """検索結果が0件の場合に空リストが返されることを確認"""
        # Embedderをモック
        mock_embeddings = Mock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_embeddings_class.return_value = mock_embeddings

        # DB mock
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_connection

        mock_cursor.fetchall.return_value = []

        searcher = VectorSearcher(
            db_params={'user': 'admin', 'password': 'pass', 'dsn': 'dsn'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )

        results = searcher.search("存在しない質問", top_k=10)

        assert results == []

    @patch('oracledb.connect')
    @patch('langchain_community.embeddings.OCIGenAIEmbeddings')
    def test_search_raises_error_on_db_connection_failure(self, mock_embeddings_class, mock_connect):
        """DB接続失敗時にVectorSearchErrorが発生することを確認"""
        # Embedderをモック
        mock_embeddings = Mock()
        mock_embeddings.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_embeddings_class.return_value = mock_embeddings

        # DB connection error
        mock_connect.side_effect = Exception("Database connection failed")

        searcher = VectorSearcher(
            db_params={'user': 'admin', 'password': 'pass', 'dsn': 'dsn'},
            embedding_model='cohere.embed-v4.0',
            genai_client=Mock(),
            compartment_id='test',
            service_endpoint='https://test'
        )

        with pytest.raises(VectorSearchError, match="Vector search failed"):
            searcher.search("テスト質問")
