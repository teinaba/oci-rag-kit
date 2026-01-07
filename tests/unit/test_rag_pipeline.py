"""
RAGPipelineクラスのユニットテスト

TDD（テスト駆動開発）アプローチで実装
目標カバレッジ: 90-95%
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
from src.rag.rag_pipeline import RAGPipeline, RAGResult, BatchResult
from src.rag.vector_searcher import SearchResult
from src.rag.reranker import RankedChunk
from src.rag.answer_generator import GeneratedAnswer
from src.rag.ragas_evaluator import EvaluationResult
from src.rag.exceptions import RAGError, EvaluationError


class TestRAGPipelineInit:
    """コンストラクタの検証"""

    def test_stores_all_components(self):
        """全コンポーネントが正しく保存されることを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()
        mock_evaluator = Mock()

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            evaluator=mock_evaluator
        )

        assert pipeline.searcher is mock_searcher
        assert pipeline.reranker is mock_reranker
        assert pipeline.generator is mock_generator
        assert pipeline.evaluator is mock_evaluator

    def test_optional_evaluator(self):
        """evaluatorがオプショナルであることを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator
        )

        assert pipeline.evaluator is None

    def test_enable_reranking_flag(self):
        """リランキング有効フラグが設定されることを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=False
        )

        assert pipeline.enable_reranking is False

    def test_progress_callback_stored(self):
        """プログレスコールバックが保存されることを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()
        mock_callback = Mock()

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            progress_callback=mock_callback
        )

        assert pipeline.progress_callback is mock_callback


class TestProcessSingle:
    """単一質問処理のテスト"""

    def test_process_single_with_reranking(self):
        """リランキング有効時の単一質問処理を確認"""
        # モックの設定
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        # ベクトル検索結果のモック
        search_results = [
            SearchResult(
                chunk_id=1,
                document_id=1,
                filename='doc1.pdf',
                chunk_text='テキスト1',
                distance=0.1
            )
        ]
        mock_searcher.search.return_value = search_results

        # リランキング結果のモック
        ranked_chunks = [
            RankedChunk(
                chunk_id=1,
                document_id=1,
                filename='doc1.pdf',
                chunk_text='テキスト1',
                distance=0.1,
                rerank_score=0.9
            )
        ]
        mock_reranker.rerank.return_value = ranked_chunks

        # LLM生成結果のモック
        generated_answer = GeneratedAnswer(
            answer='生成された回答',
            model_used='cohere.command-a-03-2025',
            generation_time=1.5
        )
        mock_generator.generate.return_value = generated_answer

        # テスト実行
        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=True
        )

        result = pipeline.process_single('質問文')

        # 検証
        assert isinstance(result, RAGResult)
        assert result.question == '質問文'
        assert result.answer == '生成された回答'
        assert result.model_used == 'cohere.command-a-03-2025'
        assert result.generation_time == 1.5
        assert result.total_time > 0

        mock_searcher.search.assert_called_once_with('質問文', top_k=10, filtering=None)
        mock_reranker.rerank.assert_called_once()
        mock_generator.generate.assert_called_once()

    def test_process_single_without_reranking(self):
        """リランキング無効時の単一質問処理を確認"""
        # モックの設定
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        # ベクトル検索結果のモック
        search_results = [
            SearchResult(
                chunk_id=1,
                document_id=1,
                filename='doc1.pdf',
                chunk_text='テキスト1',
                distance=0.1
            )
        ]
        mock_searcher.search.return_value = search_results

        # LLM生成結果のモック
        generated_answer = GeneratedAnswer(
            answer='生成された回答',
            model_used='cohere.command-a-03-2025',
            generation_time=1.5
        )
        mock_generator.generate.return_value = generated_answer

        # テスト実行
        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=False
        )

        result = pipeline.process_single('質問文')

        # 検証
        assert result.answer == '生成された回答'
        mock_searcher.search.assert_called_once()
        mock_reranker.rerank.assert_not_called()  # リランキングは呼ばれない
        mock_generator.generate.assert_called_once()

    def test_process_single_with_filtering(self):
        """フィルタリング指定時の処理を確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        search_results = [SearchResult(1, 1, 'doc1.pdf', 'テキスト1', 0.1)]
        mock_searcher.search.return_value = search_results

        generated_answer = GeneratedAnswer('回答', 'cohere.command-a-03-2025', 1.0)
        mock_generator.generate.return_value = generated_answer

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=False
        )

        result = pipeline.process_single('質問文', filtering='source1')

        # フィルタリングが渡されることを確認
        mock_searcher.search.assert_called_once_with('質問文', top_k=10, filtering='source1')

    def test_process_single_with_generator_params(self):
        """LLMパラメータが渡されることを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        search_results = [SearchResult(1, 1, 'doc1.pdf', 'テキスト1', 0.1)]
        mock_searcher.search.return_value = search_results

        generated_answer = GeneratedAnswer('回答', 'xai.grok-4-fast-non-reasoning', 1.0)
        mock_generator.generate.return_value = generated_answer

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=False
        )

        result = pipeline.process_single(
            '質問文',
            model='xai.grok-4-fast-non-reasoning',
            temperature=0.7,
            max_tokens=2000
        )

        # LLMパラメータが渡されることを確認
        call_kwargs = mock_generator.generate.call_args[1]
        assert 'model' in call_kwargs
        assert call_kwargs['model'] == 'xai.grok-4-fast-non-reasoning'
        assert call_kwargs['temperature'] == 0.7
        assert call_kwargs['max_tokens'] == 2000


class TestProcessBatch:
    """バッチ処理のテスト"""

    def test_process_batch_success(self):
        """バッチ処理が正常に動作することを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        # ベクトル検索結果のモック
        search_results = [SearchResult(1, 1, 'doc1.pdf', 'テキスト1', 0.1)]
        mock_searcher.search.return_value = search_results

        # LLM生成結果のモック
        generated_answer = GeneratedAnswer('回答', 'cohere.command-a-03-2025', 1.0)
        mock_generator.generate.return_value = generated_answer

        # FAQデータの作成
        faq_df = pd.DataFrame({
            'id': [1, 2],
            'question': ['質問1', '質問2'],
            'filter': ['source1', 'source2']
        })

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=False
        )

        result = pipeline.process_batch(faq_df)

        # 検証
        assert isinstance(result, BatchResult)
        assert result.total_questions == 2
        assert result.successful == 2
        assert result.failed == 0
        assert len(result.results_df) == 2
        assert 'answer' in result.results_df.columns
        assert 'contexts' in result.results_df.columns
        assert 'total_time' in result.results_df.columns

    def test_process_batch_with_progress_callback(self):
        """プログレスコールバックが呼ばれることを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()
        mock_callback = Mock()

        search_results = [SearchResult(1, 1, 'doc1.pdf', 'テキスト1', 0.1)]
        mock_searcher.search.return_value = search_results

        generated_answer = GeneratedAnswer('回答', 'cohere.command-a-03-2025', 1.0)
        mock_generator.generate.return_value = generated_answer

        faq_df = pd.DataFrame({
            'id': [1, 2],
            'question': ['質問1', '質問2'],
            'filter': ['', '']
        })

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=False,
            progress_callback=mock_callback
        )

        result = pipeline.process_batch(faq_df)

        # プログレスコールバックが呼ばれることを確認（少なくとも2回）
        assert mock_callback.call_count >= 2

    def test_process_batch_handles_errors(self):
        """エラーが発生しても処理を継続することを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        # 1回目は成功、2回目はエラー、3回目は成功
        mock_searcher.search.side_effect = [
            [SearchResult(1, 1, 'doc1.pdf', 'テキスト1', 0.1)],
            Exception("Vector search failed"),
            [SearchResult(2, 2, 'doc2.pdf', 'テキスト2', 0.2)]
        ]

        generated_answer = GeneratedAnswer('回答', 'cohere.command-a-03-2025', 1.0)
        mock_generator.generate.return_value = generated_answer

        faq_df = pd.DataFrame({
            'id': [1, 2, 3],
            'question': ['質問1', '質問2', '質問3'],
            'filter': ['', '', '']
        })

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=False
        )

        result = pipeline.process_batch(faq_df)

        # 検証
        assert result.total_questions == 3
        assert result.successful == 2
        assert result.failed == 1


