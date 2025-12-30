"""
データパイプライン処理用のカスタム例外クラス

このモジュールは、データパイプライン処理における
エラーハンドリングを明確にするためのカスタム例外を定義します。
"""


class DataPipelineError(Exception):
    """データパイプライン操作の基底例外クラス"""
    pass


class DocumentLoaderError(DataPipelineError):
    """ドキュメント読み込みエラー

    Object Storageからのファイル取得時のエラーを表します。
    """
    pass


class TextExtractionError(DataPipelineError):
    """テキスト抽出エラー

    PDF/TXT/CSVファイルからのテキスト抽出時のエラーを表します。
    """
    pass


class ChunkingError(DataPipelineError):
    """チャンク化エラー

    テキストのチャンク分割時のエラーを表します。
    """
    pass


class EmbeddingError(DataPipelineError):
    """埋め込み生成エラー

    OCI Generative AI Serviceでの埋め込み生成時のエラーを表します。
    """
    pass


class DocumentWriteError(DataPipelineError):
    """ドキュメント書き込みエラー

    Oracle Databaseへのドキュメントとチャンクの永続化時のエラーを表します。
    """
    pass
