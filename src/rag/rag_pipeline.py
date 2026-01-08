"""
RAGパイプライン オーケストレータ

このモジュールは、FAQから回答生成および評価まで、
すべてのRAGコンポーネントを調整して質問を処理します。
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
    単一質問のRAG処理結果

    Attributes:
        question: 入力質問
        answer: 生成された回答
        contexts: 生成に使用されたコンテキストテキスト
        vector_search_time: ベクトル検索時間（秒）
        rerank_time: リランキング時間（秒）
        generation_time: LLM生成時間（秒）
        total_time: 総処理時間（秒）
        model_used: 生成に使用されたLLMモデルID
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
    バッチ処理結果

    Attributes:
        total_questions: 処理された質問の総数
        successful: 正常に処理された質問数
        failed: 失敗した質問数
        results_df: すべての結果を含むDataFrame
        elapsed_time: 総処理時間（秒）
    """
    total_questions: int
    successful: int
    failed: int
    results_df: pd.DataFrame
    elapsed_time: float


class RAGPipeline:
    """
    すべてのコンポーネントを調整するRAGパイプライン オーケストレータ

    このクラスは、RAGパイプライン全体を統括します：
    1. VectorSearcher - ベクトル類似度検索
    2. JapaneseReranker - 検索結果のリランキング（オプション）
    3. AnswerGenerator - LLMによる回答生成
    4. RagasEvaluator - 品質評価（オプション）

    設計:
    - NOT Singleton: 異なる設定で複数のパイプライン可能
    - Composition: すべてのRAGコンポーネントクラスを使用
    - Error Isolation: 1つの質問が失敗しても処理を継続
    - Progress Tracking: 監視用のオプションのコールバック

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
        >>> # 単一質問の処理
        >>> result = pipeline.process_single("質問文")
        >>>
        >>> # バッチ処理
        >>> faq_df = pd.DataFrame({'question': ['Q1', 'Q2'], 'filter': ['', '']})
        >>> batch_result = pipeline.process_batch(faq_df)
        >>>
        >>> # 評価
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
        RAGPipelineを初期化

        Args:
            searcher: VectorSearcherインスタンス
            reranker: JapaneseRerankerインスタンス
            generator: AnswerGeneratorインスタンス
            evaluator: RagasEvaluatorインスタンス（オプション）
            enable_reranking: リランキングを有効化（デフォルト: True）
            top_k: ベクトル検索結果数（デフォルト: 10）
            rerank_top_n: リランキング後の結果数（デフォルト: 5）
            progress_callback: 進捗通知コールバック（オプション）
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
        単一質問を処理

        Args:
            question: 質問テキスト
            filtering: ソース種別フィルタ
            **generator_params: LLM生成パラメータ（model, temperatureなど）

        Returns:
            RAGResult: 処理結果

        Raises:
            RAGError: 処理に失敗した場合
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
        バッチ質問を処理

        Args:
            questions_df: 質問DataFrame（'question'列が必須、'filter'列はオプション）
            **generator_params: LLM生成パラメータ

        Returns:
            BatchResult: バッチ処理結果
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
        RAGAS評価を実行

        Args:
            results_df: process_batch()からの結果DataFrame
            ground_truths: 正解回答のリスト

        Returns:
            pd.DataFrame: 評価メトリクスが追加された結果

        Raises:
            EvaluationError: Evaluatorが設定されていない場合
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
        DataFrame保存用にコンテキストをフォーマット

        Args:
            chunks: ランク付けされたチャンクのリスト

        Returns:
            str: フォーマットされたコンテキスト文字列
        """
        # コンテキストをDataFrame保存用にフォーマット
        return "\n\n".join([
            f"[ドキュメント {i+1}: {chunk.filename}]\n{chunk.chunk_text}"
            for i, chunk in enumerate(chunks)
        ])

    def _parse_contexts_for_evaluation(self, contexts_str: str) -> List[str]:
        """
        RAGAS評価用にコンテキスト文字列をパース

        Args:
            contexts_str: フォーマットされたコンテキスト文字列

        Returns:
            List[str]: 個別のコンテキストテキスト
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
