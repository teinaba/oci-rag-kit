"""
設定ファイル読み込みモジュール
.envファイルから環境変数を読み込み、各種設定を提供します

クラスベースの設計により、テスタビリティと再利用性を向上させています。
"""

import os
from dotenv import load_dotenv
from pathlib import Path
import oci
from typing import Dict, Any, Optional


class ConfigLoader:
    """
    設定管理クラス（Singleton）

    .envファイルと~/.oci/configから設定を読み込み、
    アプリケーション全体で使用する設定値を提供します。

    使用例:
        # クラスベースの使用法
        config = ConfigLoader()
        config.load_env()
        db_params = config.get_db_params()

        # 後方互換性のための関数版も利用可能
        from config_loader import load_config, get_db_connection_params
        load_config()
        db_params = get_db_connection_params()
    """

    _instance: Optional['ConfigLoader'] = None
    _env_loaded: bool = False
    _oci_config_cache: Optional[Dict[str, Any]] = None

    def __new__(cls) -> 'ConfigLoader':
        """
        Singletonパターンの実装
        アプリケーション全体で単一のインスタンスを共有
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        初期化メソッド
        Singletonのため、複数回呼ばれても問題ないように設計
        """
        # Singletonなので初期化済みかチェック不要
        # 状態は _env_loaded と _oci_config_cache で管理
        pass

    @classmethod
    def _reset(cls) -> None:
        """
        Singletonインスタンスと状態をリセット（テスト用）

        Warning:
            この機能は単体テストでのみ使用してください。
            本番環境では使用しないでください。
        """
        cls._instance = None
        cls._env_loaded = False
        cls._oci_config_cache = None

    def load_env(self) -> None:
        """
        環境変数を読み込む
        .envファイルが存在しない場合はエラーを発生させます

        .envファイルの検索順序:
        1. カレントディレクトリ
        2. 親ディレクトリ（プロジェクトルート）

        Raises:
            FileNotFoundError: .envファイルが見つからない場合
        """
        if self._env_loaded:
            return  # 既に読み込み済み

        # カレントディレクトリで検索
        env_file = Path('.env')

        # 見つからなければ親ディレクトリで検索
        if not env_file.exists():
            env_file = Path('..') / '.env'

        # それでも見つからなければエラー
        if not env_file.exists():
            raise FileNotFoundError(
                ".envファイルが見つかりません。\n"
                "infra/oci-manual-setup-guide.mdの手順6.5を参照して.envを作成してください。\n"
                f"検索パス: {Path('.env').absolute()}, {(Path('..') / '.env').absolute()}"
            )

        load_dotenv(env_file)
        self._env_loaded = True
        print(f"✓ 環境変数を読み込みました: {env_file.absolute()}")

    def get_db_params(self) -> Dict[str, str]:
        """
        Oracle Database接続パラメータを取得

        Returns:
            dict: user, password, dsnを含む辞書

        Raises:
            ValueError: 必須パラメータが設定されていない場合
        """
        username = os.getenv('DB_USERNAME')
        password = os.getenv('DB_PASSWORD')
        dsn = os.getenv('DB_DSN')

        if not all([username, password, dsn]):
            missing = []
            if not username: missing.append('DB_USERNAME')
            if not password: missing.append('DB_PASSWORD')
            if not dsn: missing.append('DB_DSN')
            raise ValueError(
                f"必須のDB接続パラメータが設定されていません: {', '.join(missing)}"
            )

        return {
            'user': username,
            'password': password,
            'dsn': dsn
        }

    def get_admin_db_params(self) -> Dict[str, str]:
        """
        Oracle Database ADMIN接続パラメータを取得（ユーザー作成用）

        DB_ADMIN_PASSWORDが設定されている場合にADMIN接続情報を返します。
        設定されていない場合はNoneを返します。

        Returns:
            dict: user, password, dsnを含む辞書。未設定の場合はNone

        Note:
            この接続情報はRAGユーザーの作成などの管理作業に使用します。
            通常のアプリケーション接続にはget_db_params()を使用してください。
        """
        admin_password = os.getenv('DB_ADMIN_PASSWORD')
        dsn = os.getenv('DB_DSN')

        # ADMIN PWが設定されていない場合はNoneを返す
        if not admin_password:
            return None

        if not dsn:
            raise ValueError("DB_DSNが設定されていません")

        return {
            'user': os.getenv('DB_ADMIN_USERNAME', 'ADMIN'),
            'password': admin_password,
            'dsn': dsn
        }

    def get_oci_config(self) -> Dict[str, Any]:
        """
        OCI認証設定を取得
        ~/.oci/configファイルから設定を読み込みます

        一度読み込んだ設定はキャッシュされ、再利用されます。

        Returns:
            dict: OCI設定辞書

        Raises:
            FileNotFoundError: configファイルが見つからない場合
            ValueError: 設定の読み込みに失敗した場合
        """
        # キャッシュがあればそれを返す
        if self._oci_config_cache is not None:
            return self._oci_config_cache

        config_file = os.getenv('OCI_CONFIG_FILE', '~/.oci/config')
        config_file = os.path.expanduser(config_file)
        profile = os.getenv('OCI_PROFILE', 'DEFAULT')

        if not Path(config_file).exists():
            raise FileNotFoundError(
                f"OCI設定ファイルが見つかりません: {config_file}\n"
                "OCI_CONFIG_SETUP.mdを参照して、~/.oci/configを作成してください。"
            )

        try:
            config = oci.config.from_file(config_file, profile)
            # 初回のみprintを出力
            print(f"✓ OCI設定を読み込みました: {config_file} [プロファイル: {profile}]")
            # キャッシュに保存
            self._oci_config_cache = config
            return config
        except Exception as e:
            raise ValueError(f"OCI設定の読み込みに失敗しました: {e}")

    @staticmethod
    def get_genai_endpoint_from_region(region: str) -> str:
        """
        リージョン名からGenerative AI ServiceのエンドポイントURLを生成

        Args:
            region: OCI リージョン名 (例: us-chicago-1, ap-osaka-1)

        Returns:
            エンドポイントURL
        """
        return f"https://inference.generativeai.{region}.oci.oraclecloud.com"

    def get_genai_config(self) -> Dict[str, str]:
        """
        OCI Generative AI Service設定を取得

        Returns:
            dict: compartment_id, endpoint, embed_model, llm_modelを含む辞書

        Raises:
            ValueError: 必須パラメータが設定されていない場合
        """
        compartment_id = os.getenv('OCI_COMPARTMENT_ID')
        region = os.getenv('OCI_REGION')

        if not compartment_id:
            raise ValueError("OCI_COMPARTMENT_IDが設定されていません")
        if not region:
            raise ValueError("OCI_REGIONが設定されていません")

        # リージョンからエンドポイントを自動生成
        endpoint = self.get_genai_endpoint_from_region(region)

        return {
            'compartment_id': compartment_id,
            'endpoint': endpoint,
            'embed_model': os.getenv('OCI_EMBED_MODEL', 'cohere.embed-v4.0'),
            'llm_model': os.getenv('OCI_LLM_MODEL', 'cohere.command-a-03-2025')
        }

    def get_object_storage_config(self) -> Dict[str, str]:
        """
        OCI Object Storage設定を取得（オプション）

        Returns:
            dict: bucket_name, namespaceを含む辞書
        """
        return {
            'bucket_name': os.getenv('OCI_BUCKET_NAME', ''),
            'namespace': os.getenv('OCI_NAMESPACE', '')
        }

    def get_faq_bucket_name(self) -> str:
        """
        FAQ用Object Storageバケット名を取得

        OCI_FAQ_BUCKET_NAMEが設定されていればそれを返し、
        なければOCI_BUCKET_NAMEにフォールバック

        Returns:
            str: FAQファイル用バケット名
        """
        return os.getenv('OCI_FAQ_BUCKET_NAME', os.getenv('OCI_BUCKET_NAME', ''))

    def get_faq_object_name(self) -> str:
        """
        FAQファイル名を取得

        Returns:
            str: FAQファイル名（デフォルト: faq.xlsx）
        """
        return os.getenv('OCI_FAQ_OBJECT_NAME', 'faq.xlsx')

    def get_app_config(self) -> Dict[str, Any]:
        """
        アプリケーション設定を取得

        Returns:
            dict: chunk_size, chunk_overlap, top_kを含む辞書
        """
        return {
            'chunk_size': int(os.getenv('CHUNK_SIZE', 500)),
            'chunk_overlap': int(os.getenv('CHUNK_OVERLAP', 50)),
            'top_k': int(os.getenv('TOP_K', 5))
        }

    def get_genai_client(self):
        """
        OCI Generative AI Clientを取得

        Returns:
            GenerativeAiInferenceClient: 初期化済みのクライアント
        """
        oci_config = self.get_oci_config()
        genai_config = self.get_genai_config()

        client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=oci_config,
            service_endpoint=genai_config['endpoint']
        )

        return client

    def get_object_storage_client(self):
        """
        OCI Object Storage Clientを取得

        Returns:
            ObjectStorageClient: 初期化済みのクライアント
        """
        oci_config = self.get_oci_config()
        return oci.object_storage.ObjectStorageClient(oci_config)


