"""
RagasEvaluator - RAGAS評価フレームワーク統合

このモジュールは、RAGシステムの品質評価のために
RAGASフレームワークを使用した評価機能を提供します。
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Callable, Optional
import pandas as pd

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import AnswerCorrectness, ContextRecall
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_community.chat_models.oci_generative_ai import ChatOCIGenAI
from langchain_community.embeddings import OCIGenAIEmbeddings
from langchain_core.outputs import LLMResult

from .exceptions import EvaluationError


@dataclass
class EvaluationResult:
    """RAGAS評価結果

    Attributes:
        answer_correctness: Answer Correctnessスコアのリスト
        context_recall: Context Recallスコアのリスト
    """
    answer_correctness: List[float]
    context_recall: List[float]


class RagasEvaluator:
    """RAGAS評価フレームワークを使用したRAG品質評価クラス

    責務:
    - RAGシステムの出力品質をRAGASメトリクスで評価
    - OCI Generative AI Cohere Chat用のfinished_parser実装
    - 延長タイムアウト設定（接続30秒、読み取り1200秒）
    - Answer CorrectnessとContext Recallメトリクスの評価

    設計パターン:
    - NOT Singleton（異なるパラメータで複数インスタンス対応）
    - Lazy initialization（LLMとembeddingsは初回アクセス時に生成）

    使用例:
        evaluator = RagasEvaluator(
            oci_config=oci_config,
            compartment_id='ocid1.compartment...',
            service_endpoint='https://...',
            embedding_model='cohere.embed-v4.0',
            llm_model='cohere.command-a-03-2025',
            genai_client=genai_client
        )
        result = evaluator.evaluate(
            questions=['Q1', 'Q2'],
            answers=['A1', 'A2'],
            contexts=[['C1'], ['C2']],
            ground_truths=['GT1', 'GT2']
        )
    """

    def __init__(
        self,
        oci_config: Dict[str, Any],
        compartment_id: str,
        service_endpoint: str,
        embedding_model: str,
        llm_model: str = "cohere.command-a-03-2025",
        genai_client: Optional[Any] = None,
        batch_size: int = 3,
        max_retries: int = 3,
        retry_wait: int = 30
    ):
        """
        RagasEvaluatorを初期化

        Args:
            oci_config: OCI認証設定（config.from_fileの戻り値）
            compartment_id: OCI Compartment ID
            service_endpoint: OCI GenAI Service Endpoint
            embedding_model: 埋め込みモデルID（例: 'cohere.embed-v4.0'）
            llm_model: LLMモデルID（デフォルト: 'cohere.command-a-03-2025'）
            genai_client: OCI GenAI Client（タイムアウト延長版、オプション）
            batch_size: バッチサイズ（デフォルト: 3）
            max_retries: 最大リトライ回数（デフォルト: 3）
            retry_wait: リトライ待機時間（秒）（デフォルト: 30）

        Raises:
            ValueError: 必須パラメータが不足している場合、または無効な値の場合
        """
        if not oci_config:
            raise ValueError("oci_config is required")
        if not compartment_id:
            raise ValueError("compartment_id is required")
        if not service_endpoint:
            raise ValueError("service_endpoint is required")
        if not embedding_model:
            raise ValueError("embedding_model is required")
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_wait <= 0:
            raise ValueError("retry_wait must be > 0")

        self.oci_config = oci_config
        self.compartment_id = compartment_id
        self.service_endpoint = service_endpoint
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.genai_client = genai_client
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_wait = retry_wait

        # Lazy initialization
        self._llm = None
        self._embeddings = None

    @property
    def llm(self):
        """LLM評価用ラッパー（遅延初期化）

        Returns:
            LangchainLLMWrapper: RAGAS用LLMラッパー
        """
        if self._llm is None:
            # ChatOCIGenAI作成
            chat_llm = ChatOCIGenAI(
                model_id=self.llm_model,
                service_endpoint=self.service_endpoint,
                compartment_id=self.compartment_id,
                is_stream=False,
                model_kwargs={"temperature": 0.0, "max_tokens": 4000},
                auth_type="API_KEY",
                client=self.genai_client
            )

            # LangchainLLMWrapperで包む（finished_parser付き）
            self._llm = LangchainLLMWrapper(
                chat_llm,
                is_finished_parser=self._create_finished_parser()
            )

        return self._llm

    @property
    def embeddings(self):
        """埋め込みモデル（遅延初期化）

        Returns:
            LangchainEmbeddingsWrapper: RAGAS用埋め込みラッパー
        """
        if self._embeddings is None:
            # OCIGenAIEmbeddings作成
            oci_embeddings = OCIGenAIEmbeddings(
                model_id=self.embedding_model,
                service_endpoint=self.service_endpoint,
                compartment_id=self.compartment_id,
                truncate="END",
                auth_type="API_KEY",
                client=self.genai_client
            )

            # LangchainEmbeddingsWrapperで包む
            self._embeddings = LangchainEmbeddingsWrapper(oci_embeddings)

        return self._embeddings

    def _create_finished_parser(self) -> Callable[[LLMResult], bool]:
        """
        OCI Cohere Chat用のfinished_parserを作成

        OCI Generative AIのCohere Chatは、finish_reason='COMPLETE'で完了を示すため、
        カスタムparserが必要です。

        Returns:
            Callable[[LLMResult], bool]: finished_parser関数
        """
        def finished_parser(response: LLMResult) -> bool:
            """LLM生成が完了したかを判定

            Args:
                response: LLM生成結果

            Returns:
                bool: finish_reason=='COMPLETE'の場合True、それ以外False
            """
            if (response.generations
                and response.generations[0]
                and response.generations[0][0].generation_info
                and response.generations[0][0].generation_info.get('finish_reason') == 'COMPLETE'):
                return True
            return False

        return finished_parser

    def evaluate(
        self,
        questions: List[str],
        answers: List[str],
        contexts: List[List[str]],
        ground_truths: List[str]
    ) -> EvaluationResult:
        """
        RAGシステムの出力をRAGASで評価

        Args:
            questions: 質問のリスト
            answers: RAGシステムが生成した回答のリスト
            contexts: 各質問に対して検索されたコンテキストのリスト（リストのリスト）
            ground_truths: 正解となる回答のリスト

        Returns:
            EvaluationResult: 評価結果（answer_correctness, context_recall）

        Raises:
            ValueError: 入力データが不正な場合（長さ不一致、空など）
            EvaluationError: 評価に失敗した場合
        """
        # 入力検証
        if not questions:
            raise ValueError("Input lists cannot be empty")

        if not (len(questions) == len(answers) == len(contexts) == len(ground_truths)):
            raise ValueError("All input lists must have the same length")

        try:
            # データセットの作成
            ds = Dataset.from_dict({
                "question": questions,
                "answer": answers,
                "contexts": contexts,
                "ground_truth": ground_truths,
            })

            # メトリクスのインスタンスを作成（answer_correctness と context_recall のみ）
            metrics = [
                AnswerCorrectness(llm=self.llm, embeddings=self.embeddings),
                ContextRecall(llm=self.llm)
            ]

            # 評価の実行（エラー時は明示的に停止）
            result = evaluate(ds, metrics, raise_exceptions=True)

            # 結果をDataFrameに変換
            result_df = result.to_pandas()

            # EvaluationResultに変換して返却
            return EvaluationResult(
                answer_correctness=result_df['answer_correctness'].tolist(),
                context_recall=result_df['context_recall'].tolist()
            )

        except Exception as e:
            raise EvaluationError(
                f"Failed to evaluate with RAGAS: {str(e)}"
            ) from e
