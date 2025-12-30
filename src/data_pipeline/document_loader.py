"""
DocumentLoader - OCI Object Storageからのドキュメント取得

このモジュールは、OCI Object Storageからファイルをダウンロードし、
メタデータとともに返す機能を提供します。
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import oci
from .exceptions import DocumentLoaderError


@dataclass
class DocumentMetadata:
    """
    ダウンロードしたドキュメントのメタデータ

    Attributes:
        filename: ファイル名（パスを除く）
        full_path: Object Storage上のフルパス
        content: ファイルの内容（バイト列）
        content_type: MIMEタイプ
        file_size: ファイルサイズ（バイト）
    """
    filename: str
    full_path: str
    content: bytes
    content_type: str
    file_size: int


class DocumentLoader:
    """
    OCI Object Storageからドキュメントを取得するクラス

    責務:
    - Object Storage内のファイル一覧取得
    - 指定されたファイルのダウンロード
    - ファイルメタデータの提供

    設計パターン:
    - NOT Singleton（複数バケット対応のため）
    - Lazy initialization（OCIクライアントは初回アクセス時に生成）

    使用例:
        loader = DocumentLoader(oci_config, 'my-bucket', 'my-namespace')
        files = loader.list_files()
        for file_path in files:
            metadata = loader.download_file(file_path)
            print(f"Downloaded: {metadata.filename}")
    """

    def __init__(
        self,
        oci_config: Dict[str, Any],
        bucket_name: str,
        namespace: str
    ):
        """
        DocumentLoaderを初期化

        Args:
            oci_config: OCI認証設定辞書
            bucket_name: Object Storageバケット名
            namespace: Object Storageネームスペース

        Raises:
            ValueError: 必須パラメータが不足している場合
        """
        if not oci_config:
            raise ValueError("oci_config is required")
        if not bucket_name:
            raise ValueError("bucket_name is required")

        self.oci_config = oci_config
        self.bucket_name = bucket_name
        self.namespace = namespace
        self._client: Optional[oci.object_storage.ObjectStorageClient] = None

    @property
    def client(self) -> oci.object_storage.ObjectStorageClient:
        """
        OCI Object Storageクライアントを取得（遅延初期化）

        Returns:
            初期化済みのObjectStorageClient
        """
        if self._client is None:
            self._client = oci.object_storage.ObjectStorageClient(self.oci_config)
        return self._client

    def list_files(self) -> List[str]:
        """
        バケット内の全ファイルパスを取得

        Returns:
            ファイルパスのリスト

        Raises:
            DocumentLoaderError: ファイル一覧取得に失敗した場合
        """
        try:
            response = self.client.list_objects(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name
            )

            # オブジェクト名のリストを抽出
            files = [obj.name for obj in response.data.objects]
            return files

        except Exception as e:
            raise DocumentLoaderError(
                f"Failed to list files in bucket '{self.bucket_name}': {str(e)}"
            ) from e

    def download_file(self, full_path: str) -> DocumentMetadata:
        """
        指定されたファイルをダウンロード

        Args:
            full_path: Object Storage上のファイルパス

        Returns:
            DocumentMetadata: ファイル内容とメタデータ

        Raises:
            DocumentLoaderError: ファイルダウンロードに失敗した場合
        """
        try:
            response = self.client.get_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=full_path
            )

            # ファイル名を抽出
            filename = self.parse_file_path(full_path)

            # メタデータを構築
            metadata = DocumentMetadata(
                filename=filename,
                full_path=full_path,
                content=response.data.content,
                content_type=response.headers.get('Content-Type', 'application/octet-stream'),
                file_size=int(response.headers.get('Content-Length', 0))
            )

            return metadata

        except Exception as e:
            raise DocumentLoaderError(
                f"Failed to download file '{full_path}': {str(e)}"
            ) from e

    @staticmethod
    def parse_file_path(full_path: str) -> str:
        """
        フルパスからファイル名を抽出

        Args:
            full_path: ファイルのフルパス（例: "folder/subfolder/file.pdf"）

        Returns:
            ファイル名（例: "file.pdf"）

        Raises:
            ValueError: パスが空の場合
        """
        if not full_path:
            raise ValueError("File path cannot be empty")

        # 最後の "/" の後ろがファイル名
        if '/' in full_path:
            return full_path.split('/')[-1]
        else:
            # パス区切りがない場合、全体がファイル名
            return full_path