# =============================================================================
# 後方互換性のための関数版インターフェース
# 既存コードとの互換性を保つため、以前の関数ベースのAPIも提供
# =============================================================================

_default_config_loader = ConfigLoader()


def load_config():
    """
    環境変数を読み込む（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.load_env()


def get_db_connection_params() -> Dict[str, str]:
    """
    Oracle Database接続パラメータを取得（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_db_params()


def get_admin_db_connection_params() -> Dict[str, str]:
    """
    Oracle Database ADMIN接続パラメータを取得（後方互換性用）

    DB_ADMIN_PASSWORDが設定されている場合にADMIN接続情報を返します。
    設定されていない場合はNoneを返します。

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_admin_db_params()


def get_oci_config() -> Dict[str, Any]:
    """
    OCI認証設定を取得（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_oci_config()


def get_genai_endpoint_from_region(region: str) -> str:
    """
    リージョン名からGenerative AI ServiceのエンドポイントURLを生成（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader.get_genai_endpoint_from_region() を推奨します。
    """
    return ConfigLoader.get_genai_endpoint_from_region(region)


def get_genai_config() -> Dict[str, str]:
    """
    OCI Generative AI Service設定を取得（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_genai_config()


def get_object_storage_config() -> Dict[str, str]:
    """
    OCI Object Storage設定を取得（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_object_storage_config()


