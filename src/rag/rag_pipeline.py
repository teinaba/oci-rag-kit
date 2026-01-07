"""
RAG Pipeline Orchestrator

This module coordinates all RAG components to process questions
from FAQ through to answer generation and evaluation.
"""

from dataclasses import dataclass
from typing import List, Optional, Callable, Any
import time
import pandas as pd

from .vector_searcher import VectorSearcher, SearchResult
from .reranker import JapaneseReranker, RankedChunk
from .answer_generator import AnswerGenerator
from .ragas_evaluator import RagasEvaluator
from .exceptions import RAGError, EvaluationError


@dataclass
class RAGResult:
    """
    Single question RAG processing result

    Attributes:
        question: Input question
        answer: Generated answer
        contexts: Context texts used for generation
        vector_search_time: Vector search duration (seconds)
        rerank_time: Reranking duration (seconds)
        generation_time: LLM generation duration (seconds)
        total_time: Total processing time (seconds)
        model_used: LLM model ID used for generation
    """
    question: str
    answer: str
    contexts: str
    vector_search_time: float
    rerank_time: float
    generation_time: float
    total_time: float
    model_used: str


@dataclass
class BatchResult:
    """
    Batch processing result

    Attributes:
        total_questions: Total number of questions processed
        successful: Number of successfully processed questions
        failed: Number of failed questions
        results_df: DataFrame containing all results
        elapsed_time: Total processing time (seconds)
    """
    total_questions: int
    successful: int
    failed: int
    results_df: pd.DataFrame
    elapsed_time: float


