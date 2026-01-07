"""
RAG処理用のカスタム例外クラス

このモジュールは、RAG処理における
エラーハンドリングを明確にするためのカスタム例外を定義します。
"""


class RAGError(Exception):
    """RAG処理の基底例外クラス"""
    pass


class VectorSearchError(RAGError):
    """ベクトル検索エラー

    Oracle Database 26aiでのベクトル検索時のエラーを表します。
    """
    pass


class RerankError(RAGError):
    """リランキングエラー

    日本語リランカー（CrossEncoder）によるリランキング時のエラーを表します。
    """
    pass


class AnswerGenerationError(RAGError):
    """回答生成エラー

    OCI Generative AI ServiceでのLLM回答生成時のエラーを表します。
    """
    pass


class RateLimitError(AnswerGenerationError):
    """HTTP 429 Rate Limit超過エラー

    OCI APIのレート制限に達し、リトライ上限に到達した場合のエラーを表します。
    """
    pass


class EvaluationError(RAGError):
    """RAGAS評価エラー

    RAGAS評価フレームワークによる評価時のエラーを表します。
    """
    pass


class ExcelHandlerError(RAGError):
    """Excel I/Oエラー

    Object StorageとのExcelファイル入出力時のエラーを表します。
    """
    pass