def get_app_config() -> Dict[str, Any]:
    """
    アプリケーション設定を取得（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_app_config()


def get_genai_client():
    """
    OCI Generative AI Clientを取得（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_genai_client()


def get_object_storage_client():
    """
    OCI Object Storage Clientを取得（後方互換性用）

    Note:
        この関数は後方互換性のために提供されています。
        新しいコードでは ConfigLoader クラスを直接使用することを推奨します。
    """
    return _default_config_loader.get_object_storage_client()


# 使用例を表示
if __name__ == "__main__":
    print("=" * 60)
    print("設定ファイル読み込みテスト")
    print("=" * 60)

    try:
        # クラスベースの使用例
        config = ConfigLoader()
        config.load_env()
        print()

        # DB設定
        print("【Oracle Database設定】")
        db_params = config.get_db_params()
        print(f"  ユーザー名: {db_params['user']}")
        print(f"  パスワード: {'*' * len(db_params['password'])}")
        print(f"  DSN: {db_params['dsn'][:50]}...")
        print()

        # OCI設定
        print("【OCI認証設定】")
        oci_config = config.get_oci_config()
        print(f"  User: {oci_config.get('user', 'N/A')[:50]}...")
        print(f"  Region: {oci_config.get('region', 'N/A')}")
        print()

        # GenAI設定
        print("【OCI Generative AI設定】")
        genai_config = config.get_genai_config()
        print(f"  Compartment ID: {genai_config['compartment_id'][:50]}...")
        print(f"  Endpoint: {genai_config['endpoint']}")
        print(f"  Embed Model: {genai_config['embed_model']}")
        print(f"  LLM Model: {genai_config['llm_model']}")
        print()

        # アプリ設定
        print("【アプリケーション設定】")
        app_config = config.get_app_config()
        print(f"  Chunk Size: {app_config['chunk_size']}")
        print(f"  Chunk Overlap: {app_config['chunk_overlap']}")
        print(f"  Top K: {app_config['top_k']}")
        print()

        print("=" * 60)
        print("✓ すべての設定が正常に読み込まれました")
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ エラー: {e}")
        print("=" * 60)
