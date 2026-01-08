"""
AnswerGeneratorクラスのユニットテスト

テストカバレッジ:
- コンストラクタのバリデーション
- Cohereモデル生成（CohereChatRequest）
- Genericモデル生成（GenericChatRequest）
- HTTP 429リトライロジックと指数バックオフ
- プロンプト構築
- 無効なモデル指定
- Error handling
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
import time

from src.rag.answer_generator import AnswerGenerator, GeneratedAnswer
from src.rag.exceptions import AnswerGenerationError, RateLimitError
from src.rag.reranker import RankedChunk


class TestAnswerGenerator:
    """Test suite for AnswerGenerator class"""

    @pytest.fixture
    def mock_genai_client(self):
        """Mock OCI GenAI Client"""
        client = MagicMock()
        return client

    @pytest.fixture
    def valid_params(self, mock_genai_client):
        """Valid AnswerGenerator initialization parameters"""
        return {
            'genai_client': mock_genai_client,
            'compartment_id': 'ocid1.compartment.oc1..test',
            'default_model': 'cohere.command-a-03-2025',
            'max_retries': 3,
            'retry_delay': 60
        }

    @pytest.fixture
    def sample_contexts(self):
        """Sample RankedChunk list for testing"""
        return [
            RankedChunk(
                chunk_id=1,
                document_id=101,
                filename='doc1.pdf',
                chunk_text='This is context 1',
                distance=0.1,
                rerank_score=0.9
            ),
            RankedChunk(
                chunk_id=2,
                document_id=102,
                filename='doc2.pdf',
                chunk_text='This is context 2',
                distance=0.2,
                rerank_score=0.8
            )
        ]

    # ========================================
    # コンストラクタのテスト
    # ========================================

    def test_constructor_valid_params(self, valid_params):
        """Test AnswerGenerator initialization with valid parameters"""
        generator = AnswerGenerator(**valid_params)

        assert generator.genai_client == valid_params['genai_client']
        assert generator.compartment_id == valid_params['compartment_id']
        assert generator.default_model == valid_params['default_model']
        assert generator.max_retries == 3
        assert generator.retry_delay == 60

    def test_constructor_missing_genai_client(self, valid_params):
        """Test constructor raises ValueError when genai_client is missing"""
        valid_params['genai_client'] = None

        with pytest.raises(ValueError, match="genai_client is required"):
            AnswerGenerator(**valid_params)

    def test_constructor_missing_compartment_id(self, valid_params):
        """Test constructor raises ValueError when compartment_id is missing"""
        valid_params['compartment_id'] = None

        with pytest.raises(ValueError, match="compartment_id is required"):
            AnswerGenerator(**valid_params)

    def test_constructor_empty_compartment_id(self, valid_params):
        """Test constructor raises ValueError when compartment_id is empty"""
        valid_params['compartment_id'] = ''

        with pytest.raises(ValueError, match="compartment_id is required"):
            AnswerGenerator(**valid_params)

    def test_constructor_invalid_max_retries(self, valid_params):
        """Test constructor raises ValueError when max_retries is negative"""
        valid_params['max_retries'] = -1

        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            AnswerGenerator(**valid_params)

    def test_constructor_invalid_retry_delay(self, valid_params):
        """Test constructor raises ValueError when retry_delay is negative"""
        valid_params['retry_delay'] = -1

        with pytest.raises(ValueError, match="retry_delay must be > 0"):
            AnswerGenerator(**valid_params)

    # ========================================
    # Cohereモデルのテスト（CohereChatRequest）
    # ========================================

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    def test_generate_cohere_model_success(
        self,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test successful answer generation with Cohere model"""
        generator = AnswerGenerator(**valid_params)

        # レスポンスをモック
        mock_response = MagicMock()
        mock_response.data.chat_response.text = "This is the generated answer"
        generator.genai_client.chat.return_value = mock_response

        # 実行
        result = generator.generate(
            query="What is AI?",
            contexts=sample_contexts,
            model='cohere.command-a-03-2025'
        )

        # 検証
        assert isinstance(result, GeneratedAnswer)
        assert result.answer == "This is the generated answer"
        assert result.model_used == 'cohere.command-a-03-2025'
        assert result.generation_time > 0
        assert generator.genai_client.chat.called

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    def test_generate_cohere_default_model(
        self,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test answer generation uses default_model when model is None"""
        generator = AnswerGenerator(**valid_params)

        # レスポンスをモック
        mock_response = MagicMock()
        mock_response.data.chat_response.text = "Default model answer"
        generator.genai_client.chat.return_value = mock_response

        # 実行 (model=None should use default_model)
        result = generator.generate(
            query="What is AI?",
            contexts=sample_contexts
        )

        # 検証 default model was used
        assert result.model_used == 'cohere.command-a-03-2025'

    # ========================================
    # Genericモデルのテスト（GenericChatRequest）
    # ========================================

    @patch('src.rag.answer_generator.GenericChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    @patch('src.rag.answer_generator.UserMessage')
    @patch('src.rag.answer_generator.TextContent')
    def test_generate_generic_model_success(
        self,
        mock_text_content,
        mock_user_message,
        mock_serving_mode,
        mock_chat_details,
        mock_generic_request,
        valid_params,
        sample_contexts
    ):
        """Test successful answer generation with Generic model (Llama, Grok, etc.)"""
        generator = AnswerGenerator(**valid_params)

        # レスポンスをモック
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Generic model answer"
        mock_message.content = [mock_content]
        mock_choice.message = mock_message
        mock_response.data.chat_response.choices = [mock_choice]
        generator.genai_client.chat.return_value = mock_response

        # 実行 with Generic model
        result = generator.generate(
            query="What is AI?",
            contexts=sample_contexts,
            model='meta.llama-3.3-70b-instruct'
        )

        # 検証
        assert isinstance(result, GeneratedAnswer)
        assert result.answer == "Generic model answer"
        assert result.model_used == 'meta.llama-3.3-70b-instruct'
        assert result.generation_time > 0

    @patch('src.rag.answer_generator.GenericChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    @patch('src.rag.answer_generator.UserMessage')
    @patch('src.rag.answer_generator.TextContent')
    def test_generate_grok_model(
        self,
        mock_text_content,
        mock_user_message,
        mock_serving_mode,
        mock_chat_details,
        mock_generic_request,
        valid_params,
        sample_contexts
    ):
        """Test answer generation with xAI Grok model"""
        generator = AnswerGenerator(**valid_params)

        # レスポンスをモック
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "Grok model answer"
        mock_message.content = [mock_content]
        mock_choice.message = mock_message
        mock_response.data.chat_response.choices = [mock_choice]
        generator.genai_client.chat.return_value = mock_response

        # 実行
        result = generator.generate(
            query="What is AI?",
            contexts=sample_contexts,
            model='xai.grok-4-fast-non-reasoning'
        )

        # 検証
        assert result.answer == "Grok model answer"
        assert result.model_used == 'xai.grok-4-fast-non-reasoning'

    # ========================================
    # HTTP 429リトライロジックのテスト
    # ========================================

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    @patch('time.sleep', return_value=None)  # テストを高速化するためにsleepをモック
    def test_retry_on_http_429_success(
        self,
        mock_sleep,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test retry logic succeeds after HTTP 429 error"""
        generator = AnswerGenerator(**valid_params)

        # モック: 最初の呼び出しは429を返し、2回目は成功
        http_429_error = Exception("HTTP 429 Rate Limit")
        http_429_error.status = 429

        mock_success_response = MagicMock()
        mock_success_response.data.chat_response.text = "Success after retry"

        generator.genai_client.chat.side_effect = [
            http_429_error,
            mock_success_response
        ]

        # 実行
        result = generator.generate(
            query="What is AI?",
            contexts=sample_contexts
        )

        # 検証 retry occurred and succeeded
        assert result.answer == "Success after retry"
        assert generator.genai_client.chat.call_count == 2
        assert mock_sleep.called

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    @patch('time.sleep', return_value=None)
    def test_retry_on_http_429_max_retries_exceeded(
        self,
        mock_sleep,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test RateLimitError raised when max_retries exceeded"""
        generator = AnswerGenerator(**valid_params)

        # Mock: All calls raise 429
        http_429_error = Exception("HTTP 429 Rate Limit")
        http_429_error.status = 429
        generator.genai_client.chat.side_effect = http_429_error

        # 実行 and verify exception
        with pytest.raises(RateLimitError, match="Rate limit exceeded after 3 retries"):
            generator.generate(
                query="What is AI?",
                contexts=sample_contexts
            )

        # 検証 retry attempts (1 initial + 3 retries = 4 total)
        assert generator.genai_client.chat.call_count == 4

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    @patch('time.sleep', return_value=None)
    def test_retry_exponential_backoff(
        self,
        mock_sleep,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test exponential backoff in retry logic"""
        generator = AnswerGenerator(**valid_params)

        # Mock: First 2 calls raise 429, third succeeds
        http_429_error = Exception("HTTP 429")
        http_429_error.status = 429

        mock_success = MagicMock()
        mock_success.data.chat_response.text = "Success"

        generator.genai_client.chat.side_effect = [
            http_429_error,
            http_429_error,
            mock_success
        ]

        # 実行
        result = generator.generate(
            query="What is AI?",
            contexts=sample_contexts
        )

        # 検証 exponential backoff: 60, 120 seconds
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 60  # First retry: 60s
        assert mock_sleep.call_args_list[1][0][0] == 120  # Second retry: 120s

    # ========================================
    # エラーハンドリングのテスト
    # ========================================

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    def test_non_429_error_raised_immediately(
        self,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test non-429 errors are raised immediately without retry"""
        generator = AnswerGenerator(**valid_params)

        # Mock: Non-429 error
        other_error = Exception("Server error")
        other_error.status = 500
        generator.genai_client.chat.side_effect = other_error

        # 実行 and verify immediate failure
        with pytest.raises(AnswerGenerationError):
            generator.generate(
                query="What is AI?",
                contexts=sample_contexts
            )

        # 検証 only 1 attempt (no retries)
        assert generator.genai_client.chat.call_count == 1

    # ========================================
    # プロンプト構築のテスト
    # ========================================

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    def test_prompt_construction(
        self,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test prompt is correctly constructed from query and contexts"""
        generator = AnswerGenerator(**valid_params)

        # レスポンスをモック
        mock_response = MagicMock()
        mock_response.data.chat_response.text = "Answer"
        generator.genai_client.chat.return_value = mock_response

        # 実行
        generator.generate(
            query="What is AI?",
            contexts=sample_contexts
        )

        # 検証 CohereChatRequest was called with a message containing query and contexts
        assert mock_cohere_request.called
        call_kwargs = mock_cohere_request.call_args[1]
        message = call_kwargs['message']

        # プロンプトにクエリが含まれていることを確認
        assert "What is AI?" in message
        # プロンプトにコンテキストのファイル名が含まれていることを確認
        assert "doc1.pdf" in message
        assert "doc2.pdf" in message

    # ========================================
    # パラメータのテスト
    # ========================================

    @patch('src.rag.answer_generator.CohereChatRequest')
    @patch('src.rag.answer_generator.ChatDetails')
    @patch('src.rag.answer_generator.OnDemandServingMode')
    def test_custom_generation_parameters(
        self,
        mock_serving_mode,
        mock_chat_details,
        mock_cohere_request,
        valid_params,
        sample_contexts
    ):
        """Test custom generation parameters are passed correctly"""
        generator = AnswerGenerator(**valid_params)

        # レスポンスをモック
        mock_response = MagicMock()
        mock_response.data.chat_response.text = "Answer"
        generator.genai_client.chat.return_value = mock_response

        # 実行 with custom parameters
        generator.generate(
            query="What is AI?",
            contexts=sample_contexts,
            max_tokens=500,
            temperature=0.5,
            top_p=0.8,
            frequency_penalty=0.2,
            top_k=10
        )

        # 検証 parameters were passed to CohereChatRequest
        assert mock_cohere_request.called
        call_kwargs = mock_cohere_request.call_args[1]
        assert call_kwargs['max_tokens'] == 500
        assert call_kwargs['temperature'] == 0.5
        assert call_kwargs['top_p'] == 0.8
        assert call_kwargs['frequency_penalty'] == 0.2
        assert call_kwargs['top_k'] == 10
