"""
VectorSearcher - Oracle Database 26aiでのベクトル検索

このモジュールは、クエリの埋め込み生成とOracle Database 26aiの
ネイティブVECTOR_DISTANCE関数を使用したベクトル検索を提供します。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import oracledb

from .exceptions import VectorSearchError


@dataclass
class SearchResult:
    """ベクトル検索結果

    Attributes:
        chunk_id: チャンクID
        document_id: ドキュメントID
        filename: ファイル名
        chunk_text: チャンクテキスト
        distance: コサイン距離（小さいほど類似）
    """
    chunk_id: int
    document_id: int
    filename: str
    chunk_text: str
    distance: float


class VectorSearcher:
    """Oracle Database 26aiでのベクトル検索を実行するクラス

    責務:
    - クエリの埋め込みベクトル生成
    - VECTOR_DISTANCE関数を使用したCOSINE距離検索
    - フィルタリング条件に基づく検索結果の絞り込み

    設計パターン:
    - NOT Singleton（異なるDB接続で複数インスタンス対応）
    - Lazy initialization（embedderは初回アクセス時に生成）

    使用例:
        searcher = VectorSearcher(
            db_params={'user': 'admin', 'password': 'xxx', 'dsn': 'xxx'},
            embedding_model='cohere.embed-v4.0',
            genai_client=genai_client,
            compartment_id='ocid1.compartment...',
            service_endpoint='https://...'
        )
        results = searcher.search('質問文', top_k=10, filtering='manual')
    """

    def __init__(
        self,
        db_params: Dict[str, str],
        embedding_model: str,
        genai_client: Any,
        compartment_id: str,
        service_endpoint: str,
        top_k: int = 10
    ):
        """
        VectorSearcherを初期化

        Args:
            db_params: DB接続パラメータ（user, password, dsn）
            embedding_model: 埋め込みモデルID（例: 'cohere.embed-v4.0'）
            genai_client: OCI GenAI Client
            compartment_id: OCI Compartment ID
            service_endpoint: OCI GenAI Service Endpoint
            top_k: 返却する上位結果数（デフォルト: 10）

        Raises:
            ValueError: 必須パラメータが不足している場合
        """
        if not db_params:
            raise ValueError("db_params is required")
        if not embedding_model:
            raise ValueError("embedding_model is required")
        if not genai_client:
            raise ValueError("genai_client is required")
        if not compartment_id:
            raise ValueError("compartment_id is required")
        if not service_endpoint:
            raise ValueError("service_endpoint is required")
        if top_k <= 0:
            raise ValueError("top_k must be > 0")

        self.db_params = db_params
        self.embedding_model = embedding_model
        self.genai_client = genai_client
        self.compartment_id = compartment_id
        self.service_endpoint = service_endpoint
        self.top_k = top_k
        self._embedder = None  # Lazy initialization

    @property
    def embedder(self):
        """OCIGenAIEmbeddings（遅延初期化）

        Returns:
            OCIGenAIEmbeddingsインスタンス

        Raises:
            VectorSearchError: embedder初期化に失敗した場合
        """
        if self._embedder is None:
            try:
                from langchain_community.embeddings import OCIGenAIEmbeddings
                self._embedder = OCIGenAIEmbeddings(
                    model_id=self.embedding_model,
                    service_endpoint=self.service_endpoint,
                    compartment_id=self.compartment_id,
                    auth_type="API_KEY",
                    model_kwargs={"input_type": "search_query"}
                )
            except Exception as e:
                raise VectorSearchError(
                    f"Failed to initialize embedder: {str(e)}"
                ) from e
        return self._embedder

    def embed_query(self, query: str) -> List[float]:
        """クエリを埋め込みベクトルに変換

        Args:
            query: 検索クエリ文字列

        Returns:
            埋め込みベクトル（浮動小数点数のリスト）

        Raises:
            VectorSearchError: 埋め込み生成に失敗した場合
        """
        try:
            if not isinstance(query, str):
                raise VectorSearchError(
                    f"Query must be str, got {type(query).__name__}"
                )
            if not query:
                raise VectorSearchError("Query cannot be empty")

            embedding = self.embedder.embed_query(query)
            return embedding
        except VectorSearchError:
            raise  # カスタム例外はそのまま再送出
        except Exception as e:
            raise VectorSearchError(
                f"Failed to embed query: {str(e)}"
            ) from e

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filtering: Optional[str] = None
    ) -> List[SearchResult]:
        """
        ベクトル検索を実行

        Args:
            query: 検索クエリ文字列
            top_k: 返却件数（Noneの場合はself.top_kを使用）
            filtering: ソース種別フィルタ（Noneの場合はフィルタなし）

        Returns:
            検索結果リスト（距離の昇順でソート済み）

        Raises:
            VectorSearchError: 検索に失敗した場合
        """
        try:
            # パラメータ検証
            if top_k is None:
                top_k = self.top_k
            if top_k <= 0:
                raise VectorSearchError("top_k must be > 0")

            # クエリを埋め込みベクトルに変換
            query_embedding = self.embed_query(query)
            query_vector = str(query_embedding)

            # SQL文を構築（filtering指定の有無で分岐）
            if filtering:
                sql = """
                SELECT
                    c.chunk_id,
                    c.document_id,
                    s.filename,
                    c.chunk_text,
                    VECTOR_DISTANCE(c.embedding, TO_VECTOR(:query_vector), COSINE) as distance
                FROM chunks c
                JOIN source_documents s ON c.document_id = s.document_id
                WHERE s.filtering = :filtering
                ORDER BY VECTOR_DISTANCE(c.embedding, TO_VECTOR(:query_vector), COSINE)
                FETCH FIRST :top_k ROWS ONLY
                """
                bind_params = {
                    'query_vector': query_vector,
                    'filtering': filtering,
                    'top_k': top_k
                }
            else:
                sql = """
                SELECT
                    c.chunk_id,
                    c.document_id,
                    s.filename,
                    c.chunk_text,
                    VECTOR_DISTANCE(c.embedding, TO_VECTOR(:query_vector), COSINE) as distance
                FROM chunks c
                JOIN source_documents s ON c.document_id = s.document_id
                ORDER BY VECTOR_DISTANCE(c.embedding, TO_VECTOR(:query_vector), COSINE)
                FETCH FIRST :top_k ROWS ONLY
                """
                bind_params = {
                    'query_vector': query_vector,
                    'top_k': top_k
                }

            # DB接続とクエリ実行
            connection = oracledb.connect(**self.db_params)
            try:
                cursor = connection.cursor()
                cursor.execute(sql, bind_params)
                rows = cursor.fetchall()

                # 結果をSearchResult dataclassに変換
                results = []
                for row in rows:
                    chunk_id, document_id, filename, chunk_text_clob, distance = row

                    # CLOBデータを読み取り
                    if hasattr(chunk_text_clob, 'read'):
                        chunk_text = chunk_text_clob.read()
                    else:
                        chunk_text = chunk_text_clob

                    results.append(SearchResult(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        filename=filename,
                        chunk_text=chunk_text,
                        distance=float(distance)
                    ))

                return results

            finally:
                cursor.close()
                connection.close()

        except VectorSearchError:
            raise  # カスタム例外はそのまま再送出
        except Exception as e:
            raise VectorSearchError(
                f"Vector search failed (query='{query[:50]}...', "
                f"top_k={top_k}, filtering={filtering}): {str(e)}"
            ) from e
