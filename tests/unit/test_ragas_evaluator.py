"""
Unit tests for RagasEvaluator class

Tests cover:
- Constructor validation
- Evaluate method with batch processing
- Custom finished_parser for OCI Cohere Chat
- Error handling
- Lazy initialization of LLM and embeddings
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd

from src.rag.ragas_evaluator import RagasEvaluator, EvaluationResult
from src.rag.exceptions import EvaluationError


class TestRagasEvaluator:
    """Test suite for RagasEvaluator class"""

    @pytest.fixture
    def mock_oci_config(self):
        """Mock OCI config"""
        return {'region': 'us-chicago-1', 'tenancy': 'ocid1.tenancy.test'}

    @pytest.fixture
    def mock_genai_client(self):
        """Mock OCI GenAI Client"""
        client = MagicMock()
        return client

    @pytest.fixture
    def valid_params(self, mock_oci_config, mock_genai_client):
        """Valid RagasEvaluator initialization parameters"""
        return {
            'oci_config': mock_oci_config,
            'compartment_id': 'ocid1.compartment.oc1..test',
            'service_endpoint': 'https://inference.generativeai.us-chicago-1.oci.oraclecloud.com',
            'embedding_model': 'cohere.embed-v4.0',
            'llm_model': 'cohere.command-a-03-2025',
            'genai_client': mock_genai_client,
            'batch_size': 3,
            'max_retries': 3,
            'retry_wait': 30
        }

    @pytest.fixture
    def sample_evaluation_data(self):
        """Sample data for evaluation"""
        return {
            'questions': ['What is AI?', 'What is ML?', 'What is DL?'],
            'answers': ['AI is...', 'ML is...', 'DL is...'],
            'contexts': [
                ['Context for AI question'],
                ['Context for ML question'],
                ['Context for DL question']
            ],
            'ground_truths': ['AI ground truth', 'ML ground truth', 'DL ground truth']
        }

    # ========================================
    # Constructor Tests
    # ========================================

    def test_constructor_valid_params(self, valid_params):
        """Test RagasEvaluator initialization with valid parameters"""
        evaluator = RagasEvaluator(**valid_params)

        assert evaluator.oci_config == valid_params['oci_config']
        assert evaluator.compartment_id == valid_params['compartment_id']
        assert evaluator.service_endpoint == valid_params['service_endpoint']
        assert evaluator.embedding_model == valid_params['embedding_model']
        assert evaluator.llm_model == valid_params['llm_model']
        assert evaluator.batch_size == 3
        assert evaluator.max_retries == 3
        assert evaluator.retry_wait == 30
        assert evaluator._llm is None  # Lazy initialization
        assert evaluator._embeddings is None  # Lazy initialization

    def test_constructor_missing_oci_config(self, valid_params):
        """Test constructor raises ValueError when oci_config is missing"""
        valid_params['oci_config'] = None

        with pytest.raises(ValueError, match="oci_config is required"):
            RagasEvaluator(**valid_params)

    def test_constructor_missing_compartment_id(self, valid_params):
        """Test constructor raises ValueError when compartment_id is missing"""
        valid_params['compartment_id'] = None

        with pytest.raises(ValueError, match="compartment_id is required"):
            RagasEvaluator(**valid_params)

    def test_constructor_missing_service_endpoint(self, valid_params):
        """Test constructor raises ValueError when service_endpoint is missing"""
        valid_params['service_endpoint'] = None

        with pytest.raises(ValueError, match="service_endpoint is required"):
            RagasEvaluator(**valid_params)

    def test_constructor_missing_embedding_model(self, valid_params):
        """Test constructor raises ValueError when embedding_model is missing"""
        valid_params['embedding_model'] = None

        with pytest.raises(ValueError, match="embedding_model is required"):
            RagasEvaluator(**valid_params)

    def test_constructor_invalid_batch_size(self, valid_params):
        """Test constructor raises ValueError when batch_size is invalid"""
        valid_params['batch_size'] = 0

        with pytest.raises(ValueError, match="batch_size must be > 0"):
            RagasEvaluator(**valid_params)

    def test_constructor_invalid_max_retries(self, valid_params):
        """Test constructor raises ValueError when max_retries is invalid"""
        valid_params['max_retries'] = -1

        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            RagasEvaluator(**valid_params)

    # ========================================
    # Lazy Initialization Tests
    # ========================================

    @patch('src.rag.ragas_evaluator.ChatOCIGenAI')
    @patch('src.rag.ragas_evaluator.LangchainLLMWrapper')
    def test_llm_lazy_initialization(self, mock_wrapper, mock_chat, valid_params):
        """Test LLM is lazily initialized on first access"""
        evaluator = RagasEvaluator(**valid_params)

        # Initially None
        assert evaluator._llm is None

        # Access triggers initialization
        _ = evaluator.llm

        # Verify ChatOCIGenAI was created with correct parameters
        assert mock_chat.called
        call_kwargs = mock_chat.call_args[1]
        assert call_kwargs['model_id'] == 'cohere.command-a-03-2025'
        assert call_kwargs['compartment_id'] == 'ocid1.compartment.oc1..test'
        assert call_kwargs['service_endpoint'] == valid_params['service_endpoint']

        # Verify LangchainLLMWrapper was created
        assert mock_wrapper.called

    @patch('src.rag.ragas_evaluator.OCIGenAIEmbeddings')
    @patch('src.rag.ragas_evaluator.LangchainEmbeddingsWrapper')
    def test_embeddings_lazy_initialization(self, mock_wrapper, mock_embeddings, valid_params):
        """Test embeddings are lazily initialized on first access"""
        evaluator = RagasEvaluator(**valid_params)

        # Initially None
        assert evaluator._embeddings is None

        # Access triggers initialization
        _ = evaluator.embeddings

        # Verify OCIGenAIEmbeddings was created
        assert mock_embeddings.called
        call_kwargs = mock_embeddings.call_args[1]
        assert call_kwargs['model_id'] == 'cohere.embed-v4.0'

        # Verify LangchainEmbeddingsWrapper was created
        assert mock_wrapper.called

    # ========================================
    # Finished Parser Tests
    # ========================================

    def test_finished_parser_complete(self, valid_params):
        """Test finished_parser returns True for COMPLETE finish_reason"""
        evaluator = RagasEvaluator(**valid_params)

        # Mock LLMResult with COMPLETE finish_reason
        mock_result = MagicMock()
        mock_result.generations = [[MagicMock()]]
        mock_result.generations[0][0].generation_info = {'finish_reason': 'COMPLETE'}

        parser = evaluator._create_finished_parser()
        assert parser(mock_result) is True

    def test_finished_parser_incomplete(self, valid_params):
        """Test finished_parser returns False for non-COMPLETE finish_reason"""
        evaluator = RagasEvaluator(**valid_params)

        # Mock LLMResult with non-COMPLETE finish_reason
        mock_result = MagicMock()
        mock_result.generations = [[MagicMock()]]
        mock_result.generations[0][0].generation_info = {'finish_reason': 'STOP'}

        parser = evaluator._create_finished_parser()
        assert parser(mock_result) is False

    def test_finished_parser_no_generations(self, valid_params):
        """Test finished_parser returns False when no generations"""
        evaluator = RagasEvaluator(**valid_params)

        # Mock LLMResult with empty generations
        mock_result = MagicMock()
        mock_result.generations = []

        parser = evaluator._create_finished_parser()
        assert parser(mock_result) is False

    # ========================================
    # Evaluate Method Tests
    # ========================================

    @patch('src.rag.ragas_evaluator.evaluate')
    @patch('src.rag.ragas_evaluator.Dataset')
    @patch('src.rag.ragas_evaluator.AnswerCorrectness')
    @patch('src.rag.ragas_evaluator.ContextRecall')
    def test_evaluate_success(
        self,
        mock_context_recall,
        mock_answer_correctness,
        mock_dataset,
        mock_ragas_evaluate,
        valid_params,
        sample_evaluation_data
    ):
        """Test successful evaluation"""
        evaluator = RagasEvaluator(**valid_params)

        # Mock RAGAS evaluate result
        mock_result = MagicMock()
        mock_df = pd.DataFrame({
            'answer_correctness': [0.9, 0.8, 0.85],
            'context_recall': [0.95, 0.90, 0.92]
        })
        mock_result.to_pandas.return_value = mock_df
        mock_ragas_evaluate.return_value = mock_result

        # Execute
        result = evaluator.evaluate(
            questions=sample_evaluation_data['questions'],
            answers=sample_evaluation_data['answers'],
            contexts=sample_evaluation_data['contexts'],
            ground_truths=sample_evaluation_data['ground_truths']
        )

        # Verify
        assert isinstance(result, EvaluationResult)
        assert len(result.answer_correctness) == 3
        assert len(result.context_recall) == 3
        assert result.answer_correctness[0] == 0.9
        assert result.context_recall[0] == 0.95

        # Verify Dataset.from_dict was called
        assert mock_dataset.from_dict.called
        dataset_arg = mock_dataset.from_dict.call_args[0][0]
        assert dataset_arg['question'] == sample_evaluation_data['questions']

        # Verify metrics were created
        assert mock_answer_correctness.called
        assert mock_context_recall.called

        # Verify ragas evaluate was called
        assert mock_ragas_evaluate.called

    @patch('src.rag.ragas_evaluator.evaluate')
    @patch('src.rag.ragas_evaluator.Dataset')
    def test_evaluate_error_handling(
        self,
        mock_dataset,
        mock_ragas_evaluate,
        valid_params,
        sample_evaluation_data
    ):
        """Test evaluation error handling"""
        evaluator = RagasEvaluator(**valid_params)

        # Mock RAGAS evaluate to raise error
        mock_ragas_evaluate.side_effect = Exception("RAGAS evaluation failed")

        # Execute and verify exception
        with pytest.raises(EvaluationError, match="Failed to evaluate"):
            evaluator.evaluate(
                questions=sample_evaluation_data['questions'],
                answers=sample_evaluation_data['answers'],
                contexts=sample_evaluation_data['contexts'],
                ground_truths=sample_evaluation_data['ground_truths']
            )

    @patch('src.rag.ragas_evaluator.evaluate')
    @patch('src.rag.ragas_evaluator.Dataset')
    def test_evaluate_with_custom_batch_size(
        self,
        mock_dataset,
        mock_ragas_evaluate,
        valid_params,
        sample_evaluation_data
    ):
        """Test evaluation respects custom batch_size"""
        # Set custom batch_size
        valid_params['batch_size'] = 5
        evaluator = RagasEvaluator(**valid_params)

        # Mock result
        mock_result = MagicMock()
        mock_df = pd.DataFrame({
            'answer_correctness': [0.9] * 3,
            'context_recall': [0.95] * 3
        })
        mock_result.to_pandas.return_value = mock_df
        mock_ragas_evaluate.return_value = mock_result

        # Execute
        result = evaluator.evaluate(
            questions=sample_evaluation_data['questions'],
            answers=sample_evaluation_data['answers'],
            contexts=sample_evaluation_data['contexts'],
            ground_truths=sample_evaluation_data['ground_truths']
        )

        # Verify batch_size is stored correctly
        assert evaluator.batch_size == 5
        assert isinstance(result, EvaluationResult)

    # ========================================
    # Input Validation Tests
    # ========================================

    def test_evaluate_mismatched_lengths(self, valid_params):
        """Test evaluate raises error when input lengths mismatch"""
        evaluator = RagasEvaluator(**valid_params)

        with pytest.raises(ValueError, match="All input lists must have the same length"):
            evaluator.evaluate(
                questions=['Q1', 'Q2'],
                answers=['A1'],  # Length mismatch
                contexts=[['C1'], ['C2']],
                ground_truths=['GT1', 'GT2']
            )

    def test_evaluate_empty_inputs(self, valid_params):
        """Test evaluate raises error when inputs are empty"""
        evaluator = RagasEvaluator(**valid_params)

        with pytest.raises(ValueError, match="Input lists cannot be empty"):
            evaluator.evaluate(
                questions=[],
                answers=[],
                contexts=[],
                ground_truths=[]
            )
