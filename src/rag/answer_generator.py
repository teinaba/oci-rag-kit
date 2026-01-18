"""
AnswerGenerator - LLM回答生成（11モデル対応）

このモジュールは、OCI Generative AI Serviceの11モデルに対応した
回答生成機能を提供します。HTTP 429エラーの自動リトライ機能を含みます。
"""

from dataclasses import dataclass
from typing import List, Optional, Any
import time

from oci.generative_ai_inference.models import (
    CohereChatRequest,
    GenericChatRequest,
    OnDemandServingMode,
    ChatDetails,
    UserMessage,
    TextContent
)

from .reranker import RankedChunk
from .exceptions import AnswerGenerationError, RateLimitError


@dataclass
class GeneratedAnswer:
    """LLM生成結果

    Attributes:
        answer: 生成された回答テキスト
        model_used: 使用したモデルID
        generation_time: 生成にかかった時間（秒）
    """
    answer: str
    model_used: str
    generation_time: float


class AnswerGenerator:
    """LLM回答生成クラス（11モデル対応）

    責務:
    - OCI Generative AI Serviceを使用した回答生成
    - Cohere（CohereChatRequest）とその他（GenericChatRequest）の使い分け
    - HTTP 429エラーの指数バックオフリトライ

    対応モデル:
    【Cohere】
    - cohere.command-a-03-2025
    - cohere.command-r-plus-08-2024

    【Meta Llama】
    - meta.llama-3.3-70b-instruct

    【xAI Grok】
    - xai.grok-4-fast-non-reasoning (RAG推奨)
    - xai.grok-4-fast-reasoning (複雑な推論用)
    - xai.grok-4

    【Google Gemini】
    - google.gemini-2.5-pro
    - google.gemini-2.5-flash
    - google.gemini-2.5-flash-lite

    【OpenAI GPT-OSS】
    - openai.gpt-oss-20b
    - openai.gpt-oss-120b

    設計パターン:
    - NOT Singleton（異なるパラメータで複数インスタンス対応）
    - 指数バックオフリトライ（HTTP 429対策）

    使用例:
        generator = AnswerGenerator(
            genai_client=genai_client,
            compartment_id='ocid1.compartment...',
            default_model='cohere.command-a-03-2025'
        )
        result = generator.generate(
            query='質問文',
            contexts=ranked_chunks,
            max_tokens=1000
        )
    """

    # Cohereモデル（CohereChatRequest使用）
    COHERE_MODELS = [
        "cohere.command-a-03-2025",
        "cohere.command-r-plus-08-2024"
    ]

    # その他モデル（GenericChatRequest使用）
    GENERIC_MODELS = [
        "meta.llama-3.3-70b-instruct",
        "xai.grok-4-fast-non-reasoning",
        "xai.grok-4-fast-reasoning",
        "xai.grok-4",
        "google.gemini-2.5-pro",
        "google.gemini-2.5-flash",
        "google.gemini-2.5-flash-lite",
        "openai.gpt-oss-20b",
        "openai.gpt-oss-120b"
    ]

    # モデルごとの最大トークン数制限
    MAX_TOKENS_LIMIT = {
        "cohere": 4000,
        "default": 128000
    }

    def __init__(
        self,
        genai_client: Any,
        compartment_id: str,
        default_model: str = "cohere.command-a-03-2025",
        max_retries: int = 3,
        retry_delay: int = 60
    ):
        """
        AnswerGeneratorを初期化

        Args:
            genai_client: OCI GenAI Client
            compartment_id: OCI Compartment ID
            default_model: デフォルトのLLMモデル（デフォルト: cohere.command-a-03-2025）
            max_retries: HTTP 429エラーの最大リトライ回数（デフォルト: 3）
            retry_delay: リトライ初期待機時間（秒）（デフォルト: 60）

        Raises:
            ValueError: 必須パラメータが不足している場合、または無効な値の場合
        """
        if not genai_client:
            raise ValueError("genai_client is required")
        if not compartment_id:
            raise ValueError("compartment_id is required")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if retry_delay <= 0:
            raise ValueError("retry_delay must be > 0")

        self.genai_client = genai_client
        self.compartment_id = compartment_id
        self.default_model = default_model
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def generate(
        self,
        query: str,
        contexts: List[RankedChunk],
        model: Optional[str] = None,
        max_tokens: int = 128000,
        temperature: float = 0.3,
        top_p: float = 0.75,
        frequency_penalty: float = 0.0,
        top_k: int = 0,
        answer_prompt: str = ""
    ) -> GeneratedAnswer:
        """
        LLM回答を生成

        Args:
            query: 質問文
            contexts: コンテキストとなるチャンク（RankedChunkのリスト）
            model: 使用モデル（Noneの場合はdefault_modelを使用）
            max_tokens: 最大トークン数（デフォルト: 128000）
            temperature: 温度パラメータ（0-1、デフォルト: 0.3）
            top_p: Nucleus samplingパラメータ（0-1、デフォルト: 0.75）
            frequency_penalty: 頻度ペナルティ（Cohere用、0-1、デフォルト: 0.0）
            top_k: Top-Kサンプリング（Cohere用、0で無効、デフォルト: 0）
            answer_prompt: 回答生成時の追加指示文（デフォルト: ''）

        Returns:
            GeneratedAnswer: 生成された回答とメタデータ

        Raises:
            AnswerGenerationError: 回答生成に失敗した場合
            RateLimitError: HTTP 429エラーでリトライ上限に達した場合
        """
        # モデル選択（Noneの場合はdefault_modelを使用）
        model_to_use = model if model else self.default_model

        # モデルごとのmax_tokens上限を適用
        max_tokens_to_use = self._get_adjusted_max_tokens(model_to_use, max_tokens)

        # プロンプト構築
        prompt = self._build_prompt(query, contexts, answer_prompt)

        # 処理時間計測開始
        start_time = time.time()

        try:
            # Cohereモデルの場合
            if any(cohere_model in model_to_use.lower() for cohere_model in ['cohere']):
                answer = self._generate_with_cohere(
                    prompt=prompt,
                    model=model_to_use,
                    max_tokens=max_tokens_to_use,
                    temperature=temperature,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    top_k=top_k
                )
            # その他のモデル（Llama, Grok, Gemini, OpenAI GPT-OSS）
            else:
                answer = self._generate_with_generic(
                    prompt=prompt,
                    model=model_to_use,
                    max_tokens=max_tokens_to_use,
                    temperature=temperature,
                    top_p=top_p
                )

            # 処理時間計測終了
            generation_time = time.time() - start_time

            return GeneratedAnswer(
                answer=answer,
                model_used=model_to_use,
                generation_time=generation_time
            )

        except RateLimitError:
            # RateLimitErrorはそのまま再送出
            raise
        except Exception as e:
            raise AnswerGenerationError(
                f"Failed to generate answer with model {model_to_use}: {str(e)}"
            ) from e

    def _get_adjusted_max_tokens(self, model: str, max_tokens: int) -> int:
        """
        モデルごとの最大トークン数制限を適用

        Args:
            model: モデルID
            max_tokens: 指定されたmax_tokens

        Returns:
            int: モデルの上限を超えない調整後のmax_tokens
        """
        # Cohereモデルの場合は上限4000
        if 'cohere' in model.lower():
            limit = self.MAX_TOKENS_LIMIT['cohere']
        else:
            limit = self.MAX_TOKENS_LIMIT['default']

        return min(max_tokens, limit)

    def _build_prompt(
        self,
        query: str,
        contexts: List[RankedChunk],
        answer_prompt: str
    ) -> str:
        """
        プロンプトを構築

        Args:
            query: 質問文
            contexts: コンテキストチャンク
            answer_prompt: 追加指示文

        Returns:
            str: 構築されたプロンプト
        """
        # コンテキストを結合
        contexts_text = "\n\n".join([
            f"[ドキュメント {i+1}: {chunk.filename}]\n{chunk.chunk_text}"
            for i, chunk in enumerate(contexts)
        ])

        # プロンプト構築
        prompt = f"""以下のドキュメントを参考に、質問に回答してください。

【参考ドキュメント】
{contexts_text}

【質問】
{query}

【回答】
{answer_prompt}
"""
        return prompt

    def _generate_with_cohere(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        frequency_penalty: float,
        top_k: int
    ) -> str:
        """
        Cohereモデルで回答生成（CohereChatRequest使用）

        Args:
            prompt: プロンプト
            model: モデルID
            max_tokens: 最大トークン数
            temperature: 温度
            top_p: Top-P
            frequency_penalty: 頻度ペナルティ
            top_k: Top-K

        Returns:
            str: 生成された回答

        Raises:
            RateLimitError: HTTP 429エラーでリトライ上限到達時
        """
        chat_request = CohereChatRequest(
            message=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            frequency_penalty=frequency_penalty,
            top_p=top_p,
            top_k=top_k
        )

        chat_detail = ChatDetails(
            serving_mode=OnDemandServingMode(model_id=model),
            compartment_id=self.compartment_id,
            chat_request=chat_request
        )

        # リトライ付き実行
        response = self._execute_with_retry(lambda: self.genai_client.chat(chat_detail))

        # レスポンスから回答を取得
        return response.data.chat_response.text

    def _generate_with_generic(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        top_p: float
    ) -> str:
        """
        Genericモデルで回答生成（GenericChatRequest使用）

        Args:
            prompt: プロンプト
            model: モデルID
            max_tokens: 最大トークン数
            temperature: 温度
            top_p: Top-P

        Returns:
            str: 生成された回答

        Raises:
            RateLimitError: HTTP 429エラーでリトライ上限到達時
        """
        # UserMessageとTextContentを使った正しいフォーマット
        messages = [
            UserMessage(content=[TextContent(text=prompt)])
        ]

        chat_request = GenericChatRequest(
            api_format="GENERIC",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p
        )

        chat_detail = ChatDetails(
            serving_mode=OnDemandServingMode(model_id=model),
            compartment_id=self.compartment_id,
            chat_request=chat_request
        )

        # リトライ付き実行
        response = self._execute_with_retry(lambda: self.genai_client.chat(chat_detail))

        # レスポンスから回答を取得（GenericChatRequestのフォーマット）
        return response.data.chat_response.choices[0].message.content[0].text

    def _execute_with_retry(self, func):
        """
        HTTP 429エラー時に指数バックオフでリトライ

        Args:
            func: 実行する関数（callable）

        Returns:
            実行結果

        Raises:
            RateLimitError: 最大リトライ回数に達した場合
        """
        for attempt in range(self.max_retries + 1):
            try:
                return func()
            except Exception as e:
                # HTTP 429エラー（Rate Limit）の場合
                if hasattr(e, 'status') and e.status == 429:
                    if attempt < self.max_retries:
                        # 指数バックオフでリトライ間隔を延長
                        wait_time = self.retry_delay * (2 ** attempt)
                        print(f"HTTP 429 detected. Retrying after {wait_time}s... (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(wait_time)
                    else:
                        # 最大リトライ回数に達した場合
                        raise RateLimitError(
                            f"Rate limit exceeded after {self.max_retries} retries"
                        ) from e
                else:
                    # 429以外のエラーは即座に再送出
                    raise