class RAGPipeline:
    """
    RAG pipeline orchestrator that coordinates all components

    This class orchestrates the entire RAG pipeline:
    1. VectorSearcher - Vector similarity search
    2. JapaneseReranker - Rerank search results (optional)
    3. AnswerGenerator - Generate answers with LLM
    4. RagasEvaluator - Evaluate quality (optional)

    Design:
    - NOT Singleton: Multiple pipelines with different configs
    - Composition: Uses all RAG component classes
    - Error Isolation: Continue processing even if one question fails
    - Progress Tracking: Optional callback for monitoring

    Example:
        >>> searcher = VectorSearcher(db_params, embedding_model, genai_client)
        >>> reranker = JapaneseReranker()
        >>> generator = AnswerGenerator(genai_client, compartment_id)
        >>> evaluator = RagasEvaluator(genai_client, compartment_id, embedding_model)
        >>>
        >>> pipeline = RAGPipeline(
        ...     searcher=searcher,
        ...     reranker=reranker,
        ...     generator=generator,
        ...     evaluator=evaluator
        ... )
        >>>
        >>> # Single question processing
        >>> result = pipeline.process_single("質問文")
        >>>
        >>> # Batch processing
        >>> faq_df = pd.DataFrame({'question': ['Q1', 'Q2'], 'filter': ['', '']})
        >>> batch_result = pipeline.process_batch(faq_df)
        >>>
        >>> # Evaluation
        >>> evaluated_df = pipeline.evaluate(batch_result.results_df, ['GT1', 'GT2'])
    """

    def __init__(
        self,
        searcher: VectorSearcher,
        reranker: JapaneseReranker,
        generator: AnswerGenerator,
        evaluator: Optional[RagasEvaluator] = None,
        enable_reranking: bool = True,
        top_k: int = 10,
        rerank_top_n: int = 5,
        progress_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize RAGPipeline

        Args:
            searcher: VectorSearcher instance
            reranker: JapaneseReranker instance
            generator: AnswerGenerator instance
            evaluator: RagasEvaluator instance (optional)
            enable_reranking: Enable reranking (default: True)
            top_k: Number of vector search results (default: 10)
            rerank_top_n: Number of results after reranking (default: 5)
            progress_callback: Progress notification callback (optional)
        """
        self.searcher = searcher
        self.reranker = reranker
        self.generator = generator
        self.evaluator = evaluator
        self.enable_reranking = enable_reranking
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n
        self.progress_callback = progress_callback

    def process_single(
        self,
        question: str,
        filtering: Optional[str] = None,
        **generator_params
    ) -> RAGResult:
        """
        Process a single question

        Args:
            question: Question text
            filtering: Source type filter
            **generator_params: LLM generation parameters (model, temperature, etc.)

        Returns:
            RAGResult: Processing result

        Raises:
            RAGError: If processing fails
        """
        # 全体の処理時間計測開始
        start_time = time.time()

        # 1. ベクトル検索
        vector_search_start = time.time()
        search_results = self.searcher.search(
            question,
            top_k=self.top_k,
            filtering=filtering
        )
        vector_search_time = time.time() - vector_search_start

        # 2. リランキング（オプション）
        rerank_start = time.time()
        if self.enable_reranking:
            # リランキングを実行
            ranked_chunks = self.reranker.rerank(
                question,
                search_results,
                top_n=self.rerank_top_n
            )
        else:
            # リランキングなし: SearchResultをRankedChunkに変換
            ranked_chunks = [
                RankedChunk(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    filename=r.filename,
                    chunk_text=r.chunk_text,
                    distance=r.distance,
                    rerank_score=None
                )
                for r in search_results[:self.rerank_top_n]
            ]
        rerank_time = time.time() - rerank_start

        # 3. LLMで回答生成
        generation_start = time.time()
        generated_answer = self.generator.generate(
            question,
            ranked_chunks,
            **generator_params
        )
        generation_time = generated_answer.generation_time

        # 4. コンテキストを保存用にフォーマット
        contexts = self._format_contexts_for_storage(ranked_chunks)

        # 全体の処理時間計測終了
        total_time = time.time() - start_time

        return RAGResult(
            question=question,
            answer=generated_answer.answer,
            contexts=contexts,
            vector_search_time=vector_search_time,
            rerank_time=rerank_time,
            generation_time=generation_time,
            total_time=total_time,
            model_used=generated_answer.model_used
        )

    def process_batch(
        self,
        questions_df: pd.DataFrame,
        **generator_params
    ) -> BatchResult:
        """
        Process batch questions

        Args:
            questions_df: Questions DataFrame (must have 'question' column, optional 'filter' column)
            **generator_params: LLM generation parameters

        Returns:
            BatchResult: Batch processing result
        """
        # バッチ処理時間計測開始
        start_time = time.time()

        # 必須列の検証
        if 'question' not in questions_df.columns:
            raise ValueError("questions_df must have 'question' column")

        # 結果列の準備
        results_df = questions_df.copy()
        results_df['answer'] = None
        results_df['contexts'] = None
        results_df['vector_search_time'] = 0.0
        results_df['rerank_time'] = 0.0
        results_df['generation_time'] = 0.0
        results_df['total_time'] = 0.0
        results_df['model_used'] = None
        results_df['status'] = 'pending'

        successful = 0
        failed = 0

        # 各質問を処理
        for idx, row in questions_df.iterrows():
            question = row['question']
            filtering = row.get('filter', None)

            # 空のフィルタを処理
            if pd.notna(filtering) and filtering != '':
                filtering_value = filtering
            else:
                filtering_value = None

            # プログレスコールバック
            if self.progress_callback:
                self.progress_callback(f"Processing {idx + 1}/{len(questions_df)}: {question[:50]}...")

            try:
                # 単一質問を処理
                result = self.process_single(
                    question,
                    filtering=filtering_value,
                    **generator_params
                )

                # 結果を保存
                results_df.at[idx, 'answer'] = result.answer
                results_df.at[idx, 'contexts'] = result.contexts
                results_df.at[idx, 'vector_search_time'] = result.vector_search_time
                results_df.at[idx, 'rerank_time'] = result.rerank_time
                results_df.at[idx, 'generation_time'] = result.generation_time
                results_df.at[idx, 'total_time'] = result.total_time
                results_df.at[idx, 'model_used'] = result.model_used
                results_df.at[idx, 'status'] = 'success'

                successful += 1

            except Exception as e:
                # エラーハンドリング: エラーを記録して処理を継続
                results_df.at[idx, 'answer'] = ''
                results_df.at[idx, 'contexts'] = ''
                results_df.at[idx, 'status'] = 'failed'
                results_df.at[idx, 'error'] = str(e)

                failed += 1

                if self.progress_callback:
                    self.progress_callback(f"Error processing question {idx + 1}: {str(e)}")

        # バッチ処理時間計測終了
        elapsed_time = time.time() - start_time

        return BatchResult(
            total_questions=len(questions_df),
            successful=successful,
            failed=failed,
            results_df=results_df,
            elapsed_time=elapsed_time
        )

    def evaluate(
        self,
        results_df: pd.DataFrame,
        ground_truths: List[str]
    ) -> pd.DataFrame:
        """
        Execute RAGAS evaluation

        Args:
            results_df: Results DataFrame from process_batch()
            ground_truths: Ground truth answers list

        Returns:
            pd.DataFrame: Results with evaluation metrics added

        Raises:
            EvaluationError: If evaluator is not configured
        """
        # Evaluatorの設定確認
        if self.evaluator is None:
            raise EvaluationError("Evaluator is not configured")

        # 評価用データの抽出
        questions = results_df['question'].tolist()
        answers = results_df['answer'].tolist()

        # コンテキストをパース（文字列からリストに変換）
        contexts = [
            self._parse_contexts_for_evaluation(ctx)
            for ctx in results_df['contexts'].tolist()
        ]

        # 評価を実行
        evaluation_result = self.evaluator.evaluate(
            questions=questions,
            answers=answers,
            contexts=contexts,
            ground_truths=ground_truths
        )

        # 評価結果をDataFrameに追加
        results_with_eval = results_df.copy()
        results_with_eval['answer_correctness'] = evaluation_result.answer_correctness
        results_with_eval['context_recall'] = evaluation_result.context_recall

        return results_with_eval

    def _format_contexts_for_storage(self, chunks: List[RankedChunk]) -> str:
        """
        Format contexts for DataFrame storage

        Args:
            chunks: Ranked chunks list

        Returns:
            str: Formatted context string
        """
        # コンテキストをDataFrame保存用にフォーマット
        return "\n\n".join([
            f"[ドキュメント {i+1}: {chunk.filename}]\n{chunk.chunk_text}"
            for i, chunk in enumerate(chunks)
        ])

    def _parse_contexts_for_evaluation(self, contexts_str: str) -> List[str]:
        """
        Parse contexts string for RAGAS evaluation

        Args:
            contexts_str: Formatted context string

        Returns:
            List[str]: Individual context texts
        """
        # 空の場合は空リストを返す
        if not contexts_str or pd.isna(contexts_str):
            return [""]

        # "[ドキュメント"マーカーで分割
        lines = contexts_str.split('\n')
        individual_docs = []
        current_doc = ""

        for line in lines:
            if line.startswith('[ドキュメント'):
                # 新しいドキュメントが始まる
                if current_doc:
                    individual_docs.append(current_doc.strip())
                current_doc = line + '\n'
            else:
                current_doc += line + '\n'

        # 最後のドキュメントを追加
        if current_doc:
            individual_docs.append(current_doc.strip())

        return individual_docs if individual_docs else [contexts_str]
