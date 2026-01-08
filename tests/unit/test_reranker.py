"""
JapaneseRerankerクラスのユニットテスト
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.rag.reranker import JapaneseReranker, RankedChunk
from src.rag.vector_searcher import SearchResult
from src.rag.exceptions import RerankError


class TestJapaneseRerankerInit:
    """JapaneseReranker.__init__()のテスト"""

    def test_stores_configuration_parameters_with_defaults(self):
        """デフォルト設定でパラメータが正しく保存されることを確認"""
        with patch('src.rag.reranker.JapaneseReranker._detect_device', return_value='cpu'):
            reranker = JapaneseReranker()

            assert reranker.model_name == 'hotchpotch/japanese-reranker-base-v2'
            assert reranker.device == 'cpu'
            assert reranker.max_length == 512
            assert reranker.batch_size == 32
            assert reranker._model is None

    def test_stores_custom_configuration_parameters(self):
        """カスタム設定でパラメータが正しく保存されることを確認"""
        reranker = JapaneseReranker(
            model_name='custom/model',
            device='cuda',
            max_length=256,
            batch_size=16
        )

        assert reranker.model_name == 'custom/model'
        assert reranker.device == 'cuda'
        assert reranker.max_length == 256
        assert reranker.batch_size == 16

    def test_raises_error_when_max_length_is_zero(self):
        """max_lengthが0の場合にValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="max_length must be > 0"):
            JapaneseReranker(max_length=0)

    def test_raises_error_when_batch_size_is_zero(self):
        """batch_sizeが0の場合にValueErrorが発生することを確認"""
        with pytest.raises(ValueError, match="batch_size must be > 0"):
            JapaneseReranker(batch_size=0)


class TestDetectDevice:
    """_detect_device()メソッドのテスト"""

    @patch('torch.cuda.is_available', return_value=True)
    def test_detect_device_returns_cuda_when_available(self, mock_cuda):
        """CUDAが利用可能な場合にcudaが返されることを確認"""
        device = JapaneseReranker._detect_device()
        assert device == 'cuda'

    @patch('src.rag.reranker.torch.mps.is_available', return_value=True)
    @patch('src.rag.reranker.torch.cuda.is_available', return_value=False)
    def test_detect_device_returns_mps_when_cuda_unavailable(self, mock_cuda, mock_mps):
        """CUDAが利用不可でMPSが利用可能な場合にmpsが返されることを確認"""
        device = JapaneseReranker._detect_device()
        assert device == 'mps'

    @patch('src.rag.reranker.torch.cuda.is_available', return_value=False)
    def test_detect_device_returns_cpu_as_fallback(self, mock_cuda):
        """CUDA/MPSが利用不可の場合にcpuが返されることを確認"""
        # torchモジュールからmps属性を削除してシミュレート
        import src.rag.reranker as reranker_module
        original_torch = reranker_module.torch

        # mps属性を持たないtorchモジュールをモック
        mock_torch = Mock()
        mock_torch.cuda.is_available.return_value = False
        # mps属性を持たせない（古いPyTorchバージョンをシミュレート）
        if hasattr(mock_torch, 'mps'):
            delattr(mock_torch, 'mps')

        # reranker_module.torchを一時的に置き換え
        reranker_module.torch = mock_torch

        try:
            device = JapaneseReranker._detect_device()
            assert device == 'cpu'
        finally:
            # 元に戻す
            reranker_module.torch = original_torch


class TestModel:
    """modelプロパティのテスト"""

    def test_model_not_initialized_on_construction(self):
        """コンストラクタでmodelが初期化されないことを確認"""
        reranker = JapaneseReranker(device='cpu')
        assert reranker._model is None

    @patch('sentence_transformers.CrossEncoder')
    def test_model_initialized_on_first_access_cpu(self, mock_cross_encoder_class):
        """CPUデバイスでの初回アクセス時にmodelが初期化されることを確認"""
        mock_model = Mock()
        mock_cross_encoder_class.return_value = mock_model

        reranker = JapaneseReranker(device='cpu')
        model = reranker.model

        mock_cross_encoder_class.assert_called_once_with(
            'hotchpotch/japanese-reranker-base-v2',
            max_length=512,
            device='cpu'
        )
        assert model == mock_model

    @patch('sentence_transformers.CrossEncoder')
    def test_model_initialized_with_half_precision_on_gpu(self, mock_cross_encoder_class):
        """GPU/MPSデバイスでhalf精度化されることを確認"""
        mock_model = Mock()
        mock_model.model = Mock()
        mock_model.model.half = Mock()
        mock_cross_encoder_class.return_value = mock_model

        reranker = JapaneseReranker(device='cuda')
        _ = reranker.model

        mock_model.model.half.assert_called_once()

    @patch('sentence_transformers.CrossEncoder')
    def test_model_raises_error_on_initialization_failure(self, mock_cross_encoder_class):
        """model初期化失敗時にRerankErrorが発生することを確認"""
        mock_cross_encoder_class.side_effect = Exception("Model load error")

        reranker = JapaneseReranker(device='cpu')

        with pytest.raises(RerankError, match="Failed to initialize reranker model"):
            _ = reranker.model


