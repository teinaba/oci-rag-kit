"""
ExcelHandler - Object StorageとのExcelファイル入出力を担当

このモジュールは、OCI Object StorageからFAQファイルを読み込み、
RAG処理結果をExcel形式で保存する機能を提供します。
"""

from typing import Dict, Any, Optional
from io import BytesIO
import pandas as pd
import oci
from src.rag.exceptions import ExcelHandlerError


class ExcelHandler:
    """Object StorageとのExcelファイルI/Oを担当するクラス

    OCI Object StorageからExcelファイル（FAQなど）を読み込み、
    RAG処理結果をExcelファイルとして保存する機能を提供します。

    Attributes:
        oci_config (Dict[str, Any]): OCI認証設定
        bucket_name (str): Object Storageバケット名
        namespace (str): Object Storageネームスペース
    """

    def __init__(
        self,
        oci_config: Dict[str, Any],
        bucket_name: str,
        namespace: str
    ):
        """ExcelHandlerを初期化

        Args:
            oci_config: OCI認証設定（~/.oci/configから読み込んだ設定）
            bucket_name: Object Storageバケット名
            namespace: Object Storageネームスペース

        Raises:
            ValueError: 必須パラメータが不正な場合
        """
        if not oci_config:
            raise ValueError("oci_config must be provided")
        if not bucket_name:
            raise ValueError("bucket_name must be provided")
        if not namespace:
            raise ValueError("namespace must be provided")

        self.oci_config = oci_config
        self.bucket_name = bucket_name
        self.namespace = namespace
        self._client = None

    @property
    def client(self):
        """Object StorageクライアントのLazy initialization

        Returns:
            oci.object_storage.ObjectStorageClient: OCIクライアントインスタンス
        """
        if self._client is None:
            self._client = oci.object_storage.ObjectStorageClient(self.oci_config)
        return self._client

    def load_faq(
        self,
        object_name: str,
        sheet_name: str | int = 0
    ) -> pd.DataFrame:
        """Object StorageからFAQファイルを読み込み

        Args:
            object_name: Object名（例: "faq.xlsx"）
            sheet_name: シート名またはインデックス（デフォルト: 0）

        Returns:
            pd.DataFrame: FAQデータのDataFrame

        Raises:
            ExcelHandlerError: ファイル読み込みに失敗した場合、
                              または必須列が欠けている場合
        """
        try:
            # Object StorageからExcelファイルを取得
            get_object_response = self.client.get_object(
                self.namespace,
                self.bucket_name,
                object_name
            )

            # バイナリデータをExcelとして読み込み
            excel_data = BytesIO(get_object_response.data.content)
            df = pd.read_excel(excel_data, sheet_name=sheet_name)

            # 必須列のバリデーション
            required_columns = ['id', 'question', 'ground_truth', 'filter']
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                raise ExcelHandlerError(
                    f"Missing required columns: {missing_columns}"
                )

            return df

        except ExcelHandlerError:
            # ExcelHandlerErrorは再送出
            raise
        except Exception as e:
            raise ExcelHandlerError(
                f"FAQ file load failed: {str(e)}"
            ) from e

    def save_results(
        self,
        results_df: pd.DataFrame,
        filename: str,
        metadata_df: Optional[pd.DataFrame] = None
    ) -> str:
        """結果をExcelファイルとしてObject Storageに保存

        Args:
            results_df: 結果DataFrame（Results シート）
            filename: 保存ファイル名（例: "rag_results.xlsx"）
            metadata_df: メタデータDataFrame（Settings シート、オプション）

        Returns:
            str: 保存したObject名（filename）

        Raises:
            ExcelHandlerError: 保存に失敗した場合
        """
        try:
            # ExcelファイルをBytesIOバッファに書き込み
            excel_buffer = BytesIO()

            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                # 結果シート
                results_df.to_excel(writer, sheet_name='Results', index=False)

                # メタデータシート（オプション）
                if metadata_df is not None:
                    metadata_df.to_excel(writer, sheet_name='Settings', index=False)

            excel_buffer.seek(0)

            # Object Storageにアップロード
            self.client.put_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=filename,
                put_object_body=excel_buffer.getvalue()
            )

            return filename

        except Exception as e:
            raise ExcelHandlerError(
                f"Results save failed: {str(e)}"
            ) from e
