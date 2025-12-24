"""
設定ファイル読み込みモジュール
.envファイルから環境変数を読み込み、各種設定を提供します
"""

import os
from dotenv import load_dotenv
from pathlib import Path
import oci
from typing import Dict, Any, Optional


def load_config():
    """
    環境変数を読み込む
    .envファイルが存在しない場合はエラーを発生させます
    
    .envファイルの検索順序:
    1. カレントディレクトリ
    2. 親ディレクトリ（プロジェクトルート）
    """
    # カレントディレクトリで検索
    env_file = Path('.env')
    
    # 見つからなければ親ディレクトリで検索
    if not env_file.exists():
        env_file = Path('..') / '.env'
    
    # それでも見つからなければエラー
    if not env_file.exists():
        raise FileNotFoundError(
            ".envファイルが見つかりません。\n"
            "プロジェクトルートに.env.templateをコピーして.envを作成し、必要な値を設定してください。\n"
            f"検索パス: {Path('.env').absolute()}, {(Path('..') / '.env').absolute()}"
        )
    
    load_dotenv(env_file)
    print(f"✓ 環境変数を読み込みました: {env_file.absolute()}")


def get_db_connection_params() -> Dict[str, str]:
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


def get_oci_config() -> Dict[str, Any]:
    """
    OCI認証設定を取得
    ~/.oci/configファイルから設定を読み込みます
    
    Returns:
        dict: OCI設定辞書
        
    Raises:
        FileNotFoundError: configファイルが見つからない場合
        ValueError: 設定の読み込みに失敗した場合
    """
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
        print(f"✓ OCI設定を読み込みました: {config_file} [プロファイル: {profile}]")
        return config
    except Exception as e:
        raise ValueError(f"OCI設定の読み込みに失敗しました: {e}")


def get_genai_endpoint_from_region(region: str) -> str:
    """
    リージョン名からGenerative AI ServiceのエンドポイントURLを生成

    Args:
        region: OCI リージョン名 (例: us-chicago-1, ap-osaka-1)

    Returns:
        エンドポイントURL
    """
    return f"https://inference.generativeai.{region}.oci.oraclecloud.com"


def get_genai_config() -> Dict[str, str]:
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
    endpoint = get_genai_endpoint_from_region(region)

    return {
        'compartment_id': compartment_id,
        'endpoint': endpoint,
        'embed_model': os.getenv('OCI_EMBED_MODEL', 'cohere.embed-multilingual-v3.0'),
        'llm_model': os.getenv('OCI_LLM_MODEL', 'cohere.command-r-plus')
    }


def get_object_storage_config() -> Dict[str, str]:
    """
    OCI Object Storage設定を取得（オプション）
    
    Returns:
        dict: bucket_name, namespaceを含む辞書
    """
    return {
        'bucket_name': os.getenv('OCI_BUCKET_NAME', ''),
        'namespace': os.getenv('OCI_NAMESPACE', '')
    }


def get_app_config() -> Dict[str, Any]:
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


# ヘルパー関数

def get_genai_client():
    """
    OCI Generative AI Clientを取得
    
    Returns:
        GenerativeAiInferenceClient: 初期化済みのクライアント
    """
    oci_config = get_oci_config()
    genai_config = get_genai_config()
    
    client = oci.generative_ai_inference.GenerativeAiInferenceClient(
        config=oci_config,
        service_endpoint=genai_config['endpoint']
    )
    
    return client


def get_object_storage_client():
    """
    OCI Object Storage Clientを取得
    
    Returns:
        ObjectStorageClient: 初期化済みのクライアント
    """
    oci_config = get_oci_config()
    return oci.object_storage.ObjectStorageClient(oci_config)


# 使用例を表示
if __name__ == "__main__":
    print("=" * 60)
    print("設定ファイル読み込みテスト")
    print("=" * 60)
    
    try:
        # 環境変数読み込み
        load_config()
        print()
        
        # DB設定
        print("【Oracle Database設定】")
        db_params = get_db_connection_params()
        print(f"  ユーザー名: {db_params['user']}")
        print(f"  パスワード: {'*' * len(db_params['password'])}")
        print(f"  DSN: {db_params['dsn'][:50]}...")
        print()
        
        # OCI設定
        print("【OCI認証設定】")
        oci_config = get_oci_config()
        print(f"  User: {oci_config.get('user', 'N/A')[:50]}...")
        print(f"  Region: {oci_config.get('region', 'N/A')}")
        print()
        
        # GenAI設定
        print("【OCI Generative AI設定】")
        genai_config = get_genai_config()
        print(f"  Compartment ID: {genai_config['compartment_id'][:50]}...")
        print(f"  Endpoint: {genai_config['endpoint']}")
        print(f"  Embed Model: {genai_config['embed_model']}")
        print(f"  LLM Model: {genai_config['llm_model']}")
        print()
        
        # アプリ設定
        print("【アプリケーション設定】")
        app_config = get_app_config()
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