class TestRerank:
    """rerank()メソッドのテスト"""

    @patch('sentence_transformers.CrossEncoder')
    def test_rerank_returns_ranked_chunks(self, mock_cross_encoder_class):
        """リランクが正常に動作し、RankedChunkのリストが返されることを確認"""
        # CrossEncoderをモック
        mock_model = Mock()
        mock_model.predict.return_value = [0.8, 0.3, 0.9]
        mock_cross_encoder_class.return_value = mock_model

        # SearchResultのリストを作成
        search_results = [
            SearchResult(
                chunk_id=1,
                document_id=100,
                filename='doc1.pdf',
                chunk_text='チャンク1',
                distance=0.15
            ),
            SearchResult(
                chunk_id=2,
                document_id=100,
                filename='doc1.pdf',
                chunk_text='チャンク2',
                distance=0.25
            ),
            SearchResult(
                chunk_id=3,
                document_id=101,
                filename='doc2.pdf',
                chunk_text='チャンク3',
                distance=0.10
            ),
        ]

        reranker = JapaneseReranker(device='cpu')
        results = reranker.rerank('テスト質問', search_results, top_n=2)

        # 結果の検証
        assert len(results) == 2
        assert isinstance(results[0], RankedChunk)
        # スコア順（降順）で並んでいることを確認: 0.9 > 0.8 > 0.3
        assert results[0].chunk_id == 3  # score=0.9
        assert results[0].rerank_score == 0.9
        assert results[1].chunk_id == 1  # score=0.8
        assert results[1].rerank_score == 0.8

        # CrossEncoder.predict()が正しく呼ばれたことを確認
        mock_model.predict.assert_called_once()
        call_args = mock_model.predict.call_args
        pairs = call_args[0][0]
        assert pairs == [
            ['テスト質問', 'チャンク1'],
            ['テスト質問', 'チャンク2'],
            ['テスト質問', 'チャンク3'],
        ]

    @patch('sentence_transformers.CrossEncoder')
    def test_rerank_returns_empty_list_for_empty_input(self, mock_cross_encoder_class):
        """空の入力リストに対して空リストが返されることを確認"""
        reranker = JapaneseReranker(device='cpu')
        results = reranker.rerank('テスト質問', [], top_n=5)

        assert results == []

    @patch('sentence_transformers.CrossEncoder')
    def test_rerank_fallback_on_prediction_error(self, mock_cross_encoder_class):
        """予測エラー時にフォールバック（distance順）されることを確認"""
        # CrossEncoderをモック with error
        mock_model = Mock()
        mock_model.predict.side_effect = Exception("Prediction error")
        mock_cross_encoder_class.return_value = mock_model

        search_results = [
            SearchResult(1, 100, 'doc1.pdf', 'チャンク1', 0.25),
            SearchResult(2, 100, 'doc1.pdf', 'チャンク2', 0.10),
            SearchResult(3, 101, 'doc2.pdf', 'チャンク3', 0.15),
        ]

        reranker = JapaneseReranker(device='cpu')
        results = reranker.rerank('テスト質問', search_results, top_n=2)

        # フォールバック: distanceの昇順で並ぶ
        assert len(results) == 2
        assert results[0].chunk_id == 2  # distance=0.10
        assert results[0].distance == 0.10
        assert results[1].chunk_id == 3  # distance=0.15
        assert results[1].distance == 0.15
        # フォールバック時はrerank_scoreがNone
        assert results[0].rerank_score is None

    @patch('sentence_transformers.CrossEncoder')
    def test_rerank_respects_top_n_parameter(self, mock_cross_encoder_class):
        """top_nパラメータに従って結果が制限されることを確認"""
        mock_model = Mock()
        mock_model.predict.return_value = [0.5, 0.8, 0.3, 0.9, 0.6]
        mock_cross_encoder_class.return_value = mock_model

        search_results = [
            SearchResult(i, 100, 'doc.pdf', f'chunk{i}', 0.1 * i)
            for i in range(1, 6)
        ]

        reranker = JapaneseReranker(device='cpu')
        results = reranker.rerank('質問', search_results, top_n=3)

        assert len(results) == 3
        # 上位3件: 0.9, 0.8, 0.6
        assert results[0].rerank_score == 0.9
        assert results[1].rerank_score == 0.8
        assert results[2].rerank_score == 0.6

    @patch('sentence_transformers.CrossEncoder')
    def test_rerank_raises_error_for_empty_query(self, mock_cross_encoder_class):
        """空のクエリでRerankErrorが発生することを確認"""
        reranker = JapaneseReranker(device='cpu')
        search_results = [
            SearchResult(1, 100, 'doc.pdf', 'chunk', 0.1)
        ]

        with pytest.raises(RerankError, match="Query cannot be empty"):
            reranker.rerank('', search_results, top_n=5)

    @patch('sentence_transformers.CrossEncoder')
    def test_rerank_raises_error_for_invalid_top_n(self, mock_cross_encoder_class):
        """top_nが0以下の場合にRerankErrorが発生することを確認"""
        reranker = JapaneseReranker(device='cpu')
        search_results = [
            SearchResult(1, 100, 'doc.pdf', 'chunk', 0.1)
        ]

        with pytest.raises(RerankError, match="top_n must be > 0"):
            reranker.rerank('質問', search_results, top_n=0)