class TestEvaluate:
    """RAGAS評価のテスト"""

    def test_evaluate_success(self):
        """RAGAS評価が正常に実行されることを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()
        mock_evaluator = Mock()

        # バッチ処理結果のモック
        results_df = pd.DataFrame({
            'id': [1, 2],
            'question': ['質問1', '質問2'],
            'answer': ['回答1', '回答2'],
            'contexts': ['コンテキスト1', 'コンテキスト2']
        })

        # RAGAS評価結果のモック
        evaluation_result = EvaluationResult(
            answer_correctness=[0.8, 0.9],
            context_recall=[0.7, 0.85]
        )
        mock_evaluator.evaluate.return_value = evaluation_result

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            evaluator=mock_evaluator
        )

        ground_truths = ['正解1', '正解2']
        result_df = pipeline.evaluate(results_df, ground_truths)

        # 検証
        assert 'answer_correctness' in result_df.columns
        assert 'context_recall' in result_df.columns
        assert result_df['answer_correctness'].tolist() == [0.8, 0.9]
        assert result_df['context_recall'].tolist() == [0.7, 0.85]
        mock_evaluator.evaluate.assert_called_once()

    def test_evaluate_without_evaluator_raises_error(self):
        """evaluatorが未設定の場合にエラーが発生することを確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator
        )

        results_df = pd.DataFrame({
            'question': ['質問1'],
            'answer': ['回答1'],
            'contexts': ['コンテキスト1']
        })
        ground_truths = ['正解1']

        with pytest.raises(EvaluationError, match="Evaluator is not configured"):
            pipeline.evaluate(results_df, ground_truths)


class TestContextFormatting:
    """コンテキスト整形のテスト"""

    def test_format_contexts_for_llm(self):
        """LLM用コンテキスト整形を確認"""
        mock_searcher = Mock()
        mock_reranker = Mock()
        mock_generator = Mock()

        ranked_chunks = [
            RankedChunk(1, 1, 'doc1.pdf', 'テキスト1', 0.1, 0.9),
            RankedChunk(2, 1, 'doc1.pdf', 'テキスト2', 0.2, 0.8)
        ]
        mock_reranker.rerank.return_value = ranked_chunks

        search_results = [SearchResult(1, 1, 'doc1.pdf', 'テキスト1', 0.1)]
        mock_searcher.search.return_value = search_results

        generated_answer = GeneratedAnswer('回答', 'cohere.command-a-03-2025', 1.0)
        mock_generator.generate.return_value = generated_answer

        pipeline = RAGPipeline(
            searcher=mock_searcher,
            reranker=mock_reranker,
            generator=mock_generator,
            enable_reranking=True
        )

        result = pipeline.process_single('質問文')

        # LLM呼び出し時のcontextsを確認
        call_args = mock_generator.generate.call_args
        contexts_arg = call_args[0][1]  # 第2引数がcontexts

        # コンテキストが適切にフォーマットされていることを確認
        assert isinstance(contexts_arg, list)
        assert len(contexts_arg) == 2
        assert contexts_arg[0].chunk_text == 'テキスト1'
        assert contexts_arg[1].chunk_text == 'テキスト2'
