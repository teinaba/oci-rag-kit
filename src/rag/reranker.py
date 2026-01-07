"""
JapaneseReranker - 日本語特化リランカー

このモジュールは、hotchpotch/japanese-reranker-base-v2モデルを使用した
CrossEncoderによるリランキング機能を提供します。
"""

from dataclasses import dataclass
from typing import List, Optional
import torch

from .vector_searcher import SearchResult
from .exceptions import RerankError


@dataclass
class RankedChunk:
    """リランク後の結果

    Attributes:
        chunk_id: チャンクID
        document_id: ドキュメントID
        filename: ファイル名
        chunk_text: チャンクテキスト
        distance: コサイン距離（ベクトル検索時のスコア）
        rerank_score: リランクスコア（高いほど関連性が高い、Noneの場合はフォールバック）
    """
    chunk_id: int
    document_id: int
    filename: str
    chunk_text: str
    distance: float
    rerank_score: Optional[float] = None


class JapaneseReranker:
    """日本語特化リランカー

    責務:
    - ベクトル検索結果のリランキング（CrossEncoderによるスコアリング）
    - デバイス自動検出（CUDA → MPS → CPU）
    - GPU/MPS時のhalf精度化による高速化

    設計パターン:
    - NOT Singleton（異なるパラメータで複数インスタンス対応）
    - Lazy initialization（modelは初回アクセス時にロード）

    使用例:
        reranker = JapaneseReranker(device='cuda')
        ranked = reranker.rerank('質問文', search_results, top_n=5)
    """

    DEFAULT_MODEL = "hotchpotch/japanese-reranker-base-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: Optional[str] = None,
        max_length: int = 512,
        batch_size: int = 32
    ):
        """
        JapaneseRerankerを初期化

        Args:
            model_name: CrossEncoderモデル名
            device: 使用デバイス（None時は自動検出: CUDA→MPS→CPU）
            max_length: 最大トークン長（デフォルト: 512）
            batch_size: バッチサイズ（デフォルト: 32）

        Raises:
            ValueError: パラメータが不正な場合
        """
        if max_length <= 0:
            raise ValueError("max_length must be > 0")
        if batch_size <= 0:
            raise ValueError("batch_size must be > 0")

        self.model_name = model_name
        self.device = device if device else self._detect_device()
        self.max_length = max_length
        self.batch_size = batch_size
        self._model = None  # Lazy initialization

    @staticmethod
    def _detect_device() -> str:
        """デバイスを自動検出（CUDA → MPS → CPU の優先順位）

        Returns:
            str: 検出されたデバイス名（'cuda', 'mps', または 'cpu'）
        """
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch, "mps") and torch.mps.is_available():
            return "mps"
        return "cpu"

    @property
    def model(self):
        """CrossEncoderモデル（遅延初期化、GPU/MPS時はhalf精度化）

        Returns:
            CrossEncoder: ロード済みのCrossEncoderモデル

        Raises:
            RerankError: モデルのロードに失敗した場合
        """
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_name,
                    max_length=self.max_length,
                    device=self.device
                )

                # GPU/MPS時はhalf精度化で高速化
                if self.device in ["cuda", "mps"]:
                    self._model.model.half()

            except Exception as e:
                raise RerankError(f"Failed to initialize reranker model: {e}") from e

        return self._model

    def rerank(
        self,
        query: str,
        chunks: List[SearchResult],
        top_n: int = 5
    ) -> List[RankedChunk]:
        """
        検索結果をリランク

        Args:
            query: 検索クエリ
            chunks: ベクトル検索結果のリスト
            top_n: 返却する上位件数（デフォルト: 5）

        Returns:
            リランク後の結果リスト（スコア降順、最大top_n件）

        Raises:
            RerankError: クエリが空、またはtop_nが不正な場合

        Note:
            リランキングに失敗した場合は、元のベクトル検索結果を
            distance順（昇順）でソートしたものをフォールバックとして返します。
        """
        # バリデーション
        if not query or query.strip() == "":
            raise RerankError("Query cannot be empty")
        if top_n <= 0:
            raise RerankError("top_n must be > 0")

        # 空リストの場合は早期リターン
        if not chunks:
            return []

        try:
            # クエリとドキュメントのペアを作成
            pairs = [[query, chunk.chunk_text] for chunk in chunks]

            # Rerankerでスコア計算
            scores = self.model.predict(
                pairs,
                show_progress_bar=False,
                batch_size=self.batch_size
            )

            # RankedChunkに変換（rerankスコアを追加）
            ranked_chunks = [
                RankedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    chunk_text=chunk.chunk_text,
                    distance=chunk.distance,
                    rerank_score=float(score)
                )
                for chunk, score in zip(chunks, scores)
            ]

            # スコアでソート（降順）
            ranked_chunks.sort(key=lambda x: x.rerank_score, reverse=True)

            # 上位top_n件を返す
            return ranked_chunks[:top_n]

        except Exception as e:
            # リランク失敗時のフォールバック: distanceでソート（昇順）
            print(f"⚠ Rerankエラー: {e}")
            print(f"⚠ Vector Searchの結果上位{top_n}件をそのまま返します")

            fallback_chunks = [
                RankedChunk(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    filename=chunk.filename,
                    chunk_text=chunk.chunk_text,
                    distance=chunk.distance,
                    rerank_score=None  # フォールバック時はNone
                )
                for chunk in chunks
            ]

            # distanceでソート（昇順: 小さい方が類似）
            fallback_chunks.sort(key=lambda x: x.distance)

            return fallback_chunks[:top_n]
