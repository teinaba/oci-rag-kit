"""
埋め込みベクトル生成モジュール

このモジュールは、テキストをOCI Generative AI Serviceを使用して
埋め込みベクトルに変換します。
"""
from dataclasses import dataclass
from typing import Optional
import logging

from src.config import ConfigLoader
from langchain_community.embeddings import OCIGenAIEmbeddings
from .exceptions import EmbeddingError


@dataclass
class Embedding:
    """
    埋め込みベクトルのメタデータ

    Attributes:
        vector_str: ベクトルの文字列表現（例: "[0.1, 0.2, 0.3]"）
        dimension: ベクトルの次元数
        model_id: 使用されたモデルID
    """
    vector_str: str
    dimension: int
    model_id: str


class EmbeddingGenerator:
    """
    テキストを埋め込みベクトルに変換するクラス

    OCI Generative AI Serviceを使用して埋め込みベクトルを生成します。

    設計:
    - NOT Singleton: 異なるモデル設定で複数インスタンス可能
    - Lazy initialization: OCIGenAIEmbeddingsは初回アクセス時に生成
    - Parameter validation: コンストラクタで検証

    Example:
        >>> generator = EmbeddingGenerator()
        >>> embedding = generator.embed_query("これはテストです")
        >>> print(f"Dimension: {embedding.dimension}")
    """

    def __init__(self, model_id: Optional[str] = None):
        """
        EmbeddingGeneratorを初期化

        Args:
            model_id: 使用する埋め込みモデルID
                     （デフォルト: ConfigLoaderから取得）

        Raises:
            ValueError: 設定の読み込みに失敗した場合
        """
        self.logger = logging.getLogger(__name__)

        # 設定を読み込み
        config = ConfigLoader()
        genai_config = config.get_genai_config()

        self.model_id = model_id if model_id else genai_config['embed_model']
        self.compartment_id = genai_config['compartment_id']
        self.service_endpoint = genai_config['endpoint']
        self.genai_client = config.get_genai_client()

        self._embedder: Optional[OCIGenAIEmbeddings] = None

    @property
    def embedder(self) -> OCIGenAIEmbeddings:
        """
        OCIGenAIEmbeddingsを取得（遅延初期化）

        Returns:
            初期化済みのOCIGenAIEmbeddings
        """
        if self._embedder is None:
            self._embedder = OCIGenAIEmbeddings(
                model_id=self.model_id,
                service_endpoint=self.service_endpoint,
                truncate="NONE",
                compartment_id=self.compartment_id,
                auth_type="API_KEY",
                client=self.genai_client
            )
            self.logger.debug(f"Initialized OCIGenAIEmbeddings with model: {self.model_id}")
        return self._embedder

    def embed_query(self, text: str) -> Embedding:
        """
        テキストを埋め込みベクトルに変換

        Args:
            text: 埋め込み対象のテキスト

        Returns:
            Embedding: ベクトルとメタデータ

        Raises:
            EmbeddingError: 埋め込み生成に失敗した場合
        """
        try:
            # 入力のバリデーション
            if not isinstance(text, str):
                raise EmbeddingError(
                    f"Input must be str, got {type(text).__name__}"
                )

            # 空のテキストを処理
            if not text:
                raise EmbeddingError("Input text cannot be empty")

            # 埋め込みベクトルを生成
            self.logger.debug(f"Generating embedding for text (length={len(text)})")
            embedding_list = self.embedder.embed_query(text)

            # Oracle VECTOR型用の文字列形式に変換
            vector_str = str(embedding_list)
            dimension = len(embedding_list)

            self.logger.debug(f"Successfully generated {dimension}-dimensional embedding")

            return Embedding(
                vector_str=vector_str,
                dimension=dimension,
                model_id=self.model_id
            )

        except EmbeddingError:
            raise
        except Exception as e:
            text_preview = text[:50] if isinstance(text, str) else "N/A"
            raise EmbeddingError(
                f"Failed to generate embedding for text: '{text_preview}...': {str(e)}"
            ) from e
